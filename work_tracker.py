import asyncio
import discord
from discord.ext import commands
from datetime import datetime, timedelta
from state_machine import UserState
from user import User
from ui_messages import UIMessages, ConfirmationView, BreakExtensionView, BreaksView, TimeSelectionView
from config import Config
from logger import logger

class WorkTracker(commands.Cog):
    def __init__(self, bot, db_manager):
        self.bot = bot
        self.db_manager = db_manager
        self.users = {}
        self.last_status_change = {}
        self.load_users()
        logger.info("WorkTracker initialized")

    def load_users(self):
        all_users = self.db_manager.get_all_users()
        if Config.TESTING:
            self.users = {user.discord_id: user for user in all_users if user.discord_id == Config.TEST_USER_DISCORD_ID}
        else:
            self.users = {user.discord_id: user for user in all_users}
        logger.info(f"Loaded {len(self.users)} users")

    async def reconcile_states(self):
        logger.info("Starting state reconciliation")
        current_date = datetime.now().date()
        for user in self.users.values():
            if user is None or user.discord_id is None:
                logger.warning(f"Skipping reconciliation for invalid user")
                continue
            await self.reconcile_user_state(user, current_date)
        logger.info("State reconciliation completed")

    async def reconcile_user_state(self, user, current_date):
        try:
            if self.db_manager.is_user_on_leave(user.id, current_date):
                user.state = UserState.ON_LEAVE
                logger.info(f"User {user.name} is on leave today")
                return

            guild = self.bot.get_guild(int(Config.GUILD_ID))
            if not guild:
                logger.error(f"Could not find guild with ID {Config.GUILD_ID}")
                return

            discord_member = guild.get_member(int(user.discord_id))
            if not discord_member:
                logger.warning(f"Could not find Discord member for user {user.name}")
                return

            discord_status = str(discord_member.status)
            db_state = self.db_manager.get_user_state(user.id)
            
            if discord_status == 'online' and db_state == 'OFFLINE':
                await self.prompt_manual_entry(user, datetime.now())
            elif discord_status == 'online' and db_state != 'WORKING':
                await self.handle_online(user, reconciling=True)
            elif discord_status in ['offline', 'invisible'] and db_state == 'WORKING':
                await self.handle_offline(user, reconciling=True)
            elif discord_status == 'idle' and db_state == 'WORKING':
                await self.handle_idle(user, datetime.now(), reconciling=True)
            else:
                user.state = self.string_to_state(db_state)
            
            logger.info(f"Reconciled state for user {user.name}: {self.state_to_string(user.state)}")
        except Exception as e:
            logger.error(f"Error reconciling state for user {user.name}: {str(e)}")

    async def handle_status_change(self, discord_id, new_status):
        user = self.users.get(discord_id)
        if not user:
            logger.warning(f"Unknown user with discord_id {discord_id}")
            return

        current_time = datetime.now()
        
        # Controllo per evitare il doppio trigger
        if discord_id in self.last_status_change:
            last_change_time = self.last_status_change[discord_id]
            if (current_time - last_change_time).total_seconds() < 1:  # Ignora cambiamenti entro 1 secondo
                logger.debug(f"Ignoring duplicate status change for user {user.name}")
                return
        
        self.last_status_change[discord_id] = current_time
        
        if self.db_manager.is_user_on_leave(user.id, current_time.date()):
            logger.info(f"User {user.name} is on leave. Ignoring status change.")
            return

        logger.info(f"Status change for user {user.name}: {new_status} at {current_time}")

        if new_status == 'online':
            await self.handle_online(user)
        elif new_status == 'idle':
            await self.handle_idle(user, current_time)
        elif new_status in ['offline', 'invisible']:
            await self.handle_offline(user)

    async def prompt_manual_entry(self, user, current_time):
        discord_user = self.bot.get_user(int(user.discord_id))
        
        work_start_record = self.db_manager.get_work_start_for_today(user.id)
        if not work_start_record:
            start_time = await self.ask_for_time(user, "Non ho registrato un orario di inizio lavoro per oggi. Per favore, inserisci l'orario di inizio.")
            if start_time:
                start_datetime = datetime.combine(current_time.date(), datetime.strptime(start_time, "%H:%M").time())
                self.db_manager.log_work_start(user.id, start_datetime)
                user.state = UserState.WORKING
                await discord_user.send("Orario di inizio lavoro registrato con successo.")
                logger.info(f"Work start time logged for user {user.name}: {start_time}")
            else:
                logger.warning(f"Failed to get valid work start time for user {user.name}")
                return

        if current_time.time() >= datetime.strptime("12:00", "%H:%M").time() and not self.db_manager.has_lunch_break_today(user.id):
            lunch_view = ConfirmationView()
            lunch_msg = await discord_user.send("Hai già fatto la pausa pranzo oggi?", view=lunch_view)
            await lunch_view.wait()
            
            if lunch_view.value:
                lunch_start_time = await self.ask_for_time(user, "A che ora hai iniziato la pausa pranzo?")
                if lunch_start_time:
                    lunch_end_time = await self.ask_for_time(user, "A che ora hai finito la pausa pranzo?")
                    if lunch_end_time:
                        lunch_start_datetime = datetime.combine(current_time.date(), datetime.strptime(lunch_start_time, "%H:%M").time())
                        lunch_end_datetime = datetime.combine(current_time.date(), datetime.strptime(lunch_end_time, "%H:%M").time())
                        if lunch_end_datetime > lunch_start_datetime:
                            self.db_manager.log_break_start(user.id, 'ON_BREAK_LUNCH', lunch_start_datetime)
                            self.db_manager.log_break_end(user.id, lunch_end_datetime)
                            await discord_user.send(f"Pausa pranzo registrata dalle {lunch_start_time} alle {lunch_end_time}.")
                            logger.info(f"Lunch break logged for user {user.name}: {lunch_start_time} - {lunch_end_time}")
                        else:
                            await discord_user.send("L'orario di fine pausa deve essere successivo all'orario di inizio. La pausa pranzo non verrà registrata.")
                            logger.warning(f"Invalid lunch break times for user {user.name}")

        logger.info(f"Manual entry completed for user {user.name}")

    async def handle_online(self, user, reconciling=False):
        if user.state in [UserState.SHORT_BREAK, UserState.LUNCH_BREAK, UserState.EXTENDED_BREAK]:
            user.end_break()
            self.db_manager.log_break_end(user.id)
            logger.info(f"User {user.name} returned to work")
        elif user.state == UserState.OFFLINE:
            if self.is_holiday_or_weekend():
                await self.prompt_overtime_work(user)
            else:
                await self.prompt_start_work(user)

    def is_holiday_or_weekend(self):
        today = datetime.now().date()
        return today.weekday() >= 5 

    async def handle_offline(self, user, reconciling=False):
        if user.state != UserState.OFFLINE:
            current_time = datetime.now().time()
            work_end_time = datetime.strptime(Config.WORK_END_TIME, "%H:%M").time()

            if current_time >= work_end_time:
                user.reset_daily_attributes()
            
            if reconciling:
                user.end_work()
                self.db_manager.log_work_end(user.id, user.total_mobile_time, user.total_pc_time)
                logger.info(f"Automatically ended work for user {user.name} during reconciliation")
            else:
                await self.prompt_end_work(user)

    async def handle_idle(self, user, detected_time, reconciling=False):
        if user.state == UserState.WORKING:
            actual_break_start = detected_time - timedelta(minutes=Config.DISCORD_IDLE_TIME)

            if self.is_lunch_time(detected_time) and not user.has_taken_lunch_break:
                break_type = UserState.LUNCH_BREAK
                user.has_taken_lunch_break = True
                logger.info(f"User {user.name} started lunch break at {actual_break_start}")
            else:
                break_type = UserState.SHORT_BREAK
                logger.info(f"User {user.name} started short break at {actual_break_start}")

            user.start_break(break_type)
            self.db_manager.log_break_start(user.id, self.state_to_string(break_type), actual_break_start)
            
            time_difference = detected_time - actual_break_start
            minutes_ago = int(time_difference.total_seconds() / 60)
            
            logger.info(f"Started break for user {user.name} (actually started {minutes_ago} minutes ago)")
            
            remaining_break_time = max(0, Config.BREAK_DURATION - minutes_ago)
            self.bot.loop.create_task(self.monitor_break(user, remaining_break_time))

    async def monitor_break(self, user, remaining_minutes):
        logger.info(f"Monitoring break for user {user.name}, remaining duration: {remaining_minutes} minutes")
        if remaining_minutes > 0:
            await asyncio.sleep(remaining_minutes * 60)
        if user.state == UserState.SHORT_BREAK:
            discord_user = self.bot.get_user(int(user.discord_id))
            await discord_user.send(embed=UIMessages.break_ending_soon_embed())
            await self.prompt_extend_break(user)

    async def prompt_start_work(self, user):
        logger.info(f"Prompting start work for user {user.name}")
        discord_user = self.bot.get_user(int(user.discord_id))
        view = ConfirmationView()
        msg = await discord_user.send(embed=UIMessages.start_work_embed(), view=view)
        await view.wait()
        if view.value:
            user.start_work()
            self.db_manager.log_work_start(user.id)
            await msg.edit(embed=UIMessages.work_started_embed(), view=None)
            logger.info(f"User {user.name} started work")
        else:
            await msg.edit(embed=UIMessages.work_not_started_embed(), view=None)
            logger.info(f"User {user.name} did not start work")
    
    async def prompt_overtime_work(self, user):
        logger.info(f"Prompting overtime work for user {user.name}")
        discord_user = self.bot.get_user(int(user.discord_id))
        view = ConfirmationView()
        msg = await discord_user.send(embed=UIMessages.overtime_work_embed(), view=view)
        await view.wait()
        if view.value:
            user.start_work()
            self.db_manager.log_work_start(user.id, overtime=True)
            await msg.edit(embed=UIMessages.overtime_work_started_embed(), view=None)
            logger.info(f"User {user.name} started overtime work")
        else:
            await msg.edit(embed=UIMessages.overtime_work_not_started_embed(), view=None)
            logger.info(f"User {user.name} did not start overtime work")
    
    async def prompt_end_work(self, user):
        logger.info(f"Prompting end work for user {user.name}")
        discord_user = self.bot.get_user(int(user.discord_id))
        view = ConfirmationView()
        msg = await discord_user.send(embed=UIMessages.end_work_embed(), view=view)
        await view.wait()
        if view.value:
            user.end_work()
            self.db_manager.log_work_end(user.id, user.total_mobile_time, user.total_pc_time)
            await msg.edit(embed=UIMessages.work_ended_embed(), view=None)
            logger.info(f"User {user.name} ended work")
        else:
            await msg.edit(embed=UIMessages.work_not_ended_embed(), view=None)
            logger.info(f"User {user.name} did not end work")

    async def prompt_extend_break(self, user):
        logger.info(f"Prompting break extension for user {user.name}")
        discord_user = self.bot.get_user(int(user.discord_id))
        view = BreakExtensionView()
        msg = await discord_user.send(embed=UIMessages.extend_break_embed(), view=view)
        await view.wait()
        if view.value and view.duration:
            if view.duration > 5:
                approved = await self.request_admin_approval(user, view.duration, view.justification)
                if approved:
                    user.state = UserState.EXTENDED_BREAK
                    self.db_manager.log_break_extension(user.id, view.duration)
                    await msg.edit(embed=UIMessages.break_extended_embed(view.duration), view=None)
                    await discord_user.send(embed=UIMessages.break_extension_approved_embed(view.duration))
                    logger.info(f"User {user.name} extended break by {view.duration} minutes (approved)")
                else:
                    await msg.edit(embed=UIMessages.break_ended_embed(), view=None)
                    await discord_user.send(embed=UIMessages.break_extension_denied_embed())
                    logger.info(f"User {user.name} break extension denied")
            else:
                user.state = UserState.EXTENDED_BREAK
                self.db_manager.log_break_extension(user.id, view.duration)
                await msg.edit(embed=UIMessages.break_extended_embed(view.duration), view=None)
                logger.info(f"User {user.name} extended break by {view.duration} minutes")
        else:
            user.end_break()
            self.db_manager.log_break_end(user.id)
            await msg.edit(embed=UIMessages.break_ended_embed(), view=None)
            logger.info(f"User {user.name} ended break")

    async def request_admin_approval(self, user, duration, justification):
        admin_users = self.db_manager.get_admin_users()
        approval_view = ConfirmationView()
        approval_embed = UIMessages.break_extension_request_embed(user, duration, justification)
        
        for admin in admin_users:
            admin_user = self.bot.get_user(int(admin.discord_id))
            if admin_user:
                await admin_user.send(embed=approval_embed, view=approval_view)
        
        await approval_view.wait()
        return approval_view.value

    def is_lunch_time(self, current_time):
        lunch_start = datetime.strptime(Config.LUNCH_START_TIME, "%H:%M").time()
        lunch_end = datetime.strptime(Config.LUNCH_END_TIME, "%H:%M").time()
        return lunch_start <= current_time.time() <= lunch_end

    def is_work_hours(self):
        if Config.SIMULATE_WORK_HOURS:
            return True
        now = datetime.now().time()
        start = datetime.strptime(Config.WORK_START_TIME, "%H:%M").time()
        end = datetime.strptime(Config.WORK_END_TIME, "%H:%M").time()
        return start <= now <= end

    async def periodic_sync(self):
            while True:
                logger.info("Starting periodic sync")
                for user in self.users.values():
                    current_time = datetime.now()
                    time_spent = (current_time - user.last_state_change_time).total_seconds()

                    if user.is_mobile:
                        user.total_mobile_time += time_spent
                    else:
                        user.total_pc_time += time_spent

                    if user.usage_log_id:
                        self.db_manager.update_device_usage(user.usage_log_id, user.total_mobile_time, user.total_pc_time)

                    user.last_state_change_time = current_time

                await asyncio.sleep(Config.SYNC_INTERVAL)

    async def delete_message_after(self, message, timeout=180):
        await asyncio.sleep(timeout)
        try:
            await message.delete()
            logger.info(f"Message deleted after {timeout} seconds.")
        except Exception as e:
            logger.error(f"Failed to delete message: {str(e)}")

    @commands.command(name='status')
    async def status(self, ctx):
        try:
            logger.info(f"Received !status command from user ID {ctx.author.id}")
            user = self.users.get(str(ctx.author.id))
            
            if not user:
                logger.warning(f"User with ID {ctx.author.id} not found in the system.")
                user = self.db_manager.get_user_by_discord_id(ctx.author.id)
                if not user:
                    await ctx.send("Sorry, I couldn't find your work data.")
                    return
            
            logger.info(f"User found: {user.name}")
            
            start_time, total_hours, effective_hours = self.db_manager.get_total_hours(user.id)
            
            if start_time:
                work_start_datetime = start_time.strftime('%d-%m-%Y %H:%M:%S')
            else:
                work_start_datetime = "N/A"
            
            if "on going" in total_hours:
                total_hours = total_hours.replace(" (on going)", "")
                total_hours += " (in progress)"
            
            lunch_break = "Yes" if user.has_taken_lunch_break else "No"
            current_state = self.state_to_string(user.state)

            embed = discord.Embed(title="📊 **Your Work Status**", color=discord.Color.blue())
            embed.add_field(name="📅 **Work Start Date and Time**", value=work_start_datetime, inline=False)
            embed.add_field(name="👔 **Work Hours**", value=f"Total: {total_hours} | Effective: {effective_hours}", inline=False)
            embed.add_field(name="🍽️ **Lunch Break Taken**", value=lunch_break, inline=True)
            embed.add_field(name="📅 **Current State**", value=current_state, inline=False)
            embed.set_footer(text="Keep up the good work! Remember to take regular breaks for a good work-life balance.")
            
            view = BreaksView(user.id)
            msg = await ctx.send(embed=embed, view=view)
            view.message = msg
            logger.info(f"Status message sent to user {user.name}")

            self.bot.loop.create_task(self.delete_message_after(msg, timeout=180))
        
        except AttributeError as attr_err:
            logger.error(f"AttributeError: {attr_err}")
            await ctx.send("An error occurred while processing your status request.")
        
        except Exception as e:
            logger.error(f"Error sending status message: {str(e)}")
            await ctx.send("An error occurred while retrieving your status.")

    @commands.command(name='breaks')
    async def breaks(self, ctx):
        logger.info(f"Received !breaks command from user ID {ctx.author.id}")
        user = self.users.get(str(ctx.author.id))
        
        if user:
            logger.info(f"User found: {user.name}")
            try:
                break_logs = self.db_manager.get_breaks_summary(user.id)
                
                if not break_logs:
                    await ctx.send("No breaks found for today.")
                    return
                
                break_table = "Start Time | End Time | Duration | Break Type\n"
                break_table += "-" * 50 + "\n"
                
                for start_time, end_time, duration, break_type in break_logs:
                    start_time_formatted = datetime.fromisoformat(start_time).strftime('%d-%m-%Y %H:%M:%S')
                    end_time_formatted = datetime.fromisoformat(end_time).strftime('%d-%m-%Y %H:%M:%S') if end_time else "Ongoing"
                    break_table += f"{start_time_formatted} | {end_time_formatted} | {duration} min | {break_type}\n"
                
                await ctx.send(f"```Break details for {user.name}:\n{break_table}```")
                logger.info(f"Break report sent to user {user.name}")
            except Exception as e:
                logger.error(f"Error retrieving break details: {str(e)}")
                await ctx.send("An error occurred while retrieving your break details.")
        else:
            logger.warning(f"User with ID {ctx.author.id} not found in the system")
            await ctx.send("Sorry, I couldn't find your break data.")

    @staticmethod
    def state_to_string(state):
        return {
            UserState.OFFLINE: 'OFFLINE',
            UserState.WORKING: 'WORKING',
            UserState.SHORT_BREAK: 'ON_BREAK_SHORT',
            UserState.LUNCH_BREAK: 'ON_BREAK_LUNCH',
            UserState.EXTENDED_BREAK: 'ON_BREAK_EXTENDED',
            UserState.AFTER_HOURS: 'AFTER_HOURS',
            UserState.ON_LEAVE: 'ON_LEAVE'
        }.get(state, 'UNKNOWN')

    @staticmethod
    def string_to_state(state_string):
        return {
            'OFFLINE': UserState.OFFLINE,
            'WORKING': UserState.WORKING,
            'ON_BREAK_SHORT': UserState.SHORT_BREAK,
            'ON_BREAK_LUNCH': UserState.LUNCH_BREAK,
            'ON_BREAK_EXTENDED': UserState.EXTENDED_BREAK,
            'AFTER_HOURS': UserState.AFTER_HOURS,
            'ON_LEAVE': UserState.ON_LEAVE
        }.get(state_string, UserState.OFFLINE)

    async def ask_for_time(self, user, prompt_message):
        try:
            discord_user = self.bot.get_user(int(user.discord_id))
            logger.debug(f"Sending prompt message to user {user.name}")
            await discord_user.send(prompt_message)
            view = TimeSelectionView(timeout=180)
            logger.debug(f"Creating TimeSelectionView for user {user.name}")
            message = await discord_user.send("Select the time:", view=view)
            view.message = message
            logger.debug(f"Waiting for user {user.name} to select time")
            await view.wait()

            if view.selected_time:
                selected_time = view.selected_time
                await discord_user.send(f"You selected: {selected_time}")
                logger.info(f"User {user.name} selected time: {selected_time}")
                return selected_time
            else:
                await discord_user.send("Time's up! You didn't select a time.")
                logger.warning(f"Time selection timed out for user {user.name}")
                return None
        except Exception as e:
            logger.error(f"Error in ask_for_time for user {user.name}: {str(e)}")
            return None

logger.info("WorkTracker module loaded")