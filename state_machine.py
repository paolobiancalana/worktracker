from enum import Enum

class UserState(Enum):
    OFFLINE = 0
    WORKING = 1
    SHORT_BREAK = 2
    LUNCH_BREAK = 3
    EXTENDED_BREAK = 4
    AFTER_HOURS = 5
    ON_LEAVE = 6