import os
import sys
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
            {"label": "班程報名", "action": {"type": "uri", "uri": f"{liff_base}?page=class_center"}},
            {"label": "故障申報", "action": {"type": "uri", "uri": f"{liff_base}?page=fix"}},
            {"label": "個人設定", "action": {"type": "uri", "uri": f"{liff_base}?page=settings"}},
            {"label": "本週輪值", "action": {"type": "uri", "uri": f"{liff_base}?page=duty"}},
            {"label": "班程資訊", "action": {"type": "uri", "uri": f"{liff_base}?page=class_info"}}
        ]
    }
    
    # 啟動時建立選單 (已修正為只傳一個參數)
    rich_menu_handler.create_rich_menu(menu_config)

    print(f"🚀 伺服器啟動於 port {settings.PORT}")
    
    # [關鍵修改] 這裡不要啟動 waitress，直接回傳 app 給 Gunicorn 使用
    return app, "Init Success"

if __name__ == '__main__':
    # 只有在本機直接執行此檔案時，才使用 waitress
    app, _ = init_full_application()
    try:
        from waitress import serve
        serve(app, host='0.0.0.0', port=Settings().PORT)
    except ImportError:
        # 如果本機沒裝 waitress，就用 Flask 內建 server (方便測試)
        app.run(host='0.0.0.0', port=Settings().PORT)
