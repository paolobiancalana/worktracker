import asyncio
import logging
from datetime import datetime, timezone
import discord
from discord.ext import commands, tasks
from work_tracker import WorkTracker
from database_manager import DatabaseManager
from leave_management import LeaveManagement
from config import Config
from logger import log_user_action, log_exception

# Configurazione delle intenzioni di Discord
intents = discord.Intents.all()
intents.presences = True
intents.guilds = True
intents.members = True

# Inizializzazione del bot
bot = commands.Bot(command_prefix="!", intents=intents)

# Configurazione delle componenti
config = Config()
db_manager = DatabaseManager()
work_tracker = WorkTracker(bot, db_manager)
leave_management = LeaveManagement(bot, db_manager)

# Dizionario per tenere traccia dei task in esecuzione per ogni utente e del tempo dell'ultimo aggiornamento
active_tasks = {}
last_update_times = {}

# Intervallo di debounce in secondi
DEBOUNCE_INTERVAL = 2

@bot.event
async def on_ready():
    guild = bot.get_guild(int(config.GUILD_ID))
    if guild:
        log_user_action('System', f'Connected to GUILD: {guild.name}')
    log_user_action('System', f'Logged in as {bot.user.name}')
    await work_tracker.reconcile_states()

@bot.event
async def on_presence_update(before, after):
    if before.status != after.status:
        user_id = str(after.id)

        now = datetime.now(timezone.utc)
        last_update_time = last_update_times.get(user_id)

        # Debounce logic to prevent rapid duplicate state updates
        if last_update_time and (now - last_update_time).total_seconds() < DEBOUNCE_INTERVAL:
            return

        last_update_times[user_id] = now

        if user_id not in active_tasks:
            active_tasks[user_id] = bot.loop.create_task(sync_user_state(user_id))

async def sync_user_state(user_id):
    try:
        user = work_tracker.users.get(user_id)
        if user:
            await work_tracker.sync_user_state(user)
            await work_tracker.reconcile_states()  # Chiama reconcile_states dopo ogni aggiornamento di stato
    except Exception as e:
        log_exception('System', f"Error syncing state for user {user_id}: {str(e)}")
    finally:
        active_tasks.pop(user_id, None)

# Funzione per avviare task periodici
def start_periodic_tasks():
    @tasks.loop(minutes=1)
    async def periodic_task():
        try:
            log_user_action('System', 'Running periodic task')
            await work_tracker.reconcile_states()
        except Exception as e:
            log_exception('System', f"Error in periodic task: {str(e)}")

    periodic_task.start()

# Aggiungi i cog e avvia il bot
async def setup_bot():
    try:
        await bot.add_cog(work_tracker)
        await bot.add_cog(leave_management)
    except Exception as e:
        log_exception('System', f"Error in setup: {str(e)}")

if __name__ == "__main__":
    try:
        loop = asyncio.get_event_loop()
        loop.run_until_complete(setup_bot())
        log_user_action('System', "Starting bot...")
        bot.run(config.DISCORD_TOKEN)
    except Exception as e:
        log_exception('System', f"Error in main loop: {str(e)}")
