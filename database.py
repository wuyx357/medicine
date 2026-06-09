import sqlite3
import json
from datetime import date, datetime, timedelta

class Database:
    def __init__(self, db_path):
        self.db_path = db_path
        self.init_db()
        self.ensure_columns()  # 确保列存在
    
    def get_connection(self):
        return sqlite3.connect(self.db_path)
    
    def ensure_columns(self):
        """确保 medicines 表有需要的所有列"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # 检查并添加缺失的列
        cursor.execute("PRAGMA table_info(medicines)")
        existing_columns = [col[1] for col in cursor.fetchall()]
        
        columns_to_add = {
            'start_date': 'TEXT',
            'end_date': 'TEXT',
            'notes': 'TEXT'
        }
        
        for col_name, col_type in columns_to_add.items():
            if col_name not in existing_columns:
                try:
                    cursor.execute(f'ALTER TABLE medicines ADD COLUMN {col_name} {col_type}')
                except:
                    pass  # 如果列已存在或添加失败，忽略
        
        conn.commit()
        conn.close()
    
    def init_db(self):
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # 创建药品表（基础字段）
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS medicines (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                dosage TEXT,
                frequency TEXT,
                times TEXT,
                total_count INTEGER DEFAULT 0
            )
        ''')
        
        # 创建服药记录表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS daily_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                medicine_name TEXT,
                scheduled_time TEXT,
                actual_time TEXT,
                status TEXT,
                log_date TEXT
            )
        ''')
        
        # 创建聊天记录表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS chat_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                role TEXT,
                content TEXT,
                timestamp TEXT
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def add_medicine(self, name, dosage, frequency, times, total_count, start_date=None, end_date=None, notes=""):
        conn = self.get_connection()
        cursor = conn.cursor()
        
        if start_date is None:
            start_date = date.today().isoformat()
        if end_date is None:
            end_date = (date.today() + timedelta(days=30)).isoformat()
        
        times_json = json.dumps(times)
        cursor.execute('''
            INSERT INTO medicines (name, dosage, frequency, times, total_count, start_date, end_date, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (name, dosage, frequency, times_json, total_count, start_date, end_date, notes))
        
        conn.commit()
        conn.close()
        return cursor.lastrowid
    
    def get_medicines(self):
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # 查询时使用 COALESCE 处理可能不存在的列
        cursor.execute('''
            SELECT 
                id, name, dosage, frequency, times, total_count,
                COALESCE(start_date, '') as start_date,
                COALESCE(end_date, '') as end_date,
                COALESCE(notes, '') as notes
            FROM medicines
        ''')
        rows = cursor.fetchall()
        conn.close()
        
        medicines = []
        for row in rows:
            try:
                times_data = json.loads(row[4]) if row[4] else []
            except:
                times_data = []
            
            medicines.append({
                "id": row[0],
                "name": row[1],
                "dosage": row[2],
                "frequency": row[3],
                "times": times_data,
                "total_count": row[5],
                "start_date": row[6],
                "end_date": row[7],
                "notes": row[8]
            })
        return medicines
    
    def update_medicine(self, id, name, dosage, frequency, times, total_count, start_date, end_date, notes):
        conn = self.get_connection()
        cursor = conn.cursor()
        times_json = json.dumps(times)
        cursor.execute('''
            UPDATE medicines 
            SET name=?, dosage=?, frequency=?, times=?, total_count=?, 
                start_date=?, end_date=?, notes=?
            WHERE id=?
        ''', (name, dosage, frequency, times_json, total_count, start_date, end_date, notes, id))
        conn.commit()
        conn.close()
    
    def delete_medicine(self, id):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('DELETE FROM medicines WHERE id=?', (id,))
        conn.commit()
        conn.close()
    
    def get_today_logs(self):
        conn = self.get_connection()
        cursor = conn.cursor()
        today = date.today().isoformat()
        cursor.execute('SELECT id, medicine_name, scheduled_time, actual_time, status FROM daily_logs WHERE log_date=?', (today,))
        rows = cursor.fetchall()
        conn.close()
        
        logs = []
        for row in rows:
            logs.append({
                "id": row[0],
                "medicine_name": row[1],
                "scheduled_time": row[2],
                "actual_time": row[3],
                "status": row[4]
            })
        return logs
    
    def mark_taken_by_name(self, medicine_name, scheduled_time):
        conn = self.get_connection()
        cursor = conn.cursor()
        today = date.today().isoformat()
        now = datetime.now().strftime("%H:%M")
        
        cursor.execute('''
            SELECT id FROM daily_logs WHERE medicine_name=? AND scheduled_time=? AND log_date=?
        ''', (medicine_name, scheduled_time, today))
        exists = cursor.fetchone()
        
        if exists:
            cursor.execute('''
                UPDATE daily_logs SET status='已服', actual_time=? WHERE id=?
            ''', (now, exists[0]))
        else:
            cursor.execute('''
                INSERT INTO daily_logs (medicine_name, scheduled_time, actual_time, status, log_date)
                VALUES (?, ?, ?, '已服', ?)
            ''', (medicine_name, scheduled_time, now, today))
        
        conn.commit()
        conn.close()
    
    def add_chat_message(self, role, content):
        conn = self.get_connection()
        cursor = conn.cursor()
        timestamp = datetime.now().isoformat()
        cursor.execute('INSERT INTO chat_history (role, content, timestamp) VALUES (?, ?, ?)',
                       (role, content, timestamp))
        conn.commit()
        conn.close()
    
    def get_chat_history(self, limit=50):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT role, content FROM chat_history ORDER BY timestamp DESC LIMIT ?', (limit,))
        rows = cursor.fetchall()
        conn.close()
        return [{"role": row[0], "content": row[1]} for row in rows][::-1]
    
    def clear_chat_history(self):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('DELETE FROM chat_history')
        conn.commit()
        conn.close()
