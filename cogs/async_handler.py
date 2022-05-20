# -*- coding: utf-8 -*-
from nextcord.ext import commands
import nextcord
import sqlite3
import logging
from prettytable import PrettyTable, DEFAULT, ALL
import re
import asyncio
from datetime import datetime, date
from async_db_orm import *
from enum import Enum
from typing import NamedTuple

class ServerInfo(NamedTuple):
    server_id: int

    # Channel IDs
    weekly_submit_channel: int
    tourney_submit_channel: int
    race_creator_channel: int
    bot_command_channels: list[int]
    weekly_leaderboard_channel: int
    tourney_leaderboard_channel: int
    announcements_channel: int
    modchat_channel: int

    # Role IDs
    race_creator_role: int
    weekly_race_done_role: int
    weekly_racer_role: int

# 40 Bonks Server Info
FortyBonksServerInfo = ServerInfo(
    server_id = 485284146063736832,
    weekly_submit_channel = 907626630816620624,
    tourney_submit_channel = 0,
    race_creator_channel = 907626794474156062,
    bot_command_channels = [ 907627122732982363, 907626794474156062 ],
    race_creator_role = 782804969107226644,
    weekly_race_done_role = 732078040892440736,
    weekly_leaderboard_channel = 747239559175208961,
    tourney_leaderboard_channel = 0,
    announcements_channel = 734104388821450834,
    weekly_racer_role = 732048874222387200,
    modchat_channel = 782850572503744522)

# Bot Testing Things Server Info
BttServerInfo = ServerInfo(
    server_id = 853060981528723468,
    race_creator_role = 888940865337299004,
    weekly_submit_channel = 892861800612249680,
    tourney_submit_channel = 952612873534836776,
    race_creator_channel = 896494916493004880,
    bot_command_channels = [ 853061634855665694, 854508026832748544, 896494916493004880 ],
    weekly_race_done_role = 895026847954374696,
    weekly_leaderboard_channel = 895681087701909574,
    tourney_leaderboard_channel = 952612956724682763,
    announcements_channel = 896494916493004880,
    weekly_racer_role = 931946945562423369,
    modchat_channel = 854508026832748544)

SupportedServerList = [ FortyBonksServerInfo.server_id, BttServerInfo.server_id ]

PRODUCTION_DB = "AsyncRaceInfo.db"
TEST_DB = "testDbUtil.db"

# Discord limit is 2000 characters, subtract a few to account for formatting, newlines, etc
DiscordApiCharLimit = 2000 - 10
DeleteAfterTime = 30
DeleteAfterTimeEphemeral = 15
SelectTimeout = 30
AddRaceTimeout = 120
ItemsPerPage = 5
NextPageEmoji = '▶️'
OneEmoji = '1️⃣'
TwoEmoji = '2️⃣'
ThreeEmoji = '3️⃣'
FourEmoji = '4️⃣'
FiveEmoji = '5️⃣' 
SixEmoji = '6️⃣' 
SevenEmoji = '7️⃣' 
EightEmoji = '8️⃣' 
NineEmoji = '9️⃣'
NumberEmojiList = [OneEmoji, TwoEmoji, ThreeEmoji, FourEmoji, FiveEmoji, SixEmoji, SevenEmoji, EightEmoji, NineEmoji ]
PoopEmoji = '💩'
ThumbsUpEmoji = '👍'
ThumbsDownEmoji = '👎'
YesNoEmojiList = [ ThumbsUpEmoji, ThumbsDownEmoji ]
TimerEmoji = '⏲️'
ToiletPaperEmoji = '🧻'
PendantPodEmoteStr = '<:laoPoD:809226000550199306>'
WeeklySubmitInstructions = '''
To submit a time for the weekly async enter the in-game time (IGT) in H:MM:SS format followed by the collection rate. The bot will prompt you to add additional information (e.g RTA, next mode suggestion, comment).
Example:
    > 1:23:45 167

To correct any information in a submission, simply submit it again. If you take longer than 60 seconds to respond the operation will time out and you'll have to start over.

To skip running the async but still get access to the weekly spoilers and leaderboard channels, simply type `ff`
'''

TourneySubmitInstructions = '''
To submit a time for a tourney async enter the race ID followd by the in-game time (IGT) in H:MM:SS format followed by the collection rate. The bot will prompt you to add additional information (e.g RTA, comment).
Example:
    >54 1:23:45 167

To correct any information in a submission, simply submit it again. If you take longer than 60 seconds to respond the operation will time out and you'll have to start over.
'''

async def isSubmitChannel(ctx):
    return isWeeklySubmitChannel(ctx) or isTourneySubmitChannel(ctx)

async def isWeeklySubmitChannel(ctx):
    if ctx.channel.id == FortyBonksServerInfo.weekly_submit_channel or ctx.channel.id == BttServerInfo.weekly_submit_channel:
        return True
    return False

async def isTourneySubmitChannel(ctx):
    if ctx.channel.id == FortyBonksServerInfo.tourney_submit_channel or ctx.channel.id == BttServerInfo.tourney_submit_channel:
        return True
    return False

async def isRaceCreatorCommandChannel(ctx):
    if ctx.channel.id == FortyBonksServerInfo.race_creator_channel or ctx.channel.id == BttServerInfo.race_creator_channel:
        return True
    return False

async def isBotCommandChannel(ctx):
    if ctx.channel.id in FortyBonksServerInfo.bot_command_channels or ctx.channel.id in BttServerInfo.bot_command_channels:
        return True
    return False

def sort_igt(submission):
    igt = submission.finish_time_igt
    # Convert the time to seconds for sorting
    ret = 0
    if igt is not None:
        parts = igt.split(':')
        ret = (3600 * int(parts[0])) + (60 * int(parts[1])) + int(parts[2])
    return ret

AsyncSubmitButtonId = "AsyncSubmitButton"
timeout_msg = "Timeout error. I don't have all day! You'll have to start over (and be quicker this time)"

