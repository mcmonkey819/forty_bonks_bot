import sys
import discord
from discord.ext import commands
import sqlite3
from datetime import time
import config
import argparse
import logging

logging.basicConfig(level=logging.INFO)

parser = argparse.ArgumentParser(description='40 Bonks Discord Bot')
parser.add_argument('-test', '-t', action='store_true', help='Runs the bot in test mode')
args = parser.parse_args(sys.argv[1:])

bot_token = config.PRODUCTION_TOKEN
test_mode = args.test == True or config.TEST_MODE
if test_mode:
    bot_token = config.MCMONKEY_TEST_TOKEN

dbName = "importTestDB.db"
dbConn = sqlite3.connect(dbName)
dbCursor = dbConn.cursor()
client = discord.Client()

class Bot(commands.Bot):
    def __init__(self, **kwargs):
        super().__init__(command_prefix=commands.when_mentioned_or('$'), **kwargs)
        for cog in config.cogs:
            try:
                self.load_extension(cog)
            except Exception as exc:
                logging.error('Could not load extension {0} due to {1.__class__.__name__}: {1}'.format(cog, exc))

    async def on_ready(self):
        await self.change_presence(status='invisible')
        logging.info('Logged on as {0} (ID: {0.id})'.format(self.user))


intents = discord.Intents.all()
bot = Bot(intents=intents)
if test_mode:
    async_cog = bot.get_cog('40 Bonks Bot Async Commands')
    async_cog.setTestMode()
bot.run(bot_token)
