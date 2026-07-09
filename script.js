
let selectedUsername = "";
let currentLoggedInUser = "";

window.onload = function () { loadUserGrid(); checkLoginStatus(); };

function switchTab(tabName) {
    document.querySelectorAll('.tab-content').forEach(tab => tab.classList.remove('active'));
    document.querySelectorAll('.nav-item').forEach(nav => nav.classList.remove('active'));

    document.getElementById(`view-${tabName}`).classList.add('active');

    const headerTitle = document.getElementById('header-title');
    const headerBack = document.getElementById('header-back');
    headerBack.style.display = 'none'; // 基本は非表示

    if (tabName === 'home') {
        document.getElementById('nav-home').classList.add('active');
        headerTitle.innerText = 'ホーム';
        loadPosts(); // ホームに戻るたびに最新化
    } else if (tabName === 'notifications') {
        document.getElementById('nav-notifications').classList.add('active');
        headerTitle.innerText = '通知';
    } else if (tabName === 'profile') {
        document.getElementById('nav-profile').classList.add('active');
        headerTitle.innerText = 'プロフィール';
        document.getElementById('profile-name').innerText = "@" + currentLoggedInUser;
        document.getElementById('profile-large-icon').src = `/users/${encodeURIComponent(currentLoggedInUser)}/icon?t=${Date.now()}`;
    } else if (tabName === 'thread') {
        headerTitle.innerText = 'ポスト';
        headerBack.style.display = 'block'; // スレッドの時は戻るボタンを表示
    }
}

// モーダル操作
function openPostModal() { document.getElementById("createPostModal").style.display = "flex"; }
function closePostModal() { document.getElementById("createPostModal").style.display = "none"; }

function openReplyModal(postId, postName, postContent) {
    document.getElementById("replyTargetId").value = postId;
    document.getElementById("replyTargetName").innerText = "@" + postName;
    document.getElementById("replyTargetText").innerText = postContent;
    document.getElementById("replyModal").style.display = "flex";
}
function closeReplyModal() { document.getElementById("replyModal").style.display = "none"; }

function openIconModal() { document.getElementById("iconModal").style.display = "flex"; }
function closeIconModal() { document.getElementById("iconModal").style.display = "none"; }

// ★ 新設：パスワード変更モーダルの操作
function openPasswordModal() { 
    document.getElementById("passwordModal").style.display = "flex"; 
    document.getElementById("passwordError").style.display = "none";
}
function closePasswordModal() { 
    document.getElementById("passwordModal").style.display = "none"; 
    // 閉じる時に、入力欄を空っぽにリセットする
    document.getElementById("currentPasswordInput").value = "";
    document.getElementById("newPasswordInput").value = "";
    document.getElementById("confirmPasswordInput").value = "";
}

// API通信関連
async function loadUserGrid() {
    const response = await fetch("/users");
    const users = await response.json();
    const grid = document.getElementById("userGrid");
    grid.innerHTML = "";
    users.forEach(user => {
        const card = document.createElement("div");
        card.className = "user-card";
        card.id = `card-${user.username}`;
        card.innerHTML = `<img src="/users/${encodeURIComponent(user.username)}/icon" alt=""><div>${user.username}</div>`;
        card.onclick = () => selectUser(user.username);
        grid.appendChild(card);
    });
}
function selectUser(username) {
    selectedUsername = username;
    document.querySelectorAll(".user-card").forEach(c => c.classList.remove("selected"));
    document.getElementById(`card-${username}`).classList.add("selected");
}

async function checkLoginStatus() {
    const response = await fetch("/me");
    if (response.ok) {
        const me = await response.json();
        currentLoggedInUser = me.username;
        document.getElementById("login-screen").style.display = "none";
        document.getElementById("main-screen").style.display = "block";

        document.getElementById("myIconPostModal").src = `/users/${encodeURIComponent(me.username)}/icon?t=${Date.now()}`;
        document.getElementById("myIconReplyModal").src = `/users/${encodeURIComponent(me.username)}/icon?t=${Date.now()}`;

        switchTab('home');
    } else {
        document.getElementById("login-screen").style.display = "block";
        document.getElementById("main-screen").style.display = "none";
    }
}

async function login() {
    const pass = document.getElementById("passwordInput").value;
    const response = await fetch("/login", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username: selectedUsername, password: pass })
    });
    if (response.ok) {
        document.getElementById("loginError").style.display = "none";
        document.getElementById("passwordInput").value = "";
        checkLoginStatus();
    } else {
        document.getElementById("loginError").style.display = "block";
    }
}

async function logout() {
    await fetch("/logout", { method: "POST" });
    selectedUsername = ""; currentLoggedInUser = "";
    checkLoginStatus(); loadUserGrid();
}