class AsyncHandler(commands.Cog, name='AsyncRaceHandler'):
    '''Cog which handles commands related to Async Races.'''

    def __init__(self, bot):
        self.bot = bot
        self.test_mode = False
        self.db = SqliteDatabase(PRODUCTION_DB)
        self.db.bind([RaceCategory, AsyncRace, AsyncRacer, AsyncSubmission])
        self.weekly_category_id = 1
        self.weekly_submit_author_list = []
        self.tourney_category_id = 2
        self.tourney_submit_author_list = []
        self.pt = PrettyTable()
        self.resetPrettyTable()
        self.server_info = FortyBonksServerInfo
        self.replace_poop_with_tp = True

########################################################################################################################
# UI Elements
########################################################################################################################

    ########################################################################################################################
    # SUBMIT_TIME Elements
    class SubmitType(Enum):
        SUBMIT  = 1
        EDIT    = 2
        FORFEIT = 3

    class SubmitTimeModal(nextcord.ui.Modal):
        def __init__(self, asyncHandler, race_id, isWeeklyAsync, submitType):
            super().__init__("Async Time Submit")
            self.asyncHandler = asyncHandler
            self.race_id = race_id
            self.isWeeklyAsync = isWeeklyAsync
            self.submitType = submitType

            self.igt = nextcord.ui.TextInput(
                label="Enter IGT in format `H:MM:SS`",
                min_length=7,
                max_length=8)

            self.collection_rate = nextcord.ui.TextInput(
                label="Enter collection rate`",
                min_length=1,
                max_length=3)

            self.rta = nextcord.ui.TextInput(
                label="Enter RTA in format `H:MM:SS`",
                required=False,
                min_length=7,
                max_length=7)

            self.comment = nextcord.ui.TextInput(
                label="Enter Comment",
                required=False,
                min_length=1,
                max_length=1024)

            self.next_mode = nextcord.ui.TextInput(
                label="Enter Next Mode Suggestion",
                required=False,
                min_length=1,
                max_length=1024)

            if submitType is not AsyncHandler.SubmitType.FORFEIT:
                self.add_item(self.igt)
                self.add_item(self.collection_rate)
                self.add_item(self.rta)
            self.add_item(self.comment)
            if isWeeklyAsync:
                self.add_item(self.next_mode)

        async def callback(self, interaction: nextcord.Interaction) -> None:
            await self.asyncHandler.submit_time(self, interaction, self.race_id)
            if self.isWeeklyAsync:
                await self.asyncHandler.assignWeeklyAsyncRole(interaction.guild, interaction.user)

    ########################################################################################################################
    # ADD_RACE Elements
    class AddRaceModal(nextcord.ui.Modal):
        def __init__(self, asyncHandler):
            super().__init__("Add Race")
            self.asyncHandler = asyncHandler
            self.is_done = False

            self.mode = nextcord.ui.TextInput(
                label="Mode Description`",
                min_length=1,
                max_length=50)
            self.add_item(self.mode)

            self.seed = nextcord.ui.TextInput(label="Seed Link`")
            self.add_item(self.seed)

            self.instructions = nextcord.ui.TextInput(
                label="Additional Instructions`",
                required=False)
            self.add_item(self.instructions)

        async def callback(self, interaction: nextcord.Interaction):
            self.is_done = True

    class CategorySelect(nextcord.ui.Select):
        def __init__(self, callback_func, add_race_modal):
            self.callback_func = callback_func
            self.add_race_modal = add_race_modal

            # Query the categories
            categories = RaceCategory.select()

            # Create the options list from the categories
            options = []
            for c in categories:
                options.append(nextcord.SelectOption(label=c.name, description=c.description, value=str(c.id)))

            # Initialize the base class
            super().__init__(
                placeholder="Select Race Category...",
                min_values=1,
                max_values=1,
                options=options)

        async def callback(self, interaction: nextcord.Interaction):
            await interaction.response.send_modal(self.add_race_modal)
            await self.callback_func(int(interaction.data['values'][0]))

    class AddRaceView(nextcord.ui.View):
        def __init__(self, add_race_modal):
            super().__init__()
            self.category_id = 0
            self.category_select = AsyncHandler.CategorySelect(self.callback_func, add_race_modal)
            self.add_item(self.category_select)

        async def callback_func(self, category_id):
            self.category_id = category_id

    ########################################################################################################################
    # Race Selection Elements
    class RaceSelect(nextcord.ui.Select):
        def __init__(self, callback_func):
            self.callback_func = callback_func

            # Query the active races
            races = AsyncRace.select()                         \
                             .where(AsyncRace.active == True)  \
                             .order_by(AsyncRace.start.desc()) \
                             .limit(25)

            # Create the options list from the categories
            options = []
            for r in races:
                options.append(nextcord.SelectOption(label=f"Race ID {r.id} - {r.description}", description=r.description, value=str(r.id)))

            # Initialize the base class
            super().__init__(
                placeholder="Select Race. For full active race ID list use /races command.",
                min_values=1,
                max_values=1,
                options=options)

        async def callback(self, interaction: nextcord.Interaction):
            await self.callback_func(int(interaction.data['values'][0]))

    class RaceSelectView(nextcord.ui.View):
        def __init__(self):
            super().__init__()
            self.race_id = None
            self.race_select = AsyncHandler.RaceSelect(self.callback_func)
            self.add_item(self.race_select)

        async def callback_func(self, race_id):
            self.race_id = race_id

    ########################################################################################################################
    # Show races elements
    class LeaderboardButton(nextcord.ui.Button):
        def __init__(self, race_id, asyncHandler, style=nextcord.ButtonStyle.green, label="Leaderboard", row=0):
            super().__init__(style=style, row=row, label=label)
            self.race_id = race_id
            self.asyncHandler = asyncHandler
        async def callback(self, interaction):
            await self.asyncHandler.leaderboard_impl(interaction, self.race_id)

    class RaceInfoButton(nextcord.ui.Button):
        def __init__(self, race_id, asyncHandler, style=nextcord.ButtonStyle.blurple, label="Race Info", row=0):
            super().__init__(style=style, row=row, label=label)
            self.race_id = race_id
            self.asyncHandler = asyncHandler
        async def callback(self, interaction):
            await self.asyncHandler.show_race_info(interaction, self.race_id)

    class ShowRacesView(nextcord.ui.View):
        def __init__(self, asyncHandler, race_id_list):
            super().__init__()
            base_row = 0
            assert(len(race_id_list) <= 5)
            for race_id in race_id_list:
                race_info_button = AsyncHandler.RaceInfoButton(
                    race_id,
                    asyncHandler,
                    label=f"Race Info___ {race_id}",
                    row=1)
                self.add_item(race_info_button)
                leaderboard_button = AsyncHandler.LeaderboardButton(
                    race_id,
                    asyncHandler,
                    label=f"Leaderboard {race_id}",
                    row=0)
                self.add_item(leaderboard_button)

    ########################################################################################################################
    # Race info button view
    class RaceInfoButtonView(nextcord.ui.View):
        def __init__(self, asyncHandler, race_id):
            super().__init__()
            race = asyncHandler.get_race(race_id)
            isWeeklyAsync = race.category_id == asyncHandler.weekly_category_id
            self.submit = AsyncHandler.SubmitTimeModal(asyncHandler, race_id, isWeeklyAsync, AsyncHandler.SubmitType.SUBMIT)
            self.edit = AsyncHandler.SubmitTimeModal(asyncHandler, race_id, isWeeklyAsync, AsyncHandler.SubmitType.EDIT)
            self.ff = AsyncHandler.SubmitTimeModal(asyncHandler, race_id, isWeeklyAsync, AsyncHandler.SubmitType.FORFEIT)
            self.race_id = race_id
            self.asyncHandler = asyncHandler
            leaderboard_button = AsyncHandler.LeaderboardButton(race_id, asyncHandler)
            self.add_item(leaderboard_button)

        @nextcord.ui.button(style=nextcord.ButtonStyle.blurple, label='Submit Time', custom_id=AsyncSubmitButtonId)
        async def submit_button(self, button: nextcord.ui.Button, interaction: nextcord.Interaction):
            submission = self.asyncHandler.getSubmission(self.race_id, interaction.user.id)
            if submission is None:
                await interaction.response.send_modal(self.submit)
            else:
                await interaction.send("You've already submitted for this race, use the 'Edit Time' button to modify your submission", ephemeral=True)

        @nextcord.ui.button(style=nextcord.ButtonStyle.grey, label='Edit Time')
        async def edit_button(self, button: nextcord.ui.Button, interaction: nextcord.Interaction):
            # Get the user's current submission
            submission = self.asyncHandler.getSubmission(self.race_id, interaction.user.id)
            if submission is not None:
                # Update default values using the existing submission
                self.edit.igt.default_value = submission.finish_time_igt
                self.edit.collection_rate.default_value = str(submission.collection_rate)
                self.edit.rta.default_value = submission.finish_time_rta
                self.edit.comment.default_value = submission.comment
                self.edit.next_mode.default_value = submission.next_mode

            # Send the modal
            await interaction.response.send_modal(self.edit)

        @nextcord.ui.button(style=nextcord.ButtonStyle.red, label='FF')
        async def ff_button(self, button: nextcord.ui.Button, interaction: nextcord.Interaction):
            submission = self.asyncHandler.getSubmission(self.race_id, interaction.user.id)
            if submission is None:
                await interaction.response.send_modal(self.ff)
            else:
                await interaction.send("You've already submitted for this race, use the 'Edit Time' button to modify your submission", ephemeral=True)

