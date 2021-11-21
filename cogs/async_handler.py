7# -*- coding: utf-8 -*-

from discord.ext import commands
import discord
import sqlite3
from sql_commands import *
import logging
from prettytable import PrettyTable, DEFAULT, ALL
import re
import asyncio
from datetime import datetime, date

# 40 Bonks Server Info
FORTY_BONKS_SERVER_ID = 485284146063736832
FORTY_BONKS_WEEKLY_SUBMIT_CHANNEL = 907626630816620624
FORTY_BONKS_RACE_CREATOR_COMMAND_CHANNEL = 907626794474156062
FORTY_BONKS_BOT_COMMAND_CHANNELS = [ 907627122732982363, FORTY_BONKS_RACE_CREATOR_COMMAND_CHANNEL ]
FORTY_BONKS_RACE_CREATOR_ROLE = 782804969107226644
FORTY_BONKS_WEEKLY_RACER_ROLE = 732078040892440736
FORTY_BONKS_WEEKLY_LEADERBOARD_CHANNEL = 747239559175208961

# Bot Testing Things Server Info
BTT_SERVER_ID = 853060981528723468
BTT_RACE_CREATOR_ROLE = 888940865337299004
BTT_WEEKLY_SUBMIT_CHANNEL = 892861800612249680
BTT_RACE_CREATOR_COMMAND_CHANNEL = 896494916493004880
BTT_BOT_COMMAND_CHANNELS = [ 853061634855665694, 854508026832748544, BTT_RACE_CREATOR_COMMAND_CHANNEL ]
BTT_WEEKLY_RACER_ROLE = 895026847954374696
BTT_WEEKLY_LEADERBOARD_CHANNEL = 895681087701909574

PRODUCTION_DB = "AsyncRaceInfo.db"
TEST_DB = "testDbUtil.db"

# Discord limit is 2000 characters, subtract a few to account for formatting, newlines, etc
DiscordApiCharLimit = 2000 - 10
DeleteAfterTime = 30
NextPageEmoji = '▶️'
PoopEmoji = '💩'
ToiletPaperEmoji = '🧻'
PendantPodEmoteStr = '<:laoPoD:809226000550199306>'
WeeklySubmitInstructions = '''
To submit a time for the weekly async enter the in-game time (IGT) in H:MM:SS format followed by the collection rate. The bot will prompt you to add additional information (e.g RTA, next mode suggestion, comment).
Example:
    > 1:23:45 167

To correct any information in a submission, simply submit it again.

To skip running the async but still get access to the weekly spoilers and leaderboard channels, simply type `ff`
'''

async def isWeeklySubmitChannel(ctx):
    if ctx.channel.id == FORTY_BONKS_WEEKLY_SUBMIT_CHANNEL or ctx.channel.id == BTT_WEEKLY_SUBMIT_CHANNEL:
        return True
    return False

async def isRaceCreatorCommandChannel(ctx):
    if ctx.channel.id == FORTY_BONKS_RACE_CREATOR_COMMAND_CHANNEL or ctx.channel.id == BTT_RACE_CREATOR_COMMAND_CHANNEL:
        return True
    return False

async def isBotCommandChannel(ctx):
    if ctx.channel.id in FORTY_BONKS_BOT_COMMAND_CHANNELS or ctx.channel.id in BTT_BOT_COMMAND_CHANNELS:
        return True
    return False

timeout_msg = "Timeout error. I don't have all day! You'll have to start over (and be quicker this time)"
class AsyncHandler(commands.Cog, name='40 Bonks Bot Async Commands'):
    '''Cog which handles commands related to Async Races.'''

    def __init__(self, bot):
        self.bot = bot
        self.test_mode = False
        self.db_connection = sqlite3.connect(PRODUCTION_DB)
        self.cursor = self.db_connection.cursor()
        self.weekly_category_id = 1
        self.pt = PrettyTable()
        self.resetPrettyTable()
        self.server_id = FORTY_BONKS_SERVER_ID
        self.race_creator_role_id = FORTY_BONKS_RACE_CREATOR_ROLE
        self.weekly_submit_channel_id = FORTY_BONKS_WEEKLY_SUBMIT_CHANNEL
        self.weekly_submit_author_list = []
        self.weekly_racer_role = FORTY_BONKS_WEEKLY_RACER_ROLE
        self.weekly_leaderboard_channel = FORTY_BONKS_WEEKLY_LEADERBOARD_CHANNEL
        self.replace_poop_with_tp = True

