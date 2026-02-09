import os
import sys
import threading
import time
import atexit
from rich.console import Console
from rich.panel import Panel
from rich.align import Align

from config import Settings
from app import create_app
import line_bot_logic
import rich_menu_handler

console = Console()
ngrok_handler = None

def cleanup():
    """程式結束時清理"""
    pass

atexit.register(cleanup)

# ==========================================
#  核心函式：初始化應用程式 (本機與雲端共用)
#  (系統就是在這裡找不到這個函式，所以報錯)
# ==========================================
def init_full_application():
    """
    執行所有必要的初始化工作：
    1. 載入 Settings (環境變數)
    2. 初始化 LINE Bot (給予 Token)
    3. 建立 Flask App
    4. 檢查並更新 Rich Menu (圖文選單)

    回傳: (app, settings)
    """
    # 1. 載入設定
    settings = Settings()

    # 2. 初始化機器人邏輯
    line_bot_logic.init_bot(settings)

    # 3. 建立 Flask 應用程式
    app = create_app()

    # 4. 設定/更新 Rich Menu (慧霖宮專屬版)
    try:
        print("🎨 [Init] 正在檢查/更新 LINE 圖文選單...")
        liff_base = f"https://liff.line.me/{settings.LIFF_ID}"

        # 定義各功能連結 (配合您的新需求)
        url_checkin = f"{liff_base}?page=checkin"
        url_fix = f"{liff_base}?page=fix"
        url_query = f"{liff_base}?page=query"
        url_class_info = f"{liff_base}?page=class_info"
        url_help = f"{liff_base}?page=help"
        url_duty = f"{liff_base}?page=duty"
        url_settings = f"{liff_base}?page=settings"

        menu_name = f"HuiLinGong_Menu_{int(time.time())}"

        menu_config = {
            "name": menu_name,
            "chatBarText": "開啟慧霖宮小幫手",
            "buttons": [
                # 第一排
                {"label": "了愿打卡", "action": {"type": "uri", "uri": url_checkin}},
                {"label": "班程報名", "action": {"type": "uri", "uri": f"{liff_base}?page=class_center"}},
                # 第二排
                {"label": "故障申報", "action": {"type": "uri", "uri": url_fix}},
                {"label": "壇務佈告欄", "action": {"type": "uri", "uri": url_duty}},
                # 第三排
                {"label": "班程資訊", "action": {"type": "uri", "uri": url_class_info}},
                {"label": "個人設定", "action": {"type": "uri", "uri": url_settings}}
            ]
        }

        success, msg = rich_menu_handler.create_rich_menu(menu_config)
        if success:
            print(f"✅ 圖文選單設定成功！(版本: {menu_name})")
        else:
            print(f"⚠️ 圖文選單設定失敗: {msg}")

    except Exception as e:
        print(f"⚠️ 設定選單時發生錯誤 (不影響主功能): {e}")

    return app, settings


# ==========================================
#  本機開發入口 (Local Development)
# ==========================================
def main():
    console.print(Align.center(Panel("[bold cyan]慧霖宮小幫手 啟動中...[/bold cyan]", title="系統狀態")))

    # --- 呼叫共用的初始化 ---
    app, settings = init_full_application()

    # --- 啟動 Flask 伺服器 ---
    flask_thread = threading.Thread(
        target=lambda: app.run(host='0.0.0.0', port=settings.PORT, debug=True, use_reloader=False), 
        daemon=True
    )
    flask_thread.start()
    console.print(f"✅ Flask 伺服器已在背景啟動，監聽 port: {settings.PORT}")
    
    try:
        while True: time.sleep(1)
    except KeyboardInterrupt:
        console.print("\n🛑 收到關閉信號，正在強制結束...")
        os._exit(0)

if __name__ == "__main__":
    main()