########################################################################################################################
# Utility Functions
########################################################################################################################
    def setTestMode(self):
        self.test_mode = True
        self.db = SqliteDatabase(TEST_DB)
        self.db.bind([RaceCategory, AsyncRace, AsyncRacer, AsyncSubmission])
        self.server_info = BttServerInfo
        SelectTimeout = 10
        AddRaceTimeout = 30

    def resetPrettyTable(self):
        self.pt.set_style(DEFAULT)
        self.pt.clear()

    def isRaceCreator(self, guild, user):
        ret = False
        role = guild.get_role(self.server_info.race_creator_role)
        if role in user.roles:
            ret =  True
        return ret

    ####################################################################################################################
    # Removes the weekly async submit/ff button message
    async def removeWeeklySubmitButtons(self):
        # Get the weekly submit channel
        weekly_submit_channel = self.bot.get_channel(self.server_info.weekly_submit_channel)
        message_list = await weekly_submit_channel.history(limit=200).flatten()
        # Search the message history for the message containing the submit/ff buttons. We identify the message by looking
        # for a message containing an action row where the first item is a button with the AsyncSubmitButtonId custom_id
        for message in message_list:
            if message.author.id == self.bot.user.id and len(message.components) > 0:
                if isinstance(message.components[0], nextcord.ActionRow):
                    row = message.components[0]
                    if len(row.children) > 0 and isinstance(row.children[0], nextcord.Button):
                        if row.children[0].custom_id == AsyncSubmitButtonId:
                            await message.delete()
                            break

    ####################################################################################################################
    # Adds the weekly async submit/ff button message
    async def addSubmitButtons(self):
        # Get the weekly submit channel
        weekly_submit_channel = self.bot.get_channel(self.server_info.weekly_submit_channel)
        # Remove any existing submit button message
        await self.removeWeeklySubmitButtons()
        # Add the new message
        await weekly_submit_channel.send("Click below to submit a time or FF from this week's race", view=AsyncHandler.RaceInfoButtonView(self, self.queryLatestWeeklyRaceId()))

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
    # Queries for a race by ID, returning None if it doesn't exist
    def get_race(self, race_id):
        try:
            race = AsyncRace.select().where(AsyncRace.id == race_id).get()
        except:
            race = None
        return race
    
    ####################################################################################################################
    # Returns the submissions for the given race ID sorted by IGT finish time
    def get_leaderboard(self, race):
        submissions = AsyncSubmission.select()        \
                                     .where(AsyncSubmission.race_id == race.id)
        return sorted(submissions, key=sort_igt)

    ####################################################################################################################
    # Returns a string containing which numeric place (e.g. 1st, 2nd, 3rd) a user came in a specific race
    def get_place(self, race, userid):
        place = 0

        leaderboard = self.get_leaderboard(race)

        if len(leaderboard) > 0:
            for idx, s in enumerate(leaderboard):
                if s.user_id == userid:
                    place = (idx+1)
        return self.get_place_str(place)

    ####################################################################################################################
    # Given a numeric place, returns the ordinal string. e.g. 1 returns "1st", 2 "2nd" etc
    def get_place_str(self, place):
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
    async def assignWeeklyAsyncRole(self, guild, author):
        role = nextcord.utils.get(guild.roles, id=self.server_info.weekly_race_done_role)
        await author.add_roles(role)

    ####################################################################################################################
    # Removes the weekly async racer role from all users in the server
    async def removeWeeklyAsyncRole(self, ctx):
        role = nextcord.utils.get(ctx.guild.roles, id=self.server_info.weekly_race_done_role)
        for m in ctx.guild.members:
            await m.remove_roles(role)

    ####################################################################################################################
    # Queries the most recent weekly async race ID
    def queryLatestWeeklyRaceId(self):
        return AsyncRace.select()                                                                   \
                        .where(AsyncRace.category_id == self.weekly_category_id & AsyncRace.active) \
                        .order_by(AsyncRace.id.desc())                                              \
                        .get()                                                                      \
                        .id

    ####################################################################################################################
    # Builds the leaderboard message list for a specific race ID
    def buildLeaderboardMessageList(self, race_id):
        # Query race info
        race = self.get_race(race_id)
        race_submissions = self.get_leaderboard(race)

        if race is not None:
            leaderboardStr = ""
            if len(race_submissions) == 0:
                leaderboard_str = f'No results yet for race {race_id} ({race.description}) which started on {race.start}'
            else:
                leaderboard_str = f'Leaderboard for race {race_id} which started on {race.start}'
                leaderboard_str += f'\n    **Mode: {race.description}**'
                leaderboard_str += "\n"
                self.resetPrettyTable()
                self.pt.field_names = ["#", "Name", "IGT", "RTA", "CR"]
                for idx, submission in enumerate(race_submissions):
                    self.pt.add_row([idx+1,
                                     submission.username,
                                     submission.finish_time_igt,
                                     submission.finish_time_rta,
                                     submission.collection_rate])

            message_list = self.buildResponseMessageList(leaderboard_str)
            table_message_list = []
            if len(race_submissions) > 0:
                table_message_list = self.buildResponseMessageList(self.pt.get_string())
                for idx, msg in enumerate(table_message_list):
                    table_message_list[idx] = "`{}`".format(msg)
            return message_list + table_message_list
        else:
            return [f'No race found matching race ID {race_id}']

    ####################################################################################################################
    # Updates the weekly leaderboard message
    async def updateLeaderboardMessage(self, race_id, guild):
        # Remove all messages from the leaderboard channel
        leaderboard_channel = guild.get_channel(self.server_info.weekly_leaderboard_channel)
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
    # Adds the provided emoji's as reactions to a message and returns the first one the user clicks, if any, 
    # before the timeout (30s)
    async def userReactEmoji(self, author, message, emoji_list, delete_on_react = True):
        for e in emoji_list:
            await message.add_reaction(e)

        def checkUserReaction(reaction, user):
            return user == author and reaction.message == message and str(reaction.emoji) in emoji_list

        bot_member = self.bot.get_user(self.bot.user.id)
        return_emoji = TimerEmoji
        try:
            reaction, user = await self.bot.wait_for('reaction_add', timeout=30, check=checkUserReaction)
            return_emoji = str(reaction.emoji)
        except asyncio.TimeoutError:
            logging.info("User reaction timeout")
        for e in emoji_list:
            await message.remove_reaction(e, bot_member)
        if delete_on_react:
            await message.delete()
        return return_emoji

    ####################################################################################################################
    # Updates the current mode message in the weekly submit channel
    async def updateWeeklyModeMessage(self, race):
        weekly_submit_channel = self.bot.get_channel(self.server_info.weekly_submit_channel)
        message_list = await weekly_submit_channel.history(limit=200).flatten()
        for message in message_list:
            if message.author.id == self.bot.user.id:
                await message.delete()
        full_msg = WeeklySubmitInstructions + f'\n\nThe mode for the current async is: **{race.description}**'
        if race.instructions is not None:
            full_msg += f'\nAdditional Info: {race.instructions}'
        await weekly_submit_channel.send(full_msg)
        seed_embed = nextcord.Embed(title="{}".format(race.description), url=race.seed, color=nextcord.Colour.random())
        seed_embed.set_thumbnail(url="https://alttpr.com/i/logo_h.png")
        await weekly_submit_channel.send(embed=seed_embed)

    ####################################################################################################################
    # Posts an announcement about a new weekly async
    async def post_annoucement(self, race, ctx):
        announcements_channel = self.bot.get_channel(self.server_info.announcements_channel)
        role = ctx.guild.get_role(self.server_info.weekly_racer_role)
        announcement_text = f'{role.mention} The new weekly async is live! Mode is: {race.description}'
        msg = await announcements_channel.send(announcement_text)
        

    ####################################################################################################################
    # Fetches a users display name
    async def getDisplayName(self, guild, user_id):
        member = await guild.get_member(user_id)
        return member.display_name

    ####################################################################################################################
    # Checks if the provided member is in the asyc_racers table, adds them if not
    def checkAddMember(self, member):
        racer = AsyncRacer.get(AsyncRacer.user_id == member.id)
        if racer is None:
            racer = AsyncRacer(user_id = member.id, username = member.name)
            racer.save()

    ####################################################################################################################
    # Checks if the provided emoji is a poop emoji....  sigh...
    def isPoopEmoji(self, emoji):
        if str(emoji) == PoopEmoji:
            return True
        else:
            return False

    ####################################################################################################################
    # Displays race submissions for the given user_id
    async def show_races_impl(self, interaction, page, user_id):
        query_results = AsyncSubmission.select()                                     \
                                       .where(AsyncSubmission.user_id == user_id)         \
                                       .order_by(AsyncSubmission.submit_date.desc()) \
                                       .paginate(page, ItemsPerPage)

        latest_weekly_id = self.queryLatestWeeklyRaceId()
        await interaction.response.defer()

        if len(query_results) > 0:
            self.resetPrettyTable()
            self.pt.hrules = True
            self.pt.field_names = ["Date", "Place", "IGT", "Collection Rate", "RTA", "Mode", "Race ID", "Submission ID"]
            self.pt._max_width = {"Mode": 50}
            race_id_list = []
            for result in query_results:
                # First find info about the race this submission is for
                race_id = result.race_id
                race_id_list.append(race_id)
                race = self.get_race(race_id)
                date        = result.submit_date
                mode        = race.description if race is not None else ""
                igt         = result.finish_time_igt
                cr          = result.collection_rate
                rta         = result.finish_time_rta
                submit_id   = result.id
                place       = self.get_place(race, user_id)

                if rta is None: rta = ""

                # Hide completion info if this is the current weekly async
                if race_id == latest_weekly_id:
                    igt = "**:**:**"
                    rta = "**:**:**"
                    cr = "***"
                    place = "****"
                self.pt.add_row([date, place, igt, cr, rta, mode, race_id, submit_id])

            total_submissions = AsyncSubmission.select(fn.COUNT(AsyncSubmission.id)).where(AsyncSubmission.user_id == user_id).get()
            await interaction.followup.send(f"Recent Async Submissions, page {page}:", ephemeral=True)
            table_message_list = self.buildResponseMessageList(self.pt.get_string())
            for table_message in table_message_list:
                await interaction.followup.send(f"`{table_message}`", ephemeral=True)
            await interaction.followup.send(view=AsyncHandler.ShowRacesView(self, race_id_list))
        else:
            await ctx.send("There are no async submissions in that range")

    ####################################################################################################################
    # Retrieves a submission based on race and user IDs. Returns None if no matching submission exists
    def getSubmission(self, race_id, user_id):
        try:
            submission = AsyncSubmission.select()                                                                           \
                                        .where((AsyncSubmission.race_id == race_id) & (AsyncSubmission.user_id == user_id)) \
                                        .get()
        except:
            submission = None
        return submission

    ####################################################################################################################
    # Displays a RaceSelectView, waits and returns the race_id chosen by the user
    async def getRaceIdSelection(self, interaction):
        race_select_view = AsyncHandler.RaceSelectView()
        await interaction.send(view=race_select_view, ephemeral=True)
        sleep_counter = 0
        while(race_select_view.race_id is None and sleep_counter < SelectTimeout):
            await asyncio.sleep(1)
            sleep_counter += 1

        return race_select_view.race_id

    ####################################################################################################################
    # Creates a prettytable with race info
    def getRaceInfoTable(self, race, is_race_creator=False):
        info_str = None
        if race is not None:
            labels = ["Race Id:", "Start Date:", "Seed:", "Mode:", "Is Active:", "Add'l Info"]
            info_str = f"{labels[0]} {race.id}\n"
            info_str += f"{labels[1]} {race.start}\n"
            info_str += f"{labels[2]} {race.seed}\n"
            info_str += f"{labels[3]} {race.description}\n"
            if is_race_creator:
                info_str += f"{labels[4]} {race.active}\n"
            if race.additional_instructions is not None:
                info_str += f"{labels[3]} {race.additional_instructions}\n"
        return info_str

    ####################################################################################################################
    # Gets an embed object containing the seed link for the provided race
    def getSeedEmbed(self, race):
        seed_embed = nextcord.Embed(title="{}".format(race.description), url=race.seed, color=nextcord.Colour.random())
        seed_embed.set_thumbnail(url="https://alttpr.com/i/logo.png")
        return seed_embed

    ####################################################################################################################
    # Does the actual work for the leaderboard command, moved to a separate function to be reusable with buttons
    async def leaderboard_impl(self, interaction, race_id):
        response_obj = interaction
        if race_id is None:
            race_id = await self.getRaceIdSelection(interaction)
            response_obj = interaction.followup
            if race_id is None:
                await response_obj.send("Race selection timeout, be quicker next time", ephemeral=True)
                return

        # check if the user has permission to view the leaderboard. They have permission if they submitted to it or have appropriate role
        can_view = self.isRaceCreator(interaction.guild, interaction.user) or self.getSubmission(race_id, interaction.user.id) is not None
        # Make sure this race exists
        try:
            race = AsyncRace.select()                       \
                            .where(AsyncRace.id == race_id) \
                            .get()
        except:
            race = None

        if race is not None and can_view:
            message_list = self.buildLeaderboardMessageList(race_id)
            for message in message_list:
                await response_obj.send(message, ephemeral=True)
        elif can_view:
            await response_obj.send(f"Invalid Race ID: {race_id}", ephemeral=True)
        else:
            await response_obj.send(f"You must submit a time or FF from the race before viewing the leaderboard", ephemeral=True)

    ####################################################################################################################
    # Submits a time to the DB
    async def submit_time(self, modal: SubmitTimeModal, interaction: nextcord.Interaction, race_id):
        logging.info('Handling submit_time')

        # First check if the race exists
        race = self.get_race(race_id)
        if race is None or not race.active:
            await interaction.send(f"Error submitting time for race {race_id}. Race doesn't exist or is not active. Please notfiy the bot overlord(s)", ephemeral=True, delete_after=DeleteAfterTimeEphemeral)
            return
    
        self.checkAddMember(interaction.user)
        user_id = interaction.user.id
        igt = "23:59:59" if modal.igt.value is None else modal.igt.value
        rta = None if modal.rta.value == "" else modal.rta.value
        cr_int = "216" if modal.collection_rate.value is None else modal.collection_rate.value
        comment = modal.comment.value
        next_mode = modal.next_mode.value

        parse_error = not self.game_time_is_valid(igt)
        if rta is not None and not parse_error:
            parse_error = not self.game_time_is_valid(rta)
    
        if parse_error:
            await interaction.send("IGT, RTA or CR is in the wrong format, evaluate your life choices and try again", ephemeral=True, delete_after=DeleteAfterTimeEphemeral)
            return
    
        # Fix IGT and RTA with missing zero in hour place
        if len(igt.split(':')) == 2:
            igt = "0:" + igt
    
        if rta is not None and len(rta.split(':')) == 2:
            rta = "0:" + rta
    
        submission = self.getSubmission(race_id, user_id)
        if submission is None:
            # Create a brand new submission
            submission = AsyncSubmission(race_id= race_id, user_id= user_id, username= interaction.user.name, finish_time_igt= igt, collection_rate= cr_int, finish_time_rta=rta, comment=comment, next_mode=next_mode)
        else:
            # Update the fields of the existing submission
            submission.finish_time_igt= igt
            submission.collection_rate= cr_int
            submission.finish_time_rta=rta
            submission.comment=comment
            submission.next_mode=next_mode

        submission.submit_date = datetime.now().isoformat(timespec='minutes').replace('T', ' ')
        submission.save()
        await interaction.send("Submission complete", ephemeral=True, delete_after=DeleteAfterTimeEphemeral)
    
        # Finally update the leaderboard if this is for the current weekly async
        if race_id == self.queryLatestWeeklyRaceId():
            await self.updateLeaderboardMessage(race_id, interaction.guild)

    ########################################################################################################################
    # Shows info for a given race
    async def show_race_info(self, interaction, race_id):
        response_obj = interaction
        if race_id is None:
            race_id = await self.getRaceIdSelection(interaction)
            if race_id is None:
                interaction.followup.send("Race select timeout, be quicker next time", ephemeral=True)
            response_obj = interaction.followup

        if race_id is not None:
            try:
                race = AsyncRace.select()                       \
                                .where(AsyncRace.id == race_id) \
                                .get()
            except:
                race = None
            if race is None:
                response_obj.send(f"No race found for ID {race_id}", ephemeral=True)
            else:
                message = self.getRaceInfoTable(race)
                await response_obj.send(message, embed=self.getSeedEmbed(race))
                race_info_view = AsyncHandler.RaceInfoButtonView(self, race_id)
                await response_obj.send(view=race_info_view)

