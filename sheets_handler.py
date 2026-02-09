import gspread
import uuid
import json
import os
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import telegram_handler # 確保檔案存在，否則會報錯

SCOPE = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]

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

def clean_sheet_string(s):
    if not s: return ""
    return str(s).replace('\xa0', ' ').strip()

def get_system_settings():
    try:
        client = get_client()
        sheet = client.open("公堂壇務運作管理系統").worksheet("系統參數設定")
        data = sheet.get_all_values()
        config = {'ALLOWED_DISTANCE': 500}
        for row in data[1:]:
            if len(row) >= 2 and row[0]: config[row[0].strip()] = row[1].strip()
        
        locations = []
        for row in data[1:]:
            if len(row) >= 6 and row[3]:
                try:
                    locations.append({
                        "name": row[3].strip(),
                        "lat": float(row[4].strip()),
                        "lng": float(row[5].strip()),
                        "radius": int(row[6].strip()) if row[6].isdigit() else 500
                    })
                except: continue
        return config, locations
    except: return {}, []

# --- 功能區 ---
def get_user_full_profile(user_id):
    try:
        client = get_client()
        sheet = client.open("公堂壇務運作管理系統").worksheet("道親資料")
        cell = sheet.find(user_id)
        row = sheet.row_values(cell.row)
        
        # 取得身分並去除空白
        role = str(row[4]).strip() if len(row) > 4 else "組員"
        
        return {
            "user_id": user_id,
            "name": row[1] if len(row) > 1 else "",
            "hall": row[2] if len(row) > 2 else "",
            "group": row[3] if len(row) > 3 else "",
            "role": role,
            "goal": row[5] if len(row) > 5 else "0",
            "phone": row[7] if len(row) > 7 else "",
            "meal": row[8] if len(row) > 8 else "素食"
        }
    except: return {"error": "找不到資料"}

def register_class_signup(user_id, class_date, class_name, note):
    try:
        # 自動帶入個資
        profile = get_user_full_profile(user_id)
        if "error" in profile: return False, "請先至「個人設定」完善資料"
        
        client = get_client()
        wb = client.open("公堂壇務運作管理系統")
        try: sheet = wb.worksheet("班程報名紀錄")
        except: 
            sheet = wb.add_worksheet("班程報名紀錄", 1000, 9)
            sheet.append_row(["時間","日期","名稱","姓名","電話","午餐","晚餐","備註","ID"])
            
        # 檢查重複
        records = sheet.get_all_values()
        for row in records:
            if len(row) > 8 and row[8] == user_id and row[2] == class_name:
                return False, "已報名過此班程"
                
        # 寫入
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        meal = profile.get("meal", "素食")
        row = [ts, class_date, class_name, profile['name'], profile['phone'], meal, meal, note, user_id]
        sheet.append_row(row)
        return True, "報名成功"
    except Exception as e: return False, str(e)

def cancel_class_signup(user_id, class_name):
    try:
        client = get_client()
        sheet = client.open("公堂壇務運作管理系統").worksheet("班程報名紀錄")
        records = sheet.get_all_values()
        for i, r in enumerate(records):
            if len(r) > 8 and r[8] == user_id and r[2] == class_name:
                sheet.delete_rows(i+1)
                return True, "已取消報名"
        return False, "無此紀錄"
    except Exception as e: return False, str(e)

def get_my_signups(user_id):
    try:
        client = get_client()
        sheet = client.open("公堂壇務運作管理系統").worksheet("班程報名紀錄")
        records = sheet.get_all_values()
        data = []
        for r in records[1:]:
            if len(r) > 8 and r[8] == user_id:
                data.append({"date": r[1], "name": r[2]})
        return data
    except: return []

def get_upcoming_classes():
    try:
        client = get_client()
        sheet = client.open("公堂壇務運作管理系統").worksheet("班程資訊")
        data = sheet.get_all_values()
        res = []
        today = datetime.now()
        for r in data[1:]:
            if len(r) >= 2:
                try:
                    c_date = datetime.strptime(r[0], "%Y/%m/%d")
                    if c_date >= today: res.append({"date": r[0], "name": r[1]})
                except: continue
        return res
    except: return []

