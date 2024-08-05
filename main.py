import asyncio
import discord
from discord.ext import commands
from work_tracker import WorkTracker
from work_tracker import DatabaseManager
from leave_management import LeaveManagement
from config import Config
from logger import logger

intents = discord.Intents.all()
intents.presences = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

async def main():
    config = Config()
    db_manager = DatabaseManager()
    work_tracker = WorkTracker(bot, db_manager)
    leave_management = LeaveManagement(bot, db_manager)
    
    await bot.add_cog(work_tracker)
    await bot.add_cog(leave_management)

    @bot.event
    async def on_ready():
        logger.info(f'Logged in as {bot.user.name}')
        await work_tracker.reconcile_states()
        bot.loop.create_task(work_tracker.periodic_sync())

    @bot.event
    async def on_presence_update(before, after):
        if before.status != after.status:
            bot.loop.create_task(work_tracker.handle_status_change(str(after.id), str(after.status)))

    await bot.start(config.DISCORD_TOKEN)

if __name__ == "__main__":
    asyncio.run(main())