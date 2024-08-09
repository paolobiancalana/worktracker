from logger import logger
from datetime import datetime, time, timedelta
from models import User, UserState, BreakLog, BreakType
from database import Database
from config import Config

# Funzioni di condizione

async def is_work_time(user: User, current_time: datetime, mapped_status: str, db: Database) -> bool:
    work_start = time_to_datetime(Config.WORK_START_TIME, current_time.date())
    work_end = time_to_datetime(Config.WORK_END_TIME, current_time.date())
    result = work_start <= current_time <= work_end
    logger.debug(f"is_work_time for {user.full_name} at {current_time} with status {mapped_status}: {result}")
    return result

async def is_lunch_time(user: User, current_time: datetime, mapped_status: str, db: Database) -> bool:
    if user.has_taken_lunch_break:
        return False
    lunch_start = time_to_datetime(Config.LUNCH_START_TIME, current_time.date())
    lunch_end = time_to_datetime(Config.LUNCH_END_TIME, current_time.date())
    result = lunch_start <= current_time <= lunch_end or await is_buffer_time(user, current_time, mapped_status, db)
    logger.debug(f"is_lunch_time for {user.full_name} at {current_time} with status {mapped_status}: {result}")
    return result

async def is_break_time(user: User, current_time: datetime, mapped_status: str, db: Database) -> bool:
    is_work = await is_work_time(user, current_time, mapped_status, db)
    is_not_lunch = await is_not_lunch_time(user, current_time, mapped_status, db)
    result = is_work and is_not_lunch and mapped_status in ['SHORT_BREAK', 'IDLE']
    logger.debug(f"is_break_time for {user.full_name} at {current_time} with status {mapped_status}: {result}")
    return result

async def is_buffer_time(user: User, current_time: datetime, mapped_status: str, db: Database) -> bool:
    work_start = time_to_datetime(Config.WORK_START_TIME, current_time.date())
    work_end = time_to_datetime(Config.WORK_END_TIME, current_time.date())
    lunch_start = time_to_datetime(Config.LUNCH_START_TIME, current_time.date())
    lunch_end = time_to_datetime(Config.LUNCH_END_TIME, current_time.date())
    
    work_buffer_before = timedelta(hours=1)
    work_buffer_after = timedelta(hours=1)
    lunch_buffer_before = timedelta(minutes=Config.LUNCH_BUFFER_BEFORE)
    lunch_buffer_after = timedelta(minutes=Config.LUNCH_BUFFER_AFTER)
    
    is_work_buffer = (work_start - work_buffer_before) <= current_time < work_start or work_end < current_time <= (work_end + work_buffer_after)
    is_lunch_buffer = (lunch_start - lunch_buffer_before) <= current_time < lunch_start or lunch_end < current_time < (lunch_end + lunch_buffer_after)
    
    result = is_work_buffer or is_lunch_buffer
    logger.debug(f"is_buffer_time for {user.full_name} at {current_time}: {result}")
    return result

async def break_exceeded(user: User, current_time: datetime, mapped_status: str, db: Database) -> bool:
    if user.current_break_start:
        break_duration = current_time - user.current_break_start
        
        if break_duration > timedelta(minutes=Config.MAX_EXTENDED_BREAK_DURATION):
            excess_time = break_duration - timedelta(minutes=Config.MAX_EXTENDED_BREAK_DURATION)
            user.total_absence_time += excess_time
            logger.warning(f"{user.full_name} exceeded extended break by {excess_time}. Total absence time: {user.total_absence_time}")
            return True
        
        elif break_duration > timedelta(minutes=Config.BREAK_DURATION):
            excess_time = break_duration - timedelta(minutes=Config.BREAK_DURATION)
            logger.warning(f"{user.full_name} exceeded short break by {excess_time}")
            return True
    
    return False

async def idle_time_exceeded(user: User, current_time: datetime, mapped_status: str = None, db: Database = None) -> bool:
    if user.last_state_change_time:
        if (current_time - user.last_state_change_time) > timedelta(minutes=Config.IDLE_BUFFER_TIME):
            logger.debug(f"idle_time_exceeded for {user.full_name} at {current_time}: {True}")
            return True
    return False

async def is_overtime(user: User, current_time: datetime, db: Database, mapped_status: str = None) -> bool:
    if user.work_start:
        work_duration = current_time - user.work_start
        result = work_duration > timedelta(hours=Config.REGULAR_WORK_HOURS)
        logger.debug(f"is_overtime for {user.full_name} at {current_time}: {result}")
        return result
    return False