########################################################################################################################
# DASH
########################################################################################################################
    @commands.command(name="dash")
    @commands.check(isBotCommandChannel)
    async def dash(self, ctx: commands.Context):
        ''' Go ahead, see what happens when you try to go fast'''
        logging.info('Executing $dash command')
        await ctx.send("!!!!BONK!!!!")
        #self.checkAddMember(ctx.author)
        #mod_channel = ctx.guild.get_channel(self.server_info.modchat_channel)
        #await mod_channel.send(f"Get me out of this place! {PoopEmoji}")

        ##### CMC Prototype View/Button code ########
        #class ViewWithButton(nextcord.ui.View):
        #    self.submit = SubmitTime()
        #    @nextcord.ui.button(style=nextcord.ButtonStyle.blurple, label='Go Fast!')
        #    async def click_me_button(self, button: nextcord.ui.Button, interaction: nextcord.Interaction):
        #        sent_modal = await interaction.response.send_modal(self.submit)
        #        # Wait for an interaction to be given back
        #        interaction: nextcord.Interaction = await self.bot.wait_for(
        #            "modal_submit", 
        #            check=lambda i: i.data['custom_id'] == sent_modal.custom_id,
        #        )
        #
        #await ctx.send("See what happens when you try to go fast", view=ViewWithButton())
        #### CMC Prototype View/Button code ########

