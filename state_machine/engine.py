import yaml
from datetime import datetime, time
from typing import Optional, Any, Dict
from models import User, UserState
from logger import logger
from database import Database
from .callbacks import sort_transitions_by_priority, map_status
from config import Config
import importlib

class StateMachine:
    def __init__(self, config_file: str = 'state_machine/transitions.yaml', db: Database = None):
        with open(config_file, 'r') as file:
            self.transitions = yaml.safe_load(file)
        self.callbacks_module = importlib.import_module('.callbacks', package=__package__)
        self.db = db or Database()
        self.interactive_mode = Config.INTERACTIVE_MODE

    async def run(self, user: User, client_status: str, simulate_time: Optional[datetime] = None) -> Any:
        current_time = self.get_current_time(simulate_time)
        mapped_status = self.map_client_status(client_status)
        logger.debug(f"Running state machine for user {user.name}, current state: {user.state.value}, client status: {client_status}, mapped status: {mapped_status}")
        
        if user.check_in_time is None and mapped_status == 'WORKING':
            if Config.INTERACTIVE_MODE:
                check_in_str = input(f"No check-in time for {user.name}. Please enter start time (HH:MM) or press Enter for 09:00: ")
                if check_in_str:
                    user.check_in(datetime.combine(current_time.date(), datetime.strptime(check_in_str, "%H:%M").time()))
                else:
                    user.check_in(datetime.combine(current_time.date(), time(9, 0)))
            else:
                user.check_in(datetime.combine(current_time.date(), time(9, 0)))
            logger.info(f"Check-in time set for {user.name} at {user.check_in_time}")

        sorted_transitions = sort_transitions_by_priority(self.transitions)
        
        for transition in sorted_transitions:
            logger.debug(f"Checking transition: {transition}")
            if await self.check(user, transition, mapped_status, current_time):
                logger.debug(f"Transition matched: {transition}")
                new_state = UserState[transition['to']]
                
                if self.interactive_mode and transition.get('requires_confirmation', False):
                    if not await self.get_user_confirmation(user, transition, new_state):
                        logger.debug(f"User declined transition to {new_state.value}")
                        continue
                
                await self.apply(transition.get('callbacks', []), user, current_time, new_state, mapped_status)
                return new_state.value

        logger.info(f"No transition matched, staying in current state: {user.state.value}")
        return user.state.value

    async def check(self, user: User, transition: dict, mapped_status: str, current_time: datetime) -> bool:
        logger.debug(f"Checking transition from {transition['from']} to {transition['to']}")
        logger.debug(f"User state: {user.state.value}, Mapped status: {mapped_status}")
        
        if user.state.value != transition['from']:
            logger.debug(f"State mismatch: {user.state.value} != {transition['from']}")
            return False
        
        if isinstance(transition['client_status'], list):
            if mapped_status not in transition['client_status']:
                logger.debug(f"Status mismatch: {mapped_status} not in {transition['client_status']}")
                return False
        elif mapped_status != transition['client_status']:
            logger.debug(f"Status mismatch: {mapped_status} != {transition['client_status']}")
            return False

        for condition in transition['conditions']:
            func = getattr(self.callbacks_module, condition)
            result = await func(user, current_time, mapped_status, self.db)
            logger.debug(f"Condition {condition} result: {result}")
            if not result:
                return False
        return True

    async def apply(self, callbacks: list, user: User, current_time: datetime, new_state: UserState, mapped_status: str) -> None:
        for callback in callbacks:
            await self._execute_callback(callback, user, current_time, new_state, mapped_status)

    async def _execute_callback(self, callback: str, user: User, current_time: datetime, new_state: UserState, mapped_status: str) -> None:
        func = getattr(self.callbacks_module, callback)
        await func(user=user, current_time=current_time, new_state=new_state, mapped_status=mapped_status, db=self.db)

    async def get_user_confirmation(self, user: User, transition: Dict, new_state: UserState) -> bool:
        print(f"Transition from {user.state.value} to {new_state.value} requires confirmation.")
        response = input("Do you want to proceed? (y/n): ").lower()
        if response == 'y':
            reason = input("Please provide a reason (optional): ")
            return True
        return False

    def get_current_time(self, simulate_time: Optional[datetime] = None) -> datetime:
        return simulate_time if simulate_time else datetime.now()

    def map_client_status(self, client_status: str) -> str:
        return map_status(client_status)

    async def close(self):
        await self.db.close()

    def set_interactive_mode(self, mode: bool):
        self.interactive_mode = mode
