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
    # 🔥 P2.3：【全新匯入】 我們需要這 3 個
    TemplateSendMessage, ButtonsTemplate, URIAction
)

app = Flask(__name__)

line_bot_api = LineBotApi(os.environ['LINE_CHANNEL_ACCESS_TOKEN'])
handler = WebhookHandler(os.environ['LINE_CHANNEL_SECRET'])

DB_NAME = 'platform.db'

# (init_db 函數 ... 100% 完全不變)
def init_db():
    # ... (程式碼不變)
    pass

# (get_student_db_id 函數 ... 100% 完全不變)
def get_student_db_id(line_user_id, auto_create=True):
    # ... (程式碼不變)
    pass

# (callback 路由 ... 100% 完全不變)
@app.route("/callback", methods=['POST'])
def callback():
    # ... (程式碼不變)
    pass

# ----------------------------------------
# 🔥 P2.3：【重大更新】訊息處理
# ----------------------------------------
@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    """處理文字訊息"""
    user_msg = event.message.text
    user_id = event.source.user_id
    
    # 檢查學生是否「已綁定」(已完成 P2.1 流程)
    student_id, is_linked = get_student_db_id(user_id)
    
    #
    # 🔥 P2.3：【這就是我們的核心修改】
    #
    if not is_linked:
        # 偵測到「未綁定」用戶
        # 我們不再回傳純文字，而是推送「LIFF 按鈕」
        
        # 1. 建立「動作」(點了會打開 LIFF 網址)
        liff_action = URIAction(
            label="點此開始 (帳號綁定)",
            # 【關鍵！】 這裡要填您 100% 正確的「魔法網址」
            uri="https://liff.line.me/2008445452-XRn1zq19"
        )
        
        # 2. 建立「按鈕模板」
        buttons_template = ButtonsTemplate(
            title="歡迎使用 Quizpie！",
            text="您好！請先完成帳號綁定，才能開始使用測驗功能喔。",
            actions=[liff_action] # 把動作放進來
        )
        
        # 3. 建立「模板訊息」
        template_message = TemplateSendMessage(
            alt_text="歡迎使用 Quizpie！請先完成帳號綁定", # 這是手機通知欄會看到的
            template=buttons_template
        )
        
        # 4. 回覆！
        line_bot_api.reply_message(
            event.reply_token,
            template_message
        )
        return # 結束這個回合

    # --- (以下是「已綁定」用戶的邏輯 ... 100% 完全不變) ---
    if user_msg.startswith('加入 '):
        reply_msg = f"收到！正在嘗試加入題庫..."
    elif user_msg in ['題庫', '我的題庫']:
        reply_msg = "正在查詢您有權限的題庫..."
    else:
        # P2.3 優化：已登入的用戶，回覆也親切一點
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
@app.route("/api/register-bind", methods=['POST'])
def api_register_bind():
    # ... (我們 v2.2 的 API 邏輯 100% 不變)
    pass

# (啟動伺服器 ... 100% 完全不變)
if __name__ == "__main__":
    init_db() 
    port = int(os.environ.get('PORT', 5001))
    app.run(host='0.0.0.0', port=port)
