# Async DB Column Names and IDs
# race_categories columns
RACE_CATEGORY_ID = 0
RACE_CATEGORY_NAME = 1
RACE_CATEGORY_DESC = 2

# async_races columns
ASYNC_RACES_ID = 0
ASYNC_RACES_START = 1
ASYNC_RACES_SEED = 2
ASYNC_RACES_DESC = 3
ASYNC_RACES_ADDL_INSTRUCTIONS = 4
ASYNC_RACES_CATEGORY_ID = 5
ASYNC_RACES_ACTIVE = 6

# async races column names (can be indexed by column values above)
AsyncRacesColNames = ["id", "start", "seed", "description", "additional_instructions", "category_id", "active"]

# async_submissions columns
ASYNC_SUBMISSIONS_ID = 0
ASYNC_SUBMISSIONS_SUBMIT_DATE = 1
ASYNC_SUBMISSIONS_RACE_ID = 2
ASYNC_SUBMISSIONS_USERID = 3
ASYNC_SUBMISSIONS_USERNAME = 4
ASYNC_SUBMISSIONS_RTA = 5
ASYNC_SUBMISSIONS_IGT = 6
ASYNC_SUBMISSIONS_COLLECTION = 7
ASYNC_SUBMISSIONS_NEXT_MODE = 8
ASYNC_SUBMISSIONS_COMMENT = 9
#ASYNC_SUBMISSIONS_PARTNER = 11

# async_racers columns
ASYNC_RACERS_USERID = 0
ASYNC_RACERS_USERNAME = 1
ASYNC_RACERS_WHEEL_WEIGHT = 2;

CreateRaceCategoriesTableSql = '''
    CREATE TABLE IF NOT EXISTS race_categories (
    id INTEGER PRIMARY KEY NOT NULL,
    name TEXT,
    description TEXT
    );'''

CreateAsyncRacesTableSql = '''
CREATE TABLE IF NOT EXISTS async_races (
    id INTEGER PRIMARY KEY NOT NULL,
    start DATETIME,
    seed TEXT NOT NULL,
    description TEXT NOT NULL,
    additional_instructions TEXT,
    category_id INTEGER,
    active BOOLEAN DEFAULT 0
    );'''

CreateAsyncSubmissionsTableSql = '''
CREATE TABLE IF NOT EXISTS async_submissions (
    id INTEGER PRIMARY KEY NOT NULL,
    submit_date DATETIME,
    race_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    username TEXT,
    finish_time_rta TEXT,
    finish_time_igt TEXT NOT NULL,
    collection_rate INTEGER,
    partner TEXT,
    next_mode TEXT
    );'''

CreateAsyncRacersTableSql = '''
CREATE TABLE IF NOT EXISTS async_racers (
    user_id INTEGER PRIMARY KEY NOT NULL,
    username TEXT NOT NULL
    wheel_weight INTEGER DEFAULT 1
    );'''

# Adds a new race category
AddRaceCategorySql = '''
INSERT INTO race_categories
    (name, description)
VALUES
    ({});'''

# Adds a new racer
AddRacerSql = '''
INSERT INTO async_racers
    (user_id, username)
VALUES
    ({}, "{}");'''

# Query the category id for a specific race category name
QueryCategoryIdSql = '''
SELECT id FROM race_categories
WHERE name LIKE {};'''


# Map containing a field for each column added in AddAsyncRaceSql
AddAsyncRaceArgMap = {
    AsyncRacesColNames[ASYNC_RACES_START]             : None,
    AsyncRacesColNames[ASYNC_RACES_SEED]              : None,
    AsyncRacesColNames[ASYNC_RACES_DESC]              : None,
    AsyncRacesColNames[ASYNC_RACES_ADDL_INSTRUCTIONS] : None,
    AsyncRacesColNames[ASYNC_RACES_CATEGORY_ID]       : 1,
    AsyncRacesColNames[ASYNC_RACES_ACTIVE]            : 0
}

# Adds a new race, only includes the fields known at add time
AddAsyncRaceSql = '''
INSERT INTO async_races
    (seed, description, additional_instructions, category_id, active)
VALUES
    ("{}", "{}", {}, {}, {});'''

