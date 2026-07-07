import os
import sqlite3
import urllib.parse
from fastapi import FastAPI, Depends, HTTPException, status, Response, Request, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from fastapi.responses import FileResponse, Response as FastAPIResponse
from datetime import datetime, timezone
from typing import Optional

app = FastAPI()

app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"],
    allow_headers=["*"], allow_credentials=True,
)

class LoginData(BaseModel):
    username: str
    password: str

# ★ 投稿データに「親ポストのID（返信先）」を受け取れるようにしました
class PostData(BaseModel):
    content: str
    parent_id: Optional[int] = None

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
        c.execute("CREATE TABLE IF NOT EXISTS users_v6 (username TEXT PRIMARY KEY, password TEXT, icon_data BYTEA)")
        c.execute("CREATE TABLE IF NOT EXISTS posts_v6 (id SERIAL PRIMARY KEY, name TEXT, content TEXT, created_at TEXT)")
        c.execute("CREATE TABLE IF NOT EXISTS likes (post_id INTEGER, username TEXT, PRIMARY KEY (post_id, username))")
        c.execute("CREATE TABLE IF NOT EXISTS views (post_id INTEGER, username TEXT, PRIMARY KEY (post_id, username))")
    else:
        c.execute("CREATE TABLE IF NOT EXISTS users_v6 (username TEXT PRIMARY KEY, password TEXT, icon_data BLOB)")
        c.execute("CREATE TABLE IF NOT EXISTS posts_v6 (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, content TEXT, created_at TEXT)")
        c.execute("CREATE TABLE IF NOT EXISTS likes (post_id INTEGER, username TEXT, PRIMARY KEY (post_id, username))")
        c.execute("CREATE TABLE IF NOT EXISTS views (post_id INTEGER, username TEXT, PRIMARY KEY (post_id, username))")
    
    # ★ 今までのデータを消さずに「返信先ID」の箱だけを安全に追加する魔法のコード
    try:
        c.execute("ALTER TABLE posts_v6 ADD COLUMN parent_id INTEGER DEFAULT NULL")
    except:
        pass # すでに追加されている場合はスルーします
    
    # ★ ここは設定した友達の日本語名に書き換えてください
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
        except: pass
    conn.commit()
    conn.close()

init_db()

def get_current_user(request: Request):
    raw_user = request.cookies.get("session_user")
    if not raw_user: raise HTTPException(status_code=401, detail="ログインが必要です")
    return urllib.parse.unquote(raw_user)

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
    if DB_URL: c.execute("SELECT icon_data FROM users_v6 WHERE username = %s", (username,))
    else: c.execute("SELECT icon_data FROM users_v6 WHERE username = ?", (username,))
    row = c.fetchone()
    conn.close()
    
    if row and row[0]:
        img_bytes = bytes(row[0]) if isinstance(row[0], memoryview) else row[0]
        return FastAPIResponse(content=img_bytes, media_type="image/jpeg")
    else:
        import requests
        safe_seed = urllib.parse.quote(username)
        svg = requests.get(f"https://api.dicebear.com/7.x/bottts/svg?seed={safe_seed}").text
        return FastAPIResponse(content=svg, media_type="image/svg+xml")

@app.post("/login")
def login(data: LoginData, response: Response):
    conn = get_db_connection()
    c = conn.cursor()
    if DB_URL: c.execute("SELECT password FROM users_v6 WHERE username = %s", (data.username,))
    else: c.execute("SELECT password FROM users_v6 WHERE username = ?", (data.username,))
    row = c.fetchone()
    conn.close()
    if row and row[0] == data.password:
        safe_username = urllib.parse.quote(data.username)
        response.set_cookie(key="session_user", value=safe_username, max_age=2592000, httponly=True, samesite="lax")
        return {"message": "ログイン成功！"}
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
    # ★ タイムラインには「返信ではない普通の投稿（parent_id IS NULL）」だけを表示する
    c.execute("SELECT id, name, content, created_at FROM posts_v6 WHERE parent_id IS NULL ORDER BY id DESC")
    posts_data = c.fetchall()
    
    if posts_data:
        for row in posts_data:
            pid, post_author = row[0], row[1]
            if post_author != username:
                if DB_URL: c.execute("INSERT INTO views (post_id, username) VALUES (%s, %s) ON CONFLICT DO NOTHING", (pid, username))
                else: c.execute("INSERT INTO views (post_id, username) VALUES (?, ?) OR IGNORE", (pid, username))
    
    c.execute("SELECT post_id, username FROM likes")
    likes_map = {}
    for pid, uname in c.fetchall(): likes_map.setdefault(pid, []).append(uname)
        
    c.execute("SELECT post_id, username FROM views")
    views_map = {}
    for pid, uname in c.fetchall(): views_map.setdefault(pid, []).append(uname)
    
    # ★ 各投稿への返信の数（リプライ数）をまとめて計算
    c.execute("SELECT parent_id, COUNT(id) FROM posts_v6 WHERE parent_id IS NOT NULL GROUP BY parent_id")
    replies_map = dict(c.fetchall())
        
    posts = []
    for row in posts_data:
        pid, post_author = row[0], row[1]
        posts.append({
            "id": pid, "name": post_author, "content": row[2], "created_at": row[3],
            "like_count": len(likes_map.get(pid, [])),
            "is_liked": username in likes_map.get(pid, []),
            "view_count": len([u for u in views_map.get(pid, []) if u != post_author]),
            "reply_count": replies_map.get(pid, 0)
        })
        
    conn.commit() 
    conn.close()
    return posts

