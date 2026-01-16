"""Flask application that manages surveys backed by MySQL."""

from __future__ import annotations

import datetime
import json
import logging
import os
import re
import secrets
import uuid
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

import requests as http_requests
from dotenv import load_dotenv
from flask import (
    Flask,
    Response,
    abort,
    jsonify,
    redirect,
    render_template_string,
    request,
    session,
    stream_with_context,
    send_from_directory,
)
from flask_cors import CORS
from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import Engine

from functools import wraps
import base64

load_dotenv()  # Load .env
load_dotenv(".env.local")  # Override with .env.local if exists

from openai_service import (
    OPENAI_CLIENT,
    initialize_rag_store,
    get_rag_store_name,
    generate_with_rag_stream,
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DIST_DIR = os.path.join(BASE_DIR, "dist")


def _default_storage_base() -> str:
    """
    Determine where to place writable artifacts (uploads).

    When running on Vercel or other serverless providers, the project directory
    is read-only and we must fall back to a tmp filesystem.
    """
    if os.getenv("VERCEL") or os.getenv("VERCEL_ENV"):
        return os.getenv("TMPDIR") or os.getenv("TEMP") or "/tmp"
    return BASE_DIR


STORAGE_BASE = _default_storage_base()


# MySQL connection for all tables
MYSQL_URL = os.getenv("MYSQL_URL", "mysql+pymysql://root:123456@localhost/youth-chat")
mysql_engine: Engine = create_engine(MYSQL_URL, future=True, pool_pre_ping=True)


ASSET_ROUTE_PREFIX = os.getenv("ASSET_ROUTE_PREFIX", "/uploads")
ASSET_LOCAL_DIR = os.getenv("ASSET_LOCAL_DIR") or os.path.join(STORAGE_BASE, "uploads")
os.makedirs(ASSET_LOCAL_DIR, exist_ok=True)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__, static_url_path=ASSET_ROUTE_PREFIX, static_folder=ASSET_LOCAL_DIR)

# Session configuration for OAuth
app.secret_key = os.getenv("FLASK_SECRET_KEY", secrets.token_hex(32))
app.config.update(
    SESSION_COOKIE_SECURE=bool(os.getenv("VERCEL") or os.getenv("VERCEL_ENV")),
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE='Lax',
    PERMANENT_SESSION_LIFETIME=86400,  # 24 hours
)

CORS(
    app,
    resources={r"/api/*": {"origins": os.getenv("FRONTEND_ORIGIN", "*")}},
    supports_credentials=True,
)

# OAuth Configuration
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
GOOGLE_REDIRECT_URI = os.getenv("GOOGLE_REDIRECT_URI", "http://localhost:8300/auth/google/callback")

LINE_CHANNEL_ID = os.getenv("LINE_CHANNEL_ID")
LINE_CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET")
LINE_REDIRECT_URI = os.getenv("LINE_REDIRECT_URI", "http://localhost:8300/auth/line/callback")

FACEBOOK_APP_ID = os.getenv("FACEBOOK_APP_ID")
FACEBOOK_APP_SECRET = os.getenv("FACEBOOK_APP_SECRET")
FACEBOOK_REDIRECT_URI = os.getenv("FACEBOOK_REDIRECT_URI", "http://localhost:8300/auth/facebook/callback")

OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Admin Configuration
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "")

# Feedback Form URL (for questions outside knowledge base or user suggestions)
FEEDBACK_FORM_URL = os.getenv("FEEDBACK_FORM_URL", "")

def _build_system_prompt() -> str:
    """Build system prompt with optional feedback form URL."""
    env_prompt = os.getenv("SYSTEM_PROMPT")
    if env_prompt:
        return env_prompt

    # Build feedback section based on whether URL is configured
    if FEEDBACK_FORM_URL:
        feedback_section = f'''### 無法回答或提案建議時：
當遇到以下情況，**務必**引導使用者填寫回饋表單：
- 問題超出知識庫範圍，無法回答
- 在文件中找不到相關資訊
- 使用者想要提案、建議或反映意見
- 使用者有特殊需求無法透過現有服務滿足

**回覆格式（請嚴格遵守）：**
```
感謝您的提問！目前我的資料庫中尚無足夠資訊回答這個問題。

為了讓您的問題能被相關單位看到並處理，歡迎填寫問題回饋表單：

[📝 填寫問題回饋表單]({FEEDBACK_FORM_URL})
```

'''
    else:
        feedback_section = '''### 無法回答時：
若問題超出知識庫範圍，請引導使用者聯繫官方窗口：
- 總機：(03) 422-5205
- 市政服務專線：1999（外縣市 03-218-9000）

'''

    return f'''你是「桃園市政府青年事務局」智慧客服助理。

### 你的角色定位：
- 語氣：專業、簡潔、自然；像真人客服對話；不使用 emoji 或表情符號
- 回答長度：簡單問題 1-2 句；複雜問題先給摘要再詢問是否需要詳細
- 知識來源：只使用《桃園市政府青年事務局知識庫》作答
- 不承諾未載明之權責

### 核心原則：
1. **嚴格依據文件回答** — 僅引用文件中明確敘述與數字
2. **若文件未載明** — 說明「資料不足」並引導填寫回饋表單（見下方「無法回答時」段落）
3. **推薦合適方案** — 根據需求主動推薦相關資源
4. **聯絡方式相關時才附** — 只有涉及特定承辦單位時才附上該單位聯絡方式

### 回覆原則（重要！）：

**【簡單問題】** — 單一資訊查詢（電話、地址、單一事實）
- 直接回答，最多 2 句話
- 結尾一句追問即可

**【需要分流的問題】** — 選項差異大，需要先確認方向
- 一句話說明情況
- 給 A/B/C/D 選項（每個選項最多 5 個字，不加描述）
- 範例：「你想辦的是？A 講座 B 聚會 C 展覽 D 戶外活動」

**【選項型問題】** — 有多個相似選項可供選擇
- 先用一句話概述
- 列出選項名稱（純文字，不加說明）
- 詢問：「想了解哪一個？」

**【流程型問題】** — 需要多步驟說明（申請流程、資格條件等）
- 先給一句話摘要（只說結論，不列細項）
- 詢問：「需要我詳細說明嗎？」
- 不要一次展開完整流程或列表

**【追問展開時】** — 使用者說「要」「好」「請說明」等
- 直接展開細節，不要重複摘要中已說過的內容
- 不要用「如下」「以下是」再重複一遍結構
- 如果上一輪已列出項目名稱，這輪直接補充每項的細節即可

### 聯絡資訊原則：
- 只有涉及特定承辦單位時，才附上該單位聯絡方式
- 不要每次都附上總機或地址

官方聯絡窗口（供參考）
- 總機：(03) 422-5205
- 市政服務專線：1999（外縣市 03-218-9000）
- 地址：320029 桃園市中壢區環北路390號

---

### 回答範例：

**【簡單問題】**
使用者問：「青創資源中心在哪裡？」
回答：在中壢區環北路390號3樓。需要查營業時間嗎？

---

**【需要分流的問題】**
使用者問：「有地方可以辦活動嗎？」
回答：有的，青年局有提供場地。你想辦的是？
A 講座  B 聚會  C 展覽  D 戶外活動

---

**【選項型問題】**
使用者問：「剛畢業想創業，有哪些資源？」
回答：青年局有三種創業資源：青創基地、青創資源中心、資金補貼。想了解哪一個？

---

**【流程型問題】**
使用者問：「怎麼申請進駐青創基地？」
回答：青創基地每半年招募一次，需要準備簡報和公司登記。需要我詳細說明申請流程嗎？

---

**【追問展開範例】**
使用者接著問：「好，請詳細說明」
回答：
1. 資格條件
- 團隊核心成員 35 歲以下
- 公司登記地址在桃園市

2. 準備文件
- 創業計劃簡報
- 公司登記證明

3. 申請步驟
- 關注「桃園青創事」FB 或 TYC 創業資源網獲取招募公告
- 線上報名並上傳簡報
- 通過資格審查後進行簡報評選
- 錄取後簽約進駐

青創指揮部：(03) 427-9796
安東青創基地：(03) 335-5530

還有其他問題嗎？

---

{feedback_section}### 禁止事項：
- 不使用 emoji 或表情符號
- A/B/C/D 選項只在需要明確分流時使用，且每個選項最多 5 個字
- 不一次列出超過 5 個選項
- 每個選項只列名稱，不加描述
- 不使用冗餘過渡句（如「為了幫你找到最適合的，我想先確認一件事」）
- 不主動展開所有細節，讓使用者選擇要不要深入了解
- 不提供法律解釋
- 不討論政治立場或爭議議題
- 不提供文件以外的金額、名額、評分標準
- 對於未載明事項，務必引導填寫回饋表單（見上方「無法回答或提案建議時」段落）'''


