import os
import sqlite3
import urllib.parse  # ★ 日本語を安全に変換するツールを追加！
from fastapi import FastAPI, Depends, HTTPException, status, Response, Request, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from fastapi.responses import FileResponse, Response as FastAPIResponse
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
    
    if DB_URL:
        c.execute("""
            CREATE TABLE IF NOT EXISTS users_v6 (
                username TEXT PRIMARY KEY,
                password TEXT,
                icon_data BYTEA
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS posts_v6 (
                id SERIAL PRIMARY KEY,
                name TEXT,
                content TEXT,
                created_at TEXT
            )
        """)
    else:
        c.execute("""
            CREATE TABLE IF NOT EXISTS users_v6 (
                username TEXT PRIMARY KEY,
                password TEXT,
                icon_data BLOB
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS posts_v6 (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT,
                content TEXT,
                created_at TEXT
            )
        """)
    
    # ★ ここを実際の友達の日本語名とパスワードに書き換えてください
    friends = [
        ("たいき", "0000"),
        ("たくと", "0000"),
        ("ひかる", "0000"),
        ("ゆうき", "0000"),
        ("ゆうせい", "0000"),
        ("わく", "0000"),
    ]
    
    for username, password in friends:
        try:
            if DB_URL:
                c.execute("INSERT INTO users_v6 (username, password) VALUES (%s, %s) ON CONFLICT DO NOTHING", (username, password))
            else:
                c.execute("INSERT INTO users_v6 (username, password) VALUES (?, ?) OR IGNORE", (username, password))
        except:
            pass

    conn.commit()
    conn.close()

init_db()

# ★ 変更点1：Cookieから読み出すときに、記号を日本語に戻す処理を追加
def get_current_user(request: Request):
    raw_user = request.cookies.get("session_user")
    if not raw_user:
        raise HTTPException(status_code=401, detail="ログインが必要です")
    return urllib.parse.unquote(raw_user)  # 記号から日本語に復元

@app.get("/users")
def get_users():
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT username FROM users_v6")
    users = [{"username": row[0]} for row in c.fetchall()]
    conn.close()
    return users

@app.get("/users/{username}/icon")
def get_user_icon(username: str):
    conn = get_db_connection()
    c = conn.cursor()
    if DB_URL:
        c.execute("SELECT icon_data FROM users_v6 WHERE username = %s", (username,))
    else:
        c.execute("SELECT icon_data FROM users_v6 WHERE username = ?", (username,))
    row = c.fetchone()
    conn.close()
    
    if row and row[0]:
        img_bytes = bytes(row[0]) if isinstance(row[0], memoryview) else row[0]
        return FastAPIResponse(content=img_bytes, media_type="image/jpeg")
    else:
        import requests
        # ★ 変更点2：初期アイコンを取ってくるURLにも日本語を安全に変換して渡す
        safe_seed = urllib.parse.quote(username)
        svg = requests.get(f"https://api.dicebear.com/7.x/bottts/svg?seed={safe_seed}").text
        return FastAPIResponse(content=svg, media_type="image/svg+xml")

@app.post("/login")
def login(data: LoginData, response: Response):
    conn = get_db_connection()
    c = conn.cursor()
    if DB_URL:
        c.execute("SELECT password FROM users_v6 WHERE username = %s", (data.username,))
    else:
        c.execute("SELECT password FROM users_v6 WHERE username = ?", (data.username,))
    row = c.fetchone()
    conn.close()

    if row and row[0] == data.password:
        # ★ 変更点3：Cookieに保存する前に、日本語を安全な記号に変換
        safe_username = urllib.parse.quote(data.username)
        response.set_cookie(key="session_user", value=safe_username, max_age=2592000, httponly=True, samesite="lax")
        return {"message": "ログイン成功！"}
    else:
        raise HTTPException(status_code=400, detail="パスワードが違います")

@app.post("/logout")
def logout(response: Response):
    response.delete_cookie(key="session_user")
    return {"message": "ログアウトしました"}

@app.get("/me")
def get_me(username: str = Depends(get_current_user)):
    return {"username": username}

@app.post("/me/icon")
async def update_icon(file: UploadFile = File(...), username: str = Depends(get_current_user)):
    file_bytes = await file.read()
    conn = get_db_connection()
    c = conn.cursor()
    if DB_URL:
        import psycopg2
        c.execute("UPDATE users_v6 SET icon_data = %s WHERE username = %s", (psycopg2.Binary(file_bytes), username))
    else:
        c.execute("UPDATE users_v6 SET icon_data = ? WHERE username = ?", (file_bytes, username))
    conn.commit()
    conn.close()
    return {"message": "アイコンを更新しました"}

@app.get("/posts")
def get_posts(username: str = Depends(get_current_user)):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT name, content, created_at FROM posts_v6 ORDER BY id DESC")
    posts = [{"name": row[0], "content": row[1], "created_at": row[2]} for row in c.fetchall()]
    conn.close()
    return posts

@app.post("/posts")
def create_post(post: PostData, username: str = Depends(get_current_user)):
    conn = get_db_connection()
    c = conn.cursor()
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
    if DB_URL:
        c.execute("INSERT INTO posts_v6 (name, content, created_at) VALUES (%s, %s, %s)", (username, post.content, now))
    else:
        c.execute("INSERT INTO posts_v6 (name, content, created_at) VALUES (?, ?, ?)", (username, post.content, now))
    conn.commit()
    conn.close()
    return {"message": "投稿完了！"}

@app.get("/")
def read_index():
    return FileResponse("index.html")

@app.get("/favicon.ico")
def get_favicon():
    return FileResponse("favicon.ico")