########################################################################################################################
# SHOW_RACES
########################################################################################################################
    @nextcord.slash_command(guild_ids=[BttServerInfo.server_id], description="Add Async Race")
    async def show_races(self,
                         interaction,
                         page: int = nextcord.SlashOption(description="Page number to display", required=False, min_value=1),
                         user: nextcord.User = nextcord.SlashOption(description="User to view races for", required=False)):
        
        logging.info('Executing $my_races command')
        if user is None:
            user = interaction.user
        if page is None:
            page = 1
        self.checkAddMember(user)
        await self.show_races_impl(interaction, page, user.id)

########################################################################################################################
# LEADERBOARD
########################################################################################################################
    @nextcord.slash_command(guild_ids=[BttServerInfo.server_id], description="Show Race Leaderboard")
    async def leaderboard(self,
                          interaction,
                          race_id: int = nextcord.SlashOption(
                            name="race_id",
                            description="Race ID to view leaderboard of",
                            required=False,
                            min_value=1)):

        logging.info('Executing leaderboard command')
        self.checkAddMember(interaction.user)
        await self.leaderboard_impl(interaction, race_id)

########################################################################################################################
# RACES
########################################################################################################################
    @commands.command()
    @commands.check(isBotCommandChannel)
    async def races(self, ctx: commands.Context, category: int=1, page: int=1):
        ''' 
        Displays the list of async race, sorted by most recent

            Optional Parameters:
                start - By default the command will show the 5 most recent races. To view older races provide a starting point.
                        For example the command `$races 11` would show the 11th-15th most recent races.
        '''
        logging.info('Executing $races command')
        self.checkAddMember(ctx.author)
        is_race_creator_channel = await isRaceCreatorCommandChannel(ctx)

        races = None
        if is_race_creator_channel:
            races = AsyncRace.select()                                 \
                             .where(AsyncRace.category_id == category) \
                             .order_by(AsyncRace.id.desc())            \
                             .paginate(page, ItemsPerPage)
        else:
            races = AsyncRace.select()                                                            \
                             .where(AsyncRace.category_id == category & AsyncRace.active == True) \
                             .order_by(AsyncRace.id.desc())                                       \
                             .paginate(page, ItemsPerPage)
        
        if races is not None and len(races) > 0:
            self.resetPrettyTable()
            
            if is_race_creator_channel:
                self.pt.field_names = ["ID", "Start Date", "Mode", "Active"]
            else:
                self.pt.field_names = ["ID", "Start Date", "Mode"]

            self.pt._max_width = {"Mode": 50}
            self.pt.align["Mode"] = "l"

            for race in races:
                if is_race_creator_channel:
                    self.pt.add_row([race.id, race.start, race.description, race.active])
                else:
                    self.pt.add_row([race.id, race.start, race.description])
            table_message_list = self.buildResponseMessageList(self.pt.get_string())
            message = None
            for table_message in table_message_list:
                message = await ctx.send("`{}`".format(table_message))
            if message is not None:
                if await self.userReactNextPage(ctx, message):
                    await self.races(ctx, category, (page+1))

        else:
            await ctx.send("No races found in that range")

