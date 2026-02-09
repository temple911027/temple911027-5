import requests
import json
import os
from PIL import Image, ImageDraw, ImageFont

# ================== 基本設定 ==================
IMAGE_FILENAME = "rich_menu_generated.png"
IMAGE_WIDTH = 2500
IMAGE_HEIGHT = 1686 # 修正為標準兩列式高度，讓比例更完美
ICON_SIZE = 200
FONT_SIZE = 130

# ================== [風格調色盤：慧霖宮素雅風] ==================
# 背景漸層：極淺米白 -> 溫暖木質金
BG_GRADIENT_TOP = (255, 253, 245)    # 像宣紙一樣的米白
BG_GRADIENT_BOTTOM = (245, 222, 179) # 小麥色/淡木頭色

# 文字顏色：深褐色 (像木匾上的字)
TEXT_COLOR = (101, 67, 33)

# 分隔線顏色：淡淡的金色
LINE_COLOR = (210, 180, 140)

# Icon 顏色：與文字同色，保持素雅
ICON_COLOR = (101, 67, 33)
# =============================================================

# FontAwesome 圖示對照表 (對應六大功能)
ICON_MAPPING = {
    "了愿打卡": "\uf058",  # fa-check-circle (圓圈打勾)
    "班程報名": "\uf518",  # fa-book-reader (讀書)
    "故障申報": "\uf0ad",  # fa-wrench (維修)
    "壇務佈告欄": "\uf51a", # fa-broom (掃把/清潔)
    "班程資訊": "\uf073",  # fa-calendar-alt (日曆)
    "個人設定": "\uf54b",  # fa-shoe-prints (足跡)
}

def create_gradient_image(width, height, top_color, bottom_color):
    """建立漸層背景"""
    base = Image.new('RGB', (width, height), top_color)
    top = Image.new('RGB', (width, height), top_color)
    bottom = Image.new('RGB', (width, height), bottom_color)
    mask = Image.new('L', (width, height))
    mask_data = []
    for y in range(height):
        mask_data.extend([int(255 * (y / height))] * width)
    mask.putdata(mask_data)
    base.paste(bottom, (0, 0), mask)
    return base

def draw_icon(draw, x, y, icon_char, font_path="static/fonts/fa-solid-900.ttf"):
    """繪製 FontAwesome 圖示"""
    try:
        # 嘗試載入字型，如果沒有就忽略 (會顯示方框或空白)
        if not os.path.exists(font_path):
            print(f"⚠️ 找不到字型檔: {font_path}")
            return
        font = ImageFont.truetype(font_path, ICON_SIZE)
        
        # 置中計算
        bbox = draw.textbbox((0, 0), icon_char, font=font)
        w = bbox[2] - bbox[0]
        h = bbox[3] - bbox[1]
        
        draw.text((x - w / 2, y - h / 2), icon_char, font=font, fill=ICON_COLOR)
    except Exception as e:
        print(f"繪製圖示失敗: {e}")

def generate_rich_menu_image(menu_config):
    """產生六格選單圖片"""
    img = create_gradient_image(IMAGE_WIDTH, IMAGE_HEIGHT, BG_GRADIENT_TOP, BG_GRADIENT_BOTTOM)
    draw = ImageDraw.Draw(img)

    # 格線設定 (2列 x 3行 = 6格) -> 修正：通常 Rich Menu 是 2列3行 或 2列2行
    # 我們這裡用 2列 x 3行 (上3 下3)
    # 每個按鈕寬度
    btn_w = IMAGE_WIDTH / 2
    btn_h = IMAGE_HEIGHT / 3
    
    # 畫分隔線 (十字線)
    # 垂直線
    draw.line([(IMAGE_WIDTH/2, 0), (IMAGE_WIDTH/2, IMAGE_HEIGHT)], fill=LINE_COLOR, width=5)
    # 水平線 (兩條)
    draw.line([(0, IMAGE_HEIGHT/3), (IMAGE_WIDTH, IMAGE_HEIGHT/3)], fill=LINE_COLOR, width=5)
    draw.line([(0, IMAGE_HEIGHT*2/3), (IMAGE_WIDTH, IMAGE_HEIGHT*2/3)], fill=LINE_COLOR, width=5)

    # 載入中文字型 (請確保 static/fonts/NotoSansTC-Bold.otf 存在)
    font_path = "static/fonts/NotoSansTC-Bold.otf"
    try:
        font = ImageFont.truetype(font_path, FONT_SIZE)
    except:
        font = ImageFont.load_default() # 備用

    buttons = menu_config["buttons"]
    
    # 6格座標中心點計算
    # 左上, 右上
    # 左中, 右中
    # 左下, 右下
    centers = [
        (btn_w * 0.5, btn_h * 0.5), (btn_w * 1.5, btn_h * 0.5),
        (btn_w * 0.5, btn_h * 1.5), (btn_w * 1.5, btn_h * 1.5),
        (btn_w * 0.5, btn_h * 2.5), (btn_w * 1.5, btn_h * 2.5)
    ]

    for i, btn in enumerate(buttons):
        if i >= 6: break
        label = btn["label"]
        cx, cy = centers[i]
        
        # 1. 畫圖示 (在文字上方)
        icon_char = ICON_MAPPING.get(label, "")
        if icon_char:
            draw_icon(draw, cx, cy - 80, icon_char) # 往上移一點
            
        # 2. 畫文字
        bbox = draw.textbbox((0, 0), label, font=font)
        tw = bbox[2] - bbox[0]
        th = bbox[3] - bbox[1]
        draw.text((cx - tw / 2, cy + 100 - th / 2), label, font=font, fill=TEXT_COLOR) # 往下移一點

    # 加上外框
    draw.rectangle([0, 0, IMAGE_WIDTH-1, IMAGE_HEIGHT-1], outline=LINE_COLOR, width=15)
    
    img.save(IMAGE_FILENAME)
    print(f"✅ 已生成選單圖片: {IMAGE_FILENAME}")
    return IMAGE_FILENAME

