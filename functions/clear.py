import discord
from discord.ext import commands


class ClearCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command(name="clear")
    async def clear_messages(self, ctx: commands.Context, amount: int = None):

        if not isinstance(ctx.author, discord.Member):
            return

        if not (
            ctx.author.guild_permissions.manage_messages
            or ctx.author.guild_permissions.administrator
        ):
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

        amount = min(amount, 500)

        try:
            await ctx.channel.purge(
                limit=amount,
                before=ctx.message,
                reason=f"!clear usato da {ctx.author} ({ctx.author.id})",
            )
        except discord.DiscordException:
            pass

        try:
            await ctx.message.delete()
        except discord.DiscordException:
            pass

    @clear_messages.error
    async def clear_messages_error(self, ctx: commands.Context, error):
        try:
            await ctx.message.delete()
        except discord.DiscordException:
            pass


async def setup_clear_system(bot: commands.Bot):
    await bot.add_cog(ClearCog(bot))
