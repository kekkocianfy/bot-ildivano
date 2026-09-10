import os
import sys
import json
import logging
from pathlib import Path

import discord
from discord.ext import commands


# ============================================================
# PERCORSI - IMPORTANTE PER RAILWAY
# ============================================================

# Cartella in cui si trova realmente main.py
BASE_DIR = Path(__file__).resolve().parent

# Aggiunge la root del progetto agli import Python.
# Serve anche per evitare problemi con Railway.
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))


# ============================================================
# IMPORT FUNZIONI
# ============================================================

try:
    from functions.candidature import (
        setup_candidature_system,
        refresh_application_panel,
    )

    from functions.ticket import (
        setup_ticket_system,
        refresh_ticket_panel,
    )

    from functions.clear import setup_clear_system

except ModuleNotFoundError as error:
    print("=" * 60)
    print("ERRORE IMPORT")
    print(error)
    print()
    print("Controlla che il repository abbia questa struttura:")
    print()
    print("main.py")
    print("config.json")
    print("requirements.txt")
    print("functions/")
    print("    __init__.py")
    print("    candidature.py")
    print("    ticket.py")
    print("    clear.py")
    print("=" * 60)

    raise


# ============================================================
# LOG
# ============================================================

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] %(name)s: %(message)s",
)

logger = logging.getLogger("IlDivano")


# ============================================================
# CONFIG.JSON
# ============================================================

CONFIG_PATH = BASE_DIR / "config.json"

if not CONFIG_PATH.exists():
    raise FileNotFoundError(
        f"config.json non trovato in: {CONFIG_PATH}"
    )

try:
    with CONFIG_PATH.open(
        "r",
        encoding="utf-8"
    ) as file:
        CONFIG = json.load(file)

except json.JSONDecodeError as error:
    raise RuntimeError(
        f"Errore nel config.json: {error}"
    )


# ============================================================
# RAILWAY VARIABLES
# ============================================================

# Su Railway:
#
# Variables -> DISCORD_TOKEN
#
# NON mettere il token direttamente nel codice.
TOKEN = os.getenv("DISCORD_TOKEN")


if not TOKEN:
    raise RuntimeError(
        "\n"
        "============================================================\n"
        "DISCORD_TOKEN NON TROVATO\n"
        "\n"
        "Vai su Railway -> Variables e crea:\n"
        "\n"
        "DISCORD_TOKEN = token_del_bot\n"
        "============================================================"
    )


# ============================================================
# INTENTS
# ============================================================

intents = discord.Intents.default()

# Necessario per lavorare correttamente con i membri
intents.members = True

# Necessario per !clear e altri comandi con !
intents.message_content = True


# ============================================================
# BOT
# ============================================================

class IlDivanoBot(commands.Bot):

    def __init__(self):

        super().__init__(
            command_prefix="!",
            intents=intents,
            help_command=None,
            case_insensitive=True,
        )

        # Evita che Discord ricrei i pannelli ogni volta
        # che il websocket si riconnette.
        self.startup_panels_refreshed = False


    async def setup_hook(self):

        logger.info("Caricamento sistemi...")

        # ====================================================
        # CANDIDATURE
        # ====================================================

        try:
            await setup_candidature_system(
                self,
                CONFIG
            )

            logger.info(
                "Sistema candidature caricato."
            )

        except Exception:
            logger.exception(
                "Errore caricamento sistema candidature."
            )

            raise


        # ====================================================
        # TICKET
        # ====================================================

        try:
            await setup_ticket_system(
                self,
                CONFIG
            )

            logger.info(
                "Sistema ticket caricato."
            )

        except Exception:
            logger.exception(
                "Errore caricamento sistema ticket."
            )

            raise


        # ====================================================
        # CLEAR
        # ====================================================

        try:
            await setup_clear_system(
                self
            )

            logger.info(
                "Comando !clear caricato."
            )

        except Exception:
            logger.exception(
                "Errore caricamento !clear."
            )

            raise


# ============================================================
# CREA BOT
# ============================================================

bot = IlDivanoBot()


# ============================================================
# BOT ONLINE
# ============================================================

@bot.event
async def on_ready():

    print()
    print("=" * 60)
    print("IL DIVANO BOT ONLINE")
    print("=" * 60)
    print(f"Nome: {bot.user}")
    print(f"ID Bot: {bot.user.id}")
    print(f"Discord.py: {discord.__version__}")
    print("Hosting: Railway")
    print("=" * 60)
    print()

    logger.info(
        "Connessione a Discord completata."
    )


    # ========================================================
    # EVITA DOPPIO REFRESH
    # ========================================================

    if bot.startup_panels_refreshed:

        logger.info(
            "Riconnessione Discord rilevata: "
            "i pannelli non vengono ricreati."
        )

        return


    bot.startup_panels_refreshed = True


    # ========================================================
    # PANNELLO CANDIDATURE
    # ========================================================

    try:

        await refresh_application_panel(
            bot,
            CONFIG
        )

        logger.info(
            "Pannello candidature aggiornato automaticamente."
        )

    except Exception:

        logger.exception(
            "Errore durante il refresh "
            "del pannello candidature."
        )


    # ========================================================
    # PANNELLO TICKET
    # ========================================================

    try:

        await refresh_ticket_panel(
            bot,
            CONFIG
        )

        logger.info(
            "Pannello ticket aggiornato automaticamente."
        )

    except Exception:

        logger.exception(
            "Errore durante il refresh "
            "del pannello ticket."
        )


# ============================================================
# ERRORI COMANDI
# ============================================================

@bot.event
async def on_command_error(
    ctx,
    error
):

    # Non risponde se qualcuno scrive un comando inesistente.
    if isinstance(
        error,
        commands.CommandNotFound
    ):
        return


    # Per !clear vogliamo evitare messaggi inutili nel canale.
    if ctx.command is not None:

        if ctx.command.name == "clear":
            logger.warning(
                f"Errore !clear: {error}"
            )

            return


    logger.error(
        f"Errore comando: {error}"
    )


# ============================================================
# ERRORI GENERALI
# ============================================================

@bot.event
async def on_error(
    event_method,
    *args,
    **kwargs
):

    logger.exception(
        f"Errore Discord nell'evento: {event_method}"
    )


# ============================================================
# AVVIO BOT
# ============================================================

def start_bot():

    print()
    print("=" * 60)
    print("AVVIO IL DIVANO BOT")
    print("Ambiente: Railway / Python")
    print("=" * 60)
    print()

    try:

        bot.run(
            TOKEN,
            log_handler=None
        )

    except discord.LoginFailure:

        logger.error(
            "TOKEN DISCORD NON VALIDO. "
            "Controlla DISCORD_TOKEN nelle Variables di Railway."
        )

        raise

    except Exception:

        logger.exception(
            "Il bot è crashato durante l'avvio."
        )

        raise


# ============================================================
# START
# ============================================================

if __name__ == "__main__":
    start_bot()
