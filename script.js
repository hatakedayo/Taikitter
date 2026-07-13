
let selectedUsername = "";
let currentLoggedInUser = "";
let selectedPostFile = null;


window.onload = function () { loadUserGrid(); checkLoginStatus(); };

// ★ 変更：引数に targetUser（誰の画面を見るか）を追加しました
function switchTab(tabName, targetUser = null) {
    document.querySelectorAll('.tab-content').forEach(tab => tab.classList.remove('active'));
    document.querySelectorAll('.nav-item').forEach(nav => nav.classList.remove('active'));

    document.getElementById(`view-${tabName}`).classList.add('active');

    const headerTitle = document.getElementById('header-title');
    const headerBack = document.getElementById('header-back');
    headerBack.style.display = 'none';

    if (tabName === 'home') {
        document.getElementById('nav-home').classList.add('active');
        headerTitle.innerText = 'ホーム';
        loadPosts();
    } else if (tabName === 'notifications') {
        document.getElementById('nav-notifications').classList.add('active');
        headerTitle.innerText = '通知';
        loadNotifications(); // ★ これを追加！
    } else if (tabName === 'profile') {
        // ★ 誰のプロフィールを見るか（指定がなければ自分）
        const viewUser = targetUser || currentLoggedInUser;

        // 自分のプロフィールなら下の「プロフ」アイコンを光らせる。他人なら「←」戻るボタンを出す。
        if (viewUser === currentLoggedInUser) {
            document.getElementById('nav-profile').classList.add('active');
        } else {
            headerBack.style.display = 'block';
        }

        headerTitle.innerText = 'プロフィール';
        document.getElementById('profile-name').innerText = "@" + viewUser;
        document.getElementById('profile-large-icon').src = `/users/${encodeURIComponent(viewUser)}/icon?t=${Date.now()}`;

        // 自分なら設定ボタンを出し、他人なら隠す
        if (viewUser === currentLoggedInUser) {
            document.getElementById('my-profile-actions').style.display = 'flex';
        } else {
            document.getElementById('my-profile-actions').style.display = 'none';
        }

        // ★ その人の投稿一覧を読み込む
        loadUserPosts(viewUser);

    } else if (tabName === 'thread') {
        headerTitle.innerText = 'ポスト';
        headerBack.style.display = 'block';
    }
}

// ★ 新設：他人のプロフィールを開く処理
function viewUserProfile(username) {
    switchTab('profile', username);
}

// ★ 新設：特定のユーザーの投稿だけを読み込んで表示する処理
async function loadUserPosts(username) {
    const timeline = document.getElementById("profile-timeline");
    timeline.innerHTML = "<div style='text-align:center; padding: 20px; color:#536471;'>読み込み中...</div>";

    const response = await fetch(`/users/${encodeURIComponent(username)}/posts`);
    if (!response.ok) return;
    const posts = await response.json();
    timeline.innerHTML = "";

    if (posts.length === 0) {
        timeline.innerHTML = "<div style='text-align:center; padding: 40px; color:#536471;'>まだ投稿はありません</div>";
        return;
    }

    posts.forEach(post => timeline.appendChild(createPostElement(post)));
}

// モーダル操作群
function openPostModal() { document.getElementById("createPostModal").style.display = "flex"; }
function closePostModal() { 
    document.getElementById("createPostModal").style.display = "none"; 
    document.getElementById("contentInput").value = "";
    removeSelectedImage();
}

// ★ 新設：画像が選択された時にプレビューを表示する処理
function previewPostImage() {
    const fileInput = document.getElementById("postFileInput");
    if (fileInput.files.length === 0) return;
    
    selectedPostFile = fileInput.files[0];
    const reader = new FileReader();
    reader.onload = function(e) {
        document.getElementById("postImagePreview").src = e.target.result;
        document.getElementById("postImagePreviewContainer").style.display = "block";
    };
    reader.readAsDataURL(selectedPostFile);
}

// ★ 新設：選択された画像をキャンセルする処理
function removeSelectedImage() {
    selectedPostFile = null;
    document.getElementById("postFileInput").value = "";
    document.getElementById("postImagePreviewContainer").style.display = "none";
    document.getElementById("postImagePreview").src = "";
}

function openReplyModal(postId, postName, postContent) {
    document.getElementById("replyTargetId").value = postId;
    document.getElementById("replyTargetName").innerText = "@" + postName;
    document.getElementById("replyTargetText").innerText = postContent;
    document.getElementById("replyModal").style.display = "flex";
}
function closeReplyModal() { document.getElementById("replyModal").style.display = "none"; }

