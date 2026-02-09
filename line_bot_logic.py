from linebot import LineBotApi, WebhookParser
from linebot.models import MessageEvent, TextMessage, TextSendMessage, FlexSendMessage
import sheets_handler
import math
import time

line_bot_api = None
parser = None
settings = None

def init_bot(app_settings):
    global line_bot_api, parser, settings
    settings = app_settings
    line_bot_api = LineBotApi(settings.LINE_CHANNEL_ACCESS_TOKEN)
    parser = WebhookParser(settings.LINE_CHANNEL_SECRET)
    print("✅ LINE Bot 初始化完成")

def calculate_distance(lat1, lon1, lat2, lon2):
    R = 6371000
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)
    a = math.sin(delta_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c

def handle_event(event):
    if isinstance(event, MessageEvent) and isinstance(event.message, TextMessage):
        handle_text_message(event.reply_token, event.source.user_id, event.message.text)

def handle_text_message(reply_token, user_id, received_text):
    # === 打卡邏輯 ===
    if received_text.startswith("#打卡"):
        try:
            parts = received_text.split(" ", 2)
            category = parts[1] if len(parts) >= 2 else "未分類"
            extra_info = parts[2] if len(parts) >= 3 else ""
            
            # [修改] 1. 判斷是否為補單
            is_missed = "(補單)" in extra_info

            user_lat = None
            user_lng = None
            if "座標:" in extra_info:
                try:
                    coord_str = extra_info.split("座標:")[1].strip()
                    coord_clean = coord_str.split(" ")[0] 
                    lat_str, lng_str = coord_clean.split(",")
                    user_lat = float(lat_str)
                    user_lng = float(lng_str)
                except: pass

            note = ""
            matched_location_name = None

            # [修改] 2. 距離檢查 (補單則跳過)
            if user_lat and user_lng:
                config, locations = sheets_handler.get_system_settings()
                for loc in locations:
                    dist = calculate_distance(user_lat, user_lng, loc['lat'], loc['lng'])
                    if dist <= loc['radius']:
                        matched_location_name = loc['name']
                        note = f"位置確認：{loc['name']} (距離{int(dist)}m)"
                        break
                
                if not matched_location_name and not is_missed:
                    reply_text = "⚠️ 打卡失敗！\n距離太遠，若為事後補登，請勾選「補打卡」。"
                    line_bot_api.reply_message(reply_token, TextSendMessage(text=reply_text))
                    return
                
                if not matched_location_name and is_missed:
                    matched_location_name = "補單申請"
                    note = f"補打卡 (距離未知)"
            else:
                if not is_missed: # 正常打卡一定要有座標
                    note = extra_info
                else:
                    matched_location_name = "補單申請"
                    note = "補打卡 (無座標)"

            if is_missed: note += " (補單)"

            user_name = "前賢"
            try:
                profile = line_bot_api.get_profile(user_id)
                user_name = profile.display_name
            except: pass

            success, msg = sheets_handler.append_checkin_data(user_id, user_name, category, note)
            
            if success:
                reply_text = f"✅ {user_name} 前賢，已完成「補打卡」！" if is_missed else f"✅ {user_name} 前賢，打卡成功！"
            else:
                reply_text = f"⚠️ 打卡失敗：{msg}"
            
            line_bot_api.reply_message(reply_token, TextSendMessage(text=reply_text))
            
        except Exception as e:
            line_bot_api.reply_message(reply_token, TextSendMessage(text=f"❌ 系統錯誤: {str(e)}"))

    # === 報修邏輯 (保留但移除 TG) ===
    elif received_text.startswith("#報修"):
        try:
            parts = received_text.split("|")
            if len(parts) < 3:
                line_bot_api.reply_message(reply_token, TextSendMessage(text="格式錯誤"))
                return
                
            item = parts[1].strip()
            desc = parts[2].strip()
            photo_string = parts[3].strip() if len(parts) > 3 else ""

            success, msg = sheets_handler.append_fix_report(user_id, item, desc, photo_string)
            if success:
                line_bot_api.reply_message(reply_token, TextSendMessage(text="✅ 報修單已送出，感恩！"))
            else:
                line_bot_api.reply_message(reply_token, TextSendMessage(text=f"❌ 失敗: {msg}"))
        except: pass