########################################################################################################################
# Utility Functions
########################################################################################################################
    def setTestMode(self):
        self.test_mode = True
        self.db_connection = sqlite3.connect(TEST_DB)
        self.cursor = self.db_connection.cursor()
        self.server_id = BTT_SERVER_ID
        self.race_creator_role_id = BTT_RACE_CREATOR_ROLE
        self.weekly_submit_channel_id = BTT_WEEKLY_SUBMIT_CHANNEL
        self.weekly_racer_role = BTT_WEEKLY_RACER_ROLE
        self.weekly_leaderboard_channel = BTT_WEEKLY_LEADERBOARD_CHANNEL

    def resetPrettyTable(self):
        self.pt.set_style(DEFAULT)
        self.pt.clear()

    def isRaceCreator(self, ctx):
        ret = False
        role = ctx.guild.get_role(self.race_creator_role_id)
        if role in ctx.author.roles:
            ret =  True
        return ret

    ####################################################################################################################
    # This function breaks a response into multiple messages that meet the Discord API character limit
    def buildResponseMessageList(self, message):
        message_list = []
        # If we're under the character limit, just send the message
        if len(message) <= DiscordApiCharLimit:
            message_list.append(message)
        else:
            # Otherwise we'll build a list of lines, then build messages from that list
            # until we hit the message limit.
            line_list = message.split("\n")
            if line_list is not None:
                curr_message = ""
                curr_message_len = 0

                for line in line_list:
                    # If adding this line would put us over the limit, add the current message to the list and start over
                    if curr_message_len + len(line) > DiscordApiCharLimit:
                        if curr_message == "":
                            logging.error("Something went wrong in buildResponseMessageList")
                            continue
                        message_list.append(curr_message)
                        curr_message = ""
                        curr_message_len = 0

                    # If this single line is > 2000 characters, break it into sentences.
                    if len(line) > DiscordApiCharLimit:
                        sentences = re.split('[.?!;]', line)
                        for s in sentences:
                            if curr_message_len + len(s) > charLimit:
                                if curr_message == "":
                                    logging.error("Something went wrong in buildmessage_listFromLines")
                                    continue
                                message_list.append(curr_message)
                                curr_message = ""
                                curr_message_len = 0
                            curr_message += s
                            curr_message_len += len(s)
                    else:
                        curr_message += line + "\n"
                        curr_message_len += len(line) + 1
                if curr_message != "":
                    message_list.append(curr_message)
        return message_list

    ####################################################################################################################
    # Returns a string containing which numeric place (e.g. 1st, 2nd, 3rd) a user came in a specific race
    def get_place(self, race_id, userid):
        place = 0
        self.cursor.execute(QueryRaceLeaderboardSql.format(race_id))
        leaderboard = self.cursor.fetchall()
        if len(leaderboard) > 0:
            for idx, result in enumerate(leaderboard):
                if result[ASYNC_SUBMISSIONS_USERID] == userid:
                    place = (idx+1)
        place_str = ""
        if place == 0:
            place_str = "Not Found"
        else:
            place_str += str(place)
            tens = 0
            while (tens + 10) < place:
                tens += 10
            ones_digit = place - tens
            if ones_digit == 1:
                if tens == 10:
                    place_str += "th"
                else:
                    place_str += "st"
            elif ones_digit == 2:
                if tens == 10:
                    place_str += "th"
                else:
                    place_str += "nd"
            elif ones_digit == 3:
                if tens == 10:
                    place_str += "th"
                else:
                    place_str += "rd"
            else:
                place_str += "th"

        return place_str

    ####################################################################################################################
    # Queries and returns race info from the database
    def queryRaceInfo(self, race_id):
        # Query race info
        race_info_sql = QueryRaceInfoSql.format(race_id)
        self.cursor.execute(race_info_sql)
        return self.cursor.fetchone()

    ####################################################################################################################
    # Determines if an IGT or RTA time string is in the proper H:MM:SS format
    def game_time_is_valid(self, time_str):
        valid_time_str = False
        parts = time_str.split(':')
        # Hours can be left off for short seeds
        if len(parts) >= 2 and len(parts) <= 3:
            hours = 0
            minutes = -1
            seconds = -1
            try:
                seconds = int(parts[-1])
                minutes = int(parts[-2])
                hours = 0
                if len(parts) == 3:
                    hours = int(parts[0])
            except ValueError:
                valid_time_str = False
            if hours >= 0 and hours <= 24 and minutes >= 0 and minutes <= 59 and seconds >= 0 and seconds <= 59:
               valid_time_str = True
        return valid_time_str

    ####################################################################################################################
    # Asks the user a follow up question, returns the reply
    async def ask(self, ctx, question, checkFunc):
        await ctx.send(question)

        msg = None
        try:
            raw_msg = await self.bot.wait_for('message', timeout=60, check=checkFunc)
            msg = raw_msg.content
        except asyncio.TimeoutError:
            await ctx.send(timeout_msg, delete_after=DeleteAfterTime)

        return msg

    ####################################################################################################################
    # Asks the user for an RTA time
    async def get_rta(self, ctx):
        def checkRta(message):
            return message.author == ctx.author and self.game_time_is_valid(message.content)

        rta_question = "What is the RTA time? Enter in H:MM:SS format"
        question_msg = await ctx.send(rta_question)

        rta = None
        try:
            raw_msg = await self.bot.wait_for('message', timeout=60, check=checkRta)
            rta = raw_msg.content
            # Fix RTA with missing zero in hour place
            if len(rta.split(':')) == 2:
                rta = "0:" + rta
            await question_msg.delete()
            await raw_msg.delete()
        except asyncio.TimeoutError:
            await ctx.send(timeout_msg, delete_after=DeleteAfterTime)
        return rta

    ####################################################################################################################
    # Asks the user for a next mode suggestion
    async def get_mode(self, ctx):
        def check(message):
            return message.author == ctx.author

        question = "What is your suggestion for next mode?"
        question_msg = await ctx.send(question)

        mode = None
        try:
            raw_msg = await self.bot.wait_for('message', timeout=60, check=check)
            mode = raw_msg.content
            await question_msg.delete()
            await raw_msg.delete()
        except asyncio.TimeoutError:
            await ctx.send(timeout_msg, delete_after=DeleteAfterTime)
        return mode

    ####################################################################################################################
    # Asks the user for a comment
    async def get_comment(self, ctx):
        def check(message):
            return message.author == ctx.author

        question = "What's the comment?"
        question_msg = await ctx.send(question)

        comment = None
        try:
            raw_msg = await self.bot.wait_for('message', timeout=60, check=check)
            comment = raw_msg.content
            await question_msg.delete()
            await raw_msg.delete()
        except asyncio.TimeoutError:
            await ctx.send(timeout_msg, delete_after=DeleteAfterTime)
        return comment

    ####################################################################################################################
    # Assigns the weekly async racer role, which unlocks access to the spoiler channel
    async def assignWeeklyAsyncRole(self, ctx):
        role = discord.utils.get(ctx.guild.roles, id=self.weekly_racer_role)
        await ctx.author.add_roles(role)

    ####################################################################################################################
    # Removes the weekly async racer role from all users in the server
    async def removeWeeklyAsyncRole(self, ctx):
        role = discord.utils.get(ctx.guild.roles, id=self.weekly_racer_role)
        for m in ctx.guild.members:
            await m.remove_roles(role)

    ####################################################################################################################
    # Queries the most recent weekly async race ID
    def queryLatestRaceId(self):
        latest_race_sql = QueryMostRecentFromCategorySql.format(self.weekly_category_id, 0)
        self.cursor.execute(latest_race_sql)
        return self.cursor.fetchone()[ASYNC_RACES_ID]

    ####################################################################################################################
    # Builds the leaderboard message list for a specific race ID
    def buildLeaderboardMessageList(self, race_id):
        # Query race info
        raceInfo = self.queryRaceInfo(race_id)

        self.cursor.execute(QueryRaceLeaderboardSql.format(race_id))
        race_submissions = self.cursor.fetchall()

        leaderboardStr = ""
        if len(race_submissions) == 0:
            leaderboard_str = "No results yet for race {} which started on {}".format(race_id, raceInfo[ASYNC_RACES_START])
        else:
            leaderboard_str = "Leaderboard for race {} which started on {}".format(race_id, raceInfo[ASYNC_RACES_START])
            if raceInfo is not None:
                leaderboard_str += "\n    **Mode: {}**".format(raceInfo[ASYNC_RACES_DESC])
            leaderboard_str += "\n"
            self.resetPrettyTable()
            self.pt.field_names = ["#", "Name", "IGT", "RTA", "CR"]
            for idx, submission in enumerate(race_submissions):
                self.pt.add_row([idx+1, 
                            submission[ASYNC_SUBMISSIONS_USERNAME],
                            submission[ASYNC_SUBMISSIONS_IGT],
                            submission[ASYNC_SUBMISSIONS_RTA],
                            submission[ASYNC_SUBMISSIONS_COLLECTION]])

        message_list = self.buildResponseMessageList(leaderboard_str)
        table_message_list = []
        if len(race_submissions) > 0:
            table_message_list = self.buildResponseMessageList(self.pt.get_string())
            for idx, msg in enumerate(table_message_list):
                table_message_list[idx] = "`{}`".format(msg)
        return message_list + table_message_list

    ####################################################################################################################
    # Updates the weekly leaderboard message
    async def updateLeaderboardMessage(self, race_id, ctx):
        # Remove all messages from the leaderboard channel
        leaderboard_channel = ctx.guild.get_channel(self.weekly_leaderboard_channel)
        await leaderboard_channel.purge()

        # Then build and post the latest leaderboard
        message_list = self.buildLeaderboardMessageList(race_id)
        for msg in message_list:
            await leaderboard_channel.send(msg)

    ####################################################################################################################
    # Adds a forward arrow reaction to a message and returns True if the user clicks it before the timeout (30s)
    async def userReactNextPage(self, ctx, message):
        await message.add_reaction(NextPageEmoji)
        def checkNextPage(reaction, user):
            return user == ctx.author and str(reaction.emoji) == NextPageEmoji and reaction.message == message

        bot_member = self.bot.get_user(self.bot.user.id)
        try:
            reaction, user = await self.bot.wait_for('reaction_add', timeout=30, check=checkNextPage)
            await message.remove_reaction(NextPageEmoji, bot_member)
            return True
        except asyncio.TimeoutError:
            logging.info("Next page reaction timeout")
            await message.remove_reaction(NextPageEmoji, bot_member)
            return False

    ####################################################################################################################
    # Updates the current mode message in the weekly submit channel
    async def updateWeeklyModeMessage(self, race_info):
        weekly_submit_channel = self.bot.get_channel(self.weekly_submit_channel_id)
        message_list = await weekly_submit_channel.history(limit=200).flatten()
        for message in message_list:
            if message.author.id == self.bot.user.id:
                await message.delete()
        full_msg = WeeklySubmitInstructions + "\n\nThe mode for the current async is: **{}**".format(race_info[ASYNC_RACES_DESC])
        if race_info[ASYNC_RACES_ADDL_INSTRUCTIONS] is not None:
            full_msg += "\nAdditional Info: {}".format(race_info[ASYNC_RACES_ADDL_INSTRUCTIONS])
        await weekly_submit_channel.send(full_msg)
        seed_embed = discord.Embed(title="{}".format(race_info[ASYNC_RACES_DESC]), url=race_info[ASYNC_RACES_SEED], color=discord.Colour.random())
        seed_embed.set_thumbnail(url="https://alttpr.com/i/logo_h.png")
        await weekly_submit_channel.send(embed=seed_embed)

    ####################################################################################################################
    # Fetches a users display name
    async def getDisplayName(self, guild, user_id):
        member = await guild.get_member(user_id)
        return member.display_name

    ####################################################################################################################
    # Checks if the provided member is in the asyc_racers table, adds them if not
    def checkAddMember(self, member):
        member_info = self.cursor.execute(QueryRacerDataSql.format(member.id)).fetchone()
        if member_info is None:
            self.cursor.execute(AddRacerSql.format(member.id, member.name))

    ####################################################################################################################
    # Checks if the provided emoji is a poop emoji....  sigh...
    def isPoopEmoji(self, emoji):
        if str(emoji) == PoopEmoji:
            return True
        else:
            return False

    ####################################################################################################################
    # Displays race submissions for the given user_id
    async def show_races(self, ctx, start, user_id):
        # SQL is funny, providing an offset of 10 will show results 11 and later. This is counter intuitive so this command expresses it as a starting point
        # instead. So our offset is simply (start - 1)
        offset = (start - 1)
        race_data_sql = QueryRecentUserSubmissionsSql.format(user_id, offset)
        self.cursor.execute(race_data_sql)
        query_results = self.cursor.fetchall()

        if len(query_results) > 0:
            self.resetPrettyTable()
            self.pt.hrules = True
            self.pt.field_names = ["Date", "Place", "IGT", "Collection Rate", "RTA", "Mode", "Race ID", "Submission ID"]
            self.pt._max_width = {"Mode": 50}
            for result in query_results:
                # First find info about the race this submission is for
                race_id = result[ASYNC_SUBMISSIONS_RACE_ID]
                self.cursor.execute(QueryRaceInfoSql.format(race_id))
                race_info    = self.cursor.fetchone()
                date        = result[ASYNC_SUBMISSIONS_SUBMIT_DATE]
                mode        = race_info[ASYNC_RACES_DESC]
                igt         = result[ASYNC_SUBMISSIONS_IGT]
                cr          = result[ASYNC_SUBMISSIONS_COLLECTION]
                rta         = result[ASYNC_SUBMISSIONS_RTA]
                submit_id   = result[ASYNC_SUBMISSIONS_ID]
                place       = self.get_place(race_id, user_id)

                if rta is None: rta = ""
                self.pt.add_row([date, place, igt, cr, rta, mode, race_id, submit_id])

            self.cursor.execute(QueryUserSubmissionsSql.format(user_id))
            total_submissions = self.cursor.fetchone()[0]
            response_str = "Recent Async Submissions {} - {} (out of {}):\n".format(start, min((start+4), total_submissions), total_submissions)
            message_list = self.buildResponseMessageList(response_str)
            table_message_list = self.buildResponseMessageList(self.pt.get_string())
            for message in message_list:
                await ctx.send(message)
            message = None
            for table_message in table_message_list:
                message = await ctx.send("`{}`".format(table_message))

            if message is not None:
                if await self.userReactNextPage(ctx, message):
                    await self.my_races(ctx, start+5)
        else:
            await ctx.send("There are no async submissions in that range")

