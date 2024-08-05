import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
    GUILD_ID = os.getenv('GUILD_ID')
    WORK_START_TIME = "08:00"
    WORK_END_TIME = "19:00"
    LUNCH_START_TIME = "12:45"
    LUNCH_END_TIME = "14:30"
    BREAK_DURATION = 15  # in minutes
    DISCORD_IDLE_TIME = 5  # in minutes
    SYNC_INTERVAL = 300  # in seconds
    TESTING = os.getenv('TESTING', 'False').lower() == 'true'
    TEST_USER_DISCORD_ID = os.getenv('TEST_USER_DISCORD_ID')
    SIMULATE_WORK_HOURS = os.getenv('SIMULATE_WORK_HOURS', 'False').lower() == 'true'