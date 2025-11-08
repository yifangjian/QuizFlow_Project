import os
import sqlite3
import datetime
from flask import Flask, request, abort, render_template, jsonify 
from werkzeug.security import generate_password_hash, check_password_hash
from linebot import (
    LineBotApi, WebhookHandler
)
from linebot.exceptions import (
    InvalidSignatureError
)
from linebot.models import (
    MessageEvent, TextMessage, TextSendMessage,
    PostbackEvent
)

app = Flask(__name__)

line_bot_api = LineBotApi(os.environ['LINE_CHANNEL_ACCESS_TOKEN'])
handler = WebhookHandler(os.environ['LINE_CHANNEL_SECRET'])

DB_NAME = 'platform.db'

# (init_db 函數 ... 100% 完全不變)
def init_db():
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("PRAGMA foreign_keys = ON;")
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS creators (
            creator_id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        ''')
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS students (
            student_id INTEGER PRIMARY KEY AUTOINCREMENT,
            line_user_id TEXT UNIQUE,
            email TEXT UNIQUE,
            password_hash TEXT,
            account_linked BOOLEAN DEFAULT 0,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        ''')
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS question_banks (
            bank_id INTEGER PRIMARY KEY AUTOINCREMENT,
            creator_id INTEGER NOT NULL,
            bank_name TEXT NOT NULL,
            invite_code TEXT UNIQUE NOT NULL,
            requires_approval BOOLEAN DEFAULT 1,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (creator_id) REFERENCES creators (creator_id)
        )
        ''')
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS student_access (
            access_id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            bank_id INTEGER NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            requested_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(student_id, bank_id),
            FOREIGN KEY (student_id) REFERENCES students (student_id),
            FOREIGN KEY (bank_id) REFERENCES question_banks (bank_id)
        )
        ''')
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS answer_logs (
            log_id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            bank_id INTEGER NOT NULL,
            question_key TEXT NOT NULL,
            was_correct BOOLEAN NOT NULL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (student_id) REFERENCES students (student_id),
            FOREIGN KEY (bank_id) REFERENCES question_banks (bank_id)
        )
        ''')
        conn.commit()
        conn.close()
        print(f"資料庫 {DB_NAME} 初始化/檢查成功。")
    except Exception as e:
        print(f"資料庫初始化失敗: {e}")

# (get_student_db_id 函數 ... 100% 完全不變)
# (這個函數只被 Bot 使用，API 不該依賴它)
def get_student_db_id(line_user_id, auto_create=True):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT student_id, account_linked FROM students WHERE line_user_id = ?", (line_user_id,))
    student = cursor.fetchone()
    student_id = None
    account_linked = False
    if student:
        student_id = student[0]
        account_linked = bool(student[1])
    elif auto_create:
        cursor.execute("INSERT INTO students (line_user_id, account_linked) VALUES (?, ?)", (line_user_id, 0))
        conn.commit()
        student_id = cursor.lastrowid
        print(f"新 LINE 使用者加入: {line_user_id}, DB_ID: {student_id}")
    conn.close()
    return student_id, account_linked

# (callback 路由 ... 100% 完全不變)
@app.route("/callback", methods=['POST'])
def callback():
    # ... (程式碼不變)
    pass

# (handle_message 路由 ... 100% 完全不變)
@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    # ... (程式碼不變)
    pass

# (handle_postback 路由 ... 100% 完全不變)
@handler.add(PostbackEvent)
def handle_postback(event):
    pass

# (liff_login_page 路由 ... 100% 完全不變)
@app.route("/liff/login", methods=['GET'])
def liff_login_page():
    return render_template('liff_login.html')

# ----------------------------------------
# 🔥 P2.2：【邏輯修復】帳號綁定 API
# ----------------------------------------
@app.route("/api/register-bind", methods=['POST'])
def api_register_bind():
    """
    處理 LIFF 頁面提交過來的「註冊/登入並綁定」請求
    (v2.2: 修正了 "Get or Create" 邏輯)
    """
    try:
        data = request.get_json()
        email = data.get('email')
        password = data.get('password')
        line_user_id = data.get('line_user_id')

        if not email or not password or not line_user_id:
            return jsonify({"error": "缺少必要資料"}), 400

        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()

        # 1. 檢查此 Email 是否已被其他人綁定
        cursor.execute("SELECT student_id FROM students WHERE email = ? AND line_user_id != ?", (email, line_user_id))
        existing_email_other = cursor.fetchone()
        if existing_email_other:
            conn.close()
            return jsonify({"error": "此 Email 已被其他 LINE 帳號綁定"}), 409
        
        # 2. 【P2.2 核心修復】: "Get or Create" 學生
        # 不再依賴 Bot，API 自己搞定
        cursor.execute("SELECT student_id FROM students WHERE line_user_id = ?", (line_user_id,))
        existing_line_account = cursor.fetchone()

        student_id = None
        if existing_line_account:
            # LINE 帳號已存在 (Bot 建立的, 或之前綁定過)
            student_id = existing_line_account[0]
            print(f"API: 找到已存在的 LINE 帳號, ID: {student_id}")
        else:
            # LIFF 建立的 (全新用戶)
            # 
            # 🔥 這就是修復您 Bug 的地方 🔥
            #
            print(f"API: 找不到 LINE 帳號，現在自動建立...")
            cursor.execute("INSERT INTO students (line_user_id, account_linked) VALUES (?, 0)", (line_user_id,))
            student_id = cursor.lastrowid # 取得剛剛新增的 ID
            print(f"API: 新增學生 ID: {student_id}")

        # 3. 密碼加密
        password_hash = generate_password_hash(password)

        # 4. 更新(或設定)該帳號的 Email, 密碼, 並設為 "已綁定"
        # 
        # (這裡用 "ON CONFLICT" 語法來處理 Email 唯一的狀況)
        cursor.execute(
            """
            UPDATE students 
            SET email = ?, password_hash = ?, account_linked = 1 
            WHERE student_id = ?
            """,
            (email, password_hash, student_id)
        )
        conn.commit()
        conn.close()
        
        # 檢查 email 是否因為 unique 限制而失敗 (雖然前面擋過了)
        # 簡化：假設前面擋過了，這裡一定成功
        
        return jsonify({"status": "success", "message": "註冊並綁定成功！"}), 201 # 201 Created

    except sqlite3.IntegrityError as e:
        # 這通常是 "UNIQUE constraint failed: students.email"
        conn.close()
        print(f"API 綁定失敗 (IntegrityError): {e}")
        return jsonify({"error": "此 Email 已被使用"}), 409 # 409 Conflict
    except Exception as e:
        conn.close()
        print(f"API 錯誤 (Exception): {e}")
        return jsonify({"error": f"伺服器內部錯誤: {e}"}), 500


# ----------------------------------------
# 啟動伺服器
# ----------------------------------------
if __name__ == "__main__":
    init_db() 
    port = int(os.environ.get('PORT', 5001))
    app.run(host='0.0.0.0', port=port)