########################################################################################################################
# WEEKLY_ASYNC_INFO
########################################################################################################################
    @nextcord.slash_command(guild_ids=[BttServerInfo.server_id], description="Show info for past weekly async races")
    async def weekly_async_info(self,
                                interaction,
                                race_id: int = nextcord.SlashOption(
                                  description="Race ID to view leaderboard of",
                                  required=False,
                                  min_value=1)):
        logging.info("Executing weekly_async_info command")
        self.checkAddMember(interaction.user)
        await self.show_race_info(interaction, race_id)

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
        race = self.get_race(race_id)
        is_race_creator_channel = await isRaceCreatorCommandChannel(ctx)
        table_message_list = self.getRaceInfoTable(race)
        if table_message_list is not None:
            for table_message in table_message_list:
                await ctx.send("`{}`".format(table_message))
            await ctx.send(embed=self.getSeedEmbed(race))
        else:
            await ctx.send("Race ID was not found")

########################################################################################################################
########################################################################################################################
######################    RACE CREATOR COMMANDS    #####################################################################
########################################################################################################################
########################################################################################################################

########################################################################################################################
# ADD_RACE
########################################################################################################################
    @nextcord.slash_command(guild_ids=[BttServerInfo.server_id], description="Add Async Race")
    async def add_race(
        self,
        interaction,
        is_active: int = nextcord.SlashOption(description="Make the race active immediately?", choices={"Yes": 1, "No": 0})):

        logging.info('Executing add_race command')

        if self.isRaceCreator(interaction.guild, interaction.user):
            add_race_modal = AsyncHandler.AddRaceModal(self)
            add_race_view = AsyncHandler.AddRaceView(add_race_modal)
            await interaction.send(view=add_race_view, ephemeral=True)

            sleep_counter = 0
            while(not add_race_modal.is_done and sleep_counter < AddRaceTimeout):
                await asyncio.sleep(1)
                sleep_counter += 1
                if sleep_counter > SelectTimeout:
                    if add_race_view.category_id == 0:
                        await interaction.delete_original_message()
                        await interaction.followup().send("Selection timeout, be quicker next time", ephemeral=True)
                        return

            if add_race_modal.is_done:
                start_date = None
                if is_active:
                    start_date = date.today().isoformat()
                # Add the race with the provided info. Currently all are set to the weekly category and inactive
                new_race = AsyncRace(
                    seed = add_race_modal.seed.value,
                    description = add_race_modal.mode.value,
                    additional_instructions = add_race_modal.instructions.value,
                    category_id = add_race_view.category_id,
                    active = is_active,
                    start=start_date)
                new_race.save()
                await interaction.followup.send(f"Added race ID: {new_race.id}", ephemeral=True)
        else:
            await interaction.send("You do not have permissions to use this command", ephemeral=True)