async def is_regular_work(user: User, current_time: datetime, mapped_status: str, db: Database) -> bool:
    if user.work_start:
        work_duration = current_time - user.work_start
        result = timedelta(hours=Config.REGULAR_WORK_HOURS) >= work_duration > timedelta()
        logger.debug(f"is_regular_work for {user.full_name} at {current_time}: {result}")
        return result
    return False

async def is_holiday_or_weekend(user: User, current_time: datetime, mapped_status: str, db: Database) -> bool:
    result = current_time.weekday() >= 5
    logger.debug(f"is_holiday_or_weekend for {user.full_name} at {current_time}: {result}")
    return result

async def is_authorized_absence(user: User, current_time: datetime, mapped_status: str, db: Database) -> bool:
    if user.state != UserState.OFFLINE or mapped_status != 'OFFLINE':
        logger.debug(f"User {user.full_name} is not in OFFLINE state or client status is not OFFLINE")
        return False

    leave_status = await db.check_user_leave(user, current_time)
    
    if leave_status:
        leave_type = leave_status['type']
        if leave_type in ['sick', 'holidays']:
            logger.warning(f"User {user.full_name} has an authorized {leave_type} leave")
            return True
        elif leave_type == 'work permit':
            if 'start_time' in leave_status and 'end_time' in leave_status:
                start_time = datetime.strptime(leave_status['start_time'], "%H:%M").time()
                end_time = datetime.strptime(leave_status['end_time'], "%H:%M").time()
                current_time_only = current_time.time()
                if start_time <= current_time_only <= end_time:
                    logger.debug(f"User {user.full_name} has a valid work permit from {start_time} to {end_time}")
                    return True
                else:
                    logger.debug(f"User {user.full_name} has a work permit, but current time {current_time_only} is outside permitted hours {start_time} - {end_time}")
            else:
                logger.debug(f"User {user.full_name} has a work permit for the entire day")
                return True

    work_start = datetime.combine(current_time.date(), time.fromisoformat(Config.WORK_START_TIME))
    work_end = datetime.combine(current_time.date(), time.fromisoformat(Config.WORK_END_TIME))
    
    if current_time < work_start or current_time > work_end:
        logger.debug(f"User {user.full_name} is absent outside of work hours")
        return True

    lunch_start = datetime.combine(current_time.date(), time.fromisoformat(Config.LUNCH_START_TIME))
    lunch_end = datetime.combine(current_time.date(), time.fromisoformat(Config.LUNCH_END_TIME))
    
    if lunch_start <= current_time <= lunch_end:
        logger.debug(f"User {user.full_name} is absent during lunch break")
        return True

    offline_limit_time = datetime.combine(current_time.date(), time.fromisoformat(Config.CHECK_OFFLINE_LIMIT_TIME))
    if current_time <= offline_limit_time:
        logger.debug(f"User {user.full_name} is absent but within the allowed offline limit time")
        return True

    logger.warning(f"Unauthorized absence detected for user {user.full_name} at {current_time}")
    return False

async def is_unauthorized_absence(user: User, current_time: datetime, mapped_status: str, db: Database) -> bool:
    result = not await is_authorized_absence(user, current_time, mapped_status, db)
    logger.debug(f"is_unauthorized_absence for {user.full_name} at {current_time}: {result}")
    return result

async def is_not_work_time(user: User, current_time: datetime, mapped_status: str, db: Database) -> bool:
    result = not await is_work_time(user, current_time, mapped_status, db)
    logger.debug(f"is_not_work_time for {user.full_name} at {current_time}: {result}")
    return result

async def is_not_lunch_time(user: User, current_time: datetime, mapped_status: str, db: Database) -> bool:
    result = not await is_lunch_time(user, current_time, mapped_status, db)
    logger.debug(f"is_not_lunch_time for {user.full_name} at {current_time} with status {mapped_status}: {result}")
    return result
    # logger.info(f"is_not_lunch_time for {user.full_name} at {current_time} with status {mapped_status}: {result}")
    # return result

async def is_not_holiday_or_weekend(user: User, current_time: datetime, mapped_status: str, db: Database) -> bool:
    result = not await is_holiday_or_weekend(user, current_time, mapped_status, db)
    logger.debug(f"is_not_holiday_or_weekend for {user.full_name} at {current_time}: {result}")
    return result

async def is_within_work_hours(user: User, current_time: datetime, mapped_status: str, db: Database) -> bool:
    work_start = time_to_datetime(Config.WORK_START_TIME, current_time.date())
    work_end = time_to_datetime(Config.WORK_END_TIME, current_time.date())
    result = work_start <= current_time <= work_end or await is_buffer_time(user, current_time, mapped_status, db)
    logger.debug(f"is_within_work_hours for {user.full_name} at {current_time}: {result}")
    return result


