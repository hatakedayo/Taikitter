
import os
import sqlite3
import urllib.parse
from fastapi import FastAPI, Depends, HTTPException, status, Response, Request, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from fastapi.responses import FileResponse, Response as FastAPIResponse
from datetime import datetime, timezone
from typing import Optional
import cloudinary
import cloudinary.uploader

app = FastAPI()

app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"],
    allow_headers=["*"], allow_credentials=True,
)

cloudinary.config(
    cloud_name = os.environ.get("CLOUDINARY_CLOUD_NAME"),
    api_key = os.environ.get("CLOUDINARY_API_KEY"),
    api_secret = os.environ.get("CLOUDINARY_API_SECRET"),
    secure = True
)

class LoginData(BaseModel):
    username: str
    password: str

# ★ 投稿データに「親ポストのID（返信先）」を受け取れるようにしました
class PostData(BaseModel):
    content: str
    parent_id: Optional[int] = None
    image_url: Optional[str] = None

# ★ 新設：パスワード変更用のデータ型
class PasswordChangeData(BaseModel):
    current_password: str
    new_password: str


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
        conn.commit() # 一度セーブする
    else:
        c.execute("CREATE TABLE IF NOT EXISTS users_v6 (username TEXT PRIMARY KEY, password TEXT, icon_data BLOB)")
        c.execute("CREATE TABLE IF NOT EXISTS posts_v6 (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, content TEXT, created_at TEXT)")
        c.execute("CREATE TABLE IF NOT EXISTS likes (post_id INTEGER, username TEXT, PRIMARY KEY (post_id, username))")
        c.execute("CREATE TABLE IF NOT EXISTS views (post_id INTEGER, username TEXT, PRIMARY KEY (post_id, username))")
        conn.commit()
    
    # 1. parent_id の追加（失敗したらリセット）
    try:
        c.execute("ALTER TABLE posts_v6 ADD COLUMN parent_id INTEGER DEFAULT NULL")
        conn.commit()
    except:
        conn.rollback() 
    
    # 2. image_url の追加（失敗したらリセット）
    try:
        c.execute("ALTER TABLE posts_v6 ADD COLUMN image_url TEXT DEFAULT NULL")
        conn.commit()
    except:
        conn.rollback()

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
            if DB_URL: c.execute("INSERT INTO users_v6 (username, password) VALUES (%s, %s) ON CONFLICT DO NOTHING", (username, password))
            else: c.execute("INSERT INTO users_v6 (username, password) VALUES (?, ?) OR IGNORE", (username, password))
            conn.commit()
        except:
            conn.rollback()
            
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

    c.execute("SELECT id, name, content, created_at, image_url FROM posts_v6 WHERE parent_id IS NULL ORDER BY id DESC")
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
            "reply_count": replies_map.get(pid, 0),
            "image_url": row[4] # ★ 追加
        })
        
    conn.commit() 
    conn.close()
    return posts

# ★ 新機能：特定の投稿とその返信一覧（スレッド）を取得するAPI
@app.get("/posts/{post_id}/thread")
def get_thread(post_id: int, username: str = Depends(get_current_user)):
    conn = get_db_connection()
    c = conn.cursor()
    if DB_URL: c.execute("SELECT id, name, content, created_at, image_url FROM posts_v6 WHERE id = %s", (post_id,))
    else: c.execute("SELECT id, name, content, created_at, image_url FROM posts_v6 WHERE id = ?", (post_id,))
    main_data = c.fetchone()
    if not main_data:
        conn.close()
        raise HTTPException(status_code=404)
        
    if DB_URL: c.execute("SELECT id, name, content, created_at, image_url FROM posts_v6 WHERE parent_id = %s ORDER BY id ASC", (post_id,))
    else: c.execute("SELECT id, name, content, created_at, image_url FROM posts_v6 WHERE parent_id = ? ORDER BY id ASC", (post_id,))
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
            "reply_count": replies_map.get(pid, 0),
            "image_url": row[4] # ★ 追加
        }
    conn.close()
    return {"main_post": format_post(main_data), "replies": [format_post(r) for r in replies_data]}

@app.post("/posts")
def create_post(post: PostData, username: str = Depends(get_current_user)):
    conn = get_db_connection()
    c = conn.cursor()
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
    if DB_URL:
        c.execute("INSERT INTO posts_v6 (name, content, created_at, parent_id, image_url) VALUES (%s, %s, %s, %s, %s)", (username, post.content, now, post.parent_id, post.image_url))
    else:
        c.execute("INSERT INTO posts_v6 (name, content, created_at, parent_id, image_url) VALUES (?, ?, ?, ?, ?)", (username, post.content, now, post.parent_id, post.image_url))
    conn.commit()
    conn.close()
    return {"message": "投稿完了！"}

