"""
AI 用药伴侣 - 数据库操作 (SQLite)
支持药品管理 + 服药记录
"""

import sqlite3
import json
import os
import datetime
from typing import List, Dict, Optional

DB_PATH = os.path.join(os.path.dirname(__file__), "medicine.db")


class Database:
    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self._init_db()

    def _get_conn(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    def _init_db(self):
        """初始化数据库表"""
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.executescript("""
            CREATE TABLE IF NOT EXISTS medicines (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                name        TEXT NOT NULL,
                dosage      TEXT DEFAULT '1粒',
                frequency   TEXT DEFAULT '每日1次',
                times       TEXT DEFAULT '["08:00"]',
                total_count INTEGER DEFAULT 30,
                notes       TEXT DEFAULT '',
                created_at  TEXT DEFAULT (datetime('now','localtime')),
                updated_at  TEXT DEFAULT (datetime('now','localtime'))
            );

            CREATE TABLE IF NOT EXISTS medication_log (
                id             INTEGER PRIMARY KEY AUTOINCREMENT,
                medicine_id    INTEGER NOT NULL,
                medicine_name  TEXT DEFAULT '',
                scheduled_time TEXT NOT NULL,
                actual_time    TEXT,
                status         TEXT DEFAULT '待服',
                date           TEXT NOT NULL,
                FOREIGN KEY (medicine_id) REFERENCES medicines(id)
            );

            CREATE TABLE IF NOT EXISTS chat_history (
                id       INTEGER PRIMARY KEY AUTOINCREMENT,
                role     TEXT NOT NULL,
                content  TEXT NOT NULL,
                created_at TEXT DEFAULT (datetime('now','localtime'))
            );
        """)
        conn.commit()
        conn.close()

    # ===================== 药品管理 =====================

    def add_medicine(self, name, dosage, frequency, times, total_count, start_date=None, end_date=None, notes=""):
        import json
        from datetime import date

        conn = self.get_connection()
        cursor = conn.cursor()

        # 如果没有传入日期，使用默认值
        if start_date is None:
            start_date = date.today().isoformat()
        if end_date is None:
            end_date = (date.today() + timedelta(days=30)).isoformat()

        # 将 times 列表转为 JSON 字符串存储
        times_json = json.dumps(times)

        cursor.execute('''
            INSERT INTO medicines (name, dosage, frequency, times, total_count, start_date, end_date, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (name, dosage, frequency, times_json, total_count, start_date, end_date, notes))

        conn.commit()
        conn.close()

    def get_medicines(self) -> List[Dict]:
        """获取所有药品"""
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM medicines ORDER BY created_at DESC")
        rows = cursor.fetchall()
        conn.close()
        result = []
        for row in rows:
            d = dict(row)
            d["times"] = json.loads(d["times"])
            result.append(d)
        return result

    def get_medicine(self, medicine_id: int) -> Optional[Dict]:
        """获取单个药品"""
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM medicines WHERE id=?", (medicine_id,))
        row = cursor.fetchone()
        conn.close()
        if row:
            d = dict(row)
            d["times"] = json.loads(d["times"])
            return d
        return None

    def update_medicine(self, medicine_id: int, **kwargs) -> bool:
        """更新药品信息"""
        allowed = ["name", "dosage", "frequency", "times", "total_count", "notes"]
        updates = {k: v for k, v in kwargs.items() if k in allowed}
        if not updates:
            return False

        if "times" in updates:
            updates["times"] = json.dumps(updates["times"], ensure_ascii=False)

        updates["updated_at"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        set_clause = ", ".join(f"{k}=?" for k in updates.keys())
        values = list(updates.values()) + [medicine_id]

        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute(f"UPDATE medicines SET {set_clause} WHERE id=?", values)
        conn.commit()
        conn.close()
        return True

    def delete_medicine(self, medicine_id: int) -> bool:
        """删除药品及其记录"""
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM medication_log WHERE medicine_id=?", (medicine_id,))
        cursor.execute("DELETE FROM medicines WHERE id=?", (medicine_id,))
        conn.commit()
        conn.close()
        return True

    # ===================== 服药记录 =====================

    def ensure_today_logs(self):
        """确保今日已有服药记录"""
        medicines = self.get_medicines()
        today = datetime.date.today().strftime("%Y-%m-%d")
        conn = self._get_conn()
        cursor = conn.cursor()
        for med in medicines:
            for t in med["times"]:
                cursor.execute("""
                    INSERT OR IGNORE INTO medication_log
                    (medicine_id, medicine_name, scheduled_time, status, date)
                    VALUES (?, ?, ?, '待服', ?)
                """, (med["id"], med["name"], t, today))
        conn.commit()
        conn.close()

    def get_today_logs(self) -> List[Dict]:
        """获取今日服药记录"""
        self.ensure_today_logs()
        today = datetime.date.today().strftime("%Y-%m-%d")
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT ml.*, m.dosage, m.total_count
            FROM medication_log ml
            LEFT JOIN medicines m ON ml.medicine_id = m.id
            WHERE ml.date = ?
            ORDER BY ml.scheduled_time ASC
        """, (today,))
        rows = cursor.fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def get_log_by_date(self, date_str: str) -> List[Dict]:
        """获取指定日期的服药记录"""
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT ml.*, m.dosage, m.total_count
            FROM medication_log ml
            LEFT JOIN medicines m ON ml.medicine_id = m.id
            WHERE ml.date = ?
            ORDER BY ml.scheduled_time ASC
        """, (date_str,))
        rows = cursor.fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def mark_taken(self, log_id: int):
        """标记已服"""
        now = datetime.datetime.now().strftime("%H:%M")
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE medication_log SET status='已服', actual_time=?
            WHERE id=?
        """, (now, log_id))
        conn.commit()

        # 更新剩余数量
        cursor.execute("""
            SELECT medicine_id FROM medication_log WHERE id=?
        """, (log_id,))
        row = cursor.fetchone()
        if row:
            mid = row["medicine_id"]
            cursor.execute("""
                UPDATE medicines SET total_count = total_count - 1
                WHERE id=? AND total_count > 0
            """, (mid,))
        conn.commit()
        conn.close()

    def mark_missed(self, log_id: int):
        """标记漏服"""
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE medication_log SET status='漏服', actual_time='--'
            WHERE id=?
        """, (log_id,))
        conn.commit()
        conn.close()

    def get_upcoming(self, minutes: int = 30) -> List[Dict]:
        """获取即将到时间的服药提醒"""
        now = datetime.datetime.now()
        current_time = now.strftime("%H:%M")
        today = now.strftime("%Y-%m-%d")

        # 解析当前时间，计算 "分钟" 后的时间
        h, m = map(int, current_time.split(":"))
        later = now + datetime.timedelta(minutes=minutes)
        later_str = later.strftime("%H:%M")

        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT ml.*, m.dosage
            FROM medication_log ml
            LEFT JOIN medicines m ON ml.medicine_id = m.id
            WHERE ml.date = ? AND ml.status = '待服'
              AND ml.scheduled_time >= ? AND ml.scheduled_time <= ?
            ORDER BY ml.scheduled_time ASC
        """, (today, current_time, later_str))
        rows = cursor.fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def get_overdue(self) -> List[Dict]:
        """获取已过时间但未服的记录"""
        now = datetime.datetime.now().strftime("%H:%M")
        today = datetime.date.today().strftime("%Y-%m-%d")
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT ml.*, m.dosage
            FROM medication_log ml
            LEFT JOIN medicines m ON ml.medicine_id = m.id
            WHERE ml.date = ? AND ml.status = '待服'
              AND ml.scheduled_time < ?
            ORDER BY ml.scheduled_time ASC
        """, (today, now))
        rows = cursor.fetchall()
        conn.close()
        return [dict(r) for r in rows]

    # ===================== 聊天记录 =====================

    def add_chat_message(self, role: str, content: str):
        """保存聊天记录"""
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO chat_history (role, content) VALUES (?, ?)
        """, (role, content))
        conn.commit()
        conn.close()

    def get_chat_history(self, limit: int = 20) -> List[Dict]:
        """获取最近聊天记录"""
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM chat_history ORDER BY id DESC LIMIT ?
        """, (limit,))
        rows = cursor.fetchall()
        conn.close()
        result = [dict(r) for r in rows]
        result.reverse()
        return result

    def clear_chat_history(self):
        """清空聊天记录"""
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM chat_history")
        conn.commit()
        conn.close()