########################################################################################################################
# DASH
########################################################################################################################
    @commands.command(name="dash")
    @commands.check(isBotCommandChannel)
    async def dash(self, ctx: commands.Context):
        ''' Go ahead, see what happens when you try to go fast'''
        logging.info('Executing $dash command')
        self.checkAddMember(ctx.author)
        await ctx.send('!!! BONK !!!!')

########################################################################################################################
# MY_RACES
########################################################################################################################
    @commands.command()
    @commands.check(isBotCommandChannel)
    async def my_races(self, ctx: commands.Context, start: int=1):
        ''' 
        Displays your most recent async race submissions.

            Optional Parameters:
                start - By default the command will show the 5 most recent submissions. To view older race submissions provide a starting point.
                        For example the command `$my_races 11` would show your 11th-15th most recent races.
        '''
        logging.info('Executing $my_races command')
        self.checkAddMember(ctx.author)
        user_id = ctx.author.id
        await self.show_races(ctx, start, user_id)

########################################################################################################################
# LEADERBOARD
########################################################################################################################
    @commands.command()
    @commands.check(isBotCommandChannel)
    async def leaderboard(self, ctx: commands.Context, race_id: int):
        ''' 
        Displays the leaderboard for an async race

            Parameters:
                race_id - race ID of the race you'd like to see. Use `$races` command to view the list of races and IDs
        '''
        logging.info('Executing $leaderboard command')
        self.checkAddMember(ctx.author)

        # Query the race_id of the most recent weekly race
        latest_race_id = self.queryLatestRaceId()

        # We want to direct users to the leaderboard channel for the current async
        if int(race_id) == latest_race_id:
            await ctx.send("To view the current async leaderboard submit a time or FF in the weekly submit channel and the leaderboard channel will become visible")
            return

        message_list = self.buildLeaderboardMessageList(race_id)

        for message in message_list:
            await ctx.send(message)