def create_and_set_rich_menu(token, menu_config):
    """上傳並設定 Rich Menu"""
    try:
        print("🎨 開始製作 Rich Menu 圖片...")
        generate_rich_menu_image(menu_config)
        
        # 定義點擊區域 (6格)
        w = IMAGE_WIDTH
        h = IMAGE_HEIGHT
        cw = int(w / 2)
        ch = int(h / 3)
        
        areas = [
            # 上排左, 上排右
            {"bounds": {"x": 0, "y": 0, "width": cw, "height": ch}, "action": menu_config["buttons"][0]["action"]},
            {"bounds": {"x": cw, "y": 0, "width": cw, "height": ch}, "action": menu_config["buttons"][1]["action"]},
            # 中排左, 中排右
            {"bounds": {"x": 0, "y": ch, "width": cw, "height": ch}, "action": menu_config["buttons"][2]["action"]},
            {"bounds": {"x": cw, "y": ch, "width": cw, "height": ch}, "action": menu_config["buttons"][3]["action"]},
            # 下排左, 下排右
            {"bounds": {"x": 0, "y": ch*2, "width": cw, "height": ch}, "action": menu_config["buttons"][4]["action"]},
            {"bounds": {"x": cw, "y": ch*2, "width": cw, "height": ch}, "action": menu_config["buttons"][5]["action"]},
        ]

        # 1. 建立 Rich Menu 物件
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        
        # 先刪除舊的同名選單 (避免重複累積)
        try:
            old_menus = requests.get("https://api.line.me/v2/bot/richmenu/list", headers=headers).json()
            for m in old_menus.get("richmenus", []):
                if m["name"] == menu_config["name"]:
                    requests.delete(f"https://api.line.me/v2/bot/richmenu/{m['richMenuId']}", headers=headers)
        except: pass

        body = {
            "size": {"width": w, "height": h},
            "selected": True,
            "name": menu_config["name"],
            "chatBarText": menu_config["chatBarText"],
            "areas": areas
        }

        res = requests.post("https://api.line.me/v2/bot/richmenu", headers=headers, json=body)
        if res.status_code != 200:
            print(f"❌ 建立選單失敗: {res.text}")
            return

        rich_menu_id = res.json()["richMenuId"]
        print(f"✅ 建立成功 ID: {rich_menu_id}")

        # 2. 上傳圖片
        with open(IMAGE_FILENAME, "rb") as f:
            headers_img = {"Authorization": f"Bearer {token}", "Content-Type": "image/png"}
            res_img = requests.post(f"https://api-data.line.me/v2/bot/richmenu/{rich_menu_id}/content", headers=headers_img, data=f)
            
        if res_img.status_code != 200:
            print(f"❌ 上傳圖片失敗: {res_img.text}")
            return

        # 3. 設定為預設
        requests.post(f"https://api.line.me/v2/bot/user/all/richmenu/{rich_menu_id}", headers=headers)
        print("🎉 Rich Menu 更新完成！請在手機上查看！")

    except Exception as e:
        print(f"❌ 設定 Rich Menu 發生錯誤: {e}")
