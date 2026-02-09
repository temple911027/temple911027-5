# rich_menu_handler.py
import requests
import json
import os
from PIL import Image, ImageDraw, ImageFont
import config

# ================== 基本設定 ==================
IMAGE_FILENAME = "rich_menu_generated.png"
IMAGE_WIDTH = 2500
IMAGE_HEIGHT = 1200
ICON_SIZE = 220
FONT_SIZE = 150

# ================== [位置微調區] ==================
# 1. 整體垂直位置 (圖示 + 文字一起動)
#    負數 = 往上移 (預設 -40 讓視覺稍微偏上，留空間給底部)
#    正數 = 往下移
CONTENT_BASE_Y = 80

# 2. 圖示相對微調 (只動圖示，不動文字)
#    用來對齊圖示與文字的中心線
#    若圖示看起來比文字高，請設正數 (如 10)
ICON_RELATIVE_Y = -80
# ==================================================

# 背景漸層（主視覺：深藍色）
BG_GRADIENT_TOP = (20, 30, 48)
BG_GRADIENT_BOTTOM = (36, 59, 85)

# FontAwesome 圖示對照表
ICON_MAPPING = {
    "了愿打卡": "\uf00c",  # fa-check
    "班程報名": "\uf133",  # fa-calendar-alt
    "故障申報": "\uf071",  # fa-exclamation-triangle
    "資料查詢": "\uf002",  # fa-search
    "班程資訊": "\uf05a",  # fa-info-circle
    "系統說明": "\uf059",  # fa-question-circle
}

# 圖示顏色配置
ICON_COLORS = {
    "了愿打卡": (46, 204, 113),  # 綠色
    "班程報名": (52, 152, 219),  # 藍色
    "故障申報": (231, 76, 60),  # 紅色
    "資料查詢": (155, 89, 182),  # 紫色
    "班程資訊": (241, 196, 15),  # 黃色
    "系統說明": (149, 165, 166),  # 灰色
}


# ================== 字型載入邏輯 ==================
def get_font(path, size):
    if os.path.exists(path):
        try:
            return ImageFont.truetype(path, size)
        except Exception as e:
            print(f"⚠️ 字型載入失敗 ({path}): {e}")
            pass
    return None


def find_text_font(size=FONT_SIZE):
    font_paths = [
        "static/font.ttf",
        "C:/Windows/Fonts/msjhbd.ttc",
        "C:/Windows/Fonts/msjh.ttc",
        "/System/Library/Fonts/PingFang.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc",
    ]
    for p in font_paths:
        font = get_font(p, size)
        if font: return font
    return ImageFont.load_default()


def find_icon_font(size=ICON_SIZE):
    font_paths = [
        "static/Font Awesome 7 Free-Solid-900.otf",
        "static/Font Awesome 7 Free-Solid-900.ttf",
        "static/fa-solid-900.ttf",
        "static/fa-solid-900.otf",
        "static/Font Awesome 6 Free-Solid-900.otf",
        "static/fontawesome-webfont.ttf"
    ]
    for p in font_paths:
        font = get_font(p, size)
        if font:
            print(f"✅ 成功載入圖示字型: {p}")
            return font
    print("⚠️ 警告：找不到 FontAwesome 字型檔，將使用候補模式。")
    return None


# ================== 顏色工具 ==================
def lerp_color(c1, c2, t):
    return (
        int(c1[0] + (c2[0] - c1[0]) * t),
        int(c1[1] + (c2[1] - c1[1]) * t),
        int(c1[2] + (c2[2] - c1[2]) * t),
    )


# ================== 繪製圖示 (核心) ==================
def draw_fa_icon(draw_target, center_x, center_y, name):
    icon_char = ICON_MAPPING.get(name)
    icon_color = ICON_COLORS.get(name, (255, 255, 255))

    icon_font = find_icon_font(size=int(ICON_SIZE * 0.8))

    # [修改] 應用「圖示相對微調」
    # 這只會影響圖示，不會影響文字
    target_y = center_y + ICON_RELATIVE_Y

    if icon_font and icon_char:
        # 左圖右文：圖示向左偏移 70px
        OFFSET_X = 70
        target_x = center_x - OFFSET_X

        draw = ImageDraw.Draw(draw_target)
        draw.text((target_x, target_y), icon_char, font=icon_font, fill=icon_color, anchor="mm")

    else:
        # 使用 fallback
        draw_fallback_icon(draw_target, center_x, center_y, name)


