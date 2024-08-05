import discord
from discord.ext import commands
from datetime import datetime
from logger import logger

class LeaveManagement(commands.Cog):
    def __init__(self, bot, db_manager):
        self.bot = bot
        self.db_manager = db_manager

    @commands.command(name="add_leave", description="Aggiungi un'assenza per un utente")
    async def add_leave(self, ctx, user: discord.Member, leave_type: str, start_date: str, end_date: str, notes: str = ""):
        if not await self.is_admin(ctx):
            await ctx.send("Non hai i permessi per eseguire questo comando.")
            return

        try:
            start = datetime.strptime(start_date, "%Y-%m-%d").date()
            end = datetime.strptime(end_date, "%Y-%m-%d").date()
            if start > end:
                await ctx.send("La data di inizio deve essere precedente alla data di fine.")
                return
            
            target_user = self.db_manager.get_user_by_discord_id(user.id)
            if not target_user:
                await ctx.send("Utente non trovato nel database.")
                return
            
            leave_id = self.db_manager.add_leave_record(target_user.id, leave_type, start_date, end_date, notes)
            await ctx.send(f"Assenza aggiunta con successo. ID: {leave_id}")
            logger.info(f"Leave added for user {target_user.name} by {ctx.author.name}")
        except ValueError:
            await ctx.send("Formato data non valido. Usa YYYY-MM-DD.")

    @commands.command(name="view_leave", description="Visualizza un'assenza specifica")
    async def view_leave(self, ctx, leave_id: int):
        if not await self.is_admin(ctx):
            await ctx.send("Non hai i permessi per eseguire questo comando.")
            return

        leave = self.db_manager.get_leave_record(leave_id)
        if leave:
            embed = discord.Embed(title=f"Dettagli Assenza - ID: {leave['id']}")
            embed.add_field(name="Utente", value=leave['user_name'], inline=False)
            embed.add_field(name="Tipo", value=leave['leave_type'], inline=True)
            embed.add_field(name="Inizio", value=leave['start_date'], inline=True)
            embed.add_field(name="Fine", value=leave['end_date'], inline=True)
            embed.add_field(name="Note", value=leave['notes'] or "Nessuna nota", inline=False)
            await ctx.send(embed=embed)
        else:
            await ctx.send("Assenza non trovata.")

    async def is_admin(self, ctx):
        user = self.db_manager.get_user_by_discord_id(ctx.author.id)
        return user and user.admin

    # Aggiungi altri comandi per la gestione delle assenze se necessario