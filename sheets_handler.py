import gspread
import uuid
import json
import os
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime

# 設定權限範圍
SCOPE = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive"
]

def get_client():
    secret_path = '/etc/secrets/service_account.json'
    if os.path.exists(secret_path):
        creds = ServiceAccountCredentials.from_json_keyfile_name(secret_path, SCOPE)
        return gspread.authorize(creds)
    
    json_key_env = os.getenv('GOOGLE_JSON_KEY')
    if json_key_env:
        try:
            creds_dict = json.loads(json_key_env)
            creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, SCOPE)
            return gspread.authorize(creds)
        except: pass

    if os.path.exists('service_account.json'):
        creds = ServiceAccountCredentials.from_json_keyfile_name('service_account.json', SCOPE)
        return gspread.authorize(creds)

    raise Exception("找不到 Google 憑證")

def write_log(level, message):
    try:
        client = get_client()
        # 這裡工作表名稱維持原樣，或是您可以去 Excel 改名為「慧霖宮系統日誌」
        try:
            sheet = client.open("公堂壇務運作管理系統").worksheet("系統日誌")
        except:
            sheet = client.open("公堂壇務運作管理系統").add_worksheet(title="系統日誌", rows=1000, cols=3)
            sheet.append_row(["時間戳記", "層級", "訊息"])
        
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        sheet.append_row([timestamp, level, message])
        print(f"[{level}] {message}")
    except: pass

# --- 讀取系統參數 ---
def get_system_settings():
    try:
        client = get_client()
        sheet = client.open("公堂壇務運作管理系統").worksheet("系統參數設定")
        data = sheet.get_all_values()
        config = {}
        config['ALLOWED_DISTANCE'] = 500 # 放寬一點
        for row in data[1:]:
            if len(row) >= 2 and row[0]:
                config[row[0].strip()] = row[1].strip()
        
        locations = []
        for row in data[1:]:
            if len(row) >= 6 and row[3]:
                try:
                    locations.append({
                        "name": row[3].strip(),
                        "lat": float(row[4].strip()),
                        "lng": float(row[5].strip()),
                        "radius": int(row[6].strip()) if row[6].strip().isdigit() else 500
                    })
                except: continue
        return config, locations
    except: return {}, []

# --- 核心功能區 ---

def add_category_if_new(category):
    try:
        client = get_client()
        sheet = client.open("公堂壇務運作管理系統").worksheet("了愿項目")
        existing = sheet.col_values(1)
        if category not in existing:
            sheet.append_row([category])
    except: pass

def get_all_categories():
    try:
        client = get_client()
        sheet = client.open("公堂壇務運作管理系統").worksheet("了愿項目")
        return sheet.col_values(1)
    except: return []

def append_checkin_data(user_id, user_name, category, note):
    try:
        add_category_if_new(category)
        client = get_client()
        try:
            sheet = client.open("公堂壇務運作管理系統").worksheet("了愿打卡紀錄")
        except:
            sheet = client.open("公堂壇務運作管理系統").add_worksheet(title="了愿打卡紀錄", rows=1000, cols=6)
            sheet.append_row(["紀錄ID", "User ID", "時間", "姓名", "類別", "備註"])

        record_id = str(uuid.uuid4())
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        sheet.append_row([record_id, user_id, timestamp, user_name, category, note])
        return True, "打卡成功"
    except Exception as e:
        write_log("ERROR", f"打卡失敗: {e}")
        return False, str(e)

# --- 報名相關 (整合自動帶入個資) ---
def register_class_signup(user_id, class_date, class_name, note):
    try:
        client = get_client()
        wb = client.open("公堂壇務運作管理系統")
        
        # 1. 查個資
        profile = get_user_full_profile(user_id)
        if "error" in profile:
            return False, "找不到您的資料，請先至「個人設定」完善資料。"
            
        user_name = profile.get("name", "未知名稱")
        phone = profile.get("phone", "")
        default_meal = profile.get("meal", "素食")

        # 2. 準備寫入
        try:
            sheet = wb.worksheet("班程報名紀錄")
        except:
            sheet = wb.add_worksheet(title="班程報名紀錄", rows=1000, cols=9)
            sheet.append_row(["報名時間", "班程日期", "班程名稱", "姓名", "電話", "午餐", "晚餐", "備註", "UserID"])

        records = sheet.get_all_values()
        for row in records:
            if len(row) > 8 and row[8] == user_id and row[2] == class_name:
                return False, "您已經報名過這個班程囉！"

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        row_data = [timestamp, class_date, class_name, user_name, phone, default_meal, default_meal, note, user_id]
        sheet.append_row(row_data)
        
        return True, "報名成功！"
    except Exception as e:
        write_log("ERROR", f"報名失敗: {e}")
        return False, str(e)

def cancel_class_signup(user_id, class_name):
    try:
        client = get_client()
        sheet = client.open("公堂壇務運作管理系統").worksheet("班程報名紀錄")
        records = sheet.get_all_values()
        for i, row in enumerate(records):
            if len(row) > 8 and row[8] == user_id and row[2] == class_name:
                sheet.delete_rows(i + 1)
                return True, f"已取消 {class_name}"
        return False, "找不到紀錄"
    except Exception as e: return False, str(e)

def get_my_signups(user_id):
    try:
        client = get_client()
        sheet = client.open("公堂壇務運作管理系統").worksheet("班程報名紀錄")
        records = sheet.get_all_values()
        my_list = []
        for row in records[1:]:
            if len(row) > 8 and row[8] == user_id:
                my_list.append({"date": row[1], "name": row[2], "status": "已報名"})
        return my_list
    except: return []

