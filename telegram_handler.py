import requests
import os


def send_message(text):
    """
    發送訊息到指定的 Telegram 群組
    :param text: 要發送的訊息內容 (支援 HTML 格式)
    """
    try:
        # 直接從環境變數讀取，避免循環引用 config.py
        token = os.getenv('TELEGRAM_BOT_TOKEN')
        chat_id = os.getenv('TELEGRAM_CHAT_ID')

        # 如果沒有設定，則安靜地跳過 (不報錯，方便本地測試)
        if not token or not chat_id:
            # print("⚠️ Telegram 設定缺失，跳過發送通知。")
            return

        url = f"https://api.telegram.org/bot{token}/sendMessage"

        # 設定發送參數
        payload = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "HTML",  # 啟用 HTML 格式 (可使用 <b>粗體</b>, <a href>連結</a>)
            "disable_web_page_preview": False  # 允許連結預覽 (方便看照片)
        }

        # 發送請求
        response = requests.post(url, json=payload, timeout=5)

        if response.status_code == 200:
            print("✅ Telegram 通知發送成功")
        else:
            print(f"❌ Telegram 發送失敗: {response.text}")

    except Exception as e:
        print(f"❌ Telegram 模組發生錯誤: {e}")