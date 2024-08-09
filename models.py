from datetime import datetime, timedelta
from enum import Enum

class UserState(Enum):
    OFFLINE = "OFFLINE"
    ONLINE = "ONLINE"
    WORKING = "WORKING"
    SHORT_BREAK = "SHORT_BREAK"
    LUNCH_BREAK = "LUNCH_BREAK"
    EXTENDED_BREAK = "EXTENDED_BREAK"
    UNAUTHORIZED_ABSENCE = "UNAUTHORIZED_ABSENCE"
    OVERTIME = "OVERTIME"
    HOLIDAY_WORK = "HOLIDAY_WORK"

class User:
    def __init__(self, id, name, full_name, surname, email, remote, role, dept, admin, state, discord_id=None, jira_id=None):
        self.id = id
        self.name = name
        self.jira_id = jira_id
        self.discord_id = discord_id
        self.full_name = full_name
        self.surname = surname
        self.email = email
        self.remote = remote
        self.role = role
        self.dept = dept
        self.admin = admin
        self.state = UserState(state)
        self.work_start = None
        self.current_break_start = None
        self.is_mobile = False
        self.total_mobile_time = timedelta()
        self.total_pc_time = timedelta()
        self.last_state_change_time = datetime.now()
        self.usage_log_id = None
        self.has_taken_lunch_break = False
        self.daily_work_time = timedelta()
        self.weekly_work_time = timedelta()
        self.is_overtime = False
        self.is_holiday_work = False

    def start_work(self, current_time, is_holiday=False):
        if self.state == UserState.OFFLINE:
            self.state = UserState.HOLIDAY_WORK if is_holiday else UserState.WORKING
            self.work_start = current_time
            self.is_holiday_work = is_holiday
            return True
        return False

    def end_work(self, current_time):
        if self.state != UserState.OFFLINE:
            work_duration = current_time - self.work_start if self.work_start else timedelta()
            self.daily_work_time += work_duration
            self.weekly_work_time += work_duration
            self.reset_daily_attributes()
            return True
        return False

    def start_overtime(self):
        if self.state == UserState.WORKING:
            self.state = UserState.OVERTIME
            self.is_overtime = True
            return True
        return False

    def end_overtime(self):
        if self.state == UserState.OVERTIME:
            self.state = UserState.WORKING
            self.is_overtime = False
            return True
        return False

    def reset_daily_attributes(self):
        self.state = UserState.OFFLINE
        self.work_start = None
        self.current_break_start = None
        self.is_mobile = False
        self.total_mobile_time = timedelta()
        self.total_pc_time = timedelta()
        self.last_state_change_time = datetime.now()
        self.usage_log_id = None
        self.has_taken_lunch_break = False
        self.daily_work_time = timedelta()
        self.is_overtime = False
        self.is_holiday_work = False

    def reset_weekly_attributes(self):
        self.weekly_work_time = timedelta()

    def get_current_work_duration(self, current_time):
        if self.work_start:
            return current_time - self.work_start
        return timedelta()

    def get_current_break_duration(self, current_time):
        if self.current_break_start:
            return current_time - self.current_break_start
        return timedelta()

class BreakLog:
    def __init__(self, user_id, break_type, start_time, end_time):
        self.user_id = user_id
        self.break_type = break_type
        self.start_time = start_time
        self.end_time = end_time

    def get_duration(self):
        if self.end_time:
            return self.end_time - self.start_time
        return None