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
def get_student_db_id(line_user_id, auto_create=True):
    # ... (程式碼不變)
    pass

# ----------------------------------------
# 🔥 P2.14：【終極修復】 Webhook 路由
# (已將 /callback 改為 /webhook)
# ----------------------------------------
@app.route("/webhook", methods=['POST'])
def webhook():
    # 取得 X-Line-Signature 標頭
    signature = request.headers['X-Line-Signature']

    # 取得請求主體 (request body)
    body = request.get_data(as_text=True)
    app.logger.info("Request body: " + body)

    # (P2.7 的防當機 try...except 邏輯 ... 100% 不變)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        print("Invalid signature. Please check your channel secret.")
        abort(400)
    except Exception as e:
        print(f"Webhook handler error: {e}")

    return 'OK'

# ----------------------------------------
# (handle_message 路由 ... 100% 完全不變)
# (P2.7 / v2.4 的 LIFF 按鈕邏輯)
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
        return # 結束

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

# (handle_postback 路由 ... 100% 完全不變)
@handler.add(PostbackEvent)
def handle_postback(event):
    pass

# (liff_login_page 路由 ... 100% 完全不變)
@app.route("/liff/login", methods=['GET'])
def liff_login_page():
    return render_template('liff_login.html')

# (api_register_bind 路由 ... 100% 完全不變)
# (P2.2 / v2.2 的 API 邏輯)
@app.route("/api/register-bind", methods=['POST'])
def api_register_bind():
    # ... (程式碼不變)
    pass

# (啟動伺服器 ... 100% 完全不變)
if __name__ == "__main__":
    init_db() 
    port = int(os.environ.get('PORT', 5001))
    app.run(host='0.0.0.0', port=port)