// ★ HTMLを安全に組み立てるための魔法の関数（普通の投稿も返信もこれで描画します）
function createPostElement(post, isMainInThread = false) {
    const date = new Date(post.created_at + "Z");
    const timeString = date.toLocaleString('ja-JP', { month: 'numeric', day: 'numeric', hour: '2-digit', minute: '2-digit' });

    const div = document.createElement("div");
    div.className = "post" + (isMainInThread ? " main-post-in-thread" : "");

    let likeClass = "action-btn like-btn";
    let heartImgSrc = "/icons/kitsu_gray.svg";
    let canLike = true;
    if (post.name === currentLoggedInUser) {
        likeClass += " disabled"; heartImgSrc = "/icons/kitsu_disabled.svg"; canLike = false;
    } else if (post.is_liked) {
        likeClass += " liked"; heartImgSrc = "/icons/kitsu_pink.svg";
    }

    div.innerHTML = `
                <img class="user-icon" src="/users/${encodeURIComponent(post.name)}/icon" alt="">
                <div class="post-right">
                    <div class="post-header">
                        <div class="post-name">@${post.name}</div>
                        <div class="post-time">${timeString}</div>
                    </div>
                    <div class="post-text"></div>
                    <div class="post-actions">
                        <div class="${likeClass} like-trigger">
                            <img src="${heartImgSrc}" class="custom-heart-icon" alt="heart"> 
                            <span style="${post.is_liked ? 'color: #f91880;' : ''}">${post.like_count > 0 ? post.like_count : ''}</span>
                        </div>
                        <div class="action-btn reply-btn">💬 <span>${post.reply_count > 0 ? post.reply_count : ''}</span></div>                        
                        <div class="action-btn view-btn">📊 <span>${post.view_count > 0 ? post.view_count : 0}</span></div>
                    </div>
                </div>
            `;

    // テキストやクリック処理を安全に設定
    const textDiv = div.querySelector(".post-text");
    textDiv.textContent = post.content;
    textDiv.onclick = () => viewThread(post.id);

    div.querySelector(".reply-btn").onclick = () => openReplyModal(post.id, post.name, post.content);
    if (canLike) div.querySelector(".like-trigger").onclick = () => toggleLike(post.id);

    return div;
}

async function loadPosts() {
    const response = await fetch("/posts");
    if (!response.ok) return;
    const posts = await response.json();
    const timeline = document.getElementById("timeline");
    timeline.innerHTML = "";
    posts.forEach(post => timeline.appendChild(createPostElement(post)));
}

// ★ 新機能：スレッド（会話）画面を開く処理
async function viewThread(postId) {
    const response = await fetch(`/posts/${postId}/thread`);
    if (!response.ok) return;
    const data = await response.json();

    const threadMain = document.getElementById("thread-main");
    threadMain.innerHTML = "";
    threadMain.appendChild(createPostElement(data.main_post, true)); // 親は文字を大きく

    const threadReplies = document.getElementById("thread-replies");
    threadReplies.innerHTML = "";
    data.replies.forEach(reply => threadReplies.appendChild(createPostElement(reply)));

    switchTab('thread');
}

async function sendPost() {
    const content = document.getElementById("contentInput").value;
    if (content === "") return;
    await fetch("/posts", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ content: content })
    });
    document.getElementById("contentInput").value = "";
    closePostModal(); switchTab('home');
}

// ★ 新機能：返信を送信する処理
async function sendReply() {
    const content = document.getElementById("replyContentInput").value;
    const targetId = parseInt(document.getElementById("replyTargetId").value);
    if (content === "") return;

    await fetch("/posts", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ content: content, parent_id: targetId })
    });

    document.getElementById("replyContentInput").value = "";
    closeReplyModal();
    viewThread(targetId); // 送信後はスレッド画面を開く
}

async function toggleLike(postId) {
    await fetch(`/posts/${postId}/like`, { method: "POST" });
    // 今どの画面を開いているかによって、更新する場所を変える
    if (document.getElementById("view-thread").classList.contains("active")) {
        const currentPostId = document.querySelector(".main-post-in-thread .reply-btn").onclick.toString().match(/\d+/)[0];
        viewThread(currentPostId);
    } else {
        loadPosts();
    }
}

async function saveIcon() {
    const fileInput = document.getElementById("iconFileInput");
    if (fileInput.files.length === 0) return;
    const formData = new FormData();
    formData.append("file", fileInput.files[0]);
    await fetch("/me/icon", { method: "POST", body: formData });
    closeIconModal(); checkLoginStatus();
}


// ★ 新設：パスワードを保存する処理
async function savePassword() {
    const currentPw = document.getElementById("currentPasswordInput").value;
    const newPw = document.getElementById("newPasswordInput").value;
    const confirmPw = document.getElementById("confirmPasswordInput").value;
    const errorDiv = document.getElementById("passwordError");
    
    // 1. 画面側での入力チェック（空欄がないか、2回の入力が一致しているか）
    if (!currentPw || !newPw || !confirmPw) {
        errorDiv.innerText = "すべての項目を入力してください";
        errorDiv.style.display = "block";
        return;
    }
    if (newPw !== confirmPw) {
        errorDiv.innerText = "新しいパスワードが一致しません";
        errorDiv.style.display = "block";
        return;
    }
    
    // 2. PythonのAPI（/me/password）にデータを送信
    const response = await fetch("/me/password", {
        method: "POST", 
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ current_password: currentPw, new_password: newPw })
    });
    
    // 3. 成功した場合の処理（アラートを出して、強制ログアウト）
    if (response.ok) {
        alert("パスワードを変更しました！\n安全のため、新しいパスワードでもう一度ログインしてください。");
        closePasswordModal();
        logout(); 
    } else {
        // 失敗した場合（現在のパスワードが違うなど）はエラー文字を表示
        const data = await response.json();
        errorDiv.innerText = data.detail || "エラーが発生しました";
        errorDiv.style.display = "block";
    }
}

