import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from fastapi.responses import FileResponse
from datetime import datetime, timezone # ★時間を扱うためのツールを追加

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

class Post(BaseModel):
    name: str
    content: str

DB_URL = os.environ.get("DATABASE_URL")

def get_db_connection():
    if DB_URL:
        import psycopg2
        return psycopg2.connect(DB_URL)
    else:
        import sqlite3
        return sqlite3.connect("minix.db")

def init_db():
    conn = get_db_connection()
    c = conn.cursor()
    # ★新しい箱「posts_v2」を作成。時間（created_at）を保存する欄を追加しました。
    if DB_URL:
        c.execute("""
            CREATE TABLE IF NOT EXISTS posts_v2 (
                id SERIAL PRIMARY KEY,
                name TEXT,
                content TEXT,
                created_at TEXT
            )
        """)
    else:
        c.execute("""
            CREATE TABLE IF NOT EXISTS posts_v2 (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT,
                content TEXT,
                created_at TEXT
            )
        """)
    conn.commit()
    conn.close()

init_db()

@app.get("/")
def read_index():
    return FileResponse("index.html")

@app.get("/posts")
def get_posts():
    conn = get_db_connection()
    c = conn.cursor()
    # ★時間(created_at)も一緒に持ってくるように修正
    c.execute("SELECT name, content, created_at FROM posts_v2 ORDER BY id DESC")
    posts = [{"name": row[0], "content": row[1], "created_at": row[2]} for row in c.fetchall()]
    conn.close()
    return posts

@app.post("/posts")
def create_post(post: Post):
    conn = get_db_connection()
    c = conn.cursor()
    
    # ★世界標準時(UTC)で現在時刻を取得して保存します
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
    
    if DB_URL:
        c.execute("INSERT INTO posts_v2 (name, content, created_at) VALUES (%s, %s, %s)", (post.name, post.content, now))
    else:
        c.execute("INSERT INTO posts_v2 (name, content, created_at) VALUES (?, ?, ?)", (post.name, post.content, now))
    conn.commit()
    conn.close()
    return {"message": "投稿完了！"}
