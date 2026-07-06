
import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel


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

# クラウド(Render)から提供されるデータベースのURLを受け取る準備
DB_URL = os.environ.get("DATABASE_URL")

# 接続するデータベースを自動で切り替える関数
def get_db_connection():
    if DB_URL:
        import psycopg2
        return psycopg2.connect(DB_URL) # クラウドならPostgreSQL
    else:
        import sqlite3
        return sqlite3.connect("minix.db") # パソコンならSQLite

# データベースの初期設定（言語の違いを吸収します）
def init_db():
    conn = get_db_connection()
    c = conn.cursor()
    if DB_URL:
        # PostgreSQL用のテーブル作成 (SERIAL)
        c.execute("""
            CREATE TABLE IF NOT EXISTS posts (
                id SERIAL PRIMARY KEY,
                name TEXT,
                content TEXT
            )
        """)
    else:
        # SQLite用のテーブル作成 (AUTOINCREMENT)
        c.execute("""
            CREATE TABLE IF NOT EXISTS posts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT,
                content TEXT
            )
        """)
    conn.commit()
    conn.close()

init_db()

@app.get("/posts")
def get_posts():
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT name, content FROM posts ORDER BY id DESC")
    posts = [{"name": row[0], "content": row[1]} for row in c.fetchall()]
    conn.close()
    return posts

@app.post("/posts")
def create_post(post: Post):
    conn = get_db_connection()
    c = conn.cursor()
    if DB_URL:
        # PostgreSQL用のデータ書き込み (%s)
        c.execute("INSERT INTO posts (name, content) VALUES (%s, %s)", (post.name, post.content))
    else:
        # SQLite用のデータ書き込み (?)
        c.execute("INSERT INTO posts (name, content) VALUES (?, ?)", (post.name, post.content))
    conn.commit()
    conn.close()
    return {"message": "投稿完了！"}