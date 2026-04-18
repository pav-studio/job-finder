# db.py (updated env support)

import os
import sqlite3
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()

DB_FILE = os.getenv("DB_FILE", "jobs.db")


def connect():
    return sqlite3.connect(DB_FILE)


def init_db():
    conn = connect()
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS applications (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        company TEXT,
        email TEXT,
        role TEXT,
        location TEXT,
        source TEXT,
        keyword TEXT,
        applied_date TEXT,
        status TEXT,
        notes TEXT
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        created_at TEXT,
        level TEXT,
        message TEXT
    )
    """)

    conn.commit()
    conn.close()


def already_applied(company, email):
    conn = connect()
    cur = conn.cursor()

    cur.execute("""
    SELECT id FROM applications
    WHERE lower(company)=lower(?) OR lower(email)=lower(?)
    LIMIT 1
    """, (company, email))

    row = cur.fetchone()
    conn.close()

    return row is not None


def save_application(company, email, role, location, source, keyword, status):
    conn = connect()
    cur = conn.cursor()

    cur.execute("""
    INSERT INTO applications(
        company,email,role,location,source,
        keyword,applied_date,status
    )
    VALUES(?,?,?,?,?,?,?,?)
    """, (
        company,
        email,
        role,
        location,
        source,
        keyword,
        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        status
    ))

    conn.commit()
    conn.close()


def count_today_sent():
    today = datetime.now().strftime("%Y-%m-%d")

    conn = connect()
    cur = conn.cursor()

    cur.execute("""
    SELECT COUNT(*)
    FROM applications
    WHERE applied_date LIKE ?
    AND status='sent'
    """, (f"{today}%",))

    count = cur.fetchone()[0]
    conn.close()
    return count


def log(level, message):
    conn = connect()
    cur = conn.cursor()

    cur.execute("""
    INSERT INTO logs(created_at, level, message)
    VALUES(?,?,?)
    """, (
        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        level,
        message
    ))

    conn.commit()
    conn.close()