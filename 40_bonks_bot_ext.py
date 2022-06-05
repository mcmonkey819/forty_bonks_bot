import sys
import nextcord
from nextcord.ext import commands
from datetime import time
import config
import bot_tokens
import argparse
import logging
import asyncio

logging.basicConfig(level=logging.INFO)

parser = argparse.ArgumentParser(description='40 Bonks Discord Bot')
parser.add_argument('-test', '-t', action='store_true', help='Runs the bot in test mode')
args = parser.parse_args(sys.argv[1:])

bot_token = bot_tokens.PRODUCTION_TOKEN
dbName = "AsyncRaceInfo.db"
test_mode = args.test == True or config.TEST_MODE
if test_mode:
    logging.info("Setting test mode for BOT")
    bot_token = bot_tokens.TEST_TOKEN

class Bot(commands.Bot):
    def __init__(self, **kwargs):
        super().__init__(command_prefix=commands.when_mentioned_or('$'), **kwargs)
        for cog in config.cogs:
            try:
                self.load_extension(cog)
            except Exception as exc:
                logging.error(f"Could not load extension {cog} due to {exc.__class__.__name__}: {exc}")

    async def on_ready(self):
        #await self.change_presence(status='invisible')
        logging.info('Logged on as {0} (ID: {0.id})'.format(self.user))

    async def close(self):
        await self.get_cog('AsyncRaceHandler').close()
        await super().close()


intents = nextcord.Intents.all()
intents.members = True
bot = Bot(intents=intents)
if test_mode:
    #async_cog = bot.get_cog('AsyncRaceHandler')
#    async_cog.setTestMode()
    server_utils_cog = bot.get_cog('ServerUtils')
    server_utils_cog.setTestMode()
bot.run(bot_token)
logging.info("HERE")
