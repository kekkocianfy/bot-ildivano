import os
import sys
import json
import logging
from pathlib import Path

import discord
from discord.ext import commands


BASE_DIR = Path(__file__).resolve().parent

if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))


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


logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] %(name)s: %(message)s",
)

logger = logging.getLogger("IlDivano")


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


intents = discord.Intents.default()
intents.members = True
intents.message_content = True


class IlDivanoBot(commands.Bot):

    def __init__(self):

        super().__init__(
            command_prefix="!",
            intents=intents,
            help_command=None,
            case_insensitive=True,
        )

        self.startup_panels_refreshed = False


    async def setup_hook(self):

        logger.info("Caricamento sistemi...")

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


bot = IlDivanoBot()


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


    if bot.startup_panels_refreshed:

        logger.info(
            "Riconnessione Discord rilevata: "
            "i pannelli non vengono ricreati."
        )

        return


    bot.startup_panels_refreshed = True


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


@bot.event
async def on_command_error(
    ctx,
    error
):

    if isinstance(
        error,
        commands.CommandNotFound
    ):
        return


    if ctx.command is not None:

        if ctx.command.name == "clear":
            logger.warning(
                f"Errore !clear: {error}"
            )

            return


    logger.error(
        f"Errore comando: {error}"
    )


@bot.event
async def on_error(
    event_method,
    *args,
    **kwargs
):

    logger.exception(
        f"Errore Discord nell'evento: {event_method}"
    )


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


if __name__ == "__main__":
    start_bot()