def draw_fallback_icon(draw_target, center_x, center_y, name):
    OFFSET_X = 70
    target_x = center_x - OFFSET_X

    # [修改] 應用「圖示相對微調」
    target_y = center_y + ICON_RELATIVE_Y

    radius = ICON_SIZE // 2
    color = ICON_COLORS.get(name, (100, 100, 100))

    left_up = (target_x - radius, target_y - radius)
    right_down = (target_x + radius, target_y + radius)

    draw = ImageDraw.Draw(draw_target)
    draw.ellipse([left_up, right_down], fill=color)

    text = name[0] if name else "?"
    font = find_text_font(size=int(ICON_SIZE * 0.6))

    draw.text((target_x, target_y), text, font=font, fill=(255, 255, 255), anchor="mm")


# ================== 產生圖片 (排版邏輯) ==================
def create_rich_menu_image(buttons):
    image = Image.new("RGB", (IMAGE_WIDTH, IMAGE_HEIGHT))
    draw = ImageDraw.Draw(image)

    # 1. 繪製背景
    for y in range(IMAGE_HEIGHT):
        c = lerp_color(BG_GRADIENT_TOP, BG_GRADIENT_BOTTOM, y / IMAGE_HEIGHT)
        draw.line([(0, y), (IMAGE_WIDTH, y)], fill=c)

    rows, cols = 2, 3
    bw, bh = IMAGE_WIDTH / cols, IMAGE_HEIGHT / rows

    text_font = find_text_font(FONT_SIZE)
    text_color = (255, 255, 255)

    for i, text in enumerate(buttons[:6]):
        r, c = divmod(i, cols)
        cx = c * bw + bw / 2

        # [關鍵修改] 基準中心點
        # 這裡的 cy 會同時影響圖示和文字的位置
        cy = r * bh + bh / 2 + CONTENT_BASE_Y

        # 1. 繪製圖示 (傳入 cy，圖示函式會自己再加上 ICON_RELATIVE_Y)
        draw_fa_icon(image, cx, cy, text)

        # 2. 繪製文字 (傳入 cy，確保文字跟著基準點走)
        lines = [text[:2], text[2:]] if len(text) >= 4 else [text]
        lh = FONT_SIZE + 10

        # 文字區塊垂直置中於 cy
        ty = cy - (len(lines) * lh) / 2 + 10

        text_x = cx + 60

        for j, line in enumerate(lines):
            draw.text((text_x, ty + j * lh), line, font=text_font, fill=text_color, anchor="lm")

    image.save(IMAGE_FILENAME)
    print(f"✅ Rich Menu 圖片已生成: {IMAGE_FILENAME}")
    return True, IMAGE_FILENAME


# ================== LINE API 串接 ==================
def create_rich_menu(menu_config):
    token = config.Settings().LINE_CHANNEL_ACCESS_TOKEN
    buttons = [b["label"] for b in menu_config["buttons"]]

    ok, msg = create_rich_menu_image(buttons)
    if not ok:
        return False, msg

    rows, cols = 2, 3
    bw, bh = IMAGE_WIDTH / cols, IMAGE_HEIGHT / rows

    areas = []
    for i, btn in enumerate(menu_config["buttons"][:6]):
        r, c = divmod(i, cols)
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

    try:
        res = requests.post(
            "https://api.line.me/v2/bot/richmenu",
            headers=headers,
            data=json.dumps({
                "size": {"width": IMAGE_WIDTH, "height": IMAGE_HEIGHT},
                "selected": True,
                "name": menu_config["name"],
                "chatBarText": menu_config["chatBarText"],
                "areas": areas,
            }),
        )

        if res.status_code != 200:
            return False, f"建立選單物件失敗: {res.text}"

        rich_menu_id = res.json()["richMenuId"]

        with open(IMAGE_FILENAME, "rb") as f:
            upload_res = requests.post(
                f"https://api-data.line.me/v2/bot/richmenu/{rich_menu_id}/content",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "image/png",
                },
                data=f,
            )

        if upload_res.status_code != 200:
            return False, f"上傳圖片失敗: {upload_res.text}"

        default_res = requests.post(
            f"https://api.line.me/v2/bot/user/all/richmenu/{rich_menu_id}",
            headers={"Authorization": f"Bearer {token}"},
        )

        if default_res.status_code != 200:
            return False, f"設定預設失敗: {default_res.text}"

        return True, "🎉 Rich Menu 建立完成"

    except Exception as e:
        return False, f"系統錯誤: {e}"


def delete_rich_menu(rich_menu_id):
    token = config.Settings().LINE_CHANNEL_ACCESS_TOKEN
    try:
        requests.delete(
            f"https://api.line.me/v2/bot/richmenu/{rich_menu_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
    except:
        pass