# Removes an async race
RemoveAsyncRaceSql = '''
DELETE FROM async_races
WHERE id={};'''

# Updates an existing async submission
UpdateAsyncSubmissionSql = '''
UPDATE async_submissions
SET submit_date="{}",
    finish_time_rta="{}",
    finish_time_igt="{}",
    collection_rate={},
    next_mode="{}",
    comment="{}"
WHERE id={};'''

# Adds a new async submission
AddAsyncSubmissionSql = '''
INSERT INTO async_submissions
    (submit_date, race_id, user_id, username, finish_time_rta, finish_time_igt, collection_rate, next_mode, comment)
VALUES
    ("{}", {}, {}, "{}", "{}", "{}", {}, "{}", "{}");'''

# Start a race. First parameter should be start date (in YYYY-MM-DD iso format), second parameter should be race_id
StartRaceSql = '''
UPDATE async_races
SET start = "{}",
    active = 1
WHERE id={};'''

# Update a race
UpdateRaceSql = '''
UPDATE async_races
SET seed = "{}",
    description = "{}",
    additional_instructions = "{}"
WHERE id={};'''

# Query 40_bonks asyncs, order by most recent, first parameter is category_id, second parameter is offset start (e.g. 0, 5, 10, etc)
QueryMostRecentFromCategorySql = '''
SELECT * FROM async_races 
WHERE category_id={}
ORDER BY id DESC
LIMIT 5 OFFSET {};'''

# Query Active 40_bonks asyncs, order by most recent, first parameter is category_id, second parameter is offset start (e.g. 0, 5, 10, etc)
QueryMostRecentActiveFromCategorySql = '''
SELECT * FROM async_races 
WHERE category_id={} AND active=1
ORDER BY start DESC
LIMIT 5 OFFSET {};'''

# Query a specific user submission by ID
QueryAsyncSubmissionByIdSql = '''
SELECT * FROM async_submissions
WHERE id={};'''

# Query user submissions. First parameter is user_id, second parameter is offset start (e.g. 0, 5, 10, etc)
QueryRecentUserSubmissionsSql = '''
SELECT * FROM async_submissions
WHERE user_id={}
ORDER BY submit_date DESC
LIMIT 5 OFFSET {};'''

# Query the leaderboard for a race.
QueryRaceLeaderboardSql = '''
SELECT * FROM async_submissions
WHERE race_id={}
ORDER BY time(substr('0' || finish_time_igt, -8, 8)) ASC;'''

# Query submissions for a specific race_id and user_id
QueryUserRaceSubmissions = '''
SELECT * FROM async_submissions
WHERE race_id={}
  AND user_id={};'''

# Count user submissions
QueryUserSubmissionsSql = '''
SELECT COUNT(*) FROM async_submissions
WHERE user_id={};'''

# Query race information for a specific race ID
QueryRaceInfoSql = '''
SELECT * FROM async_races
WHERE id={};'''

# Query active races
QueryActiveRacesSql = '''
SELECT * FROM async_races
WHERE active=1;'''

# Query the racer data for a specific user, paramter is user id
QueryRacerDataSql = '''
SELECT * from async_racers 
WHERE user_id={};'''

# Update racer wheel weight, first parameter is new wheel weight, second parameter is user id
UpdateWheelWeightSql = '''
UPDATE async_racers
SET wheel_weight={}
WHERE user_id={};'''

# Query async racer data (id, name, wheel_weight)
QueryAllRacerDataSql = '''
SELECT * FROM async_racers;'''

# Query the most recent mode suggestion for a racer, limited to the last 2 weekly asyncs. First parameter is user id,
# second parameter is the race id to search 
QueryModeSuggestionForWheel = '''
SELECT next_mode from async_submissions
WHERE user_id={}
  AND race_id={};'''

# Edit an async submission
#UPDATE async_submissions
#SET 
#WHERE id=<submission_id>

# Query 40 bonks weekly category ID
#SELECT id FROM race_categories WHERE name LIKE "40 Bonks Weekly"