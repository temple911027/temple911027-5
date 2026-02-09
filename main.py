import os
import atexit
from config import Settings
from app import create_app
import line_bot_logic
import rich_menu_handler
from rich.console import Console

console = Console()

def init_full_application():
    settings = Settings()
    line_bot_logic.init_bot(settings)
    
    # 選單設定
    menu_name = "HuiLinGong_Menu_Final"
    liff_base = f"https://liff.line.me/{settings.LIFF_ID}"
    
    # 定義按鈕與連結
    menu_config = {
        "name": menu_name,
        "chatBarText": "開啟慧霖宮小幫手",
        "buttons": [
            # 第一排
            {"label": "了愿打卡", "action": {"type": "uri", "uri": f"{liff_base}?page=checkin"}},
            {"label": "班程報名", "action": {"type": "uri", "uri": f"{liff_base}?page=class_center"}},
            # 第二排 (壇務在左，故障在右)
            {"label": "壇務佈告欄", "action": {"type": "uri", "uri": f"{liff_base}?page=duty"}},
            {"label": "故障申報", "action": {"type": "uri", "uri": f"{liff_base}?page=fix"}},
            # 第三排
            {"label": "班程資訊", "action": {"type": "uri", "uri": f"{liff_base}?page=class_info"}},
            {"label": "個人設定", "action": {"type": "uri", "uri": f"{liff_base}?page=settings"}}
        ]
    }
    
    # 自動更新選單
    try:
        print("🎨 更新選單中...")
        rich_menu_handler.create_and_set_rich_menu(
            settings.LINE_CHANNEL_ACCESS_TOKEN,
            menu_config
        )
    except Exception as e:
        print(f"⚠️ 選單更新警告: {e}")
    
    app = create_app()
    return app, settings

app, settings = init_full_application()

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=settings.PORT)
