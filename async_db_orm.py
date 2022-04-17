from peewee import *

db = SqliteDatabase('AsyncRaceInfo.db')

class RaceCategory(Model):
    id = IntegerField(primary_key=True)
    name = CharField()
    description = CharField()

    class Meta:
        database = db
        table_name = 'race_categories'

class AsyncRace(Model):
    id = IntegerField(primary_key= True)
    start = DateTimeField()
    seed = CharField()
    description = CharField()
    additional_instructions = CharField()
    category_id = ForeignKeyField(RaceCategory, backref='races')
    active = BooleanField(default=False)

    class Meta:
        database = db
        table_name = 'async_races'

class AsyncRacer(Model):
    user_id = IntegerField(primary_key=True)
    username = CharField()
    wheel_weight = IntegerField()

    class Meta:
        database = db
        table_name = 'async_racers'

class AsyncSubmission(Model):
    id = IntegerField(primary_key=True)
    submit_date = DateTimeField()
    race_id = ForeignKeyField(AsyncRace, backref='submissions')
    user_id = ForeignKeyField(AsyncRacer, backref='racers')
    username = CharField()
    finish_time_rta = CharField(null=True)
    finish_time_igt = CharField()
    collection_rate = IntegerField()
    next_mode = CharField(null=True)

    class Meta:
        database = db
        table_name = 'async_submissions'

def AddRaceCategory()