import discord
from discord.ui import View, Button, Select, Modal, TextInput
from discord import SelectOption
from logger import logger


class ConfirmationView(View):
    def __init__(self, timeout=180):
        super().__init__(timeout=timeout)
        self.value = None

    @discord.ui.button(label="Confirm", style=discord.ButtonStyle.green)
    async def confirm(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
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
            discord.SelectOption(label="15 minutes", value="15"),
        ],
    )
    async def select_duration(
        self, interaction: discord.Interaction, select: discord.ui.Select
    ):
        await interaction.response.defer()
        self.duration = int(select.values[0])

    @discord.ui.button(label="Extend", style=discord.ButtonStyle.green)
    async def extend(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.duration:
            await interaction.response.send_message(
                "Please select a duration first.", ephemeral=True
            )
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
                await interaction.followup.send(
                    "Justification is required for breaks longer than 5 minutes.",
                    ephemeral=True,
                )
        else:
            await interaction.response.defer()
            self.value = True
            self.stop()

    @discord.ui.button(label="End Break", style=discord.ButtonStyle.red)
    async def end_break(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        await interaction.response.defer()
        self.value = False
        self.stop()


class JustificationModal(Modal):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.justification = None

        self.add_item(
            TextInput(
                label="Justification",
                style=discord.TextStyle.paragraph,
                placeholder="Enter your reason for extending the break",
                required=True,
            )
        )

    async def on_submit(self, interaction: discord.Interaction):
        self.justification = self.children[0].value
        await interaction.response.defer()
        self.stop()


class BreaksView(View):
    def __init__(self, user_id, timeout=180):
        super().__init__(timeout=timeout)
        self.user_id = user_id

    @discord.ui.button(label="View Breaks", style=discord.ButtonStyle.blurple)
    async def view_breaks(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
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

        hours_options = [
            discord.SelectOption(label=f"{i:02d}", value=f"{i:02d}") for i in range(24)
        ]
        minutes_options = [
            discord.SelectOption(label=f"{i:02d}", value=f"{i:02d}")
            for i in [0, 15, 30, 45]
        ]

        self.hour_select = Select(placeholder="Seleziona l'ora", options=hours_options)
        self.minute_select = Select(
            placeholder="Seleziona i minuti", options=minutes_options
        )

        self.hour_select.callback = self.hour_callback
        self.minute_select.callback = self.minute_callback

        self.add_item(self.hour_select)
        self.add_item(self.minute_select)

    async def hour_callback(self, interaction: discord.Interaction):
        await interaction.response.defer()

    async def minute_callback(self, interaction: discord.Interaction):
        hour = self.hour_select.values[0]
        minute = self.minute_select.values[0]
        self.selected_time = f"{hour}:{minute}"
        logger.info(f"Time selected: {self.selected_time}")
        await interaction.response.send_message(
            f"Hai selezionato: {self.selected_time}"
        )
        self.stop()

    async def interaction_check(self, interaction) -> bool:
        if len(self.children) > 0:
            logger.error(
                f"Dropdown menu with more than 25 options: {len(self.children)}"
            )
        return True

    async def on_timeout(self):
        logger.warning("TimeSelectionView timed out")
        for child in self.children:
            child.disabled = True
        if hasattr(self, "message") and self.message:
            await self.message.edit(view=self)


class ManualEntryView(View):
    def __init__(self):
        super().__init__(timeout=180)
        self.selected_time = None

    @discord.ui.button(
        label="Check In", style=discord.ButtonStyle.primary, custom_id="check_in"
    )
    async def check_in_button(self, interaction: discord.Interaction, button: Button):
        self.stop()

    @discord.ui.button(
        label="Inizio Pausa",
        style=discord.ButtonStyle.secondary,
        custom_id="break_start",
    )
    async def break_start_button(
        self, interaction: discord.Interaction, button: Button
    ):
        self.stop()

    @discord.ui.button(
        label="Fine Pausa", style=discord.ButtonStyle.secondary, custom_id="break_end"
    )
    async def break_end_button(self, interaction: discord.Interaction, button: Button):
        self.stop()

    @discord.ui.button(
        label="Pausa Pranzo",
        style=discord.ButtonStyle.secondary,
        custom_id="lunch_break",
    )
    async def lunch_break_button(
        self, interaction: discord.Interaction, button: Button
    ):
        self.stop()

    @discord.ui.button(
        label="Fine Giornata", style=discord.ButtonStyle.danger, custom_id="end_day"
    )
    async def end_day_button(self, interaction: discord.Interaction, button: Button):
        self.stop()

    @discord.ui.button(
        label="Modifica Record",
        style=discord.ButtonStyle.primary,
        custom_id="modify_record",
    )
    async def modify_record_button(
        self, interaction: discord.Interaction, button: Button
    ):
        self.stop()


class RecordSelectionView(View):
    def __init__(self, records, timeout=180):
        super().__init__(timeout=timeout)
        self.selected_record_id = None

        # Crea un'opzione per ogni record disponibile
        options = [
            SelectOption(
                label=f"{record['type']} - {record['start_time']} to {record['end_time']}",
                value=str(record["id"]),
            )
            for record in records
        ]

        # Limita a 25 opzioni a causa delle limitazioni di Discord
        options = options[:25]

        self.select = Select(
            placeholder="Seleziona un record da modificare",
            options=options,
            min_values=1,
            max_values=1,
        )
        self.select.callback = self.select_callback
        self.add_item(self.select)

    async def select_callback(self, interaction: discord.Interaction):
        self.selected_record_id = int(self.select.values[0])
        await interaction.response.send_message(
            f"Hai selezionato il record con ID: {self.selected_record_id}"
        )
        self.stop()

    async def on_timeout(self):
        # Gestione del timeout
        for child in self.children:
            child.disabled = True
        if hasattr(self, "message") and self.message:
            await self.message.edit(view=self)
        self.stop()


class UIMessages:
    @staticmethod
    def manual_entry_embed():
        embed = discord.Embed(
            title="Manual Entry",
            description="Please select the action you'd like to perform:",
            color=discord.Color.blue(),
        )
        embed.add_field(
            name="1️⃣ Check In", value="Register your work start time.", inline=False
        )
        embed.add_field(
            name="2️⃣ Break Start", value="Register the start of a break.", inline=False
        )
        embed.add_field(
            name="3️⃣ Break End", value="Register the end of a break.", inline=False
        )
        embed.add_field(
            name="4️⃣ Lunch Break",
            value="Register your lunch break time.",
            inline=False,
        )
        embed.add_field(
            name="5️⃣ Work End",
            value="Register the end of your work day.",
            inline=False,
        )
        embed.add_field(
            name="6️⃣ Request Change",
            value="Request a change to an existing record.",
            inline=False,
        )
        embed.set_footer(text="Use the buttons below to make a selection.")
        return embed

    @staticmethod
    def time_selection_embed():
        return discord.Embed(
            title="Seleziona l'ora di inizio",
            description="Per favore, seleziona l'ora e i minuti per indicare l'orario di inizio del lavoro.",
            color=discord.Color.blue(),
        )

    @staticmethod
    def start_work_embed():
        return discord.Embed(
            title="Start Work?",
            description="Are you starting your workday?",
            color=discord.Color.blue(),
        )

    @staticmethod
    def work_started_embed():
        return discord.Embed(
            title="Work Started",
            description="Your workday has been logged.",
            color=discord.Color.green(),
        )

    @staticmethod
    def work_not_started_embed():
        return discord.Embed(
            title="Work Not Started",
            description="No worries, let us know when you're ready to start.",
            color=discord.Color.orange(),
        )

    @staticmethod
    def end_work_embed():
        return discord.Embed(
            title="End Work?",
            description="Are you ending your workday?",
            color=discord.Color.blue(),
        )

    @staticmethod
    def work_ended_embed():
        return discord.Embed(
            title="Work Ended",
            description="Your workday has been logged as completed.",
            color=discord.Color.green(),
        )

    @staticmethod
    def work_not_ended_embed():
        return discord.Embed(
            title="Work Not Ended",
            description="Alright, we'll keep your work session active.",
            color=discord.Color.orange(),
        )

    @staticmethod
    def extend_break_embed():
        return discord.Embed(
            title="Extend Break?",
            description="Do you need to extend your break?",
            color=discord.Color.blue(),
        )

    @staticmethod
    def break_extended_embed(duration):
        return discord.Embed(
            title="Break Extended",
            description=f"Your break has been extended by {duration} minutes.",
            color=discord.Color.green(),
        )

    @staticmethod
    def break_ended_embed():
        return discord.Embed(
            title="Break Ended",
            description="Your break has ended. Welcome back to work!",
            color=discord.Color.green(),
        )

    @staticmethod
    def break_started_embed():
        return discord.Embed(
            title="Break Started",
            description="Your break has started. Enjoy your time off!",
            color=discord.Color.green(),
        )

    @staticmethod
    def break_ending_soon_embed():
        return discord.Embed(
            title="Break Ending Soon",
            description="Your break is about to end. Do you need to extend it?",
            color=discord.Color.yellow(),
        )

    @staticmethod
    def break_extension_request_embed(user, duration, justification):
        return discord.Embed(
            title="Break Extension Request",
            description=f"{user.name} has requested a {duration} minute break extension.\n\nJustification: {justification}",
            color=discord.Color.orange(),
        )

    @staticmethod
    def break_extension_approved_embed(duration):
        return discord.Embed(
            title="Break Extension Approved",
            description=f"Your break extension of {duration} minutes has been approved.",
            color=discord.Color.green(),
        )

    @staticmethod
    def break_extension_denied_embed():
        return discord.Embed(
            title="Break Extension Denied",
            description="Your break extension request has been denied. Please return to work.",
            color=discord.Color.red(),
        )

    @staticmethod
    def notification_embed(title, message):
        return discord.Embed(
            title=title, description=message, color=discord.Color.blue()
        )

    @staticmethod
    def overtime_work_embed():
        return discord.Embed(
            title="Lavoro straordinario",
            description="Stai per iniziare a lavorare in un giorno festivo o nel weekend. Confermi di voler iniziare il lavoro straordinario?",
            color=discord.Color.orange(),
        )

    @staticmethod
    def overtime_work_started_embed():
        return discord.Embed(
            title="Lavoro straordinario iniziato",
            description="Il tuo lavoro straordinario è stato registrato. Ricorda di prenderti delle pause regolari!",
            color=discord.Color.green(),
        )

    @staticmethod
    def overtime_work_not_started_embed():
        return discord.Embed(
            title="Lavoro straordinario non iniziato",
            description="Nessun problema, goditi il tuo tempo libero!",
            color=discord.Color.blue(),
        )
