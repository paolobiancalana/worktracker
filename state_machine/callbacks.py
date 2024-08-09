from datetime import datetime, timedelta, time
from models import User, UserState
from config import Config
from logger import logger

def log_state_transition(user: User, previous_state: UserState, new_state: UserState, current_time: datetime) -> None:
    logger.info(f"{user.name}: {previous_state.value} -> {new_state.value} at {current_time}")
    user.state = new_state
    user.last_state_change_time = current_time

def log_start_work(user: User, current_time: datetime, new_state: UserState, mapped_status: str) -> None:
    log_state_transition(user, user.state, new_state, current_time)
    user.work_start = current_time
    logger.info(f"Started work for {user.name} at {current_time} with status {mapped_status}")

def log_end_work(user: User, current_time: datetime, new_state: UserState, mapped_status: str) -> None:
    log_state_transition(user, user.state, new_state, current_time)
    if user.work_start:
        work_duration = current_time - user.work_start
        logger.info(f"Ended work for {user.name}. Work duration: {work_duration}")
    user.end_work(current_time)

def log_start_break(user: User, current_time: datetime, new_state: UserState, mapped_status: str) -> None:
    log_state_transition(user, user.state, new_state, current_time)
    user.current_break_start = current_time
    logger.info(f"Started break for {user.name} at {current_time} with status {mapped_status}")

def log_end_break(user: User, current_time: datetime, new_state: UserState, mapped_status: str) -> None:
    log_state_transition(user, user.state, new_state, current_time)
    if user.current_break_start:
        break_duration = current_time - user.current_break_start
        logger.info(f"Ended break for {user.name}. Break duration: {break_duration}")
    user.current_break_start = None

def log_start_overtime(user: User, current_time: datetime, new_state: UserState, mapped_status: str) -> None:
    log_state_transition(user, user.state, new_state, current_time)
    user.start_overtime()
    logger.info(f"Started overtime for {user.name} at {current_time} with status {mapped_status}")

def log_end_overtime(user: User, current_time: datetime, new_state: UserState, mapped_status: str) -> None:
    log_state_transition(user, user.state, new_state, current_time)
    user.end_overtime()
    logger.info(f"Ended overtime for {user.name} at {current_time}")

def log_start_holiday_work(user: User, current_time: datetime, new_state: UserState, mapped_status: str) -> None:
    log_state_transition(user, user.state, new_state, current_time)
    user.start_work(current_time, is_holiday=True)
    logger.info(f"Started holiday work for {user.name} at {current_time} with status {mapped_status}")

def log_unauthorized_absence(user: User, current_time: datetime, new_state: UserState, mapped_status: str) -> None:
    log_state_transition(user, user.state, new_state, current_time)
    logger.warning(f"Unauthorized absence detected for {user.name} at {current_time} with status {mapped_status}")

# Condition functions

def is_work_time(user: User, current_time: datetime, mapped_status: str) -> bool:
    if isinstance(current_time, str):
        current_time = datetime.fromisoformat(current_time)
    work_start = datetime.combine(current_time.date(), datetime.strptime(Config.WORK_START_TIME, "%H:%M").time())
    work_end = datetime.combine(current_time.date(), datetime.strptime(Config.WORK_END_TIME, "%H:%M").time())
    is_work_time = work_start <= current_time <= work_end and mapped_status == 'WORKING'
    logger.debug(f"is_work_time for {user.name} at {current_time} with status {mapped_status}: {is_work_time}")
    return is_work_time

def is_lunch_time(user: User, current_time: datetime, mapped_status: str = None) -> bool:
    if isinstance(current_time, str):
        current_time = datetime.fromisoformat(current_time)
    lunch_start = datetime.combine(current_time.date(), datetime.strptime(Config.LUNCH_START_TIME, "%H:%M").time())
    lunch_end = datetime.combine(current_time.date(), datetime.strptime(Config.LUNCH_END_TIME, "%H:%M").time())
    is_lunch = lunch_start <= current_time < lunch_end
    logger.debug(f"is_lunch_time for {user.name} at {current_time}: {is_lunch}")
    return is_lunch

