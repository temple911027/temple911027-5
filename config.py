import os
from dotenv import load_dotenv

# --- 讓 load_dotenv() 更穩固地找到 .env 檔案 ---
basedir = os.path.abspath(os.path.dirname(__file__))
load_dotenv(os.path.join(basedir, '.env'))


class Settings:
    """
    設定類別：僅負責讀取環境變數中的「連線金鑰」。
    業務邏輯參數 (座標、Folder ID) 已移至 Google Sheets 管理。
    """

    def __init__(self):
        # --- App 運行模式 ---
        self.APP_MODE = os.getenv('APP_MODE', 'ngrok')
        self.PORT = int(os.getenv('PORT', 5000))

        # --- LINE Channel 金鑰 (必須) ---
        self.LINE_CHANNEL_ACCESS_TOKEN = os.getenv('LINE_CHANNEL_ACCESS_TOKEN')
        self.LINE_CHANNEL_SECRET = os.getenv('LINE_CHANNEL_SECRET')
        self.LIFF_ID = os.getenv('LIFF_ID')

        # --- ngrok 認證 (開發用) ---
        self.NGROK_AUTH_TOKEN = os.getenv('NGROK_AUTH_TOKEN')

        # --- Telegram 通知 (選填) ---
        self.TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
        self.TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

        # --- 金鑰驗證 ---
        if not all([self.LINE_CHANNEL_ACCESS_TOKEN, self.LINE_CHANNEL_SECRET, self.LIFF_ID]):
            print("⚠️ 警告：.env 檔案中缺少 LINE 相關設定。")