########################################################################################################################
# RACES
########################################################################################################################
    @commands.command()
    @commands.check(isBotCommandChannel)
    async def races(self, ctx: commands.Context, start: int=1):
        ''' 
        Displays the list of async race, sorted by most recent

            Optional Parameters:
                start - By default the command will show the 5 most recent races. To view older races provide a starting point.
                        For example the command `$races 11` would show the 11th-15th most recent races.
        '''
        logging.info('Executing $races command')
        self.checkAddMember(ctx.author)
        # SQL is funny, providing an offset of 10 will show results 11 and later. This is counter intuitive so this command expresses it as a starting point
        # instead. So our offset is simply (start - 1)
        offset = (start - 1)
        race_ids_sql = ""
        is_race_creator_channel = await isRaceCreatorCommandChannel(ctx)
        if is_race_creator_channel:
            race_ids_sql = QueryMostRecentFromCategorySql.format(self.weekly_category_id, offset)
        else:
            race_ids_sql = QueryMostRecentActiveFromCategorySql.format(self.weekly_category_id, offset)
        self.cursor.execute(race_ids_sql)
        race_ids_results = self.cursor.fetchall()
        if len(race_ids_results) > 0:
            self.resetPrettyTable()
            
            if is_race_creator_channel:
                self.pt.field_names = ["ID", "Start Date", "Mode", "Active"]
            else:
                self.pt.field_names = ["ID", "Start Date", "Mode"]
            self.pt._max_width = {"Mode": 50}
            self.pt.align["Mode"] = "l"
            for race in race_ids_results:
                if is_race_creator_channel:
                    active_str = "Yes" if race[ASYNC_RACES_ACTIVE] == 1 else "No"
                    self.pt.add_row([race[ASYNC_RACES_ID], race[ASYNC_RACES_START], race[ASYNC_RACES_DESC], active_str])
                else:
                    self.pt.add_row([race[ASYNC_RACES_ID], race[ASYNC_RACES_START], race[ASYNC_RACES_DESC]])
            table_message_list = self.buildResponseMessageList(self.pt.get_string())
            message = None
            for table_message in table_message_list:
                message = await ctx.send("`{}`".format(table_message))
            if message is not None:
                if await self.userReactNextPage(ctx, message):
                    await self.races(ctx, start+5)

        else:
            await ctx.send("No races found in that range")

