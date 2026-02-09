import os
import sys
import threading
from flask import Flask
from config import Settings
from app import create_app
import rich_menu_handler

def init_full_application():
    settings = Settings()
    app = create_app()
    
    # 更新選單連結
    liff_base = f"https://liff.line.me/{settings.LIFF_ID}"
    menu_config = {
        "name": "公堂運作選單",
        "chatBarText": "開啟選單",
        "buttons": [
            {"label": "了愿打卡", "action": {"type": "uri", "uri": f"{liff_base}?page=checkin"}},
            {"label": "班程報名", "action": {"type": "uri", "uri": f"{liff_base}?page=class_center"}}, # 改這裡
            {"label": "故障申報", "action": {"type": "uri", "uri": f"{liff_base}?page=fix"}},
            {"label": "個人設定", "action": {"type": "uri", "uri": f"{liff_base}?page=settings"}}, # 改這裡
            {"label": "本週輪值", "action": {"type": "uri", "uri": f"{liff_base}?page=duty"}}, # 改這裡
            {"label": "班程資訊", "action": {"type": "uri", "uri": f"{liff_base}?page=class_info"}}
        ]
    }
    
    # 啟動時建立選單
    rich_menu_handler.create_rich_menu(menu_config)

    print(f"🚀 伺服器啟動於 port {settings.PORT}")
    from waitress import serve
    serve(app, host='0.0.0.0', port=settings.PORT)

if __name__ == '__main__':

    init_full_application()
