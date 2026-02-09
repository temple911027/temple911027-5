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
    
    # 建立「慧霖宮」專屬選單
    menu_name = "HuiLinGong_Menu_V3"
    liff_base = f"https://liff.line.me/{settings.LIFF_ID}"
    
    menu_config = {
        "name": menu_name,
        "chatBarText": "開啟慧霖宮小幫手",
        "buttons": [
            # 第一排
            {"label": "了愿打卡", "action": {"type": "uri", "uri": f"{liff_base}?page=checkin"}},
            {"label": "班程報名", "action": {"type": "uri", "uri": f"{liff_base}?page=class_center"}},
            # 第二排 (順序已更換：故障在左，壇務在右)
            {"label": "故障申報", "action": {"type": "uri", "uri": f"{liff_base}?page=fix"}},
            {"label": "壇務佈告欄", "action": {"type": "uri", "uri": f"{liff_base}?page=duty"}},
            # 第三排
            {"label": "班程資訊", "action": {"type": "uri", "uri": f"{liff_base}?page=class_info"}},
            {"label": "個人設定", "action": {"type": "uri", "uri": f"{liff_base}?page=settings"}}
        ]
    }
    
    # 自動更新選單
    rich_menu_handler.create_and_set_rich_menu(
        settings.LINE_CHANNEL_ACCESS_TOKEN,
        menu_config
    )
    
    app = create_app()
    return app, settings

app, settings = init_full_application()

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=settings.PORT)
