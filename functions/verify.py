import discord
from discord.ext import commands


VERIFY_PANEL_MARKER = "Il Divano"


class VerifyView(discord.ui.View):

    def __init__(self, config: dict):

        super().__init__(
            timeout=None
        )

        self.config = config


    @discord.ui.button(
        label="Verifica",
        emoji="✅",
        style=discord.ButtonStyle.success,
        custom_id="il_divano_verify_v1"
    )
    async def verify(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):

        if interaction.guild is None:

            await interaction.response.send_message(
                "Impossibile aggiungere ruolo.",
                ephemeral=True
            )

            return


        if not isinstance(
            interaction.user,
            discord.Member
        ):

            await interaction.response.send_message(
                "Impossibile aggiungere ruolo.",
                ephemeral=True
            )

            return


        try:

            role_id = int(
                self.config["verify_role_id"]
            )

        except (
            KeyError,
            ValueError,
            TypeError
        ):

            await interaction.response.send_message(
                "Impossibile aggiungere ruolo.",
                ephemeral=True
            )

            return


        role = interaction.guild.get_role(
            role_id
        )


        if role is None:

            await interaction.response.send_message(
                "Impossibile aggiungere ruolo.",
                ephemeral=True
            )

            return


        if role in interaction.user.roles:

            await interaction.response.send_message(
                "✅ Sei già verificato.",
                ephemeral=True
            )

            return


        bot_member = interaction.guild.me


        if bot_member is None:

            await interaction.response.send_message(
                "Impossibile aggiungere ruolo.",
                ephemeral=True
            )

            return


        if not bot_member.guild_permissions.manage_roles:

            await interaction.response.send_message(
                "Impossibile aggiungere ruolo.",
                ephemeral=True
            )

            return


        if bot_member.top_role <= role:

            await interaction.response.send_message(
                "Impossibile aggiungere ruolo.",
                ephemeral=True
            )

            return


        try:

            await interaction.user.add_roles(
                role,
                reason="Verifica completata su Il Divano"
            )

            await interaction.response.send_message(
                "✅ Verifica completata.",
                ephemeral=True
            )

        except (
            discord.Forbidden,
            discord.HTTPException
        ):

            await interaction.response.send_message(
                "Impossibile aggiungere ruolo.",
                ephemeral=True
            )


def build_verify_embed():

    embed = discord.Embed(
        title="✅・VERIFICA",
        description=(
            "Per accedere al resto del server devi completare "
            "la verifica premendo il pulsante qui sotto."
        ),
        color=discord.Color.green()
    )

    embed.add_field(
        name="🔐 Verifica account",
        value=(
            "Premi **Verifica** e riceverai automaticamente "
            "il ruolo necessario per accedere al server."
        ),
        inline=False
    )

    embed.add_field(
        name="⚡ Veloce e automatico",
        value=(
            "Non devi compilare nulla. "
            "Ti basta premere il pulsante una sola volta."
        ),
        inline=False
    )

    embed.set_footer(
        text=f"By Kekko • {VERIFY_PANEL_MARKER}"
    )

    return embed


async def resolve_verify_channel(
    bot: commands.Bot,
    channel_id: int
):

    channel = bot.get_channel(
        channel_id
    )


    if channel is not None:

        return channel


    try:

        return await bot.fetch_channel(
            channel_id
        )

    except discord.DiscordException:

        return None


async def delete_old_verify_panels(
    bot: commands.Bot,
    channel: discord.TextChannel
):

    try:

        async for message in channel.history(
            limit=150
        ):

            if bot.user is None:
                return


            if message.author.id != bot.user.id:
                continue


            for embed in message.embeds:

                footer_text = ""

                if embed.footer:
                    footer_text = (
                        embed.footer.text
                        or ""
                    )


                if VERIFY_PANEL_MARKER in footer_text:

                    try:

                        await message.delete()

                    except discord.DiscordException:

                        pass

                    break

    except discord.DiscordException:

        pass


async def refresh_verify_panel(
    bot: commands.Bot,
    config: dict
):

    try:

        channel_id = int(
            config["verify_channel_id"]
        )

    except (
        KeyError,
        ValueError,
        TypeError
    ):

        raise RuntimeError(
            "verify_channel_id non configurato."
        )


    if not channel_id:

        raise RuntimeError(
            "verify_channel_id non configurato."
        )


    channel = await resolve_verify_channel(
        bot,
        channel_id
    )


    if not isinstance(
        channel,
        discord.TextChannel
    ):

        raise RuntimeError(
            "verify_channel_id non punta "
            "a un canale testuale valido."
        )


    await delete_old_verify_panels(
        bot,
        channel
    )


    await channel.send(
        embed=build_verify_embed(),
        view=VerifyView(config)
    )


async def setup_verify_system(
    bot: commands.Bot,
    config: dict
):

    bot.add_view(
        VerifyView(config)
    )
