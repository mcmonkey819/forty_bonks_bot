from discord.ext import commands
import discord
import logging
import asyncio
from datetime import datetime

# 40 Bonks Server Info
FORTY_BONKS_SERVER_ID = 485284146063736832
FORTY_BONKS_WEEKLY_SUBMIT_CHANNEL = 0
FORTY_BONKS_RACE_CREATOR_ROLE = 0
FORTY_BONKS_WEEKLY_RACER_ROLE = 732078040892440736
FORTY_BONKS_WEEKLY_LEADERBOARD_CHANNEL = 0

# Bot Testing Things Server Info
BTT_SERVER_ID = 853060981528723468
BTT_RACE_CREATOR_ROLE = 888940865337299004
BTT_WEEKLY_SUBMIT_CHANNEL = 892861800612249680
BTT_WEEKLY_RACER_ROLE = 895026847954374696
BTT_WEEKLY_LEADERBOARD_CHANNEL = 895681087701909574

PRODUCTION_DB = "AsyncRaceInfo.db"
TEST_DB = "testDbUtil.db"

class AsyncHandler(commands.Cog, name='40 Bonks Bot Server Utils'):
    '''Cog which handles commands related to Async Races.'''

    def __init__(self, bot):
        self.bot = bot
        self.test_mode = False
        self.server_id = FORTY_BONKS_SERVER_ID

########################################################################################################################
# Utility Functions
########################################################################################################################
    def setTestMode(self):
        self.test_mode = True
        self.server_id = BTT_SERVER_ID

    @commands.command()
    @commands.check(isRaceCreatorChannel)
    @commands.has_any_role(FORTY_BONKS_RACE_CREATOR_ROLE, BTT_RACE_CREATOR_ROLE)
    async def tidy_upcoming_races(self, ctx: commands.Context):
        ''' 
        Cleans up the #upcoming-races channel, removing all messages older than 24h
        '''
        logging.info('Executing $tidy_upcoming_races command')