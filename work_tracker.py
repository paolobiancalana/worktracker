import asyncio, logging
from discord.ext import commands, tasks
from datetime import datetime, timedelta
from user import UserState
from config import Config
from logger import log_user_action, log_exception, logger


class WorkTracker(commands.Cog):
    def __init__(self, bot, db_manager):
        self.bot = bot
        self.db_manager = db_manager
        self.users = {}
        self.guild = None
        self.status_update_lock = asyncio.Lock()
        self.last_status_sync = {}
        self.debounce_time = 1
        self.load_users()

    async def load_guild(self):
        self.guild = self.bot.get_guild(int(Config.GUILD_ID))
        if self.guild is None:
            log_user_action(
                "System",
                f"Could not find guild with ID {Config.GUILD_ID}",
                level=logging.ERROR,
            )
            raise ValueError("Guild not found")

    def cog_unload(self):
        self.periodic_sync.cancel()

    def load_users(self):
        self.users = {str(user.discord_id): user for user in self.db_manager.get_all_users()}
        log_user_action('System', f"Loaded {len(self.users)} users")

    async def reconcile_states(self):
        log_user_action("System", "Starting state reconciliation")
        current_date = datetime.now().date()

        try:
            self.guild = self.bot.get_guild(int(Config.GUILD_ID))
            for user in self.users.values():
                if user.discord_id is None:
                    log_user_action(
                        "System",
                        f"{user.name} has no Discord ID, skipping.",
                        level=logging.WARNING,
                    )
                    continue

                leave_status = self.db_manager.is_user_on_leave(user.id, current_date)
                if leave_status:
                    log_user_action(
                        "System", f"{user.name} skipped due to leave status"
                    )
                    continue

                member = self.guild.get_member(int(user.discord_id))
                if member:
                    # Passa l'oggetto user invece di member
                    await self.sync_user_state(user)

            log_user_action("System", "State reconciliation completed")
        except Exception as e:
            log_exception("System", f"Error during state reconciliation: {str(e)}")

    async def reconcile_single_user_state(self, user, current_date):
        try:
            discord_member = self.guild.get_member(int(user.discord_id))
            if not discord_member:
                log_user_action(
                    user.name, "Discord member not found", level=logging.WARNING
                )
                return

            new_state = self.discord_status_to_user_state(str(discord_member.status))

            # Verifica se lo stato è cambiato
            if new_state == user.state:
                return

            # Gestione delle transizioni inusuali
            if user.state == UserState.OFFLINE and new_state in [
                UserState.SHORT_BREAK,
                UserState.LUNCH_BREAK,
            ]:
                log_user_action(
                    user.name,
                    f"Unusual transition: {user.state} -> {new_state}",
                    level=logging.WARNING,
                )
                await self.handle_start_work(user)
                await self.handle_start_break(user, new_state)
            else:
                await self.sync_user_state(user)

        except Exception as e:
            log_user_action(
                user.name,
                f"Error during state reconciliation: {str(e)}",
                level=logging.ERROR,
            )


    async def handle_overtime(self, user, current_time):
        # Verifica se si sta lavorando in un giorno festivo o fuori dall'orario standard
        if (
            current_time.date().weekday() >= 5
            or current_time.time() > Config.WORK_END_TIME
        ):
            if Config.SILENT_MODE:
                self.db_manager.log_overtime(user.id, current_time)
            else:
                # Richiede conferma
                await self.request_overtime_confirmation(user)
    
    async def sync_user_state(self, user):
        discord_id = str(user.discord_id)
        log_user_action('System', f"Synchronizing state for user {user.name} with Discord ID {discord_id}")

        member = self.guild.get_member(int(discord_id))
        if not member:
            log_user_action('System', f"Discord member with ID {discord_id} not found in guild")
            return

        # Log the detected Discord status for debugging
        detected_status = str(member.status)
        log_user_action('System', f"Detected Discord status for {user.name}: {detected_status}")

        async with self.status_update_lock:
            new_state = self.discord_status_to_user_state(detected_status)

            # Recupera lo stato corrente dal database
            old_state = self.db_manager.get_user_current_state(user.id)

            # Log the old and new state for debugging
            log_user_action('System', f"Old state from DB: {old_state}, New state: {new_state.name}")

            if new_state.name != old_state:
                log_user_action(user.name, f"{old_state} -> {new_state.name}")

                # Handle the state transition
                if new_state == UserState.OFFLINE:
                    await self.handle_end_work(user)
                elif new_state == UserState.WORKING and old_state == 'OFFLINE':
                    await self.handle_start_work(user)
                elif new_state in [UserState.SHORT_BREAK, UserState.LUNCH_BREAK] and old_state == 'WORKING':
                    await self.handle_start_break(user, new_state)

                # Update the state in the database
                self.db_manager.update_user_state(user.id, new_state.name)
                user.state = new_state  # Ensure the user state is updated

        log_user_action('System', f"State synchronization completed for user {user.name}")


    def check_leave_status(self, user, current_date):
        leave_records = self.db_manager.get_user_leave_records(user.id)
        for record in leave_records:
            start_date = datetime.strptime(record["start_date"], "%Y-%m-%d").date()
            end_date = datetime.strptime(record["end_date"], "%Y-%m-%d").date()
            if start_date <= current_date <= end_date:
                return (
                    UserState.SICK
                    if record["leave_type"] == "malattia"
                    else UserState.ON_LEAVE
                )
        return None

    def discord_status_to_user_state(self, status):
        if status == "online":
            return UserState.WORKING
        elif status == "idle":
            return UserState.SHORT_BREAK
        elif status == "dnd":
            return UserState.LUNCH_BREAK
        else:
            return UserState.OFFLINE

    async def handle_start_work(self, user):
        existing_work_log = self.db_manager.get_work_start_for_today(user.id)
        if existing_work_log:
            user.work_start = datetime.fromisoformat(existing_work_log["start_time"])
            log_user_action(
                user.name, f"Existing work log found, start time: {user.work_start}"
            )
        else:
            current_time = datetime.now()
            self.db_manager.log_work_start(user.id, start_time=current_time)
            user.work_start = current_time
            log_user_action(user.name, f"Started work at {current_time}")

    async def handle_start_break(self, user, break_type):
        # Controlla se esiste già una pausa attiva per l'utente
        active_break = self.db_manager.get_active_break(user.id)
        if active_break:
            log_user_action(
                user.name,
                f"Active break already in progress, no new break log created.",
            )
            return

        # Se non esiste una pausa attiva, logga l'inizio della nuova pausa
        current_time = datetime.now()
        self.db_manager.log_break_start(
            user.id, break_type.name, start_time=current_time
        )
        log_user_action(user.name, f"Started {break_type.name} at {current_time}")

    async def handle_end_work(self, user):
        current_time = datetime.now()
        
        # Ottieni l'ultimo log di lavoro per oggi
        work_log = self.db_manager.get_work_start_for_today(user.id)
        
        if not work_log:
            log_user_action(user.name, "No active work log found for today. Cannot end work.")
            return
        
        start_time = datetime.fromisoformat(work_log['start_time'])

        # Calcola le ore totali lavorate
        total_hours = (current_time - start_time).total_seconds() / 3600
        
        # Ottieni tutte le pause della giornata
        break_logs = self.db_manager.get_user_break_logs(user.id, start_time.date(), current_time.date())
        
        total_break_time = timedelta()
        lunch_break_time = timedelta(hours=1)  # Pausa pranzo standard di 1 ora
        extra_lunch_time = timedelta()

        for break_log in break_logs:
            break_start = datetime.fromisoformat(break_log['start_time'])
            break_end = datetime.fromisoformat(break_log['end_time']) if break_log['end_time'] else current_time
            break_duration = break_end - break_start
            
            # Classificazione delle pause
            if break_log['type'] == 'ON_BREAK_LUNCH':
                if break_duration > lunch_break_time:
                    extra_lunch_time += break_duration - lunch_break_time
            else:
                total_break_time += break_duration

        # Somma eventuale eccedenza della pausa pranzo al tempo totale delle pause
        total_break_time += extra_lunch_time

        # Calcola le ore effettive
        effective_hours = total_hours - (total_break_time.total_seconds() / 3600)
        
        # Calcola il bilancio del giorno
        standard_hours = 8.0  # Orario di lavoro standard giornaliero
        work_balance = effective_hours - standard_hours
        
        # Calcola il bilancio cumulativo
        last_cumulative_balance = self.db_manager.get_last_cumulative_balance(user.id)
        cumulative_balance = (last_cumulative_balance or 0.0) + work_balance

        # Aggiorna il log di lavoro con le ore totali, effettive, bilancio e bilancio cumulativo
        self.db_manager.log_work_end(user.id, total_mobile_time=user.total_mobile_time, total_pc_time=user.total_pc_time)
        self.db_manager.update_work_balance(user.id, work_log['id'], work_balance, cumulative_balance)
        
        log_user_action(user.name, f"Ended work. Total hours: {total_hours:.2f}, Effective hours: {effective_hours:.2f}, Balance: {work_balance:.2f}, Cumulative Balance: {cumulative_balance:.2f}")

        # Aggiorna lo stato dell'utente
        user.state = UserState.OFFLINE



    @commands.command(name="status")
    async def status(self, ctx):
        user = self.users.get(str(ctx.author.id))
        if user:
            await ctx.send(f"Your current status is: {user.state.name}")
        else:
            await ctx.send("You are not registered in the work tracking system.")

    # @commands.Cog.listener()
    # async def on_member_update(self, before, after):
    #     if before.status != after.status:
    #         user = self.users.get(str(after.id))
    #         if user:
    #             logger.info(
    #                 f"User {user.name} changed status from {before.status} to {after.status}"
    #             )
    #             new_state = self.discord_status_to_user_state(str(after.status))
    #             await self.sync_user_state(user, new_state, user.state)