SYSTEM_PROMPT = _build_system_prompt()
def utcnow() -> datetime.datetime:
    return datetime.datetime.utcnow()


def _no_store(response: Response) -> Response:
    response.headers["Cache-Control"] = "private, no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    response.headers["Vary"] = "Cookie"
    return response


def ensure_mysql_schema() -> None:
    """Create all MySQL tables if they do not exist yet."""
    try:
        with mysql_engine.begin() as conn:
            # Members table
            conn.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS members (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        external_id VARCHAR(255) UNIQUE,
                        display_name VARCHAR(255),
                        avatar_url TEXT,
                        gender VARCHAR(20),
                        birthday VARCHAR(20),
                        email VARCHAR(255),
                        phone VARCHAR(50),
                        source VARCHAR(50),
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                        last_interaction_at DATETIME
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                    """
                )
            )
            # Surveys table
            conn.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS surveys (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        name VARCHAR(255) NOT NULL,
                        description TEXT,
                        category VARCHAR(100),
                        is_active TINYINT(1) DEFAULT 1,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                    """
                )
            )
            # Survey questions table
            conn.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS survey_questions (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        survey_id INT NOT NULL,
                        question_type VARCHAR(50) NOT NULL,
                        question_text TEXT NOT NULL,
                        description TEXT,
                        font_size INT,
                        options_json TEXT,
                        is_required TINYINT(1) DEFAULT 0,
                        display_order INT DEFAULT 0,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                        FOREIGN KEY (survey_id) REFERENCES surveys(id) ON DELETE CASCADE
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                    """
                )
            )
            # Survey responses table
            conn.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS survey_responses (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        survey_id INT NOT NULL,
                        member_id INT,
                        external_id VARCHAR(255),
                        answers_json TEXT NOT NULL,
                        is_completed TINYINT(1) DEFAULT 1,
                        completed_at DATETIME,
                        source VARCHAR(50),
                        ip_address VARCHAR(45),
                        user_agent TEXT,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                        FOREIGN KEY (survey_id) REFERENCES surveys(id) ON DELETE CASCADE,
                        FOREIGN KEY (member_id) REFERENCES members(id) ON DELETE SET NULL
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                    """
                )
            )
            # Chat sessions table
            conn.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS chat_sessions (
                        id VARCHAR(255) PRIMARY KEY,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                    """
                )
            )
            # Chat messages table
            conn.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS chat_messages (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        session_id VARCHAR(255) NOT NULL,
                        role VARCHAR(50) NOT NULL,
                        content TEXT NOT NULL,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        INDEX idx_chat_messages_session_created (session_id, created_at),
                        FOREIGN KEY (session_id) REFERENCES chat_sessions(id) ON DELETE CASCADE
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                    """
                )
            )
            # Hero carousel table
            conn.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS hero_carousel (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        filename VARCHAR(255) NOT NULL,
                        content_type VARCHAR(100) NOT NULL DEFAULT 'image/jpeg',
                        image_data LONGBLOB NOT NULL,
                        alt_text VARCHAR(500),
                        link_url VARCHAR(500),
                        display_order INT DEFAULT 0,
                        is_active TINYINT(1) DEFAULT 1,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                        INDEX idx_hero_active_order (is_active, display_order)
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                    """
                )
            )
        logger.info("MySQL schema ensured (all tables)")
    except Exception as e:
        logger.error(f"Failed to create MySQL schema: {e}")


ensure_mysql_schema()


# Initialize OpenAI client and RAG store at startup
def initialize_openai_rag():
    """Initialize OpenAI client and RAG store with default documents."""
    try:
        if OPENAI_API_KEY:
            store_id = initialize_rag_store("TaoyuanYouthBureauKB")
            if store_id:
                logger.info("OpenAI File Search initialized successfully")
            else:
                logger.warning("OpenAI File Search not initialized (missing vector store)")
        else:
            logger.warning("OPENAI_API_KEY not set, OpenAI File Search not available")
    except Exception as e:
        logger.error(f"Failed to initialize OpenAI File Search: {e}")


initialize_openai_rag()


# ========== Admin Authentication ==========

def admin_required(f):
    """Decorator to require admin authentication."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get("is_admin"):
            return jsonify({"success": False, "error": "未授權"}), 401
        return f(*args, **kwargs)
    return decorated_function


def validate_url(url: Optional[str]) -> tuple[bool, Optional[str]]:
    """
    驗證 URL 格式（必須以 http:// 或 https:// 開頭）

    Args:
        url: 要驗證的 URL（可為 None 或空字串）

    Returns:
        (is_valid, error_message)
    """
    if not url or not url.strip():
        # 空值視為合法（表示無連結）
        return True, None

    url = url.strip()

    # 檢查 URL 格式：必須以 http:// 或 https:// 開頭
    url_pattern = re.compile(
        r'^https?://'  # http:// 或 https://
        r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|'  # 網域
        r'localhost|'  # localhost
        r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'  # IP
        r'(?::\d+)?'  # 可選的 port
        r'(?:/?|[/?]\S+)$',  # 路徑
        re.IGNORECASE
    )

    if not url_pattern.match(url):
        return False, "URL 格式錯誤，必須以 http:// 或 https:// 開頭"

    # 檢查長度
    if len(url) > 500:
        return False, "URL 長度不能超過 500 字元"

    return True, None


@app.post("/api/admin/login")
def admin_login():
    """Admin login endpoint."""
    if not ADMIN_PASSWORD:
        return jsonify({"success": False, "error": "管理員密碼未設定"}), 500

    data = request.get_json() or {}
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""

    if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
        session["is_admin"] = True
        session.permanent = True
        return jsonify({"success": True, "message": "登入成功"})

    return jsonify({"success": False, "error": "帳號或密碼錯誤"}), 401


@app.post("/api/admin/logout")
def admin_logout():
    """Admin logout endpoint."""
    session.pop("is_admin", None)
    return jsonify({"success": True, "message": "已登出"})


@app.get("/api/admin/check")
def admin_check():
    """Check admin authentication status."""
    if session.get("is_admin"):
        return jsonify({"success": True, "authenticated": True})
    return jsonify({"success": False, "authenticated": False}), 401


# ========== Hero Images API ==========

@app.get("/api/hero-images")
def get_hero_images():
    """Get all active hero images (public endpoint)."""
    with mysql_engine.begin() as conn:
        rows = conn.execute(
            text(
                """
                SELECT id, alt_text, display_order, link_url
                FROM hero_carousel
                WHERE is_active = 1
                ORDER BY display_order ASC
                """
            )
        ).mappings().all()

    # Build URL pointing to the image data endpoint
    images = []
    for row in rows:
        images.append({
            "id": row["id"],
            "url": f"/api/hero-images/{row['id']}/data",
            "alt_text": row["alt_text"],
            "display_order": row["display_order"],
            "link_url": row["link_url"]
        })
    return jsonify({"success": True, "images": images})


@app.get("/api/hero-images/<int:image_id>/data")
def get_hero_image_data(image_id: int):
    """Serve hero image binary data."""
    from urllib.parse import quote

    with mysql_engine.begin() as conn:
        row = conn.execute(
            text("SELECT image_data, content_type, filename FROM hero_carousel WHERE id = :id AND is_active = 1"),
            {"id": image_id}
        ).mappings().first()

    if not row:
        abort(404)

    # URL encode filename to handle non-ASCII characters
    encoded_filename = quote(row["filename"])

    return Response(
        row["image_data"],
        mimetype=row["content_type"],
        headers={
            "Cache-Control": "public, max-age=86400",
            "Content-Disposition": f"inline; filename*=UTF-8''{encoded_filename}"
        }
    )


@app.get("/api/admin/hero-images")
@admin_required
def admin_get_hero_images():
    """Get all hero images (admin endpoint)."""
    with mysql_engine.begin() as conn:
        rows = conn.execute(
            text(
                """
                SELECT id, filename, content_type, alt_text,
                       display_order, is_active, link_url,
                       created_at, updated_at
                FROM hero_carousel
                ORDER BY display_order ASC
                """
            )
        ).mappings().all()

    # Build URL pointing to the image data endpoint
    images = []
    for row in rows:
        images.append({
            "id": row["id"],
            "url": f"/api/hero-images/{row['id']}/data",
            "filename": row["filename"],
            "alt_text": row["alt_text"],
            "display_order": row["display_order"],
            "is_active": row["is_active"],
            "link_url": row["link_url"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"]
        })
    return jsonify({"success": True, "images": images})


@app.post("/api/admin/hero-images")
@admin_required
def admin_upload_hero_image():
    """Upload a new hero image (stores in database)."""
    if "file" not in request.files:
        return jsonify({"success": False, "error": "未提供檔案"}), 400

    file = request.files["file"]
    if not file.filename:
        return jsonify({"success": False, "error": "檔案名稱為空"}), 400

    # Validate file type
    allowed_types = {"image/jpeg", "image/png", "image/webp"}
    if file.content_type not in allowed_types:
        return jsonify({"success": False, "error": "只支援 JPG、PNG、WebP 格式"}), 400

    # Check file size (max 5MB)
    file_data = file.read()
    if len(file_data) > 5 * 1024 * 1024:
        return jsonify({"success": False, "error": "檔案大小不能超過 5MB"}), 400

    # Get alt_text from form
    alt_text = request.form.get("alt_text", "")

    # Get link_url from form and validate
    link_url = request.form.get("link_url", "")
    is_valid, error_msg = validate_url(link_url)
    if not is_valid:
        return jsonify({"success": False, "error": error_msg}), 400

    # Get next display order and insert into database
    with mysql_engine.begin() as conn:
        result = conn.execute(
            text("SELECT COALESCE(MAX(display_order), -1) + 1 as next_order FROM hero_carousel")
        ).mappings().first()
        next_order = result["next_order"] if result else 0

        # Check if we already have 8 images
        count_result = conn.execute(
            text("SELECT COUNT(*) as count FROM hero_carousel")
        ).mappings().first()
        if count_result and count_result["count"] >= 8:
            return jsonify({"success": False, "error": "最多只能上傳 8 張圖片"}), 400

        # Insert image data into database
        now = utcnow()
        conn.execute(
            text(
                """
                INSERT INTO hero_carousel (filename, content_type, image_data, alt_text, link_url, display_order, created_at, updated_at)
                VALUES (:filename, :content_type, :image_data, :alt_text, :link_url, :order, :now, :now)
                """
            ),
            {
                "filename": file.filename,
                "content_type": file.content_type,
                "image_data": file_data,
                "alt_text": alt_text,
                "link_url": link_url.strip() if link_url else None,
                "order": next_order,
                "now": now,
            },
        )

        # Get the inserted image
        inserted = conn.execute(
            text("SELECT id, alt_text, display_order, link_url FROM hero_carousel WHERE display_order = :order"),
            {"order": next_order}
        ).mappings().first()

    if inserted:
        return jsonify({
            "success": True,
            "image": {
                "id": inserted["id"],
                "url": f"/api/hero-images/{inserted['id']}/data",
                "alt_text": inserted["alt_text"],
                "display_order": inserted["display_order"],
                "link_url": inserted["link_url"]
            }
        })
    return jsonify({"success": False, "error": "上傳失敗"}), 500


@app.delete("/api/admin/hero-images/<int:image_id>")
@admin_required
def admin_delete_hero_image(image_id: int):
    """Delete a hero image from database."""
    with mysql_engine.begin() as conn:
        # Check if image exists
        image = conn.execute(
            text("SELECT id FROM hero_carousel WHERE id = :id"),
            {"id": image_id}
        ).mappings().first()

        if not image:
            return jsonify({"success": False, "error": "圖片不存在"}), 404

        # Delete from database
        conn.execute(
            text("DELETE FROM hero_carousel WHERE id = :id"),
            {"id": image_id}
        )

    return jsonify({"success": True, "message": "已刪除"})


@app.put("/api/admin/hero-images/reorder")
@admin_required
def admin_reorder_hero_images():
    """Reorder hero images."""
    data = request.get_json() or {}
    order = data.get("order", [])  # List of image IDs in new order

    if not isinstance(order, list):
        return jsonify({"success": False, "error": "order 必須是陣列"}), 400

    with mysql_engine.begin() as conn:
        for idx, image_id in enumerate(order):
            conn.execute(
                text(
                    """
                    UPDATE hero_carousel
                    SET display_order = :order, updated_at = :now
                    WHERE id = :id
                    """
                ),
                {"order": idx, "id": image_id, "now": utcnow()}
            )

    return jsonify({"success": True, "message": "排序已更新"})


@app.put("/api/admin/hero-images/<int:image_id>")
@admin_required
def admin_update_hero_image(image_id: int):
    """Update hero image metadata."""
    data = request.get_json() or {}

    updates = []
    params = {"id": image_id, "now": utcnow()}

    if "alt_text" in data:
        updates.append("alt_text = :alt_text")
        params["alt_text"] = data["alt_text"]

    if "is_active" in data:
        updates.append("is_active = :is_active")
        params["is_active"] = 1 if data["is_active"] else 0

    if "link_url" in data:
        link_url = data["link_url"]
        # 驗證 URL
        is_valid, error_msg = validate_url(link_url)
        if not is_valid:
            return jsonify({"success": False, "error": error_msg}), 400

        updates.append("link_url = :link_url")
        params["link_url"] = link_url.strip() if link_url else None

    if not updates:
        return jsonify({"success": False, "error": "沒有要更新的欄位"}), 400

    updates.append("updated_at = :now")

    with mysql_engine.begin() as conn:
        result = conn.execute(
            text(f"UPDATE hero_carousel SET {', '.join(updates)} WHERE id = :id"),
            params
        )

        if result.rowcount == 0:
            return jsonify({"success": False, "error": "圖片不存在"}), 404

    return jsonify({"success": True, "message": "已更新"})


def ensure_chat_session(session_id: Optional[str] = None) -> str:
    """Return an existing chat session id or create a new one."""
    chat_session_id = session_id or uuid.uuid4().hex
    now = utcnow()
    with mysql_engine.begin() as conn:
        conn.execute(
            text(
                """
                INSERT INTO chat_sessions (id, created_at, updated_at)
                VALUES (:id, :now, :now)
                ON DUPLICATE KEY UPDATE updated_at = :now
                """
            ),
            {"id": chat_session_id, "now": now},
        )
    return chat_session_id


def save_chat_message(session_id: str, role: str, content: str) -> None:
    """Persist a chat message for a given session."""
    with mysql_engine.begin() as conn:
        conn.execute(
            text(
                """
                INSERT INTO chat_messages (session_id, role, content, created_at)
                VALUES (:sid, :role, :content, :created_at)
                """
            ),
            {
                "sid": session_id,
                "role": role,
                "content": content,
                "created_at": utcnow(),
            },
        )
        conn.execute(
            text(
                """
                UPDATE chat_sessions
                SET updated_at = :updated_at
                WHERE id = :sid
                """
            ),
            {"sid": session_id, "updated_at": utcnow()},
        )


def fetch_chat_history(session_id: str, limit: int = 12) -> List[Dict[str, Any]]:
    """Fetch the most recent chat history for the session in chronological order."""
    if limit <= 0:
        limit = 1

    query = text(
        f"""
        SELECT role, content
        FROM chat_messages
        WHERE session_id = :sid
        ORDER BY created_at DESC
        LIMIT {limit}
        """
    )

    with mysql_engine.begin() as conn:
        rows = conn.execute(query, {"sid": session_id}).mappings().all()

    # Reverse to chronological order
    return [dict(row) for row in reversed(rows)]


def build_chat_history(history: Iterable[Dict[str, str]]) -> List[Dict[str, str]]:
    """Prepare chat history for OpenAI API (without system/user prompts - handled by RAG)."""
    messages: List[Dict[str, str]] = []
    for item in history:
        role = item.get("role")
        content = (item.get("content") or "").strip()
        if role in {"user", "assistant"} and content:
            messages.append({"role": role, "content": content})
    return messages


def format_sse(payload: Dict[str, Any]) -> str:
    """Serialize a Python dictionary into a Server-Sent Events data frame."""
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


# Regex pattern to remove OpenAI file search citation markers (e.g., fileciteturn0file5turn0file12)
_CITATION_PATTERN = re.compile(r"fileciteturn\d+file\d+(?:turn\d+file\d+)*")


def strip_citations(text: str) -> str:
    """Remove OpenAI file search citation markers from text."""
    return _CITATION_PATTERN.sub("", text)


@app.post("/api/chat")
@app.post("/chat")
def api_chat():
    if not request.is_json:
        return jsonify({"error": "Payload must be JSON."}), 400

    payload = request.get_json(force=True) or {}
    message = (payload.get("message") or "").strip()
    requested_session = payload.get("session_id")

    if not message:
        return jsonify({"error": "message is required"}), 400

    session_id = ensure_chat_session(
        requested_session if isinstance(requested_session, str) else None
    )
    history = fetch_chat_history(session_id)

    # Persist the user's message before streaming.
    save_chat_message(session_id, "user", message)

    client = OPENAI_CLIENT
    rag_store = get_rag_store_name()

    def generate():
        logger.info("Streaming response for session %s", session_id)
        yield format_sse({"type": "session", "content": "", "session_id": session_id})

        if client is None or rag_store is None:
            assistant_text = (
                "無法連接 OpenAI 服務。請檢查伺服器設定。\n\n"
                f"待發送訊息：{message}\n"
                "請確認 OPENAI_API_KEY 已設定後再試。"
            )
            save_chat_message(session_id, "assistant", assistant_text)
            yield format_sse(
                {"type": "text", "content": assistant_text, "session_id": session_id}
            )
            yield format_sse({"type": "end", "content": "", "session_id": session_id})
            return

        accumulated: List[str] = []
        sources: List[Dict[str, Any]] = []

        try:
            chat_history = build_chat_history(history)

            for chunk in generate_with_rag_stream(
                query=message,
                system_prompt=SYSTEM_PROMPT,
                chat_history=chat_history,
                model=OPENAI_MODEL
            ):
                if chunk["type"] == "text":
                    delta = chunk["content"]
                    if delta:
                        # Remove citation markers before sending to client
                        clean_delta = strip_citations(delta)
                        accumulated.append(clean_delta)
                        if clean_delta:
                            yield format_sse(
                                {
                                    "type": "text",
                                    "content": clean_delta,
                                    "session_id": session_id,
                                }
                            )
                elif chunk["type"] == "sources":
                    sources = chunk["content"]
                elif chunk["type"] == "end":
                    pass

        except Exception:
            logger.exception("Chat streaming failed for session %s", session_id)
            error_message = (
                "產生回覆時發生問題，請稍後再試或聯繫我們的服務人員。"
            )
            save_chat_message(session_id, "assistant", error_message)
            yield format_sse(
                {"type": "text", "content": error_message, "session_id": session_id}
            )
            yield format_sse({"type": "end", "content": "", "session_id": session_id})
            return

        full_text = "".join(accumulated).strip()

        if full_text:
            save_chat_message(session_id, "assistant", full_text)
        else:
            fallback_text = "抱歉，我目前無法回覆。請重新描述您的問題或聯繫我們的服務人員。"
            save_chat_message(session_id, "assistant", fallback_text)
            yield format_sse(
                {"type": "text", "content": fallback_text, "session_id": session_id}
            )

        # Yield sources if available
        if sources:
            yield format_sse(
                {"type": "sources", "content": sources, "session_id": session_id}
            )

        yield format_sse({"type": "end", "content": "", "session_id": session_id})

    response = Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
    )
    response.headers["Cache-Control"] = "no-cache"
    response.headers["X-Accel-Buffering"] = "no"
    return response


def fetchall(sql: str, params: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    with mysql_engine.begin() as conn:
        return [
            dict(row)
            for row in conn.execute(text(sql), params or {}).mappings().all()
        ]


def fetchone(sql: str, params: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
    with mysql_engine.begin() as conn:
        result = conn.execute(text(sql), params or {}).mappings().first()
        return dict(result) if result else None


def execute(sql: str, params: Optional[Dict[str, Any]] = None) -> None:
    with mysql_engine.begin() as conn:
        conn.execute(text(sql), params or {})


def _clean(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    trimmed = str(value).strip()
    return trimmed or None


def upsert_member(
    external_id: Optional[str],
    display_name: Optional[str] = None,
    avatar_url: Optional[str] = None,
    gender: Optional[str] = None,
    birthday: Optional[str] = None,
    email: Optional[str] = None,
    phone: Optional[str] = None,
    source: Optional[str] = "form",
) -> Optional[int]:
    """Create or update a member record identified by an external id."""
    external_id = _clean(external_id)
    if not external_id:
        return None

    now = utcnow()
    data = {
        "display_name": _clean(display_name),
        "avatar_url": _clean(avatar_url),
        "gender": _clean(gender),
        "birthday": _clean(birthday),
        "email": _clean(email),
        "phone": _clean(phone),
        "source": source or "form",
        "updated_at": now,
        "last_interaction_at": now,
    }

    with mysql_engine.begin() as conn:
        existing = conn.execute(
            text("SELECT id FROM members WHERE external_id = :ext"),
            {"ext": external_id},
        ).scalar()
        if existing:
            conn.execute(
                text(
                    """
                    UPDATE members
                       SET display_name=:display_name,
                           avatar_url=:avatar_url,
                           gender=:gender,
                           birthday=:birthday,
                           email=:email,
                           phone=:phone,
                           source=:source,
                           updated_at=:updated_at,
                           last_interaction_at=:last_interaction_at
                     WHERE id=:member_id
                    """
                ),
                {**data, "member_id": existing},
            )
            return int(existing)

        insert_params = {
            "external_id": external_id,
            **data,
            "created_at": now,
        }
        result = conn.execute(
            text(
                """
                INSERT INTO members (
                    external_id,
                    display_name,
                    avatar_url,
                    gender,
                    birthday,
                    email,
                    phone,
                    source,
                    created_at,
                    updated_at,
                    last_interaction_at
                ) VALUES (
                    :external_id,
                    :display_name,
                    :avatar_url,
                    :gender,
                    :birthday,
                    :email,
                    :phone,
                    :source,
                    :created_at,
                    :updated_at,
                    :last_interaction_at
                )
                """
            ),
            insert_params,
        )
        member_id = result.lastrowid
    return int(member_id) if member_id is not None else None


QUESTION_TYPE_ALIASES: Dict[str, List[str]] = {
    "TEXT": ["TEXT", "INPUT", "SHORT_TEXT"],
    "TEXTAREA": ["TEXTAREA", "LONG_TEXT", "PARAGRAPH"],
    "SINGLE_CHOICE": ["SINGLE_CHOICE", "SINGLE", "RADIO", "CHOICE_SINGLE"],
    "MULTI_CHOICE": ["MULTI_CHOICE", "MULTI", "CHECKBOX", "CHOICE_MULTI", "MULTIPLE"],
    "SELECT": ["SELECT", "DROPDOWN", "PULLDOWN"],
    "NAME": ["NAME"],
    "PHONE": ["PHONE", "TEL", "MOBILE"],
    "EMAIL": ["EMAIL"],
    "BIRTHDAY": ["BIRTHDAY", "DOB", "DATE_OF_BIRTH", "DATE"],
    "ADDRESS": ["ADDRESS"],
    "GENDER": ["GENDER", "SEX"],
    "IMAGE": ["IMAGE", "PHOTO"],
    "VIDEO": ["VIDEO"],
    "ID_NUMBER": ["ID_NUMBER", "IDENTIFICATION"],
    "LINK": ["LINK", "URL"],
}

DEFAULT_QUESTION_TYPE = "TEXT"


def normalize_question_type(raw: Any) -> str:
    token = _clean(str(raw) if raw is not None else None)
    if not token:
        return DEFAULT_QUESTION_TYPE
    token = token.replace("-", "_").upper()
    for canonical, aliases in QUESTION_TYPE_ALIASES.items():
        if token == canonical or token in aliases:
            return canonical
    for canonical, aliases in QUESTION_TYPE_ALIASES.items():
        if any(alias in token for alias in aliases):
            return canonical
    return DEFAULT_QUESTION_TYPE


def register_survey_from_json(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Persist a survey described by JSON payload."""
    if not isinstance(payload, dict):
        raise ValueError("payload must be a mapping")

    name = _clean(payload.get("name")) or "Survey"
    description = _clean(payload.get("description"))
    category = _clean(payload.get("category"))
    questions = payload.get("questions") or []
    if not isinstance(questions, list):
        raise ValueError("questions must be a list")

    now = utcnow()
    with mysql_engine.begin() as conn:
        result = conn.execute(
            text(
                """
                INSERT INTO surveys (name, description, category, is_active, created_at, updated_at)
                VALUES (:name, :description, :category, 1, :now, :now)
                """
            ),
            {"name": name, "description": description, "category": category, "now": now},
        )
        survey_id = int(result.lastrowid)

        for idx, question in enumerate(questions, start=1):
            if not isinstance(question, dict):
                continue
            q_type = normalize_question_type(question.get("question_type"))
            options = question.get("options") or question.get("options_json") or []
            if not isinstance(options, list):
                options = []
            entry = {
                "survey_id": survey_id,
                "question_type": q_type,
                "question_text": _clean(question.get("question_text")) or f"Question {idx}",
                "description": _clean(question.get("description")),
                "font_size": question.get("font_size") if isinstance(question.get("font_size"), int) else None,
                "options_json": json.dumps(options, ensure_ascii=False),
                "is_required": 1 if question.get("is_required") else 0,
                "display_order": question.get("order") if isinstance(question.get("order"), int) else idx,
                "created_at": now,
                "updated_at": now,
            }
            conn.execute(
                text(
                    """
                    INSERT INTO survey_questions (
                        survey_id,
                        question_type,
                        question_text,
                        description,
                        font_size,
                        options_json,
                        is_required,
                        display_order,
                        created_at,
                        updated_at
                    )
                    VALUES (
                        :survey_id,
                        :question_type,
                        :question_text,
                        :description,
                        :font_size,
                        :options_json,
                        :is_required,
                        :display_order,
                        :created_at,
                        :updated_at
                    )
                    """
                ),
                entry,
            )

    logger.info("Survey %s created with %s questions", survey_id, len(questions))
    return {"survey_id": survey_id, "question_count": len(questions)}


def load_survey_meta(survey_id: int) -> Dict[str, Any]:
    survey = fetchone(
        "SELECT id, name, description FROM surveys WHERE id = :sid", {"sid": survey_id}
    )
    if not survey:
        raise ValueError(f"survey {survey_id} not found")

    rows = fetchall(
        """
        SELECT id,
               question_type,
               question_text,
               description,
               font_size,
               options_json,
               is_required,
               display_order
          FROM survey_questions
         WHERE survey_id = :sid
         ORDER BY display_order ASC, id ASC
        """,
        {"sid": survey_id},
    )

    questions: List[Dict[str, Any]] = []
    for row in rows:
        options: List[Any]
        try:
            options = json.loads(row.get("options_json") or "[]")
        except json.JSONDecodeError:
            options = []
        questions.append(
            {
                "id": row["id"],
                "question_type": row["question_type"],
                "question_text": row["question_text"],
                "description": row.get("description"),
                "font_size": row.get("font_size"),
                "options": options,
                "is_required": bool(row.get("is_required")),
                "display_order": row.get("display_order"),
            }
        )

    return {
        "id": survey["id"],
        "name": survey["name"],
        "description": survey.get("description") or "",
        "questions": questions,
    }


def save_survey_submission(
    survey_id: int,
    answers: Dict[str, Any],
    participant: Optional[Dict[str, Any]] = None,
) -> None:
    """Store a survey response."""
    if not fetchone("SELECT 1 FROM surveys WHERE id=:sid", {"sid": survey_id}):
        raise ValueError("survey not found")
    if not isinstance(answers, dict):
        raise ValueError("answers must be a mapping")

    normalized: Dict[str, Any] = {}
    for key, value in answers.items():
        if not isinstance(key, str) or not key.startswith("q_"):
            continue
        suffix = key.split("_", 1)[1] if "_" in key else key
        if isinstance(value, list):
            normalized[suffix] = value
        elif value is None:
            normalized[suffix] = ""
        else:
            normalized[suffix] = str(value)

    participant = participant or {}
    external_id = (
        participant.get("external_id")
        or participant.get("id")
        or participant.get("identifier")
    )
    display_name = participant.get("display_name") or participant.get("name")
    email = participant.get("email")
    phone = participant.get("phone")

    member_id = upsert_member(
        external_id,
        display_name=display_name,
        email=email,
        phone=phone,
        source="form",
    )

    now = utcnow()
    execute(
        """
        INSERT INTO survey_responses (
            survey_id,
            member_id,
            external_id,
            answers_json,
            is_completed,
            completed_at,
            source,
            ip_address,
            user_agent,
            created_at,
            updated_at
        )
        VALUES (
            :survey_id,
            :member_id,
            :external_id,
            :answers_json,
            1,
            :completed_at,
            :source,
            :ip_address,
            :user_agent,
            :created_at,
            :updated_at
        )
        """,
        {
            "survey_id": survey_id,
            "member_id": member_id,
            "external_id": _clean(external_id),
            "answers_json": json.dumps(normalized, ensure_ascii=False),
            "completed_at": now,
            "source": "form",
            "ip_address": request.headers.get("X-Forwarded-For", request.remote_addr),
            "user_agent": request.headers.get("User-Agent"),
            "created_at": now,
            "updated_at": now,
        },
    )


SURVEY_TEMPLATE = """
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{{ survey.name or "Survey" }}</title>
  <style>
    body { font-family: system-ui, -apple-system, "Segoe UI", sans-serif; margin: 0; background: #f6f7fb; color: #111827; }
    .wrap { max-width: 720px; margin: 0 auto; padding: 32px 16px; }
    .card { background: #ffffff; border-radius: 16px; box-shadow: 0 20px 40px rgba(15, 23, 42, 0.12); padding: 28px; }
    h1 { margin: 0 0 16px; font-size: 24px; }
    .desc { margin: 0 0 24px; color: #475569; font-size: 15px; }
    .participant { border: 1px dashed #cbd5f5; border-radius: 12px; padding: 16px; margin-bottom: 24px; background: #f8fafc; }
    .participant label { display: block; font-weight: 500; margin-bottom: 12px; }
    .participant input { width: 100%; padding: 10px 12px; border-radius: 10px; border: 1px solid #d1d9e6; font-size: 15px; margin-top: 6px; }
    .question { margin-bottom: 22px; }
    .prompt { display: block; font-weight: 600; margin-bottom: 8px; }
    .required { color: #dc2626; margin-left: 4px; }
    .description { font-size: 14px; color: #64748b; margin-bottom: 8px; }
    input[type="text"], input[type="tel"], input[type="email"], input[type="date"], input[type="url"], textarea, select {
      width: 100%; padding: 10px 12px; border-radius: 10px; border: 1px solid #d1d9e6; font-size: 15px; box-sizing: border-box;
    }
    textarea { min-height: 96px; resize: vertical; }
    .options { display: flex; flex-wrap: wrap; gap: 8px; }
    .chip { display: flex; align-items: center; gap: 6px; padding: 8px 12px; border: 1px solid #cbd5f5; border-radius: 999px; background: #f8fafc; cursor: pointer; }
    .chip input { margin: 0; }
    button { width: 100%; padding: 14px 16px; border: none; border-radius: 12px; background: #2563eb; color: #ffffff; font-size: 16px; font-weight: 600; cursor: pointer; }
    button:disabled { opacity: 0.7; cursor: wait; }
    .hint { margin-top: 16px; font-size: 13px; color: #64748b; }
    .status { margin-top: 18px; font-size: 15px; }
    .status.error { color: #b91c1c; }
    .status.success { color: #047857; }
  </style>
</head>
<body>
  <div class="wrap">
    <div class="card">
      <h1>{{ survey.name or "Survey" }}</h1>
      {% if survey.description %}
      <p class="desc">{{ survey.description }}</p>
      {% endif %}
      <form id="surveyForm">
        <input type="hidden" name="sid" value="{{ survey_id }}">
        <div class="participant">
          <label>
            Contact (optional)
            <input type="text" name="participant_id" placeholder="Email or phone">
          </label>
          <label>
            Name (optional)
            <input type="text" name="participant_name" placeholder="Your name">
          </label>
        </div>
        {% for q in survey.questions %}
        {% set qtype = (q.question_type or "").lower() %}
        {% set field_name = "q_" ~ q.id %}
        <div class="question" data-type="{{ qtype }}" data-id="{{ q.id }}"{% if q.is_required %} data-required="1"{% endif %}>
          <label class="prompt">{{ q.question_text or ("Question " ~ loop.index) }}{% if q.is_required %}<span class="required">*</span>{% endif %}</label>
          {% if q.description %}<div class="description">{{ q.description }}</div>{% endif %}
          {% if qtype in ["text", "name", "address", "phone", "email", "birthday", "id_number", "link"] %}
            {% set input_type = {
              "text": "text",
              "name": "text",
              "address": "text",
              "phone": "tel",
              "email": "email",
              "birthday": "date",
              "id_number": "text",
              "link": "url"
            }[qtype] if qtype in ["text","name","address","phone","email","birthday","id_number","link"] else "text" %}
            <input type="{{ input_type }}" name="{{ field_name }}"{% if q.is_required %} required{% endif %}>
          {% elif qtype == "textarea" %}
            <textarea name="{{ field_name }}"{% if q.is_required %} required{% endif %}></textarea>
          {% elif qtype in ["single_choice", "gender"] %}
            <div class="options">
              {% for opt in q.options %}
                {% set value = opt.value if opt.value is not none else (opt.label if opt.label is not none else "option_" ~ loop.index) %}
                {% set label = opt.label if opt.label is not none else (opt.value if opt.value is not none else "Option " ~ loop.index) %}
                <label class="chip">
                  <input type="radio" name="{{ field_name }}" value="{{ value }}"{% if q.is_required and loop.first %} required{% endif %}>
                  {{ label }}
                </label>
              {% endfor %}
              {% if not q.options %}
              <div>No options configured.</div>
              {% endif %}
            </div>
          {% elif qtype == "multi_choice" %}
            <div class="options">
              {% for opt in q.options %}
                {% set value = opt.value if opt.value is not none else (opt.label if opt.label is not none else "option_" ~ loop.index) %}
                {% set label = opt.label if opt.label is not none else (opt.value if opt.value is not none else "Option " ~ loop.index) %}
                <label class="chip">
                  <input type="checkbox" name="{{ field_name }}" value="{{ value }}"{% if q.is_required and loop.first %} required{% endif %}>
                  {{ label }}
                </label>
              {% endfor %}
              {% if not q.options %}
              <div>No options configured.</div>
              {% endif %}
            </div>
          {% elif qtype == "select" %}
            <select name="{{ field_name }}"{% if q.is_required %} required{% endif %}>
              <option value="">Select??/option>
              {% for opt in q.options %}
                {% set value = opt.value if opt.value is not none else (opt.label if opt.label is not none else "option_" ~ loop.index) %}
                {% set label = opt.label if opt.label is not none else (opt.value if opt.value is not none else "Option " ~ loop.index) %}
                <option value="{{ value }}">{{ label }}</option>
              {% endfor %}
            </select>
          {% else %}
            <input type="text" name="{{ field_name }}"{% if q.is_required %} required{% endif %}>
          {% endif %}
        </div>
        {% endfor %}
        <button type="submit" id="submitBtn">Submit</button>
        <p class="hint">We only use the information to support your request.</p>
      </form>
      <div id="formMessage" class="status" hidden></div>
    </div>
  </div>
  <script>
    const form = document.getElementById("surveyForm");
    const messageEl = document.getElementById("formMessage");
    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      messageEl.hidden = true;
      const sidField = form.querySelector("input[name='sid']");
      const sid = sidField ? Number(sidField.value) : NaN;
      if (!sid) {
        messageEl.textContent = "Invalid survey id.";
        messageEl.className = "status error";
        messageEl.hidden = false;
        return;
      }

      const sections = Array.from(form.querySelectorAll(".question"));
      const data = {};
      let missingRequired = false;

      sections.forEach((section) => {
        const type = (section.getAttribute("data-type") || "").toLowerCase();
        const id = section.getAttribute("data-id");
        const name = "q_" + id;
        const required = section.hasAttribute("data-required");

        if (type === "multi_choice") {
          const values = Array.from(
            section.querySelectorAll("input[type='checkbox'][name='" + name + "']:checked")
          ).map((el) => el.value);
          if (required && values.length === 0) {
            missingRequired = true;
          }
          data[name] = values;
        } else if (type === "single_choice" || type === "gender") {
          const chosen = section.querySelector("input[type='radio'][name='" + name + "']:checked");
          if (required && !chosen) {
            missingRequired = true;
          }
          data[name] = chosen ? chosen.value : "";
        } else if (type === "select") {
          const selectEl = section.querySelector("select[name='" + name + "']");
          const value = selectEl ? selectEl.value : "";
          if (required && !value) {
            missingRequired = true;
          }
          data[name] = value;
        } else {
          const field = section.querySelector("[name='" + name + "']");
          const value = field ? field.value : "";
          if (required && !value) {
            missingRequired = true;
          }
          data[name] = value;
        }
      });

      if (missingRequired) {
        messageEl.textContent = "Please complete the required fields.";
        messageEl.className = "status error";
        messageEl.hidden = false;
        return;
      }

      const participant = {
        external_id: (form.querySelector("input[name='participant_id']").value || "").trim(),
        display_name: (form.querySelector("input[name='participant_name']").value || "").trim()
      };
      if (!participant.external_id) {
        delete participant.external_id;
      }
      if (!participant.display_name) {
        delete participant.display_name;
      }

      const payload = { sid, data, participant };

      try {
        form.querySelector("#submitBtn").disabled = true;
        const response = await fetch("/__survey_submit", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload)
        });
        const result = await response.json().catch(() => ({ ok: false, error: "Unexpected response." }));
        if (result.ok) {
          messageEl.textContent = "Thank you! Your response has been recorded.";
          messageEl.className = "status success";
          form.reset();
        } else {
          messageEl.textContent = result.error || "Unable to submit the survey.";
          messageEl.className = "status error";
        }
      } catch (err) {
        console.error("Submit error:", err);
        messageEl.textContent = "An unexpected error occurred.";
        messageEl.className = "status error";
      } finally {
        form.querySelector("#submitBtn").disabled = false;
        messageEl.hidden = false;
      }
    });
  </script>
</body>
</html>
"""


@app.get("/")
def index():
    """Serve the index.html file from dist directory in production, or BASE_DIR in development"""
    # 优先从 dist 目录提供（生产环境），否则从 BASE_DIR（开发环境）
    dist_index = os.path.join(DIST_DIR, "index.html")
    if os.path.exists(dist_index):
        return send_from_directory(DIST_DIR, "index.html")
    return send_from_directory(BASE_DIR, "index.html")


@app.route("/<path:path>")
def serve_static(path: str):
    """Serve static files from dist directory"""
    # 检查是否是 API 路由，如果是则跳过
    if path.startswith("api/") or path.startswith("__") or path.startswith("survey/"):
        abort(404)
    
    # 优先从 dist 目录提供静态文件
    dist_path = os.path.join(DIST_DIR, path)
    if os.path.exists(dist_path) and os.path.isfile(dist_path):
        return send_from_directory(DIST_DIR, path)
    
    # 如果文件不存在，返回 index.html（用于 SPA 路由）
    dist_index = os.path.join(DIST_DIR, "index.html")
    if os.path.exists(dist_index):
        return send_from_directory(DIST_DIR, "index.html")
    
    abort(404)


@app.get("/health")
def health() -> tuple[str, int]:
    return "OK", 200


# ==================== OAuth Routes ====================

@app.get("/auth/config")
def api_auth_config():
    """Return OAuth configuration for frontend (without secrets)."""
    return jsonify({
        "google": {
            "enabled": bool(GOOGLE_CLIENT_ID),
            "client_id": GOOGLE_CLIENT_ID,
            "redirect_uri": GOOGLE_REDIRECT_URI
        },
        "line": {
            "enabled": bool(LINE_CHANNEL_ID),
            "channel_id": LINE_CHANNEL_ID,
            "redirect_uri": LINE_REDIRECT_URI
        },
        "facebook": {
            "enabled": bool(FACEBOOK_APP_ID),
            "app_id": FACEBOOK_APP_ID,
            "redirect_uri": FACEBOOK_REDIRECT_URI
        }
    })


@app.get("/auth/google/callback")
def auth_google_callback():
    """Handle Google OAuth callback."""
    code = request.args.get("code")
    error = request.args.get("error")

    if error:
        logger.error(f"Google OAuth error: {error}")
        return redirect("/?error=google_auth_failed")

    if not code:
        return redirect("/?error=no_code")

    try:
        # Exchange code for token
        token_response = http_requests.post(
            "https://oauth2.googleapis.com/token",
            data={
                "code": code,
                "client_id": GOOGLE_CLIENT_ID,
                "client_secret": GOOGLE_CLIENT_SECRET,
                "redirect_uri": GOOGLE_REDIRECT_URI,
                "grant_type": "authorization_code"
            }
        )
        token_data = token_response.json()
        access_token = token_data.get("access_token")

        if not access_token:
            logger.error(f"Google token exchange failed: {token_data}")
            return redirect("/?error=google_token_exchange_failed")

        # Get user info
        user_response = http_requests.get(
            "https://www.googleapis.com/oauth2/v2/userinfo",
            headers={"Authorization": f"Bearer {access_token}"}
        )
        user_info = user_response.json()

        # Upsert member and store in session
        member_id = upsert_member(
            external_id=f"google_{user_info['id']}",
            display_name=user_info.get("name"),
            avatar_url=user_info.get("picture"),
            email=user_info.get("email"),
            source="google"
        )

        session["user"] = {
            "member_id": member_id,
            "provider": "google",
            "external_id": f"google_{user_info['id']}",
            "email": user_info.get("email"),
            "name": user_info.get("name")
        }
        session.permanent = True

        return redirect("/?login=success")

    except Exception as e:
        logger.exception("Google OAuth token exchange failed")
        return redirect("/?error=google_token_exchange_failed")


@app.get("/auth/line/callback")
def auth_line_callback():
    """Handle LINE OAuth callback."""
    code = request.args.get("code")
    error = request.args.get("error")

    if error:
        logger.error(f"LINE OAuth error: {error}")
        return redirect("/?error=line_auth_failed")

    if not code:
        return redirect("/?error=no_code")

    try:
        # Exchange code for token (LINE requires form-urlencoded)
        token_response = http_requests.post(
            "https://api.line.me/oauth2/v2.1/token",
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": LINE_REDIRECT_URI,
                "client_id": LINE_CHANNEL_ID,
                "client_secret": LINE_CHANNEL_SECRET
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"}
        )
        token_data = token_response.json()
        access_token = token_data.get("access_token")

        if not access_token:
            logger.error(f"LINE token exchange failed: {token_data}")
            return redirect("/?error=line_token_exchange_failed")

        # Get user profile
        profile_response = http_requests.get(
            "https://api.line.me/v2/profile",
            headers={"Authorization": f"Bearer {access_token}"}
        )
        profile = profile_response.json()

        # Upsert member and store in session
        member_id = upsert_member(
            external_id=f"line_{profile['userId']}",
            display_name=profile.get("displayName"),
            avatar_url=profile.get("pictureUrl"),
            source="line"
        )

        # 清除舊的 session 資料，確保乾淨的登入狀態
        session.clear()

        session["user"] = {
            "member_id": member_id,
            "provider": "line",
            "external_id": f"line_{profile['userId']}",
            "name": profile.get("displayName")
        }
        session.permanent = True

        logger.info(f"[LINE Login] User logged in: {profile.get('displayName')} (member_id: {member_id}, external_id: line_{profile['userId']})")

        return redirect("/?login=success")

    except Exception as e:
        logger.exception("LINE OAuth token exchange failed")
        return redirect("/?error=line_token_exchange_failed")


@app.get("/auth/facebook/callback")
def auth_facebook_callback():
    """Handle Facebook OAuth callback."""
    code = request.args.get("code")
    error = request.args.get("error")

    if error:
        logger.error(f"Facebook OAuth error: {error}")
        return redirect("/?error=facebook_auth_failed")

    if not code:
        return redirect("/?error=no_code")

    try:
        # Exchange code for token
        token_response = http_requests.get(
            "https://graph.facebook.com/v18.0/oauth/access_token",
            params={
                "client_id": FACEBOOK_APP_ID,
                "client_secret": FACEBOOK_APP_SECRET,
                "redirect_uri": FACEBOOK_REDIRECT_URI,
                "code": code
            }
        )
        token_data = token_response.json()
        access_token = token_data.get("access_token")

        if not access_token:
            logger.error(f"Facebook token exchange failed: {token_data}")
            return redirect("/?error=facebook_token_exchange_failed")

        # Get user profile
        profile_response = http_requests.get(
            "https://graph.facebook.com/me",
            params={
                "fields": "id,name,email,picture.type(large)",
                "access_token": access_token
            }
        )
        profile = profile_response.json()

        picture_url = None
        if profile.get("picture") and profile["picture"].get("data"):
            picture_url = profile["picture"]["data"].get("url")

        # Upsert member and store in session
        member_id = upsert_member(
            external_id=f"facebook_{profile['id']}",
            display_name=profile.get("name"),
            avatar_url=picture_url,
            email=profile.get("email"),
            source="facebook"
        )

        session["user"] = {
            "member_id": member_id,
            "provider": "facebook",
            "external_id": f"facebook_{profile['id']}",
            "email": profile.get("email"),
            "name": profile.get("name")
        }
        session.permanent = True

        return redirect("/?login=success")

    except Exception as e:
        logger.exception("Facebook OAuth token exchange failed")
        return redirect("/?error=facebook_token_exchange_failed")


@app.get("/api/user")
def api_get_user():
    """Return current authenticated user or 401."""
    # Debug: 記錄 session 資訊
    from flask import request as flask_request
    logger.info(f"[/api/user] Session ID cookie: {flask_request.cookies.get('session', 'N/A')[:20] if flask_request.cookies.get('session') else 'None'}...")
    logger.info(f"[/api/user] Session data: {dict(session) if session else 'Empty'}")
    if "user" in session:
        user_data = session["user"].copy()
        # 從資料庫讀取頭像 (避免 session cookie 過大導致 431 錯誤)
        if user_data.get("member_id"):
            member = fetchone(
                "SELECT avatar_url FROM members WHERE id = :id",
                {"id": user_data["member_id"]}
            )
            if member:
                user_data["picture"] = member.get("avatar_url")
        response = jsonify({
            "success": True,
            "user": user_data
        })
        return _no_store(response)
    response = jsonify({
        "success": False,
        "message": "Not authenticated"
    })
    response.status_code = 401
    return _no_store(response)


@app.post("/api/logout")
def api_logout():
    """Destroy session and logout user."""
    session.clear()
    return jsonify({
        "success": True,
        "message": "Logged out successfully"
    })


@app.get(f"{ASSET_ROUTE_PREFIX}/<path:filename>")
def serve_uploads(filename: str):
    return send_from_directory(ASSET_LOCAL_DIR, filename, conditional=True)


@app.get("/survey/form")
def survey_form():
    sid = request.args.get("sid", type=int)
    if not sid:
        abort(400, "missing sid")
    try:
        meta = load_survey_meta(sid)
    except ValueError:
        abort(404, "survey not found")
    return render_template_string(SURVEY_TEMPLATE, survey=meta, survey_id=sid)


@app.get("/__survey_load")
def survey_load():
    sid = request.args.get("sid", type=int)
    if not sid:
        return jsonify({"error": "missing sid"}), 400
    try:
        data = load_survey_meta(sid)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 404
    return jsonify(data)


@app.post("/__survey_submit")
def survey_submit():
    if request.is_json:
        payload = request.get_json(force=True) or {}
        sid = payload.get("sid") or payload.get("survey_id")
        answers = payload.get("data") or payload.get("answers") or {}
        participant = payload.get("participant") or {}
    else:
        data = request.form.to_dict(flat=False)
        sid = data.get("sid", [None])[0]
        answers = {
            key: (values if len(values) > 1 else values[0])
            for key, values in data.items()
            if key.startswith("q_")
        }
        participant = {
            "external_id": (data.get("participant_id", [""])[0] or "").strip(),
            "display_name": (data.get("participant_name", [""])[0] or "").strip(),
        }

    try:
        sid_int = int(sid)
    except (TypeError, ValueError):
        return jsonify({"ok": False, "error": "invalid sid"}), 400

    try:
        save_survey_submission(sid_int, answers, participant)
    except ValueError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400

    return jsonify({"ok": True})


if __name__ == "__main__":
    port = int(os.getenv("PORT", "8300"))
    debug_mode = os.getenv("FLASK_DEBUG", "0") in {"1", "true", "True"}
    app.run(host="0.0.0.0", port=port, debug=debug_mode)
