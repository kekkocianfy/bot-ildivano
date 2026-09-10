import discord
from discord.ext import commands


class ClearCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command(name="clear")
    async def clear_messages(self, ctx: commands.Context, amount: int = None):
        """
        !clear NUMERO

        Elimina:
        - il numero di messaggi indicato
        - il messaggio !clear stesso

        Non invia nessuna conferma o risposta nel canale.
        """

        # Solo utenti con Gestisci Messaggi o Administrator.
        if not isinstance(ctx.author, discord.Member):
            return

        if not (
            ctx.author.guild_permissions.manage_messages
            or ctx.author.guild_permissions.administrator
        ):
            # Nessun messaggio di errore: resta completamente silenzioso.
            try:
                await ctx.message.delete()
            except discord.DiscordException:
                pass
            return

        if amount is None or amount < 1:
            try:
                await ctx.message.delete()
            except discord.DiscordException:
                pass
            return

        # Limite ragionevole per evitare cancellazioni accidentali gigantesche.
        amount = min(amount, 500)

        try:
            # Cancella esattamente N messaggi PRIMA del comando.
            await ctx.channel.purge(
                limit=amount,
                before=ctx.message,
                reason=f"!clear usato da {ctx.author} ({ctx.author.id})",
            )
        except discord.DiscordException:
            pass

        # Cancella il comando stesso.
        try:
            await ctx.message.delete()
        except discord.DiscordException:
            pass

    @clear_messages.error
    async def clear_messages_error(self, ctx: commands.Context, error):
        # Anche in caso di sintassi errata, nessuna risposta.
        try:
            await ctx.message.delete()
        except discord.DiscordException:
            pass


async def setup_clear_system(bot: commands.Bot):
    await bot.add_cog(ClearCog(bot))
