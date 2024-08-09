from datetime import datetime, timedelta
from enum import Enum
from typing import Optional, List
from config import Config

class UserState(Enum):
    OFFLINE = "OFFLINE"
    ONLINE = "ONLINE"
    WORKING = "WORKING"
    SHORT_BREAK = "SHORT_BREAK"
    ON_BREAK_LUNCH = "ON_BREAK_LUNCH"
    EXTENDED_BREAK = "EXTENDED_BREAK"
    UNAUTHORIZED_ABSENCE = "UNAUTHORIZED_ABSENCE"
    OVERTIME = "OVERTIME"
    HOLIDAY_WORK = "HOLIDAY_WORK"
    RETURNING_FROM_BREAK = "RETURNING_FROM_BREAK"

class BreakType(Enum):
    SHORT_BREAK = "SHORT_BREAK"
    EXTENDED_BREAK = "EXTENDED_BREAK"
    ON_BREAK_LUNCH = "ON_BREAK_LUNCH"

class BreakLog:
    def __init__(self, user_id: int, break_type: BreakType, start_time: datetime, end_time: datetime = None):
        self.user_id = user_id
        self.break_type = break_type
        self.start_time = start_time
        self.end_time = end_time
        self.excess_time = timedelta()

    def end_break(self, end_time: datetime):
        self.end_time = end_time
        if self.break_type == BreakType.ON_BREAK_LUNCH:
            standard_duration = timedelta(minutes=Config.MAX_LUNCH_DURATION)
        elif self.break_type == BreakType.SHORT_BREAK:
            standard_duration = timedelta(minutes=Config.BREAK_DURATION)
        else:  # EXTENDED_BREAK
            standard_duration = timedelta(minutes=Config.MAX_EXTENDED_BREAK_DURATION)
        actual_duration = self.get_duration()
        if actual_duration > standard_duration:
            self.excess_time = actual_duration - standard_duration

    def get_duration(self) -> timedelta:
        if self.end_time:
            return self.end_time - self.start_time
        return timedelta()

    def is_excess(self) -> bool:
        return self.excess_time > timedelta()

    def __str__(self):
        return f"BreakLog(user_id={self.user_id}, type={self.break_type.value}, start={self.start_time}, end={self.end_time}, duration={self.get_duration()}, excess={self.excess_time})"

class User:
    def __init__(self, id: int, name: str, full_name: str, surname: str, email: str, 
                 remote: bool, role: str, dept: str, admin: bool, state: str, 
                 discord_id: Optional[str] = None, jira_id: Optional[str] = None):
        # Basic user information
        self.id = id
        self.name = name
        self.full_name = full_name
        self.surname = surname
        self.email = email
        self.remote = remote
        self.role = role
        self.dept = dept
        self.admin = admin
        self.discord_id = discord_id
        self.jira_id = jira_id

        # Work state and timing
        self.state = UserState(state)
        self.check_in_time = None
        self.check_out_time = None
        self.daily_work_time = timedelta()
        self.weekly_work_time = timedelta()
        self.is_overtime = False
        self.is_holiday_work = False

        # Break tracking
        self.break_logs: List[BreakLog] = []
        self.current_break: Optional[BreakLog] = None

        # Absence tracking
        self.total_absence_time = timedelta()
        self.last_state_change_time = datetime.now()

    # Work-related methods
    def check_in(self, time: datetime):
        self.check_in_time = time

    def check_out(self, time: datetime):
        self.check_out_time = time

    def start_work(self, current_time: datetime, is_holiday: bool = False) -> bool:
        if self.state == UserState.OFFLINE:
            self.state = UserState.HOLIDAY_WORK if is_holiday else UserState.WORKING
            self.check_in(current_time)
            self.is_holiday_work = is_holiday
            return True
        return False

    def end_work(self, current_time: datetime) -> bool:
        if self.state != UserState.OFFLINE:
            self.check_out(current_time)
            work_duration = current_time - self.check_in_time if self.check_in_time else timedelta()
            self.daily_work_time += work_duration
            self.weekly_work_time += work_duration
            self.reset_daily_attributes()
            return True
        return False

    def calculate_total_work_time(self, current_time: datetime) -> timedelta:
        return current_time - self.check_in_time if self.check_in_time else timedelta()

    def calculate_effective_work_time(self, current_time: datetime) -> timedelta:
        total_time = self.calculate_total_work_time(current_time)
        return total_time - self.get_total_break_time() - self.total_absence_time

    # Break-related methods
    def start_break(self, break_type: BreakType, start_time: datetime):
        self.current_break = BreakLog(self.id, break_type, start_time)
        self.break_logs.append(self.current_break)

    def end_break(self, end_time: datetime):
        if self.current_break:
            self.current_break.end_break(end_time)
            self.current_break = None

    def get_total_break_time(self) -> timedelta:
        return sum((log.get_duration() for log in self.break_logs), timedelta())

    def get_total_excess_break_time(self) -> timedelta:
        return sum((log.excess_time for log in self.break_logs), timedelta())

    # Overtime methods
    def start_overtime(self) -> bool:
        if self.state == UserState.WORKING:
            self.state = UserState.OVERTIME
            self.is_overtime = True
            return True
        return False

    def end_overtime(self) -> bool:
        if self.state == UserState.OVERTIME:
            self.state = UserState.WORKING
            self.is_overtime = False
            return True
        return False

    # Absence-related method
    def calculate_absence_time(self, current_time: datetime) -> timedelta:
        if self.last_state_change_time:
            absence_duration = current_time - self.last_state_change_time
            self.total_absence_time += absence_duration
            self.last_state_change_time = current_time
        return self.total_absence_time

    # Reset methods
    def reset_daily_attributes(self):
        self.state = UserState.OFFLINE
        self.check_in_time = None
        self.check_out_time = None
        self.break_logs = []
        self.current_break = None
        self.last_state_change_time = datetime.now()
        self.daily_work_time = timedelta()
        self.is_overtime = False
        self.is_holiday_work = False
        self.total_absence_time = timedelta()

    def reset_weekly_attributes(self):
        self.weekly_work_time = timedelta()

    # Class method for database operations
    @classmethod
    def from_db_row(cls, row):
        id, jira_id, discord_id, full_name, name, surname, email, remote, role, dept, admin, state = row
        return cls(
            id=id, name=name, full_name=full_name, surname=surname, email=email,
            remote=bool(remote), role=role, dept=dept, admin=bool(admin), state=state,
            discord_id=discord_id if discord_id else None,
            jira_id=jira_id if jira_id else None
        )