########################################################################################################################
# RACE_INFO
########################################################################################################################
    @commands.command()
    @commands.check(isBotCommandChannel)
    async def race_info(self, ctx: commands.Context, race_id: int):
        ''' 
        Displays full race information for an async race

            Parameters:
                race_id - The race_id of the race you'd like info for. Use `$races` command to view the list of races and IDs.
        '''
        logging.info('Executing $race_info command')
        self.checkAddMember(ctx.author)
        race_info = self.queryRaceInfo(race_id)
        is_race_creator_channel = await isRaceCreatorCommandChannel(ctx)
        if race_info is not None:
            self.resetPrettyTable()
            self.pt.header = False
            self.pt.hrules = ALL
            self.pt.align["Value"] = "l"
            self.pt.field_names = ["Label", "Value"]
            self.pt.add_row(["Race Id", race_info[ASYNC_RACES_ID]])
            if is_race_creator_channel:
                self.pt.add_row(["Is Active", "Yes" if race_info[ASYNC_RACES_ACTIVE] else "No"])
            self.pt.add_row(["Start Date", race_info[ASYNC_RACES_START]])
            self.pt.add_row(["Seed", race_info[ASYNC_RACES_SEED]])
            self.pt.add_row(["Mode", race_info[ASYNC_RACES_DESC]])
            if race_info[ASYNC_RACES_ADDL_INSTRUCTIONS] is not None:
                self.pt.add_row(["Add'l Info", race_info[ASYNC_RACES_ADDL_INSTRUCTIONS]])
            table_message_list = self.buildResponseMessageList(self.pt.get_string())
            for table_message in table_message_list:
                await ctx.send("`{}`".format(table_message))
            seed_embed = discord.Embed(title="{}".format(race_info[ASYNC_RACES_DESC]), url=race_info[ASYNC_RACES_SEED], color=discord.Colour.random())
            seed_embed.set_thumbnail(url="https://alttpr.com/i/logo_h.png")
            await ctx.send(embed=seed_embed)
        else:
            await ctx.send("Race ID was not found")

########################################################################################################################
# SUBMIT_TIME
########################################################################################################################
    @commands.command(hidden=True)
    @commands.check(isWeeklySubmitChannel)
    async def submit_time(self, ctx: commands.Context, race_id: int, igt, collection_rate: int):
        ''' 
        Submits a time for an async race.

            Parameters:
                race_id         - The race_id of the race submitting to.
                igt             - Final in-game time in H:MM:SS format
                collection_rate - In-game collection rate
        '''
        logging.info('Executing $submit_time command')
        self.checkAddMember(ctx.author)
        await ctx.message.delete()

        # Check to see if there's already a submission for this race from this user
        is_update = False
        self.cursor.execute(QueryUserRaceSubmissions.format(race_id, ctx.author.id))
        existing_submission = self.cursor.fetchone()
        if existing_submission is not None:
            def checkYesNo(message):
                ret = False
                if message.author == ctx.author:
                    msg = message.content.lower()
                    if msg == "yes" or msg == "no":
                        ret = True
                return ret
            question = await ctx.send("You already have submitted a time for this race, do you want to replace it with this time? Reply yes or no")
            try:
                raw_msg = await self.bot.wait_for('message', timeout=60, check=checkYesNo)
                user_choice_msg = raw_msg.content
                await question.delete()
                await raw_msg.delete()
                if user_choice_msg.lower() == "yes":
                    is_update = True
                else:
                    await ctx.send("Submission cancelled", delete_after=DeleteAfterTime)
                    return
            except asyncio.TimeoutError:
                await ctx.send(timeout_msg, delete_after=DeleteAfterTime)
                await ctx.send("Submission cancelled", delete_after=DeleteAfterTime)
                return

        parse_error = not self.game_time_is_valid(igt)
        cr_int = 0
        try:
            cr_int = int(collection_rate)
        except ValueError:
            parse_error = True

        # Fix IGT with missing zero in hour place
        if len(igt.split(':')) == 2:
            igt = "0:" + igt

        if parse_error:
            await ctx.send("IGT or CR is in the wrong format, evaluate your life choices and try again", delete_after=DeleteAfterTime)
        else:
            # Verify the race exists and is active
            race_info = self.queryRaceInfo(race_id)
            if race_info is None or race_info[ASYNC_RACES_ACTIVE] == 0:
                await ctx.send("{} is not a valid race to submit to".format(race_id), delete_after=DeleteAfterTime)
            else:
                def checkChoice(message):
                    ret = False
                    if message.author == ctx.author:
                        if len(message.content) == 1:
                            value = int(message.content)
                            if value >= 1 and value <= 6:
                                ret = True
                    return ret

                user_choice = 0
                rta = None
                mode = None
                comment = None
                user_choice = 0
                # Loop asking the user for additional info
                while user_choice != 4:
                    question = "Do you want to add any additional info:\n  1 - RTA\n  2 - Next Mode Suggestion\n  3 - Comment\n  4 - I'm done"
                    question = await ctx.send(question)
                    user_choice_msg = None
                    try:
                        raw_msg = await self.bot.wait_for('message', timeout=60, check=checkChoice)
                        user_choice_msg = raw_msg.content
                        await raw_msg.delete()
                    except asyncio.TimeoutError:
                        await ctx.send(timeout_msg, delete_after=DeleteAfterTime)

                    await question.delete()

                    if user_choice_msg is None: return

                    # Get the additional info
                    user_choice = int(user_choice_msg)
                    if user_choice == 1:
                        rta = await self.get_rta(ctx)
                    elif user_choice == 2:
                        mode = await self.get_mode(ctx)
                    elif user_choice == 3:
                        comment = await self.get_comment(ctx)

                submit_time = datetime.now().isoformat(timespec='minutes').replace('T', ' ')
                submission_sql = ""
                # If we're updating an existing time, we need to use different SQL
                if is_update:
                    if rta is None: rta = existing_submission[ASYNC_SUBMISSIONS_RTA]
                    if mode is None: mode = existing_submission[ASYNC_SUBMISSIONS_NEXT_MODE]
                    if comment is None: comment = existing_submission[ASYNC_SUBMISSIONS_COMMENT]
                    submission_sql = UpdateAsyncSubmissionSql.format(submit_time, rta, igt, cr_int, mode, comment, existing_submission[ASYNC_SUBMISSIONS_ID])
                else:
                    submission_sql = AddAsyncSubmissionSql.format(submit_time, race_id, ctx.author.id, ctx.author.name, rta, igt, cr_int, mode, comment)
                self.cursor.execute(submission_sql)
                self.db_connection.commit()

                await ctx.send("Time submitted for {}".format(ctx.author.name), delete_after=DeleteAfterTime)
                # And remove them from the submit author list so on_message will start listening to them again
                if ctx.author.id in self.weekly_submit_author_list:
                    self.weekly_submit_author_list.remove(ctx.author.id)

                # Finally update the leaderboard if this is for the current weekly async
                if race_id == self.queryLatestRaceId():
                    await self.updateLeaderboardMessage(race_id, ctx)