########################################################################################################################
# EDIT_RACE
########################################################################################################################
    @commands.command()
    @commands.check(isRaceCreatorCommandChannel)
    @commands.has_any_role(FortyBonksServerInfo.race_creator_role, BttServerInfo.race_creator_role)
    async def edit_race(self, ctx: commands.Context, race_id: int):
        ''' 
        Edits an async race with the given race_id
    
            Required Parameters:
                race_id - ID of the race being edited.
        '''
        logging.info('Executing $edit_race command')
        race = self.get_race(race_id)
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
            if edit_choice == 1:
                new_value_question = f"Current value is \n{race.seed}\nWhat's the new value?"
                value_msg = await self.ask(ctx, new_value_question, checkSameAuthor)
                if value_msg is None: return
                race.seed = value_msg
                race.save()
                await ctx.send(f"Updated race {race_id}")
            elif edit_choice == 2:
                new_value_question = f"Current value is \n{race.description}\nWhat's the new value?"
                value_msg = await self.ask(ctx, new_value_question, checkSameAuthor)
                if value_msg is None: return
                race.description = value_msg
                race.save()
                await ctx.send(f"Updated race {race_id}")
            elif edit_choice == 3:
                new_value_question = f"Current value is \n{race.additional_instructions}\nWhat's the new value?"
                value_msg = await self.ask(ctx, new_value_question, checkSameAuthor)
                if value_msg is None: return
                race.additional_instructions = value_msg
                race.save()
                await ctx.send(f"Updated race {race_id}")


########################################################################################################################
# START_RACE
########################################################################################################################
    @commands.command()
    @commands.check(isRaceCreatorCommandChannel)
    @commands.has_any_role(FortyBonksServerInfo.race_creator_role, BttServerInfo.race_creator_role)
    async def start_race(self, ctx: commands.Context, race_id: int):
        ''' 
        Starts an async race with the given race_id, making it active and avaiable for submissions
    
            Required Parameters:
                race_id - ID of the race being started.
        '''
        logging.info('Executing $start_race command')
        race = self.get_race(race_id)
        if race is not None and race.active:
            await ctx.send(f'Race ID {race.id} was already started on {race.start}')
            await self.updateWeeklyModeMessage(race)
        else:
            start_date = date.today().isoformat()
            logging.info("Start Date: {}".format(start_date))
            race.start = start_date
            race.active = True
            race.save()
            await ctx.send(f'Started race {race.id}')
            if race.category_id == self.weekly_category_id:
                await self.updateWeeklyModeMessage(race)
                await self.updateLeaderboardMessage(race.id, ctx.guild)
                await self.removeWeeklyAsyncRole(ctx)
                await self.post_annoucement(race, ctx)