# ★ 新機能：特定の投稿とその返信一覧（スレッド）を取得するAPI
@app.get("/posts/{post_id}/thread")
def get_thread(post_id: int, username: str = Depends(get_current_user)):
    conn = get_db_connection()
    c = conn.cursor()
    
    if DB_URL: c.execute("SELECT id, name, content, created_at FROM posts_v6 WHERE id = %s", (post_id,))
    else: c.execute("SELECT id, name, content, created_at FROM posts_v6 WHERE id = ?", (post_id,))
    main_data = c.fetchone()
    if not main_data:
        conn.close()
        raise HTTPException(status_code=404)
        
    if DB_URL: c.execute("SELECT id, name, content, created_at FROM posts_v6 WHERE parent_id = %s ORDER BY id ASC", (post_id,))
    else: c.execute("SELECT id, name, content, created_at FROM posts_v6 WHERE parent_id = ? ORDER BY id ASC", (post_id,))
    replies_data = c.fetchall()
    
    c.execute("SELECT post_id, username FROM likes")
    likes_map = {}
    for pid, uname in c.fetchall(): likes_map.setdefault(pid, []).append(uname)
        
    c.execute("SELECT post_id, username FROM views")
    views_map = {}
    for pid, uname in c.fetchall(): views_map.setdefault(pid, []).append(uname)
        
    c.execute("SELECT parent_id, COUNT(id) FROM posts_v6 WHERE parent_id IS NOT NULL GROUP BY parent_id")
    replies_map = dict(c.fetchall())
    
    def format_post(row):
        pid, author = row[0], row[1]
        return {
            "id": pid, "name": author, "content": row[2], "created_at": row[3],
            "like_count": len(likes_map.get(pid, [])),
            "is_liked": username in likes_map.get(pid, []),
            "view_count": len([u for u in views_map.get(pid, []) if u != author]),
            "reply_count": replies_map.get(pid, 0)
        }
        
    conn.close()
    return {"main_post": format_post(main_data), "replies": [format_post(r) for r in replies_data]}

@app.post("/posts")
def create_post(post: PostData, username: str = Depends(get_current_user)):
    conn = get_db_connection()
    c = conn.cursor()
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
    # ★ 返信先ID（parent_id）も一緒に保存する
    if DB_URL:
        c.execute("INSERT INTO posts_v6 (name, content, created_at, parent_id) VALUES (%s, %s, %s, %s)", (username, post.content, now, post.parent_id))
    else:
        c.execute("INSERT INTO posts_v6 (name, content, created_at, parent_id) VALUES (?, ?, ?, ?)", (username, post.content, now, post.parent_id))
    conn.commit()
    conn.close()
    return {"message": "投稿完了！"}

@app.post("/posts/{post_id}/like")
def toggle_like(post_id: int, username: str = Depends(get_current_user)):
    conn = get_db_connection()
    c = conn.cursor()
    if DB_URL: c.execute("SELECT name FROM posts_v6 WHERE id = %s", (post_id,))
    else: c.execute("SELECT name FROM posts_v6 WHERE id = ?", (post_id,))
    post_row = c.fetchone()
    if not post_row:
        conn.close()
        raise HTTPException(status_code=404)
    if post_row[0] == username:
        conn.close()
        raise HTTPException(status_code=400, detail="自分の投稿にはいいねできません")

    if DB_URL: c.execute("SELECT 1 FROM likes WHERE post_id = %s AND username = %s", (post_id, username))
    else: c.execute("SELECT 1 FROM likes WHERE post_id = ? AND username = ?", (post_id, username))
    if c.fetchone():
        if DB_URL: c.execute("DELETE FROM likes WHERE post_id = %s AND username = %s", (post_id, username))
        else: c.execute("DELETE FROM likes WHERE post_id = ? AND username = ?", (post_id, username))
    else:
        if DB_URL: c.execute("INSERT INTO likes (post_id, username) VALUES (%s, %s)", (post_id, username))
        else: c.execute("INSERT INTO likes (post_id, username) VALUES (?, ?)", (post_id, username))
    conn.commit()
    conn.close()
    return {"message": "いいね状態を更新"}

@app.get("/")
def read_index(): return FileResponse("index.html")
    
@app.get("/favicon.ico")
def get_favicon(): return FileResponse("favicon.ico")

# ★ 新しく作ったJSファイルを配る設定
@app.get("/script.js")
def get_script():
    return FileResponse("script.js")

@app.get("/style.css")
def get_css(): return FileResponse("style.css")
    
@app.get("/icons/{filename}")
def get_custom_icon(filename: str):
    if filename in ["kitsu_pink.ico", "kitsu_gray.ico", "kitsu_disabled.ico"]: return FileResponse(filename)
    return {"error": "画像が見つかりません"}
