import sqlite3
from datetime import datetime, timedelta
from user import User
from logger import logger

class DatabaseManager:
    def __init__(self, db_name='work_tracker.db'):
        self.conn = sqlite3.connect(db_name)
        self.conn.row_factory = sqlite3.Row
        self.create_tables()

    def create_tables(self):
        self.conn.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            discord_id TEXT UNIQUE NOT NULL,
            full_name TEXT,
            surname TEXT,
            email TEXT,
            remote BOOLEAN,
            role TEXT,
            dept TEXT,
            admin BOOLEAN
        )
        ''')

        self.conn.execute('''
        CREATE TABLE IF NOT EXISTS work_logs (
            id INTEGER PRIMARY KEY,
            user_id INTEGER,
            start_time TEXT NOT NULL,
            end_time TEXT,
            total_hours REAL,
            effective_hours REAL,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
        ''')

        self.conn.execute('''
        CREATE TABLE IF NOT EXISTS break_logs (
            id INTEGER PRIMARY KEY,
            user_id INTEGER,
            start_time TEXT NOT NULL,
            end_time TEXT,
            type TEXT,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
        ''')

        self.conn.execute('''
        CREATE TABLE IF NOT EXISTS device_usage_logs (
            id INTEGER PRIMARY KEY,
            user_id INTEGER,
            work_log_id INTEGER,
            mobile_time REAL,
            pc_time REAL,
            FOREIGN KEY (user_id) REFERENCES users(id),
            FOREIGN KEY (work_log_id) REFERENCES work_logs(id)
        )
        ''')

        self.conn.execute('''
        CREATE TABLE IF NOT EXISTS leave_types (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL UNIQUE
        )
        ''')

        self.conn.execute('''
        CREATE TABLE IF NOT EXISTS leave_records (
            id INTEGER PRIMARY KEY,
            user_id INTEGER,
            leave_type_id INTEGER,
            start_date TEXT NOT NULL,
            end_date TEXT NOT NULL,
            notes TEXT,
            FOREIGN KEY (user_id) REFERENCES users(id),
            FOREIGN KEY (leave_type_id) REFERENCES leave_types(id)
        )
        ''')

        self.conn.commit()

    def get_all_users(self):
        cursor = self.conn.execute('SELECT * FROM users')
        return [User(
            id=row['id'],
            name=row['name'],
            discord_id=row['discord_id'],
            full_name=row['full_name'],
            surname=row['surname'],
            email=row['email'],
            remote=bool(row['remote']),
            role=row['role'],
            dept=row['dept'],
            admin=bool(row['admin'])
        ) for row in cursor.fetchall()]

    def get_user_by_discord_id(self, discord_id):
        cursor = self.conn.execute('SELECT * FROM users WHERE discord_id = ?', (discord_id,))
        row = cursor.fetchone()
        if row:
            return User(
                id=row['id'],
                name=row['name'],
                discord_id=row['discord_id'],
                full_name=row['full_name'],
                surname=row['surname'],
                email=row['email'],
                remote=bool(row['remote']),
                role=row['role'],
                dept=row['dept'],
                admin=bool(row['admin'])
            )
        return None

    def get_user_state(self, user_id):
        cursor = self.conn.execute('SELECT end_time FROM work_logs WHERE user_id = ? ORDER BY start_time DESC LIMIT 1', (user_id,))
        last_work = cursor.fetchone()
        if last_work and last_work['end_time'] is None:
            return 'WORKING'
        cursor = self.conn.execute('SELECT end_time FROM break_logs WHERE user_id = ? ORDER BY start_time DESC LIMIT 1', (user_id,))
        last_break = cursor.fetchone()
        if last_break and last_break['end_time'] is None:
            return 'ON_BREAK'
        return 'OFFLINE'

    def log_work_start(self, user_id, start_time=None, overtime=False):
        if start_time is None:
            start_time = datetime.now()
        self.conn.execute('INSERT INTO work_logs (user_id, start_time, is_overtime) VALUES (?, ?, ?)', 
                        (user_id, start_time.isoformat(), overtime))
        self.conn.commit()
        
        work_log_id = self.conn.execute('SELECT last_insert_rowid()').fetchone()[0]
        self.conn.execute('INSERT INTO device_usage_logs (user_id, work_log_id, mobile_time, pc_time) VALUES (?, ?, 0, 0)', 
                        (user_id, work_log_id))
        self.conn.commit()
        
        return work_log_id

    def log_work_end(self, user_id, total_mobile_time, total_pc_time):
        current_time = datetime.now()
        cursor = self.conn.cursor()
        
        cursor.execute('SELECT start_time, id FROM work_logs WHERE user_id = ? AND end_time IS NULL', (user_id,))
        start_time, work_log_id = cursor.fetchone()
        start_time = datetime.fromisoformat(start_time)
        
        total_hours = (current_time - start_time).total_seconds() / 3600
        
        cursor.execute('SELECT SUM(CASE WHEN end_time IS NOT NULL THEN (julianday(end_time) - julianday(start_time)) * 24 ELSE 0 END) FROM break_logs WHERE user_id = ? AND start_time >= ?', (user_id, start_time.isoformat()))
        break_hours = cursor.fetchone()[0] or 0
        
        effective_hours = total_hours - break_hours
        
        cursor.execute('UPDATE work_logs SET end_time = ?, total_hours = ?, effective_hours = ? WHERE id = ?', 
                    (current_time.isoformat(), total_hours, effective_hours, work_log_id))
        self.conn.commit()

        cursor.execute('UPDATE device_usage_logs SET mobile_time = ?, pc_time = ? WHERE work_log_id = ?', 
                    (total_mobile_time, total_pc_time, work_log_id))
        self.conn.commit()

    def log_break_start(self, user_id, break_type='SHORT_BREAK', start_time=None):
        if start_time is None:
            start_time = datetime.now()
        logger.debug(f"Logging break start for user_id: {user_id}, break_type: {break_type}, start_time: {start_time}")
        self.conn.execute('INSERT INTO break_logs (user_id, start_time, type) VALUES (?, ?, ?)', 
                        (user_id, start_time.isoformat(), break_type))
        self.conn.commit()

    def log_break_end(self, user_id, end_time=None):
        if end_time is None:
            end_time = datetime.now()
        logger.debug(f"Logging break end for user_id: {user_id}, end_time: {end_time}")
        self.conn.execute('UPDATE break_logs SET end_time = ? WHERE user_id = ? AND end_time IS NULL', 
                        (end_time.isoformat(), user_id))
        self.conn.commit()

    def log_break_extension(self, user_id, duration):
        extended_type = f'EXTENDED_{duration}'
        logger.debug(f"Logging break extension for user_id: {user_id}, extended_type: {extended_type}")
        self.conn.execute('UPDATE break_logs SET type = ? WHERE user_id = ? AND end_time IS NULL', (extended_type, user_id))
        self.conn.commit()

    def update_device_usage(self, usage_log_id, mobile_time, pc_time):
        self.conn.execute(
            'UPDATE device_usage_logs SET mobile_time = ?, pc_time = ? WHERE id = ?', 
            (mobile_time, pc_time, usage_log_id)
        )
        self.conn.commit()

    def get_work_start_date(self, user_id):
        cursor = self.conn.execute('''
            SELECT DATE(start_time) FROM work_logs
            WHERE user_id = ? AND end_time IS NULL
            ORDER BY start_time DESC
            LIMIT 1
        ''', (user_id,))
        result = cursor.fetchone()
        return result[0] if result else None

    def get_admin_users(self):
        cursor = self.conn.execute('SELECT * FROM users WHERE admin = 1')
        return [User(
            id=row['id'],
            name=row['name'],
            discord_id=row['discord_id'],
            full_name=row['full_name'],
            surname=row['surname'],
            email=row['email'],
            remote=bool(row['remote']),
            role=row['role'],
            dept=row['dept'],
            admin=True
        ) for row in cursor.fetchall()]
    
    def get_total_hours(self, user_id):
        work_log = self.conn.execute('''
            SELECT start_time, end_time FROM work_logs
            WHERE user_id = ? 
            ORDER BY start_time DESC
            LIMIT 1
        ''', (user_id,)).fetchone()
        
        if not work_log:
            return None, None, None
        
        start_time = datetime.fromisoformat(work_log[0])
        end_time = datetime.fromisoformat(work_log[1]) if work_log[1] else datetime.now()

        total_time = end_time - start_time

        break_logs = self.conn.execute('''
            SELECT start_time, end_time FROM break_logs
            WHERE user_id = ? AND DATE(start_time) = DATE(?)
        ''', (user_id, start_time.date())).fetchall()

        total_break_time = timedelta()

        for break_start, break_end in break_logs:
            if break_end:
                break_duration = datetime.fromisoformat(break_end) - datetime.fromisoformat(break_start)
            else:
                break_duration = datetime.now() - datetime.fromisoformat(break_start)
            total_break_time += break_duration

        effective_time = total_time - total_break_time

        total_hours_str = f"{total_time.total_seconds() / 3600:.2f} hours"
        if not work_log[1]:
            total_hours_str += " (on going)"
        effective_hours_str = f"{effective_time.total_seconds() / 3600:.2f} hours"

        return start_time, total_hours_str, effective_hours_str

    def has_lunch_break_today(self, user_id):
        today = datetime.now().date()
        cursor = self.conn.execute('''
            SELECT COUNT(*) FROM break_logs
            WHERE user_id = ? 
            AND type = 'ON_BREAK_LUNCH'
            AND DATE(start_time) = ?
        ''', (user_id, today))
        result = cursor.fetchone()[0]
        return result > 0

    def get_breaks_summary(self, user_id):
        cursor = self.conn.execute('''
            SELECT start_time, end_time, 
            (julianday(end_time) - julianday(start_time)) * 24 * 60 AS duration_minutes,
            type
            FROM break_logs 
            WHERE user_id = ? 
            AND type != 'ON_BREAK_LUNCH'
            AND DATE(start_time) = DATE('now')
            ORDER BY start_time ASC
        ''', (user_id,))
        
        breaks = []
        for row in cursor.fetchall():
            start_time = row['start_time']
            end_time = row['end_time'] or "Ongoing"
            duration = row['duration_minutes'] if row['end_time'] else "Ongoing"
            break_type = row['type']
            breaks.append((start_time, end_time, f"{duration:.2f}", break_type))
        
        return breaks

    def add_leave_record(self, user_id, leave_type, start_date, end_date, notes=""):
        cursor = self.conn.cursor()
        cursor.execute('SELECT id FROM leave_types WHERE name = ?', (leave_type,))
        leave_type_id = cursor.fetchone()[0]
        
        cursor.execute('''
        INSERT INTO leave_records (user_id, leave_type_id, start_date, end_date, notes)
        VALUES (?, ?, ?, ?, ?)
        ''', (user_id, leave_type_id, start_date, end_date, notes))
        
        self.conn.commit()
        return cursor.lastrowid

    def get_leave_record(self, leave_id):
        cursor = self.conn.cursor()
        cursor.execute('''
        SELECT lr.id, u.name as user_name, lt.name as leave_type, lr.start_date, lr.end_date, lr.notes
        FROM leave_records lr
        JOIN users u ON lr.user_id = u.id
        JOIN leave_types lt ON lr.leave_type_id = lt.id
        WHERE lr.id = ?
        ''', (leave_id,))
        
        return cursor.fetchone()

    def get_user_leave_records(self, user_id):
        cursor = self.conn.cursor()
        cursor.execute('''
        SELECT lr.id, lt.name as leave_type, lr.start_date, lr.end_date, lr.notes
        FROM leave_records lr
        JOIN leave_types lt ON lr.leave_type_id = lt.id
        WHERE lr.user_id = ?
        ORDER BY lr.start_date DESC
        ''', (user_id,))
        
        return cursor.fetchall()

    def update_leave_record(self, leave_id, leave_type, start_date, end_date, notes):
        cursor = self.conn.cursor()
        cursor.execute('SELECT id FROM leave_types WHERE name = ?', (leave_type,))
        leave_type_id = cursor.fetchone()[0]
        
        cursor.execute('''
        UPDATE leave_records
        SET leave_type_id = ?, start_date = ?, end_date = ?, notes = ?
        WHERE id = ?
        ''', (leave_type_id, start_date, end_date, notes, leave_id))
        
        self.conn.commit()
        return cursor.rowcount > 0

    def delete_leave_record(self, leave_id):
        cursor = self.conn.cursor()
        cursor.execute('DELETE FROM leave_records WHERE id = ?', (leave_id,))
        self.conn.commit()
        return cursor.rowcount > 0

    def is_user_on_leave(self, user_id, date):
        cursor = self.conn.cursor()
        cursor.execute('''
        SELECT COUNT(*) 
        FROM leave_records 
        WHERE user_id = ? AND start_date <= ? AND end_date >= ?
        ''', (user_id, date.isoformat(), date.isoformat()))
        
        count = cursor.fetchone()[0]
        return count > 0

    def get_work_start_for_today(self, user_id):
            today = datetime.now().date()
            cursor = self.conn.execute('''
                SELECT id, start_time FROM work_logs
                WHERE user_id = ? AND DATE(start_time) = ?
                ORDER BY start_time DESC LIMIT 1
            ''', (user_id, today.isoformat()))
            result = cursor.fetchone()
            return result if result else None

    def update_user_state(self, user_id, state):
        if not isinstance(state, str):
            raise ValueError(f"State must be a string, got {type(state)}")
        
        if state == 'WORKING':
            self.log_work_start(user_id)
        elif state == 'OFFLINE':
            self.log_work_end(user_id, 0, 0)  # Assuming 0 mobile and PC time when ending work
            self.log_break_end(user_id)
        elif state.startswith('ON_BREAK'):
            break_type = state.split('_')[2] if len(state.split('_')) > 2 else 'SHORT'
            self.log_break_start(user_id, break_type)
        elif state == 'AFTER_HOURS':
            self.log_work_start(user_id)  # Treat after hours as working
        else:
            raise ValueError(f"Unknown state: {state}")

    def add_user(self, name, discord_id, full_name, surname, email, remote, role, dept, admin):
        cursor = self.conn.cursor()
        cursor.execute('''
        INSERT INTO users (name, discord_id, full_name, surname, email, remote, role, dept, admin)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (name, discord_id, full_name, surname, email, remote, role, dept, admin))
        self.conn.commit()
        return cursor.lastrowid

    def update_user(self, user_id, name, full_name, surname, email, remote, role, dept, admin):
        cursor = self.conn.cursor()
        cursor.execute('''
        UPDATE users
        SET name = ?, full_name = ?, surname = ?, email = ?, remote = ?, role = ?, dept = ?, admin = ?
        WHERE id = ?
        ''', (name, full_name, surname, email, remote, role, dept, admin, user_id))
        self.conn.commit()
        return cursor.rowcount > 0

    def delete_user(self, user_id):
        cursor = self.conn.cursor()
        cursor.execute('DELETE FROM users WHERE id = ?', (user_id,))
        self.conn.commit()
        return cursor.rowcount > 0

    def get_user_by_id(self, user_id):
        cursor = self.conn.execute('SELECT * FROM users WHERE id = ?', (user_id,))
        row = cursor.fetchone()
        if row:
            return User(
                id=row['id'],
                name=row['name'],
                discord_id=row['discord_id'],
                full_name=row['full_name'],
                surname=row['surname'],
                email=row['email'],
                remote=bool(row['remote']),
                role=row['role'],
                dept=row['dept'],
                admin=bool(row['admin'])
            )
        return None

    def add_leave_type(self, name):
        cursor = self.conn.cursor()
        cursor.execute('INSERT INTO leave_types (name) VALUES (?)', (name,))
        self.conn.commit()
        return cursor.lastrowid

    def get_leave_types(self):
        cursor = self.conn.execute('SELECT * FROM leave_types')
        return [{'id': row['id'], 'name': row['name']} for row in cursor.fetchall()]

    def get_user_work_logs(self, user_id, start_date, end_date):
        cursor = self.conn.execute('''
        SELECT * FROM work_logs
        WHERE user_id = ? AND DATE(start_time) BETWEEN ? AND ?
        ORDER BY start_time DESC
        ''', (user_id, start_date, end_date))
        return cursor.fetchall()

    def get_user_break_logs(self, user_id, start_date, end_date):
        cursor = self.conn.execute('''
        SELECT * FROM break_logs
        WHERE user_id = ? AND DATE(start_time) BETWEEN ? AND ?
        ORDER BY start_time DESC
        ''', (user_id, start_date, end_date))
        return cursor.fetchall()

    def get_user_device_usage(self, user_id, start_date, end_date):
        cursor = self.conn.execute('''
        SELECT d.* FROM device_usage_logs d
        JOIN work_logs w ON d.work_log_id = w.id
        WHERE d.user_id = ? AND DATE(w.start_time) BETWEEN ? AND ?
        ORDER BY w.start_time DESC
        ''', (user_id, start_date, end_date))
        return cursor.fetchall()

    def close(self):
        self.conn.close()