# --- 雜項支援 ---
def get_all_categories():
    try:
        client = get_client()
        sheet = client.open("公堂壇務運作管理系統").worksheet("了愿項目")
        return sheet.col_values(1)
    except: return []

def get_button_config(): return [] # 預留
def get_class_result_links(): return [] # 預留

def get_dashboard_data(user_id):
    p = get_user_full_profile(user_id)
    if "error" in p: return p
    # 簡單計算
    p['target'] = int(p['goal']) if p['goal'].isdigit() else 0
    p['actual'] = 0 # 這裡可加入讀取打卡紀錄邏輯
    return p

def update_user_goal(user_id, goal):
    try:
        client = get_client()
        sheet = client.open("公堂壇務運作管理系統").worksheet("道親資料")
        cell = sheet.find(user_id)
        sheet.update_cell(cell.row, 6, goal)
        return True
    except: return False

def update_user_profile(user_id, phone, meal, goal):
    try:
        client = get_client()
        sheet = client.open("公堂壇務運作管理系統").worksheet("道親資料")
        cell = sheet.find(user_id)
        if phone: sheet.update_cell(cell.row, 8, phone)
        if meal: sheet.update_cell(cell.row, 9, meal)
        if goal: sheet.update_cell(cell.row, 6, goal)
        return True, "更新成功"
    except Exception as e: return False, str(e)

def append_checkin_data(user_id, user_name, category, note):
    try:
        client = get_client()
        try: sheet = client.open("公堂壇務運作管理系統").worksheet("了愿打卡紀錄")
        except: sheet = client.open("公堂壇務運作管理系統").add_worksheet("了愿打卡紀錄", 1000, 6)
        
        rid = str(uuid.uuid4())
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        sheet.append_row([rid, user_id, ts, user_name, category, note])
        return True, "打卡成功"
    except Exception as e: return False, str(e)

def append_fix_report(user_id, user_name, hall, item, desc, display_url, record_url=None):
    try:
        client = get_client()
        try: sheet = client.open("公堂壇務運作管理系統").worksheet("故障申報紀錄")
        except: sheet = client.open("公堂壇務運作管理系統").add_worksheet("故障申報紀錄", 100, 8)
        
        rid = str(uuid.uuid4())
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        item_full = f"【{hall}】{item}" if hall else item
        
        # 寫入
        sheet.append_row([rid, ts, user_name, item_full, desc, display_url, "待處理", record_url or display_url])
        
        # 嘗試發送 TG
        try:
            telegram_handler.send_message(f"🛠 報修通知: {user_name} - {item_full}")
        except: pass
            
        return True, "申報成功"
    except Exception as e: return False, str(e)

# 臨時任務與輪值
def get_group_duties(group_name):
    # 這裡放回您原本的輪值邏輯
    return {"tasks": []} 

def get_public_tasks():
    try:
        client = get_client()
        sheet = client.open("公堂壇務運作管理系統").worksheet("臨時任務")
        data = sheet.get_all_records()
        res = []
        for r in data:
            if str(r['狀態']) == 'Open' and r['目前人數'] < r['需求人數']:
                res.append({"id": r['ID'], "name": r['任務名稱'], "desc": r['說明'], "needed": r['需求人數'], "current": r['目前人數']})
        return res
    except: return []

def claim_public_task(user_id, task_id, task_name):
    try:
        client = get_client()
        wb = client.open("公堂壇務運作管理系統")
        sheet = wb.worksheet("臨時任務")
        cell = sheet.find(str(task_id))
        cur = int(sheet.cell(cell.row, 5).value)
        sheet.update_cell(cell.row, 5, cur + 1)
        append_checkin_data(user_id, "自動", "臨時了愿", f"認領: {task_name}")
        return True, "認領成功"
    except Exception as e: return False, str(e)

def add_task_by_leader(user_id, name):
    # 權限檢查邏輯
    p = get_user_full_profile(user_id)
    if "error" in p: return False, "無資料"
    # 只要有'長'字或特定職稱
    if "長" in p['role'] or p['role'] in ["管理員", "點傳師"]:
        # 新增項目邏輯...
        return True, "新增成功"
    return False, "權限不足"