########################################################################################################################
########################################################################################################################
######################    RACE CREATOR COMMANDS    #####################################################################
########################################################################################################################
########################################################################################################################


########################################################################################################################
# ADD_RACE
########################################################################################################################
    @commands.command()
    @commands.check(isRaceCreatorCommandChannel)
    @commands.has_any_role(FORTY_BONKS_RACE_CREATOR_ROLE, BTT_RACE_CREATOR_ROLE)
    async def add_race(self, ctx: commands.Context, seed):
        ''' 
        Adds a new async race
    
            Parameters:
                seed - link to the seed or patch file for the race
        '''
        logging.info('Executing $add_race command')
        def checkSameAuthor(message):
            return message.author == ctx.author

        mode = await self.ask(ctx, "What's the mode? (limited to 50 characters)", checkSameAuthor)
        if mode is None: return

        mode = mode[:50]

        msg = await self.ask(ctx, "Is there any additional info? Reply with 'No' or the info text", checkSameAuthor)
        if msg is None: return

        instructions = "NULL" 
        if msg.lower() != "no":
            # Need to quote the message
            instructions = '"{}"'.format(msg)

        # Add the race with the provided info. Currently all are set to the weekly category and inactive
        add_race_sql = AddAsyncRaceSql.format(seed, mode, instructions, self.weekly_category_id, 0)
        self.cursor.execute(add_race_sql)
        race_id = self.cursor.lastrowid
        await ctx.send("Added race ID: {}".format(race_id))
        self.db_connection.commit()

########################################################################################################################
# EDIT_RACE
########################################################################################################################
    @commands.command()
    @commands.check(isRaceCreatorCommandChannel)
    @commands.has_any_role(FORTY_BONKS_RACE_CREATOR_ROLE, BTT_RACE_CREATOR_ROLE)
    async def edit_race(self, ctx: commands.Context, race_id: int):
        ''' 
        Edits an async race with the given race_id
    
            Required Parameters:
                race_id - ID of the race being edited.
        '''
        logging.info('Executing $edit_race command')
        race_info = self.queryRaceInfo(race_id)
        race_info_map = AddAsyncRaceArgMap
        race_info_map[AsyncRacesColNames[ASYNC_RACES_ID]]                = race_info[ASYNC_RACES_ID]
        race_info_map[AsyncRacesColNames[ASYNC_RACES_START]]             = race_info[ASYNC_RACES_START]
        race_info_map[AsyncRacesColNames[ASYNC_RACES_SEED]]              = race_info[ASYNC_RACES_SEED]
        race_info_map[AsyncRacesColNames[ASYNC_RACES_DESC]]              = race_info[ASYNC_RACES_DESC]
        race_info_map[AsyncRacesColNames[ASYNC_RACES_ADDL_INSTRUCTIONS]] = race_info[ASYNC_RACES_ADDL_INSTRUCTIONS]
        race_info_map[AsyncRacesColNames[ASYNC_RACES_CATEGORY_ID]]       = race_info[ASYNC_RACES_CATEGORY_ID]
        race_info_map[AsyncRacesColNames[ASYNC_RACES_ACTIVE]]            = race_info[ASYNC_RACES_ACTIVE]

        def checkChoice(message):
            ret = False
            if message.author == ctx.author:
                if len(message.content) == 1:
                    value = int(message.content)
                    if value >= 1 and value <= 4:
                        ret = True
            return ret

        def checkSameAuthor(message):
            return message.author == ctx.author

        edit_choice = 0
        is_updated = False
        while edit_choice != 4:
            edit_question = "What do you want to edit:\n  1 - Seed Link\n  2 - Mode\n  3 - Additional Info\n  4 - I'm done"
            edit_choice_msg = await self.ask(ctx, edit_question, checkChoice)
            if edit_choice_msg is None: return
            edit_choice = int(edit_choice_msg)
            if edit_choice != 4:
                edit_choice_map = { 1: AsyncRacesColNames[ASYNC_RACES_SEED],
                                    2: AsyncRacesColNames[ASYNC_RACES_DESC],
                                    3: AsyncRacesColNames[ASYNC_RACES_ADDL_INSTRUCTIONS] }
                new_value_question = "Current value is \n`{}`\nWhat's the new value?".format(race_info_map[edit_choice_map[edit_choice]])
                value_msg = await self.ask(ctx, new_value_question, checkSameAuthor)
                if value_msg is None: return
                race_info_map[edit_choice_map[edit_choice]] = value_msg
                is_updated = True

        if is_updated:
            update_sql = UpdateRaceSql.format(
                race_info_map[AsyncRacesColNames[ASYNC_RACES_SEED]],
                race_info_map[AsyncRacesColNames[ASYNC_RACES_DESC]],
                race_info_map[AsyncRacesColNames[ASYNC_RACES_ADDL_INSTRUCTIONS]],
                race_id)
            self.cursor.execute(update_sql)
            self.db_connection.commit()
            await ctx.send("Updated race {}".format(race_id))
        else:
            await ctx.send("No updates applied")

########################################################################################################################
# START_RACE
########################################################################################################################
    @commands.command()
    @commands.check(isRaceCreatorCommandChannel)
    @commands.has_any_role(FORTY_BONKS_RACE_CREATOR_ROLE, BTT_RACE_CREATOR_ROLE)
    async def start_race(self, ctx: commands.Context, race_id: int):
        ''' 
        Starts an async race with the given race_id, making it active and avaiable for submissions
    
            Required Parameters:
                race_id - ID of the race being started.
        '''
        logging.info('Executing $start_race command')
        race_info = self.queryRaceInfo(race_id)
        if race_info[ASYNC_RACES_ACTIVE] == 1:
            await ctx.send("Race ID {} was already started on {}".format(race_id, race_info[ASYNC_RACES_START]))
            await self.updateWeeklyModeMessage(race_info)
        else:
            start_date = date.today().isoformat()
            logging.info("Start Date: {}".format(start_date))
            start_race_sql = StartRaceSql.format(start_date, race_id)
            self.cursor.execute(start_race_sql)
            self.db_connection.commit()
            await ctx.send("Started race {}".format(race_id))
            if race_info[ASYNC_RACES_CATEGORY_ID] == self.weekly_category_id:
                await self.updateWeeklyModeMessage(race_info)
                await self.removeWeeklyAsyncRole(ctx)