function openIconModal() { document.getElementById("iconModal").style.display = "flex"; }
function closeIconModal() { document.getElementById("iconModal").style.display = "none"; }

function openPasswordModal() {
    document.getElementById("passwordModal").style.display = "flex";
    document.getElementById("passwordError").style.display = "none";
}
function closePasswordModal() {
    document.getElementById("passwordModal").style.display = "none";
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

function createPostElement(post, isMainInThread = false) {
    const date = new Date(post.created_at + "Z");
    const timeString = date.toLocaleString('ja-JP', { month: 'numeric', day: 'numeric', hour: '2-digit', minute: '2-digit' });

    const div = document.createElement("div");
    div.className = "post" + (isMainInThread ? " main-post-in-thread" : "");
    div.dataset.id = post.id; // ★追加：箱に見えないゼッケン（ID）を付ける

    let likeClass = "action-btn like-btn";
    let heartImgSrc = "/icons/kitsu_gray.svg";
    let canLike = true;
    if (post.name === currentLoggedInUser) {
        likeClass += " disabled"; heartImgSrc = "/icons/kitsu_disabled.svg"; canLike = false;
    } else if (post.is_liked) {
        likeClass += " liked"; heartImgSrc = "/icons/kitsu_pink.svg";
    }

    let imageHtml = "";
    if (post.image_url) {
        imageHtml = `<div style="margin-top: 10px; max-height: 600px; overflow: hidden; border-radius: 12px; border: 1px solid #eff3f4;"><img src="${post.image_url}" style="width:100%; height:100%; object-fit:cover;"></div>`;
    }

    // ★ 変更：アイコンと名前にマウスポインターを乗せた時に「指マーク」になるようにし、クリック可能（clickable-user）にしました
    div.innerHTML = `
        <img class="user-icon clickable-user" src="/users/${encodeURIComponent(post.name)}/icon" alt="" style="cursor: pointer;">
        <div class="post-right">
            <div class="post-header">
                <div class="post-name clickable-user" style="cursor: pointer;">@${post.name}</div>
                <div class="post-time">${timeString}</div>
            </div>
            <div class="post-text"></div>
            ${imageHtml}
            <div class="post-actions">
                <div class="${likeClass} like-trigger">
                    <img src="${heartImgSrc}" class="custom-heart-icon" alt="heart"> 
                    <span style="${post.is_liked ? 'color: #f91880;' : ''}">${post.like_count > 0 ? post.like_count : ''}</span>
                </div>
                <div class="action-btn reply-btn">
                <img src="/icons/reply.svg" class="custom-heart-icon" alt="heart"> 
                <span>${post.reply_count > 0 ? post.reply_count : ''}</span>
                </div>
                <div class="action-btn view-btn">
                <img src="/icons/view.svg" class="custom-view-icon" alt="view">
                <span>${post.view_count > 0 ? post.view_count : 0}
                </span></div>
            </div>
        </div>
    `;

    const textDiv = div.querySelector(".post-text");
    textDiv.textContent = post.content;
    textDiv.onclick = () => viewThread(post.id);

    // ★ 追加：アイコンか名前を押したらその人のプロフィールを開く
    div.querySelectorAll('.clickable-user').forEach(el => {
        el.onclick = () => viewUserProfile(post.name);
    });

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

async function viewThread(postId) {
    const response = await fetch(`/posts/${postId}/thread`);
    if (!response.ok) return;
    const data = await response.json();

    const threadMain = document.getElementById("thread-main");
    threadMain.innerHTML = "";
    threadMain.appendChild(createPostElement(data.main_post, true));

    const threadReplies = document.getElementById("thread-replies");
    threadReplies.innerHTML = "";
    data.replies.forEach(reply => threadReplies.appendChild(createPostElement(reply)));

    switchTab('thread');
}



async function sendPost() {
    const content = document.getElementById("contentInput").value;
    if (content === "" && !selectedPostFile) return;

    // 「ポストする」ボタンを一時的に無効化して連打を防ぐ
    const saveBtn = document.querySelector("#createPostModal .save-btn");
    saveBtn.innerText = "送信中...";
    saveBtn.disabled = true;

    let uploadedImageUrl = null;

    // 1段階目：画像が選ばれていたら、まずCloudinaryにアップロードしてURLをもらう
    if (selectedPostFile) {
        const formData = new FormData();
        formData.append("file", selectedPostFile);
        
        const imgResponse = await fetch("/posts/image", {
            method: "POST",
            body: formData
        });
        
        if (imgResponse.ok) {
            const imgData = await imgResponse.json();
            uploadedImageUrl = imgData.image_url; // 「https://res.cloudinary.com/...」というURLが手に入る
        } else {
            alert("画像のアップロードに失敗しました。");
            saveBtn.innerText = "ポストする";
            saveBtn.disabled = false;
            return;
        }
    }

    // 2段階目：文章と画像のURLを合体させて、いつもの投稿APIに送信する
    await fetch("/posts", {
        method: "POST", 
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ 
            content: content, 
            parent_id: null,
            image_url: uploadedImageUrl // ここで画像URLを渡す！
        })
    });

    // 送信ボタンを元に戻して画面を更新
    saveBtn.innerText = "ポストする";
    saveBtn.disabled = false;
    
    closePostModal(); 
    switchTab('home');
}

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
    viewThread(targetId);
}

