import sqlite3
from datetime import datetime, timezone

import discord
from discord.ext import commands

from functions.ticket import send_interview_ticket_message


DB_PATH = "applications.db"
PANEL_MARKER = "Il Divano"


# ============================================================
# DATABASE
# ============================================================

def connect_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with connect_db() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS applications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                guild_id INTEGER NOT NULL,
                message_id INTEGER UNIQUE NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                reviewed_by INTEGER,
                created_at TEXT NOT NULL,
                reviewed_at TEXT
            )
            """
        )

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


def has_pending_application(user_id: int, guild_id: int) -> bool:
    with connect_db() as conn:
        row = conn.execute(
            """
            SELECT 1
            FROM applications
            WHERE user_id = ?
              AND guild_id = ?
              AND status = 'pending'
            LIMIT 1
            """,
            (user_id, guild_id),
        ).fetchone()

        return row is not None


def save_application(user_id: int, guild_id: int, message_id: int):
    with connect_db() as conn:
        conn.execute(
            """
            INSERT INTO applications
            (
                user_id,
                guild_id,
                message_id,
                status,
                created_at
            )
            VALUES (?, ?, ?, 'pending', ?)
            """,
            (
                user_id,
                guild_id,
                message_id,
                datetime.now(timezone.utc).isoformat(),
            ),
        )
        conn.commit()


def get_application(message_id: int):
    with connect_db() as conn:
        return conn.execute(
            """
            SELECT *
            FROM applications
            WHERE message_id = ?
            """,
            (message_id,),
        ).fetchone()


def close_application(message_id: int, status: str, reviewer_id: int) -> bool:
    """
    Fa l'UPDATE solo se la candidatura è ancora pending.
    Ritorna True soltanto se questa istanza ha effettivamente gestito il bando.
    """
    with connect_db() as conn:
        cursor = conn.execute(
            """
            UPDATE applications
            SET
                status = ?,
                reviewed_by = ?,
                reviewed_at = ?
            WHERE message_id = ?
              AND status = 'pending'
            """,
            (
                status,
                reviewer_id,
                datetime.now(timezone.utc).isoformat(),
                message_id,
            ),
        )
        conn.commit()
        return cursor.rowcount == 1


# ============================================================
# PANEL
# ============================================================

def build_panel_embed(config: dict) -> discord.Embed:
    server_name = config.get("server_name", "Il Divano")
    color_value = int(config.get("application_panel_color", 0xF1C40F))

    embed = discord.Embed(
        title="🌟・CANDIDATURE STAFF",
        description=(
            f"Vuoi entrare nello staff di **{server_name}**?\n"
            "Premi il pulsante qui sotto e compila il modulo con attenzione."
        ),
        color=discord.Color(color_value),
    )

    embed.add_field(
        name="📝 Nel modulo ti chiederemo",
        value=(
            "• Nome e cognome\n"
            "• Perché vuoi entrare nello staff\n"
            "• Cosa faresti per migliorare il server\n"
            "• I tuoi orari di disponibilità"
        ),
        inline=False,
    )

    embed.add_field(
        name="📩 Dopo l'invio",
        value=(
            "La candidatura verrà valutata dallo staff e riceverai l'esito direttamente in **DM**."
        ),
        inline=False,
    )

    embed.set_footer(text=f"By Kekko • {PANEL_MARKER}")

    return embed

async def resolve_channel(bot: commands.Bot, channel_id: int):
    channel = bot.get_channel(channel_id)
    if channel is not None:
        return channel

    try:
        return await bot.fetch_channel(channel_id)
    except discord.DiscordException:
        return None


async def delete_old_application_panels(
    bot: commands.Bot,
    channel: discord.TextChannel,
):
    # 1) Prova a cancellare il messaggio esatto salvato nel DB.
    old_message_id = get_state("application_panel_message_id")

    if old_message_id:
        try:
            old_message = await channel.fetch_message(int(old_message_id))
            await old_message.delete()
        except (discord.NotFound, discord.Forbidden, discord.HTTPException, ValueError):
            pass

    # 2) Recupero extra: elimina eventuali pannelli duplicati lasciati da crash
    #    o da un DB cancellato.
    try:
        async for message in channel.history(limit=100):
            if bot.user is None or message.author.id != bot.user.id:
                continue

            for embed in message.embeds:
                footer_text = embed.footer.text if embed.footer else ""
                if PANEL_MARKER in footer_text:
                    try:
                        await message.delete()
                    except discord.DiscordException:
                        pass
                    break
    except discord.DiscordException:
        pass


async def refresh_application_panel(bot: commands.Bot, config: dict):
    """
    Ad ogni AVVIO del bot:
    - elimina il pannello precedente;
    - pubblica un pannello nuovo;
    - salva l'ID del nuovo messaggio.

    Le candidature già inviate NON vengono eliminate e i loro
    pulsanti continuano a funzionare grazie alle persistent views.
    """
    panel_channel_id = int(config.get("panel_channel_id", 0))

    if not panel_channel_id:
        raise RuntimeError(
            "panel_channel_id non configurato in config.json."
        )

    channel = await resolve_channel(bot, panel_channel_id)

    if not isinstance(channel, discord.TextChannel):
        raise RuntimeError(
            "panel_channel_id non punta a un canale testuale valido."
        )

    await delete_old_application_panels(bot, channel)

    message = await channel.send(
        embed=build_panel_embed(config),
        view=ApplicationPanelView(bot, config),
    )

    set_state("application_panel_message_id", str(message.id))


# ============================================================
# APPLICATION MODAL
# ============================================================

class ApplicationModal(discord.ui.Modal, title="Candidatura Staff"):
    nome = discord.ui.TextInput(
        label="Nome e cognome",
        placeholder="Inserisci nome e cognome",
        max_length=100,
        required=True,
    )

    motivazione = discord.ui.TextInput(
        label="Perché vorresti entrare nello staff?",
        placeholder="Spiegaci perché vuoi entrare nello staff...",
        style=discord.TextStyle.paragraph,
        max_length=1000,
        required=True,
    )

    miglioramenti = discord.ui.TextInput(
        label="Cosa faresti per migliorare il server?",
        placeholder="Scrivi cosa miglioreresti nella community...",
        style=discord.TextStyle.paragraph,
        max_length=1000,
        required=True,
    )

    disponibilita = discord.ui.TextInput(
        label="Quando sei disponibile?",
        placeholder="Es. Lun-Ven 15:00-20:00",
        style=discord.TextStyle.paragraph,
        max_length=500,
        required=True,
    )

    def __init__(self, bot: commands.Bot, config: dict):
        super().__init__()
        self.bot = bot
        self.config = config

    async def on_submit(self, interaction: discord.Interaction):
        if interaction.guild is None:
            await interaction.response.send_message(
                "Le candidature possono essere inviate solo dal server.",
                ephemeral=True,
            )
            return

        if has_pending_application(interaction.user.id, interaction.guild.id):
            await interaction.response.send_message(
                "Hai già una candidatura in attesa di revisione.",
                ephemeral=True,
            )
            return

        applications_channel_id = int(
            self.config.get("applications_channel_id", 0)
        )

        channel = await resolve_channel(
            self.bot,
            applications_channel_id,
        )

        if not isinstance(channel, discord.TextChannel):
            await interaction.response.send_message(
                "Il canale candidature non è configurato correttamente.",
                ephemeral=True,
            )
            return

        embed = discord.Embed(
            title="📨 Nuova candidatura staff",
            description=f"Candidatura di {interaction.user.mention}",
            color=discord.Color.blurple(),
            timestamp=discord.utils.utcnow(),
        )

        embed.set_author(
            name=str(interaction.user),
            icon_url=interaction.user.display_avatar.url,
        )

        embed.add_field(
            name="👤 Nome e cognome",
            value=self.nome.value,
            inline=False,
        )

        embed.add_field(
            name="💬 Perché vuole entrare nello staff?",
            value=self.motivazione.value,
            inline=False,
        )

        embed.add_field(
            name="🛠️ Cosa farebbe per migliorare il server?",
            value=self.miglioramenti.value,
            inline=False,
        )

        embed.add_field(
            name="🕒 Disponibilità",
            value=self.disponibilita.value,
            inline=False,
        )

        embed.add_field(
            name="🔎 Account Discord",
            value=f"{interaction.user.mention}\n`{interaction.user.id}`",
            inline=False,
        )

        embed.set_footer(text="Stato: IN ATTESA")

        review_message = await channel.send(
            embed=embed,
            view=ReviewView(self.bot, self.config),
            allowed_mentions=discord.AllowedMentions.none(),
        )

        save_application(
            interaction.user.id,
            interaction.guild.id,
            review_message.id,
        )

        await interaction.response.send_message(
            "✅ Candidatura inviata correttamente.",
            ephemeral=True,
        )


# ============================================================
# PERSISTENT PUBLIC BUTTON
# ============================================================

class ApplicationPanelView(discord.ui.View):
    def __init__(self, bot: commands.Bot, config: dict):
        super().__init__(timeout=None)
        self.bot = bot
        self.config = config

    @discord.ui.button(
        label="Candidati ora",
        emoji="✨",
        style=discord.ButtonStyle.success,
        custom_id="il_divano_application_open_v1",
    )
    async def open_application(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ):
        if interaction.guild is None:
            await interaction.response.send_message(
                "Puoi candidarti solo dal server.",
                ephemeral=True,
            )
            return

        if has_pending_application(
            interaction.user.id,
            interaction.guild.id,
        ):
            await interaction.response.send_message(
                "Hai già una candidatura in attesa di revisione.",
                ephemeral=True,
            )
            return

        await interaction.response.send_modal(
            ApplicationModal(self.bot, self.config)
        )


# ============================================================
# PERSISTENT REVIEW BUTTONS
# ============================================================

class ReviewView(discord.ui.View):
    def __init__(self, bot: commands.Bot, config: dict):
        super().__init__(timeout=None)
        self.bot = bot
        self.config = config

    def reviewer_allowed(self, member: discord.Member) -> bool:
        if member.guild_permissions.administrator:
            return True

        reviewer_role_id = int(
            self.config.get("reviewer_role_id", 0)
        )

        return any(
            role.id == reviewer_role_id
            for role in member.roles
        )

    async def process(
        self,
        interaction: discord.Interaction,
        accepted: bool,
    ):
        if (
            interaction.guild is None
            or not isinstance(interaction.user, discord.Member)
        ):
            await interaction.response.send_message(
                "Azione non disponibile.",
                ephemeral=True,
            )
            return

        if not self.reviewer_allowed(interaction.user):
            await interaction.response.send_message(
                "Non hai il permesso di gestire le candidature.",
                ephemeral=True,
            )
            return

        if interaction.message is None:
            await interaction.response.send_message(
                "Candidatura non trovata.",
                ephemeral=True,
            )
            return

        application = get_application(interaction.message.id)

        if application is None:
            await interaction.response.send_message(
                "Questa candidatura non è presente nel database.",
                ephemeral=True,
            )
            return

        if application["status"] != "pending":
            await interaction.response.send_message(
                "Questa candidatura è già stata gestita.",
                ephemeral=True,
            )
            return

        await interaction.response.defer(ephemeral=True)

        status = "accepted" if accepted else "rejected"

        # UPDATE atomico: evita che due revisori gestiscano insieme lo stesso bando.
        if not close_application(
            interaction.message.id,
            status,
            interaction.user.id,
        ):
            await interaction.followup.send(
                "Questa candidatura è già stata gestita.",
                ephemeral=True,
            )
            return

        applicant = None

        try:
            applicant = await self.bot.fetch_user(
                int(application["user_id"])
            )
        except discord.DiscordException:
            pass

        dm_sent = False

        if applicant is not None:
            if accepted:
                # NESSUN RUOLO automatico.
                dm_sent = await send_interview_ticket_message(applicant)
            else:
                try:
                    await applicant.send(
                        "La tua candidatura staff su Il Divano è stata rifiutata."
                    )
                    dm_sent = True
                except discord.DiscordException:
                    dm_sent = False

        if interaction.message.embeds:
            embed = interaction.message.embeds[0].copy()
        else:
            embed = discord.Embed(title="Candidatura Staff")

        if accepted:
            embed.color = discord.Color.green()
            result_text = "✅ ACCETTATA"
        else:
            embed.color = discord.Color.red()
            result_text = "❌ RIFIUTATA"

        embed.set_footer(
            text=f"Stato: {result_text} • Gestita da {interaction.user}"
        )

        embed.add_field(
            name="📋 Esito",
            value=(
                f"{result_text}\n"
                f"**Revisore:** {interaction.user.mention}\n"
                f"**DM inviato:** {'Sì' if dm_sent else 'No'}"
            ),
            inline=False,
        )

        disabled = discord.ui.View(timeout=None)

        disabled.add_item(
            discord.ui.Button(
                label="Accetta",
                emoji="✅",
                style=discord.ButtonStyle.success,
                custom_id="il_divano_application_accept_v1",
                disabled=True,
            )
        )

        disabled.add_item(
            discord.ui.Button(
                label="Rifiuta",
                emoji="❌",
                style=discord.ButtonStyle.danger,
                custom_id="il_divano_application_reject_v1",
                disabled=True,
            )
        )

        try:
            await interaction.message.edit(
                embed=embed,
                view=disabled,
            )
        except discord.DiscordException:
            pass

        await interaction.followup.send(
            f"{result_text} — candidatura gestita.",
            ephemeral=True,
        )

    @discord.ui.button(
        label="Accetta",
        emoji="✅",
        style=discord.ButtonStyle.success,
        custom_id="il_divano_application_accept_v1",
    )
    async def accept(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ):
        await self.process(interaction, True)

    @discord.ui.button(
        label="Rifiuta",
        emoji="❌",
        style=discord.ButtonStyle.danger,
        custom_id="il_divano_application_reject_v1",
    )
    async def reject(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ):
        await self.process(interaction, False)


async def setup_candidature_system(
    bot: commands.Bot,
    config: dict,
):
    init_db()

    # Persistent Views.
    #
    # Essendo timeout=None + custom_id fisso, discord.py associa nuovamente
    # i pulsanti ai callback dopo ogni riavvio del bot.
    bot.add_view(
        ApplicationPanelView(bot, config)
    )

    bot.add_view(
        ReviewView(bot, config)
    )
