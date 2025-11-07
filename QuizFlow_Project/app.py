import os
import sqlite3
import datetime
from flask import Flask, request, abort, render_template # 1. 確保 'render_template' 已匯入
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

# 從環境變數讀取 LINE Bot 資訊
line_bot_api = LineBotApi(os.environ['LINE_CHANNEL_ACCESS_TOKEN'])
handler = WebhookHandler(os.environ['LINE_CHANNEL_SECRET'])

# ----------------------------------------
# 1. 資料庫設定 (平台架構版)
# ----------------------------------------
DB_NAME = 'platform.db'

def init_db():
    """初始化資料庫：建立我們規劃的 5 個核心資料表"""
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

def get_student_db_id(line_user_id, auto_create=True):
    """
    用 line_user_id 查找或新增一個學生，並回傳
    """
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
# 2. LINE Webhook 路由
# ----------------------------------------
@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)
    app.logger.info("Request body: " + body)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    return 'OK'

# ----------------------------------------
# 3. 訊息處理 (v2.0 邏輯)
# ----------------------------------------
@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    """處理文字訊息"""
    user_msg = event.message.text
    user_id = event.source.user_id
    
    student_id, is_linked = get_student_db_id(user_id)
    
    if not is_linked:
        # P1.1 的核心：Bot 回覆要求綁定
        reply_msg = "您好！請先點擊下方的「帳號登入/綁定」來啟用測驗功能。"
        # TODO: 下一步我們會把這個訊息改成「LIFF 按鈕」
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text=reply_msg)
        )
        return

    # --- (以下是未來 P1.2 要實作的) ---
    if user_msg.startswith('加入 '):
        invite_code = user_msg.split(' ')[1]
        reply_msg = f"收到！正在嘗試加入題庫：{invite_code}..."
    elif user_msg in ['題庫', '我的題庫']:
        reply_msg = "正在查詢您有權限的題庫..."
    else:
        reply_msg = "您好，請輸入「我的題庫」來開始測驗，或輸入「加入 [邀請碼]」來加入新題庫。"

    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text=reply_msg)
    )

@handler.add(PostbackEvent)
def handle_postback(event):
    # (P1.2 才會實作的答題邏輯)
    pass

# ----------------------------------------
# 4. LIFF 頁面路由 (P1.1 新增)
# ----------------------------------------
@app.route("/liff/login", methods=['GET'])
def liff_login_page():
    """
    提供「LIFF 帳號綁定」的 HTML 頁面
    """
    # Flask 會自動去 'templates' 資料夾中尋找 'liff_login.html'
    return render_template('liff_login.html')

# ----------------------------------------
# 啟動伺服器
# ----------------------------------------
if __name__ == "__main__":
    init_db() 
    port = int(os.environ.get('PORT', 5001))
    app.run(host='0.0.0.0', port=port)