async function toggleLike(postId) {
    await fetch(`/posts/${postId}/like`, { method: "POST" });
    if (document.getElementById("view-thread").classList.contains("active")) {
        const currentPostId = document.querySelector(".main-post-in-thread").dataset.id;
        viewThread(currentPostId);
    } else if (document.getElementById("view-profile").classList.contains("active")) {
        // ★ 追加：プロフィール画面でいいねした時は、そのプロフィール画面を更新する
        const currentProfileUser = document.getElementById("profile-name").innerText.replace("@", "");
        loadUserPosts(currentProfileUser);
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

async function savePassword() {
    const currentPw = document.getElementById("currentPasswordInput").value;
    const newPw = document.getElementById("newPasswordInput").value;
    const confirmPw = document.getElementById("confirmPasswordInput").value;
    const errorDiv = document.getElementById("passwordError");

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

    const response = await fetch("/me/password", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ current_password: currentPw, new_password: newPw })
    });

    if (response.ok) {
        alert("パスワードを変更しました！\n安全のため、新しいパスワードでもう一度ログインしてください。");
        closePasswordModal();
        logout();
    } else {
        const data = await response.json();
        errorDiv.innerText = data.detail || "エラーが発生しました";
        errorDiv.style.display = "block";
    }
}

// ★ 新設：通知一覧を読み込んで表示する処理
async function loadNotifications() {
    const list = document.getElementById("notifications-list");
    list.innerHTML = "<div style='text-align:center; padding: 20px; color:#536471;'>読み込み中...</div>";
    
    const response = await fetch("/notifications");
    if (!response.ok) return;
    const notifications = await response.json();
    
    list.innerHTML = "";
    
    if (notifications.length === 0) {
        list.innerHTML = "<div style='text-align:center; padding: 40px; color:#536471;'>まだ通知はありません</div>";
        return;
    }
    
    notifications.forEach(notif => {
        const div = document.createElement("div");
        div.style.padding = "15px 20px";
        div.style.borderBottom = "1px solid #eff3f4";
        div.style.cursor = "pointer";
        
        // ★ 通知をタップしたら、その投稿のスレッド（詳細画面）に飛ぶようにする
        div.onclick = () => viewThread(notif.post_id); 
        
        // いいねか返信かで、表示するアイコンとテキストを変える
        const iconHtml = notif.type === 'like' 
            ? '<span style="color: #f91880; font-size: 1.5em; margin-right: 10px;">❤️</span>' 
            : '<span style="color: #1d9bf0; font-size: 1.5em; margin-right: 10px;">💬</span>';
        
        const actionText = notif.type === 'like' ? '「きっつ」' : 'さんがあなたのポストに返信しました';
        
        div.innerHTML = `
            <div style="display: flex; align-items: center; margin-bottom: 8px;">
                ${iconHtml}
                <img class="clickable-user" src="/users/${encodeURIComponent(notif.actor)}/icon" style="width: 30px; height: 30px; border-radius: 50%; margin-right: 10px; objetc-fit: cover;" onclick="event.stopPropagation(); viewUserProfile('${notif.actor}')">
                <span style="font-weight: bold; color: black; margin-right: 5px;">${notif.actor}</span>
                <span style="color: #536471; font-size: 0.9em;">${actionText}</span>
            </div>
            
            <div style="color: #536471; font-size: 0.9em; margin-left: 40px; margin-bottom: 8px; padding-left: 10px; border-left: 3px solid #cfd9de;">
                ${notif.target_content}
            </div>
            
            ${notif.type === 'reply' ? `<div style="margin-left: 40px; color: black;">${notif.content}</div>` : ''}
        `;
        
        list.appendChild(div);
    });
}