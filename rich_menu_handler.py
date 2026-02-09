import requests
import json
import os
from PIL import Image, ImageDraw, ImageFont

# ================== 基本設定 ==================
IMAGE_FILENAME = "rich_menu_generated.png"
IMAGE_WIDTH = 2500
IMAGE_HEIGHT = 1686 
ICON_SIZE = 200
FONT_SIZE = 130

# ================== [風格調色盤：慧霖宮素雅風] ==================
# 背景漸層：極淺米白 -> 溫暖木質金
BG_GRADIENT_TOP = (255, 253, 245)    
BG_GRADIENT_BOTTOM = (245, 222, 179) 

# 文字顏色：深褐色
TEXT_COLOR = (101, 67, 33)
# 分隔線顏色：淡淡的金色
LINE_COLOR = (210, 180, 140)
# Icon 顏色
ICON_COLOR = (101, 67, 33)

# Icon 對應表 (使用您要的白話文)
ICON_MAPPING = {
    "了愿打卡": "\uf058",  # fa-check-circle
    "班程報名": "\uf518",  # fa-book-reader
    "故障申報": "\uf0ad",  # fa-wrench
    "壇務佈告欄": "\uf51a", # fa-broom
    "班程資訊": "\uf073",  # fa-calendar-alt
    "個人設定": "\uf54b",  # fa-shoe-prints
}

def create_gradient_image(width, height, top_color, bottom_color):
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

def draw_icon(draw, x, y, icon_char):
    # 嘗試多種路徑找字型
    font_paths = [
        "static/fonts/fa-solid-900.ttf",
        "static/fa-solid-900.ttf", 
        "static/fonts/Font Awesome 6 Free-Solid-900.otf"
    ]
    font_path = None
    for p in font_paths:
        if os.path.exists(p):
            font_path = p
            break
            
    if not font_path:
        print("⚠️ 找不到 Icon 字型檔，將略過繪製圖示")
        return

    try:
        font = ImageFont.truetype(font_path, ICON_SIZE)
        draw.text((x, y), icon_char, font=font, fill=ICON_COLOR, anchor="mm")
    except Exception as e:
        print(f"繪製圖示錯誤: {e}")

def generate_rich_menu_image(menu_config):
    img = create_gradient_image(IMAGE_WIDTH, IMAGE_HEIGHT, BG_GRADIENT_TOP, BG_GRADIENT_BOTTOM)
    draw = ImageDraw.Draw(img)

    btn_w = IMAGE_WIDTH / 2
    btn_h = IMAGE_HEIGHT / 3
    
    # 畫分隔線
    draw.line([(IMAGE_WIDTH/2, 0), (IMAGE_WIDTH/2, IMAGE_HEIGHT)], fill=LINE_COLOR, width=5)
    draw.line([(0, IMAGE_HEIGHT/3), (IMAGE_WIDTH, IMAGE_HEIGHT/3)], fill=LINE_COLOR, width=5)
    draw.line([(0, IMAGE_HEIGHT*2/3), (IMAGE_WIDTH, IMAGE_HEIGHT*2/3)], fill=LINE_COLOR, width=5)

    # 找中文字型
    font_path = "static/fonts/NotoSansTC-Bold.otf"
    if not os.path.exists(font_path): font_path = "static/fonts/msjhbd.ttc" # Windows 備用
    
    try:
        font = ImageFont.truetype(font_path, FONT_SIZE)
    except:
        font = ImageFont.load_default()

    centers = [
        (btn_w * 0.5, btn_h * 0.5), (btn_w * 1.5, btn_h * 0.5),
        (btn_w * 0.5, btn_h * 1.5), (btn_w * 1.5, btn_h * 1.5),
        (btn_w * 0.5, btn_h * 2.5), (btn_w * 1.5, btn_h * 2.5)
    ]

    for i, btn in enumerate(menu_config["buttons"]):
        if i >= 6: break
        label = btn["label"]
        cx, cy = centers[i]
        
        icon_char = ICON_MAPPING.get(label, "")
        if icon_char:
            draw_icon(draw, cx, cy - 80, icon_char)
            
        draw.text((cx, cy + 100), label, font=font, fill=TEXT_COLOR, anchor="mm")

    draw.rectangle([0, 0, IMAGE_WIDTH-1, IMAGE_HEIGHT-1], outline=LINE_COLOR, width=15)
    img.save(IMAGE_FILENAME)
    return IMAGE_FILENAME

def create_and_set_rich_menu(token, menu_config):
    try:
        generate_rich_menu_image(menu_config)
        
        w, h = IMAGE_WIDTH, IMAGE_HEIGHT
        cw, ch = int(w / 2), int(h / 3)
        
        areas = [
            {"bounds": {"x": 0, "y": 0, "width": cw, "height": ch}, "action": menu_config["buttons"][0]["action"]},
            {"bounds": {"x": cw, "y": 0, "width": cw, "height": ch}, "action": menu_config["buttons"][1]["action"]},
            {"bounds": {"x": 0, "y": ch, "width": cw, "height": ch}, "action": menu_config["buttons"][2]["action"]},
            {"bounds": {"x": cw, "y": ch, "width": cw, "height": ch}, "action": menu_config["buttons"][3]["action"]},
            {"bounds": {"x": 0, "y": ch*2, "width": cw, "height": ch}, "action": menu_config["buttons"][4]["action"]},
            {"bounds": {"x": cw, "y": ch*2, "width": cw, "height": ch}, "action": menu_config["buttons"][5]["action"]},
        ]

        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        
        # 刪除舊選單
        try:
            old = requests.get("https://api.line.me/v2/bot/richmenu/list", headers=headers).json()
            for m in old.get("richmenus", []):
                if m["name"] == menu_config["name"]:
                    requests.delete(f"https://api.line.me/v2/bot/richmenu/{m['richMenuId']}", headers=headers)
        except: pass

        body = {"size": {"width": w, "height": h}, "selected": True, "name": menu_config["name"], "chatBarText": menu_config["chatBarText"], "areas": areas}
        res = requests.post("https://api.line.me/v2/bot/richmenu", headers=headers, json=body)
        if res.status_code != 200: return

        rich_menu_id = res.json()["richMenuId"]
        with open(IMAGE_FILENAME, "rb") as f:
            requests.post(f"https://api-data.line.me/v2/bot/richmenu/{rich_menu_id}/content", headers={"Authorization": f"Bearer {token}", "Content-Type": "image/png"}, data=f)
        
        requests.post(f"https://api.line.me/v2/bot/user/all/richmenu/{rich_menu_id}", headers=headers)
        print("🎉 選單更新完成！")

    except Exception as e:
        print(f"❌ 選單錯誤: {e}")