def is_break_time(user: User, current_time: datetime, mapped_status: str) -> bool:
    if isinstance(current_time, str):
        current_time = datetime.fromisoformat(current_time)
    is_break = is_work_time(user, current_time, 'WORKING') and mapped_status == 'SHORT_BREAK'
    logger.debug(f"is_break_time for {user.name} at {current_time} with status {mapped_status}: {is_break}")
    return is_break

def break_exceeded(user: User, current_time: datetime, mapped_status: str = None) -> bool:
    if isinstance(current_time, str):
        current_time = datetime.fromisoformat(current_time)
    if user.current_break_start:
        break_duration = current_time - user.current_break_start
        exceeded = break_duration > timedelta(minutes=Config.BREAK_DURATION)
        logger.debug(f"break_exceeded for {user.name} at {current_time}: {exceeded}")
        return exceeded
    return False

def idle_time_exceeded(user: User, current_time: datetime, mapped_status: str = None) -> bool:
    if isinstance(current_time, str):
        current_time = datetime.fromisoformat(current_time)
    if user.last_state_change_time:
        idle_duration = current_time - user.last_state_change_time
        exceeded = idle_duration > timedelta(minutes=Config.IDLE_BUFFER_TIME)
        logger.debug(f"idle_time_exceeded for {user.name} at {current_time}: {exceeded}")
        return exceeded
    return False

def is_overtime(user: User, current_time: datetime, mapped_status: str = None) -> bool:
    if isinstance(current_time, str):
        current_time = datetime.fromisoformat(current_time)
    if user.work_start:
        work_duration = current_time - user.work_start
        return work_duration > timedelta(hours=Config.REGULAR_WORK_HOURS)
    return False

def is_regular_work(user: User, current_time: datetime, mapped_status: str = None) -> bool:
    if isinstance(current_time, str):
        current_time = datetime.fromisoformat(current_time)
    if user.work_start:
        work_duration = current_time - user.work_start
        return timedelta(hours=Config.REGULAR_WORK_HOURS) >= work_duration > timedelta()
    return False

def is_holiday_or_weekend(current_time: datetime, mapped_status: str = None) -> bool:
    if isinstance(current_time, str):
        current_time = datetime.fromisoformat(current_time)
    holiday_or_weekend = current_time.weekday() >= 5  # 5 is Saturday, 6 is Sunday
    logger.debug(f"is_holiday_or_weekend for {current_time}: {holiday_or_weekend}")
    return holiday_or_weekend

async def is_authorized_absence(user: User, current_time: datetime, mapped_status: str = None) -> bool:
    if isinstance(current_time, str):
        current_time = datetime.fromisoformat(current_time)
    if user.state != UserState.OFFLINE or mapped_status != 'OFFLINE':
        logger.debug(f"User {user.name} is not in OFFLINE state or client status is not OFFLINE")
        return False
    # Simulating the absence of leave permissions
    leave = False
    sick_leave = False
    work_permit = False

    if leave or sick_leave:
        logger.info(f"User {user.name} has an authorized leave or sick leave")
        return True
    
    if work_permit:
        # Normally, we'd check work_permit.start_time and work_permit.end_time
        pass
    offline_limit_time = datetime.combine(current_time.date(), time.fromisoformat(Config.CHECK_OFFLINE_LIMIT_TIME))
    unauthorized = current_time > offline_limit_time
    logger.warning(f"Unauthorized absence detected for user {user.name} after offline limit time: {unauthorized}")
    return not unauthorized

def is_not_work_time(user: User, current_time: datetime, mapped_status: str) -> bool:
    return not is_work_time(user, current_time, mapped_status)

async def is_unauthorized_absence(user: User, current_time: datetime, mapped_status: str = None) -> bool:
    return not await is_authorized_absence(user, current_time, mapped_status)

def map_status(status: str) -> str:
    status_mapping = Config.load_status_mapping()
    mapped_status = status_mapping.get(status, status).upper()
    logger.debug(f"Mapped Discord status '{status}' to '{mapped_status}'")
    return mapped_status
