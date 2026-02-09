# rich_menu_handler.py
import requests
import json
import os
from PIL import Image
import config

# ================== 設定區 ==================
# 請確認您的圖片放在 static 資料夾，且檔名正確
STATIC_IMAGE_PATH = "static/rich_menu.jpg"
# ===========================================

def create_rich_menu(menu_config):
    """
    使用靜態圖片建立 Rich Menu
    """
    settings = config.Settings()
    token = settings.LINE_CHANNEL_ACCESS_TOKEN
    
    # 1. 檢查圖片是否存在
    if not os.path.exists(STATIC_IMAGE_PATH):
        print(f"❌ 找不到圖片！請確認 {STATIC_IMAGE_PATH} 檔案存在。")
        return False, "找不到選單圖片"

    try:
        # 2. 讀取圖片尺寸 (為了精準設定點擊區域)
        with Image.open(STATIC_IMAGE_PATH) as img:
            w, h = img.size
            print(f"🖼️ 讀取到圖片尺寸: {w} x {h}")
        
        # 3. 定義 6 格按鈕的點擊區域 (2列 x 3行)
        # 程式會自動根據您的圖片大小來計算切割位置
        cols = 3
        rows = 2
        bw = w / cols
        bh = h / rows
        
        areas = []
        buttons = menu_config["buttons"]
        
        # 確保按鈕數量不超過 6 個
        for i, btn in enumerate(buttons[:6]):
            r, c = divmod(i, cols) # 計算是第幾列、第幾行
            areas.append({
                "bounds": {
                    "x": int(c * bw),
                    "y": int(r * bh),
                    "width": int(bw),
                    "height": int(bh),
                },
                "action": btn["action"],
            })

        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

        # 4. 先刪除舊的同名選單 (避免重複累積)
        try:
            old_menus = requests.get("https://api.line.me/v2/bot/richmenu/list", headers=headers).json()
            for m in old_menus.get("richmenus", []):
                if m["name"] == menu_config["name"]:
                    print(f"🗑️ 刪除舊選單: {m['richMenuId']}")
                    requests.delete(f"https://api.line.me/v2/bot/richmenu/{m['richMenuId']}", headers=headers)
        except Exception as e:
            print(f"⚠️ 清理舊選單時發生小錯誤 (不影響): {e}")

        # 5. 上傳選單設定 (JSON)
        body = {
            "size": {"width": w, "height": h},
            "selected": True,
            "name": menu_config["name"],
            "chatBarText": menu_config["chatBarText"],
            "areas": areas,
        }

        res = requests.post(
            "https://api.line.me/v2/bot/richmenu",
            headers=headers,
            data=json.dumps(body),
        )

        if res.status_code != 200:
            return False, f"建立選單物件失敗: {res.text}"

        rich_menu_id = res.json()["richMenuId"]
        print(f"✅ 選單物件建立成功 ID: {rich_menu_id}")

        # 6. 上傳圖片檔案
        with open(STATIC_IMAGE_PATH, "rb") as f:
            # 判斷是 png 還是 jpg
            content_type = "image/png" if STATIC_IMAGE_PATH.endswith(".png") else "image/jpeg"
            
            upload_res = requests.post(
                f"https://api-data.line.me/v2/bot/richmenu/{rich_menu_id}/content",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": content_type,
                },
                data=f,
            )

        if upload_res.status_code != 200:
            return False, f"上傳圖片失敗: {upload_res.text}"

        # 7. 設定為預設選單
        default_res = requests.post(
            f"https://api.line.me/v2/bot/user/all/richmenu/{rich_menu_id}",
            headers={"Authorization": f"Bearer {token}"},
        )

        if default_res.status_code != 200:
            return False, f"設定預設失敗: {default_res.text}"

        return True, "🎉 Rich Menu 圖片上傳成功！"

    except Exception as e:
        return False, f"系統錯誤: {e}"

def delete_rich_menu(rich_menu_id):
    # 保留這個函式以免 main.py 報錯
    pass
