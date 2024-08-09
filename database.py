import sqlite3
import asyncio
from typing import Union, List, Dict, Any, Optional, Tuple
from models import User
from datetime import datetime

class Database:
    def __init__(self, db_name: str = 'worktracker.db'):
        self.db_name = db_name
        self.conn = None
        self.lock = asyncio.Lock()

    async def _get_connection(self):
        if self.conn is None:
            self.conn = sqlite3.connect(self.db_name)
        return self.conn

    async def _execute(self, query: str, params: tuple = ()):
        async with self.lock:
            conn = await self._get_connection()
            cursor = conn.cursor()
            cursor.execute(query, params)
            conn.commit()
            return cursor
    
    def _convert_to_lowercase(self, user: User) -> User:
        user.full_name = user.full_name.lower()
        user.name = user.name.lower()
        user.surname = user.surname.lower()
        user.email = user.email.lower()
        user.role = user.role.lower()
        user.dept = user.dept.lower()
        return user

    async def save_users(self, users: Union[User, List[User]]) -> bool:
        if not isinstance(users, list):
            users = [users]

        query = """
        INSERT OR REPLACE INTO users 
        (id, jira_id, discord_id, full_name, name, surname, email, remote, role, dept, admin, state) 
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        
        try:
            for user in users:
                user = self._convert_to_lowercase(user)
                await self._execute(query, (
                    user.id, user.jira_id, user.discord_id, user.full_name, user.name, 
                    user.surname, user.email, user.remote, user.role, user.dept, 
                    user.admin, user.state
                ))
            return True
        except sqlite3.Error:
            return False

    async def retrieve_users(self, filters: Optional[Dict[str, Any]] = None) -> List[User]:
        query = "SELECT * FROM users"
        params = ()
        
        if filters:
            conditions = []
            for key, value in filters.items():
                if isinstance(value, str):
                    conditions.append(f"LOWER({key}) = ?")
                    params += (value.lower(),)
                else:
                    conditions.append(f"{key} = ?")
                    params += (value,)
            
            if conditions:
                query += " WHERE " + " AND ".join(conditions)
        
        cursor = await self._execute(query, params)
        rows = cursor.fetchall()
        
        users = []
        for row in rows:
            user = User.from_db_row(row)
            users.append(user)
        
        return users

    async def update_users(self, users: Union[User, List[User]]) -> bool:
        if not isinstance(users, list):
            users = [users]

        query = """
        UPDATE users SET 
        jira_id=?, discord_id=?, full_name=?, name=?, surname=?, email=?, 
        remote=?, role=?, dept=?, admin=?, state=?
        WHERE id=?
        """
        
        try:
            for user in users:
                user = self._convert_to_lowercase(user)
                await self._execute(query, (
                    user.jira_id, user.discord_id, user.full_name, user.name, 
                    user.surname, user.email, user.remote, user.role, user.dept, 
                    user.admin, user.state, user.id
                ))
            return True
        except sqlite3.Error:
            return False

    async def delete_users(self, users: Union[User, List[User]]) -> bool:
        if not isinstance(users, list):
            users = [users]

        query = "DELETE FROM users WHERE id = ?"
        
        try:
            for user in users:
                await self._execute(query, (user.id,))
            return True
        except sqlite3.Error:
            return False

    async def check_user_leave(self, user: User, current_time: datetime) -> Optional[Dict[str, Any]]:
        query = """
        SELECT lt.name, lr.start_time, lr.end_time
        FROM leave_records lr
        JOIN leave_types lt ON lr.leave_type_id = lt.id
        WHERE lr.user_id = ? 
        AND ? BETWEEN lr.start_date AND lr.end_date
        AND lr.authorize = 1
        """
        cursor = await self._execute(query, (user.id, current_time.strftime('%Y-%m-%d')))
        leaves = cursor.fetchall()

        for leave_type, start_time, end_time in leaves:
            if leave_type in ['sick', 'holidays']:
                return {'type': leave_type}
            elif leave_type == 'work permit':
                if start_time and end_time:
                    start_datetime = datetime.combine(current_time.date(), datetime.strptime(start_time, '%H:%M').time())
                    end_datetime = datetime.combine(current_time.date(), datetime.strptime(end_time, '%H:%M').time())
                    if start_datetime <= current_time <= end_datetime:
                        return {'type': leave_type, 'start_time': start_time, 'end_time': end_time}
                else:
                    return {'type': leave_type}

        return None
    
    async def get_upcoming_leaves(self, user: User, start_date: datetime, end_date: datetime) -> List[dict]:
        query = """
        SELECT lt.name, lr.start_date, lr.end_date, lr.start_time, lr.end_time, lr.total_hours
        FROM leave_records lr
        JOIN leave_types lt ON lr.leave_type_id = lt.id
        WHERE lr.user_id = ? AND lr.start_date >= ? AND lr.end_date <= ?
        AND lr.authorize = 1
        ORDER BY lr.start_date
        """
        cursor = await self._execute(query, (user.id, start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d')))
        leaves = cursor.fetchall()

        return [
            {
                'type': leave[0],
                'start_date': leave[1],
                'end_date': leave[2],
                'start_time': leave[3],
                'end_time': leave[4],
                'total_hours': leave[5]
            }
            for leave in leaves
        ]

    async def add_leave_record(self, user: User, leave_type_id: int, start_date: str, end_date: str, 
                               notes: Optional[str] = None, start_time: Optional[str] = None, 
                               end_time: Optional[str] = None, total_hours: Optional[float] = None, 
                               authorize: int = 0) -> bool:
        query = """
        INSERT INTO leave_records 
        (user_id, leave_type_id, start_date, end_date, notes, start_time, end_time, total_hours, authorize)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        try:
            await self._execute(query, (user.id, leave_type_id, start_date, end_date, notes, 
                                        start_time, end_time, total_hours, authorize))
            return True
        except Exception as e:
            print(f"Error adding leave record: {e}")
            return False

    async def update_leave_record(self, leave_id: int, **kwargs) -> bool:
        allowed_fields = ['start_date', 'end_date', 'notes', 'start_time', 'end_time', 'total_hours', 'authorize']
        update_fields = [f"{k} = ?" for k in kwargs.keys() if k in allowed_fields]
        if not update_fields:
            return False

        query = f"UPDATE leave_records SET {', '.join(update_fields)} WHERE id = ?"
        values = list(kwargs.values()) + [leave_id]

        try:
            await self._execute(query, tuple(values))
            return True
        except Exception as e:
            print(f"Error updating leave record: {e}")
            return False

    async def delete_leave_record(self, leave_id: int) -> bool:
        query = "DELETE FROM leave_records WHERE id = ?"
        try:
            await self._execute(query, (leave_id,))
            return True
        except Exception as e:
            print(f"Error deleting leave record: {e}")
            return False

    async def close(self):
        if self.conn:
            self.conn.close()
            self.conn = None