########################################################################################################################
# REMOVE_RACE
########################################################################################################################
    @commands.command()
    @commands.check(isRaceCreatorCommandChannel)
    @commands.has_any_role(FORTY_BONKS_RACE_CREATOR_ROLE, BTT_RACE_CREATOR_ROLE)
    async def remove_race(self, ctx: commands.Context, race_id: int):
        ''' 
        Removes an async race with the given race_id

            Required Parameters:
                race_id - ID of the race being removed.
        '''
        def checkYesNo(message):
            ret = False
            if message.author == ctx.author:
                msg = message.content.lower()
                if msg == "yes" or msg == "no":
                    ret = True
            return ret
            
        logging.info('Executing $remove_race command')
        race_info = self.queryRaceInfo(race_id)
        self.cursor.execute(QueryRaceLeaderboardSql.format(race_id))
        if self.cursor.fetchone() is not None:
            await ctx.send("This race has user submissions and cannot be removed via command, please contact the bot overlord to remove it.")
        else:
            race_info = self.queryRaceInfo(race_id)
            if race_info is None:
                ctx.send("Race ID {} does not exist", race_id, delete_after=DeleteAfterTime)
                return

            await ctx.send("Removing race {}".format(race_id))
            await self.race_info(ctx, race_id)
            confirm_question = "Are you sure you want to remove this race? This cannot be undone. Reply Yes or No"
            msg = await self.ask(ctx, confirm_question, checkYesNo)
            if msg is None: return
            if msg == "yes":
                self.cursor.execute(RemoveAsyncRaceSql.format(race_id))
                self.db_connection.commit()
                await ctx.send("Race {} removed".format(race_id))
            else:
                await ctx.send("Remove cancelled")

########################################################################################################################
# SET_WEIGHT
########################################################################################################################
    #@commands.command()
    #@commands.check(isRaceCreatorCommandChannel)
    #@commands.has_any_role(FORTY_BONKS_RACE_CREATOR_ROLE, BTT_RACE_CREATOR_ROLE)
    #async def edit_weight(self, ctx: commands.Context, user_id: int, weight: int):
    #    ''' 
    #    Sets the wheel weight for a user
    #
    #        Required Parameters:
    #            user_id - ID of the user to update
    #            weight  - Weight to be set for the user
    #    '''
    #    logging.info('Executing $edit_weight command')
    #    # First query the user's current wheel weight
    #    self.cursor.execute(QueryRacerDataSql.format(user_id))
    #    racer_data = self.cursor.fetchone()
    #    await ctx.send("Current wheel weight for {} is {}. Updating it to {}".format(racer_data[ASYNC_RACERS_USERID], racer_data[ASYNC_RACERS_WHEEL_WEIGHT], weight))
    #
    #    self.cursor.execute(UpdateWheelWeightSql.format(weight, user_id))
    #    self.db_connection.commit()

########################################################################################################################
# WHEEL_INFO
########################################################################################################################
    @commands.command()
    @commands.check(isRaceCreatorCommandChannel)
    @commands.has_any_role(FORTY_BONKS_RACE_CREATOR_ROLE, BTT_RACE_CREATOR_ROLE)
    async def wheel_info(self, ctx: commands.Context):
        ''' 
        Prints the current wheel info, this will be a list of all users who have raced in one or both of the two most recent
        weekly asyncs and will include their most recent mode suggestion and their wheel weight.
        '''
        logging.info('Executing $wheel_info command')
        racers = self.cursor.execute(QueryAllRacerDataSql).fetchall()
        # Query the 5 most recent weekly races
        recent_races = self.cursor.execute(QueryMostRecentActiveFromSql.format(self.weekly_category_id, 0)).fetchall()
        race_id_range_begin = recent_races[0][ASYNC_RACES_ID]
        race_id_range_end   = recent_races[1][ASYNC_RACES_ID]
        wheel_list_str = "*Name* > *Mode*\n"
        for r in racers:
            # Query mode suggestions for this user, we will query each of the two most recent weekly async races. If the user has not completed
            # either async then the query will return None
            mode_data = self.cursor.execute(QueryModeSuggestionForWheel.format(r[ASYNC_RACERS_USERID], race_id_range_begin)).fetchone()
            if mode_data is not None:
                mode_str = mode_data[0]
                if mode_str is not None:
                    wheel_list_str += "{} > {}\n".format(r[ASYNC_RACERS_USERNAME], mode_str.strip().replace('\n', ' '))

            mode_data = self.cursor.execute(QueryModeSuggestionForWheel.format(r[ASYNC_RACERS_USERID], race_id_range_end)).fetchone()
            if mode_data is not None:
                mode_str = mode_data[0]
                if mode_str is not None:
                    wheel_list_str += "{} > {}\n".format(r[ASYNC_RACERS_USERNAME], mode_str.strip().replace('\n', ' '))

        await ctx.send(wheel_list_str)

########################################################################################################################
# MOD_UTIL
########################################################################################################################
    @commands.command(hidden=True)
    @commands.check(isRaceCreatorCommandChannel)
    @commands.has_any_role(FORTY_BONKS_RACE_CREATOR_ROLE, BTT_RACE_CREATOR_ROLE)
    async def mod_util(self, ctx: commands.Context, function: int):
        ''' 
        A selection of utility functions. Parameter determines which function to run:

            Required Parameter:
                function - Which utility function to run. Options are:
                    1 - Force update leaderboard message
                    2 - Force update weekly submit channel message
                    3 - Toggle enable/disable of toilet paper
        '''
        logging.info('Executing $mod_util command')
        if function == 1:
            await self.updateLeaderboardMessage(self.queryLatestRaceId(), ctx)
            await ctx.send("Updated weekly leaderboard channel")
        elif function == 2:
            race_info = self.queryRaceInfo(self.queryLatestRaceId())
            await self.updateWeeklyModeMessage(race_info)
            await ctx.send("Updated weekly mode message in submit channel")
        elif function == 3:
            self.replace_poop_with_tp = not self.replace_poop_with_tp
            await ctx.send("Toilet paper replacement is now {}".format("Enabled" if self.replace_poop_with_tp else "Disabled"))

