from datetime import datetime
from state_machine import UserState

class User:
    def __init__(self, id, name, discord_id, full_name, surname, email, remote, role, dept, admin):
        self.id = id
        self.name = name
        self.discord_id = discord_id
        self.full_name = full_name
        self.surname = surname
        self.email = email
        self.remote = remote
        self.role = role
        self.dept = dept
        self.admin = admin
        self.state = UserState.OFFLINE
        self.work_start = None
        self.current_break_start = None
        self.is_mobile = False
        self.total_mobile_time = 0
        self.total_pc_time = 0
        self.last_state_change_time = datetime.now()
        self.usage_log_id = None
        self.has_taken_lunch_break = False

    def start_work(self):
        if self.state == UserState.OFFLINE:
            self.state = UserState.WORKING
            self.work_start = datetime.now()
            return True
        return False

    def start_break(self, break_type):
        if self.state == UserState.WORKING:
            self.state = break_type
            self.current_break_start = datetime.now()
            return True
        return False

    def end_break(self):
        if self.state in [UserState.SHORT_BREAK, UserState.LUNCH_BREAK, UserState.EXTENDED_BREAK]:
            self.state = UserState.WORKING
            self.current_break_start = None
            return True
        return False

    def end_work(self):
        if self.state != UserState.OFFLINE:
            self.reset_daily_attributes()
            return True
        return False
    
    def reset_daily_attributes(self):
        self.state = UserState.OFFLINE
        self.work_start = None
        self.current_break_start = None
        self.is_mobile = False
        self.total_mobile_time = 0
        self.total_pc_time = 0
        self.last_state_change_time = datetime.now()
        self.usage_log_id = None
        self.has_taken_lunch_break = False