########################################################################################################################
# REMOVE_RACE
########################################################################################################################
    @commands.command()
    @commands.check(isRaceCreatorCommandChannel)
    @commands.has_any_role(FortyBonksServerInfo.race_creator_role, BttServerInfo.race_creator_role)
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
        race = self.get_race(race_id)
        if race is not None:
            # Check first to see if there are any submissions to this race
            
            try:
                submissions = AsyncSubmission.select().where(AsyncSubmission.race_id == race.id).get()
            except:
                submissions = None
            if submissions is not None:
                await ctx.send("This race has user submissions and cannot be removed via command, please contact the bot overlord to remove it.")
            else:
                await ctx.send(f'Removing race {race.id}')
                confirm_question = "Are you sure you want to remove this race? This cannot be undone. Reply Yes or No"
                msg = await self.ask(ctx, confirm_question, checkYesNo)
                if msg is None: return
                if msg.lower() == "yes":
                    race.delete_instance()
                    await ctx.send(f"Race {race_id} removed")
                else:
                    await ctx.send("Remove cancelled")
        else:
            ctx.send(f"Race ID {race_id} does not exist", delete_after=DeleteAfterTime)

########################################################################################################################
# WHEEL_INFO
########################################################################################################################
    @commands.command()
    @commands.check(isRaceCreatorCommandChannel)
    @commands.has_any_role(FortyBonksServerInfo.race_creator_role, BttServerInfo.race_creator_role)
    async def wheel_info(self, ctx: commands.Context):
        ''' 
        Prints the current wheel info, this will be a list of all users who have raced in one or both of the two most recent
        weekly asyncs and will include their most recent mode suggestion and their wheel weight.
        '''
        logging.info('Executing $wheel_info command')
        racers = AsyncRacer.select()
        # Query the most recent weekly races
        recent_races = AsyncRace.select()                                                                               \
                                .where((AsyncRace.category_id == self.weekly_category_id) & (AsyncRace.active == True)) \
                                .order_by(AsyncRace.start.desc())

        wheel_list = ["*Name* > *Mode*\n"]
        for r in racers:
            # Query mode suggestions for this user, we will query each of the two most recent weekly async races. If the user has not completed
            # either async then the query will return None
            try:
                submission1 = AsyncSubmission.select()                                                                                        \
                                             .where((AsyncSubmission.race_id == recent_races[0].id) & (AsyncSubmission.user_id == r.user_id)) \
                                             .get()
            except:
                submission1 = None
            try:
                submission2 = AsyncSubmission.select()                                                                                        \
                                             .where((AsyncSubmission.race_id == recent_races[1].id) & (AsyncSubmission.user_id == r.user_id)) \
                                             .get()
            except:
                submission2 = None
            if submission1 is not None and submission1.next_mode is not None:
                next_mode_str = submission1.next_mode.strip().replace('\n', ' ')
                if next_mode_str != "None":
                    wheel_list.append(f"{r.username} > {next_mode_str}")

            if submission2 is not None and submission2.next_mode is not None:
                next_mode_str = submission2.next_mode.strip().replace('\n', ' ')
                if next_mode_str != "None":
                    wheel_list.append(f"{r.username} > {next_mode_str}")

        await ctx.send('\n'.join(wheel_list))

########################################################################################################################
# MOD_UTIL
########################################################################################################################
    @commands.command(hidden=True)
    @commands.check(isRaceCreatorCommandChannel)
    @commands.has_any_role(FortyBonksServerInfo.race_creator_role, BttServerInfo.race_creator_role)
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
            await self.updateLeaderboardMessage(self.queryLatestWeeklyRaceId(), ctx.guild)
            await ctx.send("Updated weekly leaderboard channel")
        elif function == 2:
            race = self.get_race(race_id)
            await self.updateWeeklyModeMessage(race)
            await ctx.send("Updated weekly mode message in submit channel")
        elif function == 3:
            self.replace_poop_with_tp = not self.replace_poop_with_tp
            await ctx.send("Toilet paper replacement is now {}".format("Enabled" if self.replace_poop_with_tp else "Disabled"))

########################################################################################################################
# EDIT_SUBMISSION
########################################################################################################################
    @commands.command(hidden=True)
    @commands.check(isRaceCreatorCommandChannel)
    @commands.has_any_role(FortyBonksServerInfo.race_creator_role, BttServerInfo.race_creator_role)
    async def edit_submission(self, ctx: commands.Context, submission_id: int):
        ''' 
        Edits a submission on behalf of a user

            Required Parameter:
                submission_id - ID of the submission to edit
        '''
        logging.info('Executing $edit_submission command')
        submission_to_edit = AsyncSubmission.select().where(AsyncSubmission.id == submission_id).get()
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
            submission_to_edit.finish_time_igt = parts[0]
            submission_to_edit.collection_rate = parts[1]
            if len(parts) == 3 and self.game_time_is_valid(parts[2]):
                submission_to_edit.finish_time_rta = parts[2]

            submission_to_edit.save()
            await ctx.send(f"Updated submission ID {submission_id}")

########################################################################################################################
# ON_MESSAGE
########################################################################################################################
    @commands.Cog.listener("on_message")
    async def message_handler(self, message):
        if message.author == self.bot.user:
            return

        if "pendant pod" in message.content.lower():
            logging.info("adding pendant pod emoji")
            guild = self.bot.get_guild(self.server_info.server_id)
            emoji = None
            for e in guild.emojis:
                if str(e) == PendantPodEmoteStr:
                    emoji = e
            if emoji is not None:
                await message.add_reaction(emoji)

########################################################################################################################
# STARTUP and SHUTDOWN
########################################################################################################################
    @commands.Cog.listener("on_ready")
    async def on_ready_handler(self):
        logging.info("Async Handler Ready")
        if self.test_mode:
            logging.info("  Running in test mode")
        await self.addSubmitButtons()

    async def close(self):
        logging.info("Shutting down Async Handler")
        await self.removeWeeklySubmitButtons()

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
