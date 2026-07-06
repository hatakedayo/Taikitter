import os
import sqlite3
from fastapi import FastAPI, Depends, HTTPException, status, Response, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from fastapi.responses import FileResponse, JSONResponse
from datetime import datetime, timezone

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=True,
)

class LoginData(BaseModel):
    username: str
    password: str

class PostData(BaseModel):
    content: str

# ★ アイコンURLを変更するためのデータ構造
class UpdateIconData(BaseModel):
    icon_url: str

DB_URL = os.environ.get("DATABASE_URL")

def get_db_connection():
    if DB_URL:
        import psycopg2
        return psycopg2.connect(DB_URL)
    else:
        return sqlite3.connect("minix.db")

def init_db():
    conn = get_db_connection()
    c = conn.cursor()
    
    # ユーザーテーブルに「icon_url（アイコン画像）」の保存欄を追加 (posts_v4にバージョンアップ)
    if DB_URL:
        c.execute("""
            CREATE TABLE IF NOT EXISTS users_v4 (
                username TEXT PRIMARY KEY,
                password TEXT,
                icon_url TEXT
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS posts_v4 (
                id SERIAL PRIMARY KEY,
                name TEXT,
                content TEXT,
                created_at TEXT
            )
        """)
    else:
        c.execute("""
            CREATE TABLE IF NOT EXISTS users_v4 (
                username TEXT PRIMARY KEY,
                password TEXT,
                icon_url TEXT
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS posts_v4 (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT,
                content TEXT,
                created_at TEXT
            )
        """)
    
    # 6人分の初期アカウント（可愛い動物のフリーアイコンを初期値にしています）
    friends = [
        ("user1", "pass1", "https://api.dicebear.com/7.x/bottts/svg?seed=user1"),
        ("user2", "pass2", "https://api.dicebear.com/7.x/bottts/svg?seed=user2"),
        ("user3", "pass3", "https://api.dicebear.com/7.x/bottts/svg?seed=user3"),
        ("user4", "pass4", "https://api.dicebear.com/7.x/bottts/svg?seed=user4"),
        ("user5", "pass5", "https://api.dicebear.com/7.x/bottts/svg?seed=user5"),
        ("user6", "pass6", "https://api.dicebear.com/7.x/bottts/svg?seed=user6")
    ]
    for username, password, icon in friends:
        try:
            if DB_URL:
                c.execute("INSERT INTO users_v4 (username, password, icon_url) VALUES (%s, %s, %s) ON CONFLICT DO NOTHING", (username, password, icon))
            else:
                c.execute("INSERT INTO users_v4 (username, password, icon_url) VALUES (?, ?, ?) OR IGNORE", (username, password, icon))
        except:
            pass

    conn.commit()
    conn.close()

init_db()

def get_current_user(request: Request):
    username = request.cookies.get("session_user")
    if not username:
        raise HTTPException(status_code=401, detail="ログインが必要です")
    return username

# ★ ログイン画面に一覧表示するために、ユーザー名とアイコンのリストを返すAPI
@app.get("/users")
def get_users():
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT username, icon_url FROM users_v4")
    users = [{"username": row[0], "icon_url": row[1]} for row in c.fetchall()]
    conn.close()
    return users

@app.post("/login")
def login(data: LoginData, response: Response):
    conn = get_db_connection()
    c = conn.cursor()
    if DB_URL:
        c.execute("SELECT password FROM users_v4 WHERE username = %s", (data.username,))
    else:
        c.execute("SELECT password FROM users_v4 WHERE username = ?", (data.username,))
    row = c.fetchone()
    conn.close()

    if row and row[0] == data.password:
        response.set_cookie(key="session_user", value=data.username, max_age=2592000, httponly=True, samesite="lax")
        return {"message": "ログイン成功！"}
    else:
        raise HTTPException(status_code=400, detail="パスワードが違います")

@app.post("/logout")
def logout(response: Response):
    response.delete_cookie(key="session_user")
    return {"message": "ログアウトしました"}

# ★ ログインユーザーのアイコン情報も一緒に返すように強化
@app.get("/me")
def get_me(username: str = Depends(get_current_user)):
    conn = get_db_connection()
    c = conn.cursor()
    if DB_URL:
        c.execute("SELECT icon_url FROM users_v4 WHERE username = %s", (username,))
    else:
        c.execute("SELECT icon_url FROM users_v4 WHERE username = ?", (username,))
    row = c.fetchone()
    conn.close()
    icon_url = row[0] if row else ""
    return {"username": username, "icon_url": icon_url}

# ★ アイコンのURLを更新するAPI
@app.post("/me/icon")
def update_icon(data: UpdateIconData, username: str = Depends(get_current_user)):
    conn = get_db_connection()
    c = conn.cursor()
    if DB_URL:
        c.execute("UPDATE users_v4 SET icon_url = %s WHERE username = %s", (data.icon_url, username))
    else:
        c.execute("UPDATE users_v4 SET icon_url = ? WHERE username = ?", (data.icon_url, username))
    conn.commit()
    conn.close()
    return {"message": "アイコンを更新しました"}

# ★ タイムライン取得（投稿者の現在のアイコンも一緒に持ってくる）
@app.get("/posts")
def get_posts(username: str = Depends(get_current_user)):
    conn = get_db_connection()
    c = conn.cursor()
    # 投稿(posts_v4)とユーザー情報(users_v4)を合体させて、最新のアイコンを取得する
    c.execute("""
        SELECT p.name, p.content, p.created_at, u.icon_url 
        FROM posts_v4 p
        LEFT JOIN users_v4 u ON p.name = u.username
        ORDER BY p.id DESC
    """)
    posts = [{"name": row[0], "content": row[1], "created_at": row[2], "icon_url": row[3]} for row in c.fetchall()]
    conn.close()
    return posts

@app.post("/posts")
def create_post(post: PostData, username: str = Depends(get_current_user)):
    conn = get_db_connection()
    c = conn.cursor()
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
    if DB_URL:
        c.execute("INSERT INTO posts_v4 (name, content, created_at) VALUES (%s, %s, %s)", (username, post.content, now))
    else:
        c.execute("INSERT INTO posts_v4 (name, content, created_at) VALUES (?, ?, ?)", (username, post.content, now))
    conn.commit()
    conn.close()
    return {"message": "投稿完了！"}

@app.get("/")
def read_index():
    return FileResponse("index.html")

@app.get("/favicon.ico")
def get_favicon():
    return FileResponse("favicon.ico")