########################################################################################################################
# USER_RACES
########################################################################################################################
    @commands.command(hidden=True)
    @commands.check(isRaceCreatorCommandChannel)
    @commands.has_any_role(FORTY_BONKS_RACE_CREATOR_ROLE, BTT_RACE_CREATOR_ROLE)
    async def user_races(self, ctx: commands.Context, user_id: int):
        ''' 
        Shows races for the user with the provided user ID

            Required Parameter:
                user_id - ID of the user to edit a submission for
        '''
        logging.info('Executing $user_races command')
        member_info = self.cursor.execute(QueryRacerDataSql.format(user_id)).fetchone()
        if member_info is None:
            await ctx.send("No user found with ID {}".format(user_id))
            return
        await ctx.send("Showing races for {}".format(member_info[ASYNC_RACERS_USERNAME]))
        await self.show_races(ctx, 1, user_id)


########################################################################################################################
# EDIT_SUBMISSION
########################################################################################################################
    @commands.command(hidden=True)
    @commands.check(isRaceCreatorCommandChannel)
    @commands.has_any_role(FORTY_BONKS_RACE_CREATOR_ROLE, BTT_RACE_CREATOR_ROLE)
    async def edit_submission(self, ctx: commands.Context, submission_id: int):
        ''' 
        Edits a submission on behalf of a user

            Required Parameter:
                submission_id - ID of the submission to edit
        '''
        logging.info('Executing $edit_submission command')
        submission_to_edit = self.cursor.execute(QueryAsyncSubmissionByIdSql.format(submission_id)).fetchone()
        if submission_to_edit is None:
            await ctx.send("No submission found with ID {}".format(submission_id))
            return

        def checkInfo(message):
            ret = False
            if len(message.content.split(' ')) >= 2 and len(message.content.split(' ')) <= 3:
                ret = True
            return ret

        new_info_prompt = "Enter the new info as follows, RTA can be left out if unavailable: `<IGT in H:MM:SS> <cr> {RTA in H:MM:SS}`"
        info_msg = await self.ask(ctx, new_info_prompt, checkInfo)
        parts = info_msg.split(' ')
        if self.game_time_is_valid(parts[0]):
            new_igt = parts[0]
            new_collection = parts[1]
            new_rta = None
            if len(parts) == 3 and self.game_time_is_valid(parts[2]):
                new_rta = parts[2]
            update_sql = UpdateAsyncSubmissionSql.format(submission_to_edit[ASYNC_SUBMISSIONS_SUBMIT_DATE],
                                                         new_rta,
                                                         new_igt,
                                                         new_collection,
                                                         submission_to_edit[ASYNC_SUBMISSIONS_NEXT_MODE],
                                                         submission_to_edit[ASYNC_SUBMISSIONS_COMMENT],
                                                         submission_to_edit[ASYNC_SUBMISSIONS_ID])
            self.cursor.execute(update_sql)
            self.db_connection.commit()
            await ctx.send("Updated submission ID {}".format(submission_to_edit[ASYNC_SUBMISSIONS_ID]))

########################################################################################################################
# ON_MESSAGE
########################################################################################################################
    @commands.Cog.listener("on_message")
    async def message_handler(self, message):
        if message.author == self.bot.user:
            return

        # Check if this is a weekly async submission
        if message.guild.id == self.server_id and message.channel.id == self.weekly_submit_channel_id:
            args = message.content.split(' ')
            ctx = await self.bot.get_context(message)

            # For a forfeit, we just assign the weekly racer role
            if message.content.lower() == "ff":
                await ctx.send("Lurk mode activated", delete_after=DeleteAfterTime)
                await self.assignWeeklyAsyncRole(ctx)
            # For a valid submission, we forward it to submit_time and then assign the weekly racer role
            elif len(args) == 2 and self.game_time_is_valid(args[0]):
                # Query the current race_id and send the message to submit_time, then assign the weekly racer role
                self.cursor.execute(QueryMostRecentFromCategorySql.format(self.weekly_category_id, 0))
                race_id = self.cursor.fetchone()[ASYNC_RACES_ID]
                self.weekly_submit_author_list.append(message.author.id)
                await self.submit_time(ctx, race_id, args[0], args[1])
                await self.assignWeeklyAsyncRole(ctx)
            # Any other message, we just reply with the usage instructions
            elif message.author.id not in self.weekly_submit_author_list:
                await message.delete()
                await message.channel.send("Missing or invalid parameters. IGT (in H:MM:SS format) and collection rate are required.", delete_after=DeleteAfterTime)
            # Wait and then delete the message just in case it's not otherwise handled/deleted above
            await asyncio.sleep(DeleteAfterTime)
            await message.delete()

        if "pendant pod" in message.content.lower():
            logging.info("adding pendant pod emoji")
            guild = self.bot.get_guild(self.server_id)
            emoji = None
            for e in guild.emojis:
                if str(e) == PendantPodEmoteStr:
                    emoji = e
            if emoji is not None:
                await message.add_reaction(emoji)

########################################################################################################################
# ON_READY
########################################################################################################################
    @commands.Cog.listener("on_ready")
    async def on_ready_handler(self):
        logging.info("Ready")
        if self.test_mode:
            logging.info("Running in test mode")

########################################################################################################################
# REACTION ADD HANDLER
########################################################################################################################
    @commands.Cog.listener("on_raw_reaction_add")
    async def reaction_add_handler(self, payload):
        if self.isPoopEmoji(payload.emoji):
            logging.info("Cleaning up some poop")
            guild = self.bot.get_guild(payload.guild_id)
            channel = guild.get_channel(payload.channel_id)
            message = await channel.fetch_message(payload.message_id)
            await message.remove_reaction(payload.emoji, payload.member)
            if self.replace_poop_with_tp:
                await message.add_reaction(ToiletPaperEmoji)


def setup(bot):
    bot.add_cog(AsyncHandler(bot))