@app.post("/posts/image")
async def upload_post_image(file: UploadFile = File(...), username: str = Depends(get_current_user)):
    try:
        file_bytes = await file.read()
        # Cloudinaryに画像を送信。自動的にサイズ調整と最適化（圧縮）をかける設定を施しています
        result = cloudinary.uploader.upload(
            file_bytes,
            transformation=[
                {"width": 800, "crop": "limit"}, # 横幅は最大800pxに自動縮小
                {"quality": "auto"},            # 画質を劣化させずに容量を自動最適化
                {"fetch_format": "auto"}        # ブラウザに最適な形式(WebPなど)に自動変換
            ]
        )
        return {"image_url": result["secure_url"]} # 生成された「https://...」のURLを返す
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

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


# ★ 新設：パスワードを変更するAPI
@app.post("/me/password")
def change_password(data: PasswordChangeData, username: str = Depends(get_current_user)):
    conn = get_db_connection()
    c = conn.cursor()
    
    # 1. 現在のパスワードが合っているか確認
    if DB_URL: c.execute("SELECT password FROM users_v6 WHERE username = %s", (username,))
    else: c.execute("SELECT password FROM users_v6 WHERE username = ?", (username,))
    row = c.fetchone()
    
    # もしパスワードが違ったらエラーを返す
    if not row or row[0] != data.current_password:
        conn.close()
        raise HTTPException(status_code=400, detail="現在のパスワードが違います")
    
    # 2. 新しいパスワードでデータベースを上書き保存
    if DB_URL: c.execute("UPDATE users_v6 SET password = %s WHERE username = %s", (data.new_password, username))
    else: c.execute("UPDATE users_v6 SET password = ? WHERE username = ?", (data.new_password, username))
    
    conn.commit()
    conn.close()
    return {"message": "パスワードを更新しました"}


# ★ 新設：特定のユーザーの投稿一覧を取得するAPI
@app.get("/users/{username}/posts")
def get_user_posts(username: str, current_user: str = Depends(get_current_user)):
    conn = get_db_connection()
    c = conn.cursor()
    if DB_URL: c.execute("SELECT id, name, content, created_at, image_url FROM posts_v6 WHERE name = %s AND parent_id IS NULL ORDER BY id DESC", (username,))
    else: c.execute("SELECT id, name, content, created_at, image_url FROM posts_v6 WHERE name = ? AND parent_id IS NULL ORDER BY id DESC", (username,))
    posts_data = c.fetchall()
    
    c.execute("SELECT post_id, username FROM likes")
    likes_map = {}
    for pid, uname in c.fetchall(): likes_map.setdefault(pid, []).append(uname)
    c.execute("SELECT post_id, username FROM views")
    views_map = {}
    for pid, uname in c.fetchall(): views_map.setdefault(pid, []).append(uname)
    c.execute("SELECT parent_id, COUNT(id) FROM posts_v6 WHERE parent_id IS NOT NULL GROUP BY parent_id")
    replies_map = dict(c.fetchall())
        
    posts = []
    for row in posts_data:
        pid, post_author = row[0], row[1]
        posts.append({
            "id": pid, "name": post_author, "content": row[2], "created_at": row[3],
            "like_count": len(likes_map.get(pid, [])),
            "is_liked": current_user in likes_map.get(pid, []),
            "view_count": len([u for u in views_map.get(pid, []) if u != post_author]),
            "reply_count": replies_map.get(pid, 0),
            "image_url": row[4] # ★ 追加
        })
    conn.close()
    return posts


@app.get("/")
def read_index(): return FileResponse("index.html")
    
@app.get("/favicon.ico")
def get_favicon(): return FileResponse("favicon.ico")

@app.get("/taikitter_logo.svg")
def get_logo(): return FileResponse("taikitter_logo.svg")

# ★ 新しく作ったJSファイルを配る設定
@app.get("/script.js")
def get_script():
    return FileResponse("script.js")

@app.get("/style.css")
def get_css(): return FileResponse("style.css")
    
@app.get("/icons/{filename}")
def get_custom_icon(filename: str):
    if filename in ["kitsu_pink.svg", "kitsu_gray.svg", "kitsu_disabled.svg", "reply.svg", "view.svg"]: return FileResponse(filename)
    return {"error": "画像が見つかりません"}
