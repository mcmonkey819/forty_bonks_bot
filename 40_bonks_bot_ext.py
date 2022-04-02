import sys
import nextcord
from nextcord.ext import commands
import sqlite3
from datetime import time
import config
import argparse
import logging
import asyncio

logging.basicConfig(level=logging.INFO)

parser = argparse.ArgumentParser(description='40 Bonks Discord Bot')
parser.add_argument('-test', '-t', action='store_true', help='Runs the bot in test mode')
args = parser.parse_args(sys.argv[1:])

bot_token = config.PRODUCTION_TOKEN
dbName = "AsyncRaceInfo.db"
test_mode = args.test == True or config.TEST_MODE
if test_mode:
    bot_token = config.MCMONKEY_TEST_TOKEN
    dbName = "testDbUtil.db"
dbConn = sqlite3.connect(dbName)
dbCursor = dbConn.cursor()
client = nextcord.Client()

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


intents = nextcord.Intents.all()
bot = Bot(intents=intents)
if test_mode:
    async_cog = bot.get_cog('AsyncRaceHandler')
    async_cog.setTestMode()
    server_utils_cog = bot.get_cog('ServerUtils')
    server_utils_cog.setTestMode()
bot.run(bot_token)
logging.info("HERE")
