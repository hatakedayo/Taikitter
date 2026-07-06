import os
import sqlite3
from fastapi import FastAPI, Depends, HTTPException, status, Response, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from fastapi.responses import FileResponse, JSONResponse
from datetime import datetime, timezone

app = FastAPI()

# フロントエンドからの通信を許可
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=True, # クッキー（ログイン情報）のやり取りを許可
)

# データの形を定義
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
    
    # 1. ユーザー管理用のテーブル（users）を作成
    if DB_URL:
        c.execute("""
            CREATE TABLE IF NOT EXISTS users (
                username TEXT PRIMARY KEY,
                password TEXT
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS posts_v3 (
                id SERIAL PRIMARY KEY,
                name TEXT,
                content TEXT,
                created_at TEXT
            )
        """)
    else:
        c.execute("""
            CREATE TABLE IF NOT EXISTS users (
                username TEXT PRIMARY KEY,
                password TEXT
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS posts_v3 (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT,
                content TEXT,
                created_at TEXT
            )
        """)
    
    # 2. 友達6人分の初期アカウントを登録（すでに無ければ追加）
    # ※ password は簡易的に平文で保存していますが、身内用として機能します
    friends = [
        ("user1", "pass1"),
        ("user2", "pass2"),
        ("user3", "pass3"),
        ("user4", "pass4"),
        ("user5", "pass5"),
        ("user6", "pass6")
    ]
    for username, password in friends:
        try:
            if DB_URL:
                c.execute("INSERT INTO users (username, password) VALUES (%s, %s) ON CONFLICT DO NOTHING", (username, password))
            else:
                c.execute("INSERT INTO users (username, password) VALUES (?, ?) OR IGNORE", (username, password))
        except:
            pass

    conn.commit()
    conn.close()

init_db()

# 🔑 ログインしているかチェックする共通関数（クッキーから名前を読み取る）
def get_current_user(request: Request):
    username = request.cookies.get("session_user")
    if not username:
        raise HTTPException(status_code=401, detail="ログインが必要です")
    return username

# ① ログイン処理（IDとパスワードが合っていれば、クッキーに名前を刻む）
@app.post("/login")
def login(data: LoginData, response: Response):
    conn = get_db_connection()
    c = conn.cursor()
    if DB_URL:
        c.execute("SELECT password FROM users WHERE username = %s", (data.username,))
    else:
        c.execute("SELECT password FROM users WHERE username = ?", (data.username,))
    row = c.fetchone()
    conn.close()

    if row and row[0] == data.password:
        # ログイン成功：ブラウザにクッキーを保存させる
        response.set_cookie(key="session_user", value=data.username, max_age=2592000, httponly=True, samesite="lax")
        return {"message": "ログイン成功！", "username": data.username}
    else:
        raise HTTPException(status_code=400, detail="ユーザー名またはパスワードが違います")

# ② ログアウト処理（クッキーを消す）
@app.post("/logout")
def logout(response: Response):
    response.delete_cookie(key="session_user")
    return {"message": "ログアウトしました"}

# ③ ログイン中のユーザー情報を取得するAPI
@app.get("/me")
def get_me(username: str = Depends(get_current_user)):
    return {"username": username}

# ④ タイムライン取得（ログイン中のみ許可）
@app.get("/posts")
def get_posts(username: str = Depends(get_current_user)):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT name, content, created_at FROM posts_v3 ORDER BY id DESC")
    posts = [{"name": row[0], "content": row[1], "created_at": row[2]} for row in c.fetchall()]
    conn.close()
    return posts

# ⑤ 新規投稿（ログイン中の名前を自動で使うので、nameの送信は不要！）
@app.post("/posts")
def create_post(post: PostData, username: str = Depends(get_current_user)):
    conn = get_db_connection()
    c = conn.cursor()
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
    
    if DB_URL:
        c.execute("INSERT INTO posts_v3 (name, content, created_at) VALUES (%s, %s, %s)", (username, post.content, now))
    else:
        c.execute("INSERT INTO posts_v3 (name, content, created_at) VALUES (?, ?, ?)", (username, post.content, now))
    conn.commit()
    conn.close()
    return {"message": "投稿完了！"}

# 画面とアイコンの配信
@app.get("/")
def read_index():
    return FileResponse("index.html")

@app.get("/favicon.ico")
def get_favicon():
    return FileResponse("favicon.ico")