# Funzioni di callback

async def log_start_work(user: User, current_time: datetime, new_state: UserState, mapped_status: str, db: Database) -> None:
    if not check_transition_safety(user.state, new_state):
        logger.warning(f"Unsafe transition attempted: {user.state} -> {new_state}")
        return
    user.state = new_state
    user.check_in(current_time)
    logger.info(f"Started work for {user.full_name} at {current_time} with status {mapped_status}")

async def log_end_work(user: User, current_time: datetime, new_state: UserState, mapped_status: str, db: Database) -> None:
    if not check_transition_safety(user.state, new_state):
        logger.warning(f"Unsafe transition attempted: {user.state} -> {new_state}")
        return
    previous_state = user.state
    user.check_out(current_time)
    user.state = new_state
    user.last_state_change_time = current_time

    if user.check_in_time:
        total_work_time = current_time - user.check_in_time
        effective_work_time = total_work_time - user.get_total_break_time()
        logger.info(f"Ended work for {user.full_name}.")
        logger.info(f"Check-in time: {user.check_in_time}")
        logger.info(f"Check-out time: {current_time}")
        logger.info(f"Total work time: {total_work_time}")
        logger.info(f"Effective work time: {effective_work_time}")
        logger.info(f"Total break time: {user.get_total_break_time()}")
        logger.info(f"Total excess break time: {user.get_total_excess_break_time()}")
        logger.info(f"Total absence time: {user.total_absence_time}")

        for break_log in user.break_logs:
            logger.info(f"Break: {break_log}")
    else:
        logger.warning(f"No check-in time recorded for {user.full_name}")

    user.end_work(current_time)
    logger.debug(f"{user.full_name}: {previous_state.value} -> {new_state.value} at {current_time}")

async def log_start_break(user: User, current_time: datetime, new_state: UserState, mapped_status: str, db: Database) -> None:
    if not check_transition_safety(user.state, new_state):
        logger.warning(f"Unsafe transition attempted: {user.state} -> {new_state}")
        return
    break_type = BreakType.ON_BREAK_LUNCH if new_state == UserState.ON_BREAK_LUNCH else BreakType.SHORT_BREAK
    user.start_break(break_type, current_time)
    user.state = new_state
    logger.info(f"{user.full_name}: Started {break_type.value} at {current_time}")

async def log_end_break(user: User, current_time: datetime, new_state: UserState, mapped_status: str, db: Database) -> None:
    if not check_transition_safety(user.state, new_state):
        logger.warning(f"Unsafe transition attempted: {user.state} -> {new_state}")
        return
    previous_state = user.state
    user.end_break(current_time)
    user.state = new_state
    user.last_state_change_time = current_time

    if user.current_break:
        break_type = user.current_break.break_type.value
        break_duration = user.current_break.get_duration()
        logger.info(f"{user.full_name}: {previous_state.value} ({break_type}) -> {new_state.value} at {current_time}. Break duration: {break_duration}")
        
        if break_type == "ON_BREAK_LUNCH":
            logger.info(f"Ended lunch break for {user.full_name}. Duration: {break_duration}")
            if user.current_break.excess_time > timedelta():
                logger.warning(f"{user.full_name} exceeded lunch break by {user.current_break.excess_time}")
            elif user.current_break.excess_time < timedelta():
                logger.info(f"{user.full_name} took a shorter lunch break by {abs(user.current_break.excess_time)}")
        
        logger.debug(f"Total break time for {user.full_name}: {user.get_total_break_time()}")
    
    user.current_break = None

async def log_start_overtime(user: User, current_time: datetime, new_state: UserState, mapped_status: str, db: Database) -> None:
    if not check_transition_safety(user.state, new_state):
        logger.warning(f"Unsafe transition attempted: {user.state} -> {new_state}")
        return
    previous_state = user.state
    user.state = new_state
    user.last_state_change_time = current_time
    user.start_overtime()
    logger.debug(f"{user.full_name}: {previous_state.value} -> {new_state.value} (Started overtime) at {current_time}")

async def log_end_overtime(user: User, current_time: datetime, new_state: UserState, mapped_status: str, db: Database) -> None:
    if not check_transition_safety(user.state, new_state):
        logger.warning(f"Unsafe transition attempted: {user.state} -> {new_state}")
        return
    previous_state = user.state
    user.state = new_state
    user.last_state_change_time = current_time
    user.end_overtime()
    logger.debug(f"{user.full_name}: {previous_state.value} -> {new_state.value} (Ended overtime) at {current_time}")