def get_upcoming_classes():
    try:
        client = get_client()
        sheet = client.open("公堂壇務運作管理系統").worksheet("班程資訊")
        data = sheet.get_all_values()
        classes = []
        today = datetime.now()
        for row in data[1:]:
            if len(row) >= 2:
                try:
                    c_date = datetime.strptime(row[0], "%Y/%m/%d")
                    if c_date >= today:
                        classes.append({"date": row[0], "name": row[1]})
                except: continue
        return classes
    except: return []

# --- 個人資料與權限 ---
def get_user_full_profile(user_id):
    try:
        client = get_client()
        sheet = client.open("公堂壇務運作管理系統").worksheet("道親資料")
        cell = sheet.find(user_id)
        row = sheet.row_values(cell.row)
        
        raw_role = row[4] if len(row) > 4 else "組員"
        clean_role = str(raw_role).strip() # 去除空白
        
        return {
            "user_id": user_id,
            "name": row[1] if len(row) > 1 else "",
            "hall": row[2] if len(row) > 2 else "",
            "group": row[3] if len(row) > 3 else "",
            "role": clean_role,
            "goal": row[5] if len(row) > 5 else "0",
            "phone": row[7] if len(row) > 7 else "",
            "meal": row[8] if len(row) > 8 else "素食"
        }
    except: return {"error": "找不到資料"}

def update_user_profile(user_id, phone, meal, goal):
    try:
        client = get_client()
        sheet = client.open("公堂壇務運作管理系統").worksheet("道親資料")
        cell = sheet.find(user_id)
        if goal: sheet.update_cell(cell.row, 6, goal)
        if phone: sheet.update_cell(cell.row, 8, phone)
        if meal: sheet.update_cell(cell.row, 9, meal)
        return True, "更新成功"
    except Exception as e: return False, str(e)

def add_task_by_leader(user_id, new_task_name):
    try:
        profile = get_user_full_profile(user_id)
        if "error" in profile: return False, "找不到資料"
        
        role = profile['role']
        allowed = ["小組長", "組長", "管理員", "區道務部", "壇主", "點傳師"]
        
        if role not in allowed and "長" not in role:
             return False, "權限不足"
            
        add_category_if_new(new_task_name)
        return True, f"已新增：{new_task_name}"
    except Exception as e: return False, str(e)

# --- 輪值與臨時任務 ---
def get_group_duties(group_name):
    try:
        client = get_client()
        ss = client.open("公堂壇務運作管理系統")
        today = datetime.now()
        month_index = today.month - 1
        time_slot = month_index // 2
        
        gn = str(group_name).strip()
        group_offset = 0
        if any(x in gn for x in ["1", "一", "庶務"]): group_offset = 0
        elif any(x in gn for x in ["2", "二", "佛堂"]): group_offset = 1
        elif any(x in gn for x in ["3", "三", "天廚", "廚房"]): group_offset = 2
            
        target_id = (time_slot + group_offset) % 3
        
        try:
            order_data = ss.worksheet("order").get_all_values()[1:]
            task_data = ss.worksheet("tasks").get_all_values()[1:]
        except: return {"error": "缺少 order 或 tasks 分頁"}

        target_areas = []
        for row in order_data:
            if str(row[0]).strip() == str(target_id):
                target_areas = [x.strip() for x in row[1].replace("，", ",").split(",") if x.strip()]
        
        final_list = []
        for row in task_data:
            if len(row) < 2: continue
            area = row[0].strip()
            task = row[1].strip()
            if area in target_areas:
                final_list.append({"area": area, "task": task, "done": False})
                
        return {"group_name": gn, "tasks": final_list}
    except Exception as e: return {"error": str(e)}

def get_public_tasks():
    try:
        client = get_client()
        # 請確認有「臨時任務」這個分頁
        sheet = client.open("公堂壇務運作管理系統").worksheet("臨時任務")
        data = sheet.get_all_records()
        tasks = []
        for row in data:
            if str(row['狀態']).lower() == 'open' and int(row['目前人數']) < int(row['需求人數']):
                tasks.append({
                    "id": row['ID'],
                    "name": row['任務名稱'],
                    "desc": row['說明'],
                    "needed": row['需求人數'],
                    "current": row['目前人數']
                })
        return tasks
    except: return []

def claim_public_task(user_id, task_id, task_name):
    try:
        client = get_client()
        wb = client.open("公堂壇務運作管理系統")
        task_sheet = wb.worksheet("臨時任務")
        cell = task_sheet.find(str(task_id))
        current_val = int(task_sheet.cell(cell.row, 5).value)
        task_sheet.update_cell(cell.row, 5, current_val + 1)
        append_checkin_data(user_id, "自動", "臨時了愿", f"認領任務：{task_name}")
        return True, "認領成功！"
    except Exception as e: return False, str(e)

# --- 雜項 (報修、儀表板) ---
def get_dashboard_data(user_id):
    # 這裡簡化回傳，為了讓首頁能跑
    p = get_user_full_profile(user_id)
    return p

def append_fix_report(user_id, user_name, item, desc, photo_url):
    try:
        client = get_client()
        sheet = client.open("公堂壇務運作管理系統").worksheet("故障報修紀錄")
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        sheet.append_row([timestamp, user_name, item, desc, photo_url, "待處理", "", "", user_id])
        return True, "報修成功"
    except Exception as e: return False, str(e)
