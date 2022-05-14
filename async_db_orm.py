from peewee import *

class RaceCategory(Model):
    id = IntegerField(primary_key=True)
    name = CharField()
    description = CharField()

    class Meta:
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
        table_name = 'async_races'

class AsyncRacer(Model):
    user_id = IntegerField(primary_key=True)
    username = CharField()
    wheel_weight = IntegerField()

    class Meta:
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
        table_name = 'async_submissions'

def format_igt_substr(igt):
    ret_str = '0'
    if igt is not None:
        ret_str = igt[-8:]
    return ret_str

def collate_igt(s1, s2):
    if s1 is None:
        s1 = '0:00:00'
    if s2 is None:
        s2 = '0:00:00'

    parts1 = s1.split(':')
    parts2 = s2.split(':')

    cmp = (parts1[0] > parts2[0]) - (parts1[0] < parts2[0])
    if cmp == 0:
        cmp = (parts1[1] > parts2[1]) - (parts1[1] < parts2[1])
    if cmp == 0:
        cmp = (parts1[2] > parts2[2]) - (parts1[2] < parts2[2])
    return cmp