async def log_start_holiday_work(user: User, current_time: datetime, new_state: UserState, mapped_status: str, db: Database) -> None:
    if not check_transition_safety(user.state, new_state):
        logger.warning(f"Unsafe transition attempted: {user.state} -> {new_state}")
        return
    previous_state = user.state
    user.state = new_state
    user.last_state_change_time = current_time
    user.start_work(current_time, is_holiday=True)
    logger.debug(f"{user.full_name}: {previous_state.value} -> {new_state.value} (Started holiday work) at {current_time}")

async def log_unauthorized_absence(user: User, current_time: datetime, new_state: UserState, mapped_status: str, db: Database) -> None:
    if not check_transition_safety(user.state, new_state):
        logger.warning(f"Unsafe transition attempted: {user.state} -> {new_state}")
        return
    user.state = new_state
    absence_duration = user.calculate_absence_time(current_time)
    logger.warning(f"Unauthorized absence detected for {user.full_name} at {current_time}. Total absence duration: {absence_duration}")

async def log_end_unauthorized_absence(user: User, current_time: datetime, new_state: UserState, mapped_status: str, db: Database) -> None:
    if user.current_break_start:
        absence_duration = current_time - user.current_break_start
        logger.warning(f"Unauthorized absence ended for {user.full_name}. Duration: {absence_duration}")
        user.total_absence_time += absence_duration
        user.current_break_start = None
    user.state = new_state
    user.last_state_change_time = current_time

# Funzioni di utilità

def check_transition_safety(from_state: UserState, to_state: UserState) -> bool:
    illegal_transitions = [
        (UserState.OFFLINE, UserState.SHORT_BREAK),
        (UserState.OFFLINE, UserState.EXTENDED_BREAK),
        (UserState.OFFLINE, UserState.ON_BREAK_LUNCH),
        (UserState.OFFLINE, UserState.OVERTIME),
        (UserState.UNAUTHORIZED_ABSENCE, UserState.SHORT_BREAK),
        (UserState.UNAUTHORIZED_ABSENCE, UserState.EXTENDED_BREAK),
        (UserState.UNAUTHORIZED_ABSENCE, UserState.ON_BREAK_LUNCH),
        (UserState.UNAUTHORIZED_ABSENCE, UserState.OVERTIME),
        (UserState.HOLIDAY_WORK, UserState.SHORT_BREAK),
        (UserState.HOLIDAY_WORK, UserState.EXTENDED_BREAK),
        (UserState.HOLIDAY_WORK, UserState.ON_BREAK_LUNCH),
        (UserState.OVERTIME, UserState.HOLIDAY_WORK),
        (UserState.SHORT_BREAK, UserState.OVERTIME),
        (UserState.EXTENDED_BREAK, UserState.OVERTIME),
        (UserState.ON_BREAK_LUNCH, UserState.OVERTIME),
        (UserState.RETURNING_FROM_BREAK, UserState.SHORT_BREAK),
        (UserState.RETURNING_FROM_BREAK, UserState.EXTENDED_BREAK),
        (UserState.RETURNING_FROM_BREAK, UserState.ON_BREAK_LUNCH),
    ]
    return (from_state, to_state) not in illegal_transitions

def get_transition_priority(from_state: UserState, to_state: UserState) -> int:
    priority_map = {
        (UserState.WORKING, UserState.ON_BREAK_LUNCH): 10,
        (UserState.WORKING, UserState.OVERTIME): 9,
        (UserState.WORKING, UserState.SHORT_BREAK): 8,
        (UserState.WORKING, UserState.OFFLINE): 7,
        (UserState.WORKING, UserState.HOLIDAY_WORK): 6,
        (UserState.SHORT_BREAK, UserState.EXTENDED_BREAK): 5,
        (UserState.SHORT_BREAK, UserState.WORKING): 4,
        (UserState.EXTENDED_BREAK, UserState.UNAUTHORIZED_ABSENCE): 3,
        (UserState.ONLINE, UserState.WORKING): 2,
        (UserState.OFFLINE, UserState.WORKING): 1,
        (UserState.RETURNING_FROM_BREAK, UserState.WORKING): 8,
    }
    return priority_map.get((from_state, to_state), 0)

def sort_transitions_by_priority(transitions: list) -> list:
    return sorted(transitions, key=lambda t: get_transition_priority(UserState[t['from']], UserState[t['to']]), reverse=True)

def map_status(status: str) -> str:
    status_mapping = Config.load_status_mapping()
    mapped_status = status_mapping.get(status, status).upper()
    logger.debug(f"Mapped client status '{status}' to '{mapped_status}'")
    return mapped_status

def time_to_datetime(t: str, current_date: datetime.date) -> datetime:
    hour, minute = map(int, t.split(':'))
    return datetime.combine(current_date, time(hour, minute))