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
    PostbackEvent,
    TemplateSendMessage, ButtonsTemplate, URIAction
)

app = Flask(__name__)

line_bot_api = LineBotApi(os.environ['LINE_CHANNEL_ACCESS_TOKEN'])
handler = WebhookHandler(os.environ['LINE_CHANNEL_SECRET'])

DB_NAME = 'platform.db'

# --- 1. 完整的 init_db ---
def init_db():
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("PRAGMA foreign_keys = ON;")

        # 1. 製作者 (老師) 表
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS creators (
            creator_id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        ''')
        
        # 2. 學生 (用戶) 表
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

        # 3. 題庫 (Bank) 表
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
        
        # 4. 學生權限 (Access) 表
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS student_access (
            access_id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            bank_id INTEGER NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending', -- 'pending', 'approved', 'rejected'
            requested_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(student_id, bank_id),
            FOREIGN KEY (student_id) REFERENCES students (student_id),
            FOREIGN KEY (bank_id) REFERENCES question_banks (bank_id)
        )
        ''')

        # 5. 作答紀錄 (Logs) 表
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
        print(f"資料庫 {DB_NAME} 初始化/檢查成功。 5 個資料表已就緒。")
    except Exception as e:
        print(f"資料庫初始化失敗: {e}")

# --- 2. 完整的 get_student_db_id ---
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

# ----------------------------------------
# --- 3. 完整的 Webhook 路由 (v2.5 版) ---
# ----------------------------------------
@app.route("/webhook", methods=['POST'])
def webhook():
    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)
    app.logger.info("Request body: " + body)

    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        print("Invalid signature. Please check your channel secret.")
        abort(400)
    except Exception as e:
        print(f"Webhook handler error: {e}")

    return 'OK'

# ----------------------------------------
# --- 4. 完整的 handle_message (v2.5 版) ---
# ----------------------------------------
@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    """處理文字訊息"""
    user_msg = event.message.text
    user_id = event.source.user_id
    
    student_id, is_linked = get_student_db_id(user_id)
    
    if not is_linked:
        # 偵測到「未綁定」用戶 -> 推送「LIFF 按鈕」
        liff_action = URIAction(
            label="點此開始 (帳號綁定)",
            uri="https://liff.line.me/2008445452-XRn1zq19" # 您的魔法網址
        )
        buttons_template = ButtonsTemplate(
            title="歡迎使用 Quizpie！",
            text="您好！請先完成帳號綁定，才能開始使用測驗功能喔。",
            actions=[liff_action]
        )
        template_message = TemplateSendMessage(
            alt_text="歡迎使用 Quizpie！請先完成帳號綁定",
            template=buttons_template
        )
        line_bot_api.reply_message(
            event.reply_token,
            template_message
        )
        return

    # --- (以下是「已綁定」用戶的邏輯) ---
    if user_msg.startswith('加入 '):
        reply_msg = f"收到！正在嘗試加入題庫..."
    elif user_msg in ['題庫', '我的題庫']:
        reply_msg = "正在查詢您有權限的題庫..."
    else:
        reply_msg = "您好！請輸入「我的題庫」來開始測驗，或輸入「加入 [邀請碼]」來加入新題庫。"
    
    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text=reply_msg)
    )

# --- 5. 完整的 handle_postback ---
@handler.add(PostbackEvent)
def handle_postback(event):
    # 未來 P3 會用到
    pass

# --- 6. 完整的 liff_login_page ---
@app.route("/liff/login", methods=['GET'])
def liff_login_page():
    return render_template('liff_login.html')

# ----------------------------------------
# --- 7. 完整的 api_register_bind (v2.2 版) ---
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
        cursor.execute("SELECT student_id FROM students WHERE line_user_id = ?", (line_user_id,))
        existing_line_account = cursor.fetchone()

        student_id = None
        if existing_line_account:
            student_id = existing_line_account[0]
            print(f"API: 找到已存在的 LINE 帳號, ID: {student_id}")
        else:
            print(f"API: 找不到 LINE 帳號，現在自動建立...")
            cursor.execute("INSERT INTO students (line_user_id, account_linked) VALUES (?, 0)", (line_user_id,))
            student_id = cursor.lastrowid # 取得剛剛新增的 ID
            print(f"API: 新增學生 ID: {student_id}")

        # 3. 密碼加密
        password_hash = generate_password_hash(password)

        # 4. 更新(或設定)該帳號的 Email, 密碼, 並設為 "已綁定"
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
        
        return jsonify({"status": "success", "message": "註冊並綁定成功！"}), 201

    except sqlite3.IntegrityError as e:
        conn.close()
        print(f"API 綁定失敗 (IntegrityError): {e}")
        return jsonify({"error": "此 Email 已被使用"}), 409 
    except Exception as e:
        conn.close()
        print(f"API 錯誤 (Exception): {e}")
        return jsonify({"error": f"伺服器內部錯誤: {e}"}), 500


# --- 8. 完整的啟動伺服器 ---
if __name__ == "__main__":
    init_db() 
    port = int(os.environ.get('PORT', 5001))
    app.run(host='0.0.0.0', port=port)
