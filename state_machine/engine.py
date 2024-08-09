# worktracker/engine.py
import yaml
import importlib
from datetime import datetime
from typing import Optional, Any
import asyncio
from models import User, UserState
from logger import logger

class StateMachine:
    def __init__(self, config_file: str = 'state_machine/transitions.yaml'):
        with open(config_file, 'r') as file:
            self.transitions = yaml.safe_load(file)
        
        self.callbacks_module = importlib.import_module('state_machine.callbacks')

    async def run(self, user: User, client_status: str, simulate_time: Optional[datetime] = None) -> Any:
        current_time = self.get_current_time(simulate_time)
        mapped_status = self.map_client_status(client_status)
        
        logger.debug(f"Running state machine for user {user.name}, current state: {user.state.value}, client status: {client_status}, mapped status: {mapped_status}")
        
        for transition in self.transitions:
            logger.debug(f"Checking transition: {transition}")
            if await self.check(user, transition, mapped_status, current_time):
                logger.info(f"Transition matched: {transition}")
                new_state = UserState[transition['to']]
                await self.apply(transition.get('callbacks', []), user, current_time, new_state, mapped_status)
                return new_state.value

        logger.debug(f"No transition matched, staying in current state: {user.state.value}")
        return user.state.value

    def get_current_time(self, simulate_time: Optional[datetime] = None) -> datetime:
        return simulate_time if simulate_time else datetime.now()

    async def check(self, user: User, transition: dict, mapped_status: str, current_time: datetime) -> bool:
        logger.debug(f"Checking transition from {transition['from']} to {transition['to']}")
        logger.debug(f"User state: {user.state.value}, Mapped status: {mapped_status}")
        
        if user.state.value != transition['from']:
            logger.debug(f"State mismatch: {user.state.value} != {transition['from']}")
            return False
        
        if mapped_status != transition['client_status']:
            logger.debug(f"Status mismatch: {mapped_status} != {transition['client_status']}")
            return False

        for condition in transition['conditions']:
            func = getattr(self.callbacks_module, condition)
            result = await func(user, current_time, mapped_status) if asyncio.iscoroutinefunction(func) else func(user, current_time, mapped_status)
            logger.debug(f"Condition {condition} result: {result}")
            if not result:
                return False

        return True

    async def apply(self, callbacks: list, user: User, current_time: datetime, new_state: UserState, mapped_status: str) -> None:
        for callback in callbacks:
            await self._execute_callback(callback, user, current_time, new_state, mapped_status)

    async def _execute_callback(self, callback: str, user: User, current_time: datetime, new_state: UserState, mapped_status: str) -> None:
        func = getattr(self.callbacks_module, callback)
        if asyncio.iscoroutinefunction(func):
            await func(user=user, current_time=current_time, new_state=new_state, mapped_status=mapped_status)
        else:
            func(user=user, current_time=current_time, new_state=new_state, mapped_status=mapped_status)

    def map_client_status(self, client_status: str) -> str:
        return self.callbacks_module.map_status(client_status)
