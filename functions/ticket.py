import re
import sqlite3

import discord
from discord.ext import commands


DB_PATH = "tickets.db"
TICKET_PANEL_MARKER = "Il Divano"


def connect_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with connect_db() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS bot_state (
                key TEXT PRIMARY KEY,
                value TEXT
            )
            """
        )
        conn.commit()


def get_state(key: str):
    with connect_db() as conn:
        row = conn.execute(
            "SELECT value FROM bot_state WHERE key = ?",
            (key,),
        ).fetchone()
        return row["value"] if row else None


def set_state(key: str, value: str):
    with connect_db() as conn:
        conn.execute(
            """
            INSERT INTO bot_state (key, value)
            VALUES (?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
            """,
            (key, value),
        )
        conn.commit()



async def resolve_channel(bot: commands.Bot, channel_id: int):
    channel = bot.get_channel(channel_id)

    if channel is not None:
        return channel

    try:
        return await bot.fetch_channel(channel_id)
    except discord.DiscordException:
        return None


def safe_channel_name(name: str) -> str:
    name = name.lower().strip()
    name = re.sub(r"[^a-z0-9-]", "-", name)
    name = re.sub(r"-+", "-", name).strip("-")
    return name[:60] or "utente"


def get_ticket_owner_id(channel: discord.TextChannel):
    if not channel.topic:
        return None

    marker = "IL_DIVANO_TICKET_OWNER:"

    if marker not in channel.topic:
        return None

    try:
        return int(channel.topic.split(marker, 1)[1].split("|", 1)[0].strip())
    except (ValueError, IndexError):
        return None


def member_is_ticket_staff(member: discord.Member, config: dict) -> bool:
    if member.guild_permissions.administrator:
        return True

    support_role_id = int(
        config.get(
            "ticket_support_role_id",
            config.get("reviewer_role_id", 0),
        )
    )

    if not support_role_id:
        return False

    return any(role.id == support_role_id for role in member.roles)


async def send_interview_ticket_message(user: discord.abc.User) -> bool:
    try:
        await user.send("Apri un ticket per organizzare un colloquio.")
        return True
    except (discord.Forbidden, discord.HTTPException):
        return False



def build_ticket_panel_embed(config: dict) -> discord.Embed:
    color_value = int(config.get("ticket_panel_color", 0x2563EB))

    embed = discord.Embed(
        title="🎫・CENTRO TICKET",
        description=(
            "### Hai bisogno di parlare con lo staff?\n"
            "Apri un ticket privato e verrai seguito direttamente da un membro dello staff.\n\n"
            "Se la tua **candidatura staff è stata accettata**, usa questo pannello "
            "per organizzare il colloquio."
        ),
        color=discord.Color(color_value),
    )

    embed.add_field(
        name="📩 APERTURA",
        value=(
            "Premi **Apri ticket** qui sotto.\n"
            "Verrà creato un canale privato dedicato a te."
        ),
        inline=True,
    )

    embed.add_field(
        name="🔐 PRIVACY",
        value=(
            "Il ticket sarà visibile soltanto a **te** e allo **staff autorizzato**."
        ),
        inline=True,
    )

    embed.add_field(
        name="⚡ IMPORTANTE",
        value=(
            "Puoi avere **un solo ticket aperto alla volta**.\n"
            "Evita di aprirne più di uno per la stessa richiesta."
        ),
        inline=False,
    )

    embed.set_footer(
        text=f"By Kekko • {TICKET_PANEL_MARKER}"
    )

    return embed


def build_ticket_open_embed(user: discord.Member) -> discord.Embed:
    embed = discord.Embed(
        title="🎟️・TICKET APERTO",
        description=(
            f"Ciao {user.mention}, il tuo ticket è stato creato correttamente.\n\n"
            "Scrivi qui tutto ciò che serve. Un membro dello staff ti risponderà appena possibile."
        ),
        color=discord.Color.green(),
    )

    embed.add_field(
        name="🗣️ Se sei qui per la candidatura",
        value="Indica che devi organizzare il **colloquio staff**.",
        inline=False,
    )

    embed.add_field(
        name="🔒 Chiusura",
        value="Quando avete terminato, usa il pulsante **Chiudi ticket**.",
        inline=False,
    )

    embed.set_footer(text="By Kekko")
    return embed



class TicketPanelView(discord.ui.View):
    def __init__(self, bot: commands.Bot, config: dict):
        super().__init__(timeout=None)
        self.bot = bot
        self.config = config

    @discord.ui.button(
        label="Apri ticket",
        emoji="🟡",
        style=discord.ButtonStyle.secondary,
        custom_id="il_divano_open_ticket_v1",
    )
    async def open_ticket(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ):
        if (
            interaction.guild is None
            or not isinstance(interaction.user, discord.Member)
        ):
            await interaction.response.send_message(
                "Puoi aprire un ticket solo dal server.",
                ephemeral=True,
            )
            return

        category_id = int(self.config.get("ticket_category_id", 0))
        support_role_id = int(
            self.config.get(
                "ticket_support_role_id",
                self.config.get("reviewer_role_id", 0),
            )
        )

        category = interaction.guild.get_channel(category_id)
        support_role = interaction.guild.get_role(support_role_id)

        if not isinstance(category, discord.CategoryChannel):
            await interaction.response.send_message(
                "La categoria ticket non è configurata correttamente.",
                ephemeral=True,
            )
            return

        for channel in category.text_channels:
            if get_ticket_owner_id(channel) == interaction.user.id:
                await interaction.response.send_message(
                    f"Hai già un ticket aperto: {channel.mention}",
                    ephemeral=True,
                )
                return

        bot_member = interaction.guild.me

        overwrites = {
            interaction.guild.default_role: discord.PermissionOverwrite(
                view_channel=False,
            ),
            interaction.user: discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                read_message_history=True,
                attach_files=True,
                embed_links=True,
            ),
        }

        if bot_member is not None:
            overwrites[bot_member] = discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                read_message_history=True,
                manage_channels=True,
                manage_messages=True,
            )

        if support_role is not None:
            overwrites[support_role] = discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                read_message_history=True,
                attach_files=True,
                embed_links=True,
                manage_messages=True,
            )

        channel_name = (
            f"ticket-{safe_channel_name(interaction.user.display_name)}-"
            f"{str(interaction.user.id)[-4:]}"
        )

        try:
            ticket_channel = await interaction.guild.create_text_channel(
                name=channel_name,
                category=category,
                topic=(
                    f"IL_DIVANO_TICKET_OWNER:{interaction.user.id}"
                    f"|USER:{interaction.user}"
                ),
                overwrites=overwrites,
                reason=f"Ticket aperto da {interaction.user}",
            )
        except discord.Forbidden:
            await interaction.response.send_message(
                "Il bot non ha i permessi per creare il ticket.",
                ephemeral=True,
            )
            return
        except discord.HTTPException:
            await interaction.response.send_message(
                "Non sono riuscito a creare il ticket.",
                ephemeral=True,
            )
            return

        staff_mention = support_role.mention if support_role else ""

        await ticket_channel.send(
            content=f"{interaction.user.mention} {staff_mention}".strip(),
            embed=build_ticket_open_embed(interaction.user),
            view=TicketControlView(self.bot, self.config),
            allowed_mentions=discord.AllowedMentions(
                users=True,
                roles=True,
                everyone=False,
            ),
        )

        await interaction.response.send_message(
            f"✅ Ticket creato: {ticket_channel.mention}",
            ephemeral=True,
        )


class TicketControlView(discord.ui.View):
    def __init__(self, bot: commands.Bot, config: dict):
        super().__init__(timeout=None)
        self.bot = bot
        self.config = config

    @discord.ui.button(
        label="Chiudi ticket",
        emoji="🔒",
        style=discord.ButtonStyle.danger,
        custom_id="il_divano_close_ticket_v1",
    )
    async def close_ticket(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ):
        if (
            interaction.guild is None
            or not isinstance(interaction.channel, discord.TextChannel)
            or not isinstance(interaction.user, discord.Member)
        ):
            await interaction.response.send_message(
                "Questo pulsante funziona solo dentro un ticket.",
                ephemeral=True,
            )
            return

        owner_id = get_ticket_owner_id(interaction.channel)

        allowed = (
            interaction.user.id == owner_id
            or member_is_ticket_staff(interaction.user, self.config)
        )

        if not allowed:
            await interaction.response.send_message(
                "Non puoi chiudere questo ticket.",
                ephemeral=True,
            )
            return

        
        await interaction.response.defer(ephemeral=True)

        try:
            await interaction.channel.delete(
                reason=f"Ticket chiuso da {interaction.user}",
            )
        except discord.DiscordException:
            try:
                await interaction.followup.send(
                    "Non sono riuscito a chiudere il ticket.",
                    ephemeral=True,
                )
            except discord.DiscordException:
                pass



async def delete_old_ticket_panels(
    bot: commands.Bot,
    channel: discord.TextChannel,
):
    old_message_id = get_state("ticket_panel_message_id")

    if old_message_id:
        try:
            old_message = await channel.fetch_message(int(old_message_id))
            await old_message.delete()
        except (
            discord.NotFound,
            discord.Forbidden,
            discord.HTTPException,
            ValueError,
        ):
            pass

    try:
        async for message in channel.history(limit=150):
            if bot.user is None or message.author.id != bot.user.id:
                continue

            for embed in message.embeds:
                footer_text = embed.footer.text if embed.footer else ""

                if TICKET_PANEL_MARKER in footer_text:
                    try:
                        await message.delete()
                    except discord.DiscordException:
                        pass
                    break
    except discord.DiscordException:
        pass


async def refresh_ticket_panel(bot: commands.Bot, config: dict):
    channel_id = int(config.get("ticket_panel_channel_id", 0))

    if not channel_id:
        raise RuntimeError(
            "ticket_panel_channel_id non configurato in config.json."
        )

    channel = await resolve_channel(bot, channel_id)

    if not isinstance(channel, discord.TextChannel):
        raise RuntimeError(
            "ticket_panel_channel_id non punta a un canale testuale valido."
        )

    await delete_old_ticket_panels(bot, channel)

    message = await channel.send(
        embed=build_ticket_panel_embed(config),
        view=TicketPanelView(bot, config),
    )

    set_state("ticket_panel_message_id", str(message.id))


async def setup_ticket_system(bot: commands.Bot, config: dict):
    init_db()

    bot.add_view(TicketPanelView(bot, config))
    bot.add_view(TicketControlView(bot, config))
