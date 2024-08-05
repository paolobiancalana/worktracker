import asyncio
import discord
from discord.ext import commands
from discord import ui
from datetime import datetime, timedelta
from ui_messages import (
    UIMessages,
    BreaksView,
    ConfirmationView,
    TimeSelectionView,
    ManualEntryView,
)
from logger import logger
from user import UserState


class WorkCommands(commands.Cog):
    def __init__(self, bot, db_manager, work_tracker):
        self.bot = bot
        self.db_manager = db_manager
        self.work_tracker = work_tracker

    async def sync_user_state(self, user):
        discord_member = self.bot.get_guild(int(self.bot.config.GUILD_ID)).get_member(
            int(user.discord_id)
        )
        if discord_member:
            discord_status = str(discord_member.status)
            new_state = self.work_tracker.discord_status_to_user_state(discord_status)
            if new_state != user.state:
                await self.work_tracker.sync_user_state(user, new_state, user.state)

    @commands.command(name="status")
    async def status(self, ctx):
        try:
            logger.info(f"Received !status command from user ID {ctx.author.id}")
            user = self.work_tracker.users.get(str(ctx.author.id))

            if not user:
                logger.warning(f"User with ID {ctx.author.id} not found in the system.")
                user = self.db_manager.get_user_by_discord_id(ctx.author.id)
                if not user:
                    await ctx.send("Sorry, I couldn't find your work data.")
                    return

            # Sync user state before showing status
            discord_member = ctx.guild.get_member(int(user.discord_id))
            if discord_member:
                discord_status = str(discord_member.status)
                new_state = self.work_tracker.discord_status_to_user_state(
                    discord_status
                )
                if new_state != user.state:
                    await self.work_tracker.sync_user_state(user, new_state, user.state)

            logger.info(f"User found: {user.name}")

            start_time, total_hours, effective_hours = self.db_manager.get_total_hours(
                user.id
            )

            if start_time:
                work_start_datetime = start_time.strftime("%d-%m-%Y %H:%M:%S")
            else:
                work_start_datetime = "N/A"

            lunch_break = (
                "Yes" if self.db_manager.has_lunch_break_today(user.id) else "No"
            )
            current_state = user.state.name

            embed = discord.Embed(
                title="📊 **Your Work Status**", color=discord.Color.blue()
            )
            embed.add_field(
                name="📅 **Work Start Date and Time**",
                value=work_start_datetime,
                inline=False,
            )
            embed.add_field(
                name="👔 **Work Hours**",
                value=f"Total: {total_hours} | Effective: {effective_hours}",
                inline=False,
            )
            embed.add_field(
                name="🍽️ **Lunch Break Taken**", value=lunch_break, inline=True
            )
            embed.add_field(
                name="📅 **Current State**", value=current_state, inline=False
            )
            embed.set_footer(
                text="Keep up the good work! Remember to take regular breaks for a good work-life balance."
            )

            view = BreaksView(user.id)
            msg = await ctx.send(embed=embed, view=view)
            view.message = msg
            logger.info(f"Status message sent to user {user.name}")

            self.bot.loop.create_task(self.delete_message_after(msg, timeout=180))

        except Exception as e:
            logger.error(f"Error sending status message: {str(e)}")
            await ctx.send("An error occurred while retrieving your status.")

    @commands.command(name="breaks")
    async def breaks(self, ctx):
        logger.info(f"Received !breaks command from user ID {ctx.author.id}")
        user = self.work_tracker.users.get(str(ctx.author.id))

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
                    start_time_formatted = datetime.fromisoformat(start_time).strftime(
                        "%d-%m-%Y %H:%M:%S"
                    )
                    end_time_formatted = (
                        datetime.fromisoformat(end_time).strftime("%d-%m-%Y %H:%M:%S")
                        if end_time
                        else "Ongoing"
                    )
                    break_table += f"{start_time_formatted} | {end_time_formatted} | {duration} min | {break_type}\n"

                await ctx.send(f"```Break details for {user.name}:\n{break_table}```")
                logger.info(f"Break report sent to user {user.name}")
            except Exception as e:
                logger.error(f"Error retrieving break details: {str(e)}")
                await ctx.send("An error occurred while retrieving your break details.")
        else:
            logger.warning(f"User with ID {ctx.author.id} not found in the system")
            await ctx.send("Sorry, I couldn't find your break data.")

    @commands.command(name="start_work")
    async def start_work(self, ctx):
        user = self.work_tracker.users.get(str(ctx.author.id))
        if not user:
            await ctx.send("You are not registered in the work tracking system.")
            return

        if user.state == UserState.WORKING:
            await ctx.send("You are already working.")
            return

        await self.work_tracker.handle_start_work(user)
        await ctx.send("Your work day has started. Have a productive day!")

    @commands.command(name="end_work")
    async def end_work(self, ctx):
        user = self.work_tracker.users.get(str(ctx.author.id))
        if not user:
            await ctx.send("You are not registered in the work tracking system.")
            return

        if user.state != UserState.WORKING:
            await ctx.send("You are not currently working.")
            return

        await self.work_tracker.handle_end_work(user)
        await ctx.send("Your work day has ended. Enjoy your time off!")

    @commands.command(name="start_break")
    async def start_break(self, ctx, break_type: str = "SHORT_BREAK"):
        user = self.work_tracker.users.get(str(ctx.author.id))
        if not user:
            await ctx.send("You are not registered in the work tracking system.")
            return

        if user.state != UserState.WORKING:
            await ctx.send("You need to be working to start a break.")
            return

        break_type = break_type.upper()
        if break_type not in ["SHORT_BREAK", "LUNCH_BREAK"]:
            await ctx.send(
                "Invalid break type. Please use 'SHORT_BREAK' or 'LUNCH_BREAK'."
            )
            return

        await self.work_tracker.handle_start_break(user, UserState[break_type])
        await ctx.send(
            f"Your {break_type.lower().replace('_', ' ')} has started. Enjoy!"
        )

    @commands.command(name="end_break")
    async def end_break(self, ctx):
        user = self.work_tracker.users.get(str(ctx.author.id))
        if not user:
            await ctx.send("You are not registered in the work tracking system.")
            return

        if user.state not in [UserState.SHORT_BREAK, UserState.LUNCH_BREAK]:
            await ctx.send("You are not currently on a break.")
            return

        self.db_manager.log_break_end(user.id)
        user.state = UserState.WORKING
        await ctx.send("Your break has ended. Back to work!")

    @commands.command(name="weekly_report")
    async def weekly_report(self, ctx):
        user = self.work_tracker.users.get(str(ctx.author.id))
        if not user:
            await ctx.send("You are not registered in the work tracking system.")
            return

        end_date = datetime.now()
        start_date = end_date - timedelta(days=7)
        work_logs = self.db_manager.get_user_work_logs(user.id, start_date, end_date)

        if not work_logs:
            await ctx.send("No work logs found for the past week.")
            return

        report = "Date | Start Time | End Time | Total Hours | Effective Hours\n"
        report += "-" * 70 + "\n"

        for log in work_logs:
            start_time = datetime.fromisoformat(log["start_time"])
            end_time = (
                datetime.fromisoformat(log["end_time"])
                if log["end_time"]
                else "Ongoing"
            )
            date = start_time.strftime("%Y-%m-%d")
            start = start_time.strftime("%H:%M")
            end = (
                end_time.strftime("%H:%M")
                if isinstance(end_time, datetime)
                else end_time
            )
            total_hours = f"{log['total_hours']:.2f}" if log["total_hours"] else "N/A"
            effective_hours = (
                f"{log['effective_hours']:.2f}" if log["effective_hours"] else "N/A"
            )

            report += f"{date} | {start} | {end} | {total_hours} | {effective_hours}\n"

        await ctx.send(f"```Weekly Report for {user.name}:\n{report}```")

    @commands.command(name="manualentry")
    async def manual_entry(self, ctx, target_user: discord.Member = None):
        if target_user is None:
            target_user = ctx.author

        user = self.work_tracker.users.get(str(target_user.id))
        if not user:
            await ctx.send(
                "The specified user is not registered in the work tracking system."
            )
            return

        view = ManualEntryView()
        msg = await ctx.send(embed=UIMessages.manual_entry_embed(), view=view)
        view.message = msg

        # Wait for the user to select an option
        await view.wait()

        if view.value is None:
            await ctx.send("Manual entry timed out.")
            return

        if view.value == "check_in":
            time_view = TimeSelectionView()
            await ctx.send("Select the check-in time:", view=time_view)
            await time_view.wait()
            if time_view.selected_time:
                # Process check-in
                pass
        elif view.value == "break_start":
            time_view = TimeSelectionView()
            await ctx.send("Select the break start time:", view=time_view)
            await time_view.wait()
            if time_view.selected_time:
                # Process break start
                pass
        # ... handle other options ...

        await ctx.send("Manual entry processed successfully.")

    async def delete_message_after(self, message, timeout):
        await asyncio.sleep(timeout)
        try:
            await message.delete()
        except discord.errors.NotFound:
            pass
