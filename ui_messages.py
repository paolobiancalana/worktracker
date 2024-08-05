import discord
from discord.ui import View, Button, Select, Modal, TextInput
from logger import logger

class ConfirmationView(View):
    def __init__(self, timeout=180):
        super().__init__(timeout=timeout)
        self.value = None

    @discord.ui.button(label="Confirm", style=discord.ButtonStyle.green)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        self.value = True
        self.stop()

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.red)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        self.value = False
        self.stop()

class BreakExtensionView(View):
    def __init__(self, timeout=180):
        super().__init__(timeout=timeout)
        self.value = None
        self.duration = None
        self.justification = None

    @discord.ui.select(
        placeholder="Select break extension duration",
        options=[
            discord.SelectOption(label="5 minutes", value="5"),
            discord.SelectOption(label="10 minutes", value="10"),
            discord.SelectOption(label="15 minutes", value="15")
        ]
    )
    async def select_duration(self, interaction: discord.Interaction, select: discord.ui.Select):
        await interaction.response.defer()
        self.duration = int(select.values[0])

    @discord.ui.button(label="Extend", style=discord.ButtonStyle.green)
    async def extend(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.duration:
            await interaction.response.send_message("Please select a duration first.", ephemeral=True)
            return

        if self.duration > 5:
            modal = JustificationModal(title="Break Extension Justification")
            await interaction.response.send_modal(modal)
            await modal.wait()
            if modal.justification:
                self.justification = modal.justification
                self.value = True
                self.stop()
            else:
                await interaction.followup.send("Justification is required for breaks longer than 5 minutes.", ephemeral=True)
        else:
            await interaction.response.defer()
            self.value = True
            self.stop()

    @discord.ui.button(label="End Break", style=discord.ButtonStyle.red)
    async def end_break(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        self.value = False
        self.stop()

class JustificationModal(Modal):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.justification = None

        self.add_item(TextInput(label="Justification", style=discord.TextStyle.paragraph, placeholder="Enter your reason for extending the break", required=True))

    async def on_submit(self, interaction: discord.Interaction):
        self.justification = self.children[0].value
        await interaction.response.defer()
        self.stop()

class BreaksView(View):
    def __init__(self, user_id, timeout=180):
        super().__init__(timeout=timeout)
        self.user_id = user_id

    @discord.ui.button(label="View Breaks", style=discord.ButtonStyle.blurple)
    async def view_breaks(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        ctx = await interaction.client.get_context(interaction.message)
        ctx.author = interaction.user
        await ctx.invoke(ctx.bot.get_command("breaks"))

    async def on_timeout(self):
        for child in self.children:
            child.disabled = True
        await self.message.edit(view=self)

class TimeSelectionView(View):
    def __init__(self, timeout=180):
        super().__init__(timeout=timeout)
        self.selected_time = None

        hours = [discord.SelectOption(label=f"{i:02}", value=f"{i:02}") for i in range(0, 24)]
        self.hour_select = Select(placeholder="Select hour", options=hours)
        self.hour_select.callback = self.hour_callback
        self.add_item(self.hour_select)

        minutes = [discord.SelectOption(label=f"{i:02}", value=f"{i:02}") for i in [0, 15, 30, 45]]
        self.minute_select = Select(placeholder="Select minutes", options=minutes)
        self.minute_select.callback = self.minute_callback
        self.add_item(self.minute_select)

    async def hour_callback(self, interaction: discord.Interaction):
        await interaction.response.defer()

    async def minute_callback(self, interaction: discord.Interaction):
        hour = self.hour_select.values[0]
        minute = interaction.data['values'][0]
        self.selected_time = f"{hour}:{minute}"
        logger.info(f"Time selected: {self.selected_time}")
        await interaction.response.defer()
        self.stop()

    async def on_timeout(self):
        logger.warning("TimeSelectionView timed out")
        for child in self.children:
            child.disabled = True
        if hasattr(self, 'message') and self.message:
            await self.message.edit(view=self)

class UIMessages:
    @staticmethod
    def start_work_embed():
        return discord.Embed(title="Start Work?", description="Are you starting your workday?", color=discord.Color.blue())

    @staticmethod
    def work_started_embed():
        return discord.Embed(title="Work Started", description="Your workday has been logged.", color=discord.Color.green())

    @staticmethod
    def work_not_started_embed():
        return discord.Embed(title="Work Not Started", description="No worries, let us know when you're ready to start.", color=discord.Color.orange())

    @staticmethod
    def end_work_embed():
        return discord.Embed(title="End Work?", description="Are you ending your workday?", color=discord.Color.blue())

    @staticmethod
    def work_ended_embed():
        return discord.Embed(title="Work Ended", description="Your workday has been logged as completed.", color=discord.Color.green())

    @staticmethod
    def work_not_ended_embed():
        return discord.Embed(title="Work Not Ended", description="Alright, we'll keep your work session active.", color=discord.Color.orange())

    @staticmethod
    def extend_break_embed():
        return discord.Embed(title="Extend Break?", description="Do you need to extend your break?", color=discord.Color.blue())

    @staticmethod
    def break_extended_embed(duration):
        return discord.Embed(title="Break Extended", description=f"Your break has been extended by {duration} minutes.", color=discord.Color.green())

    @staticmethod
    def break_ended_embed():
        return discord.Embed(title="Break Ended", description="Your break has ended. Welcome back to work!", color=discord.Color.green())

    @staticmethod
    def break_started_embed():
        return discord.Embed(title="Break Started", description="Your break has started. Enjoy your time off!", color=discord.Color.green())

    @staticmethod
    def break_ending_soon_embed():
        return discord.Embed(title="Break Ending Soon", description="Your break is about to end. Do you need to extend it?", color=discord.Color.yellow())

    @staticmethod
    def break_extension_request_embed(user, duration, justification):
        return discord.Embed(
            title="Break Extension Request",
            description=f"{user.name} has requested a {duration} minute break extension.\n\nJustification: {justification}",
            color=discord.Color.orange()
        )

    @staticmethod
    def break_extension_approved_embed(duration):
        return discord.Embed(
            title="Break Extension Approved",
            description=f"Your break extension of {duration} minutes has been approved.",
            color=discord.Color.green()
        )

    @staticmethod
    def break_extension_denied_embed():
        return discord.Embed(
            title="Break Extension Denied",
            description="Your break extension request has been denied. Please return to work.",
            color=discord.Color.red()
        )

    @staticmethod
    def notification_embed(title, message):
        return discord.Embed(title=title, description=message, color=discord.Color.blue())
    
    @staticmethod
    def overtime_work_embed():
        return discord.Embed(title="Lavoro straordinario", description="Stai per iniziare a lavorare in un giorno festivo o nel weekend. Confermi di voler iniziare il lavoro straordinario?", color=discord.Color.orange())

    @staticmethod
    def overtime_work_started_embed():
        return discord.Embed(title="Lavoro straordinario iniziato", description="Il tuo lavoro straordinario è stato registrato. Ricorda di prenderti delle pause regolari!", color=discord.Color.green())

    @staticmethod
    def overtime_work_not_started_embed():
        return discord.Embed(title="Lavoro straordinario non iniziato", description="Nessun problema, goditi il tuo tempo libero!", color=discord.Color.blue())