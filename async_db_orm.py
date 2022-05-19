# -*- coding: utf-8 -*-
from peewee import *

class RaceCategory(Model):
    id = IntegerField(primary_key=True)
    name = CharField()
    description = CharField()

    class Meta:
        table_name = 'race_categories'

class AsyncRace(Model):
    id = IntegerField(primary_key= True)
    start = DateField()
    seed = CharField()
    description = CharField()
    additional_instructions = CharField()
    category_id = IntegerField()
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
    race_id = IntegerField()
    user_id = IntegerField()
    username = CharField()
    finish_time_rta = CharField(null=True)
    finish_time_igt = CharField()
    collection_rate = IntegerField()
    next_mode = CharField(null=True)
    comment = CharField(null=True)

    class Meta:
        table_name = 'async_submissions'
