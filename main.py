import json
import discord
from discord.ext import commands

from functions.candidature import (
    setup_candidature_system,
    refresh_application_panel,
)
from functions.ticket import (
    setup_ticket_system,
    refresh_ticket_panel,
)
from functions.clear import setup_clear_system


with open("config.json", "r", encoding="utf-8") as f:
    CONFIG = json.load(f)

TOKEN = CONFIG["token"]

intents = discord.Intents.default()
intents.members = True
intents.message_content = True


class IlDivanoBot(commands.Bot):
    def __init__(self):
        super().__init__(
            command_prefix="!",
            intents=intents,
            help_command=None,
        )

        # on_ready può scattare anche dopo una semplice riconnessione.
        # Vogliamo rigenerare i pannelli una sola volta per ogni avvio reale.
        self.startup_panels_refreshed = False

    async def setup_hook(self):
        # Registra subito tutte le view persistenti.
        await setup_candidature_system(self, CONFIG)
        await setup_ticket_system(self, CONFIG)
        await setup_clear_system(self)


bot = IlDivanoBot()


@bot.event
async def on_ready():
    print("=" * 58)
    print(f"Bot online come: {bot.user} ({bot.user.id})")
    print("Server: Il Divano")
    print("=" * 58)

    if bot.startup_panels_refreshed:
        return

    bot.startup_panels_refreshed = True

    try:
        await refresh_application_panel(bot, CONFIG)
        print("✓ Pannello candidature aggiornato automaticamente.")
    except Exception as exc:
        print(f"✗ Pannello candidature: {exc}")

    try:
        await refresh_ticket_panel(bot, CONFIG)
        print("✓ Pannello ticket aggiornato automaticamente.")
    except Exception as exc:
        print(f"✗ Pannello ticket: {exc}")


if not TOKEN or TOKEN == "INSERISCI_TOKEN_NUOVO":
    raise RuntimeError(
        "Inserisci il token Discord in config.json prima di avviare il bot."
    )

bot.run(TOKEN)
