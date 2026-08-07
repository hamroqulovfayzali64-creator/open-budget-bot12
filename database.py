import sqlite3
from config import DATABASE

db = sqlite3.connect(DATABASE, check_same_thread=False)
cursor = db.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS users(
    user_id INTEGER PRIMARY KEY,
    language TEXT DEFAULT 'uz',
    joined_date TEXT,
    project_clicks INTEGER DEFAULT 0,
    vote_clicks INTEGER DEFAULT 0
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS projects(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name_uz TEXT,
    name_ru TEXT,
    url TEXT
)
""")

db.commit()