import gspread
import uuid
import json
import os
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime, timedelta

# 設定權限範圍
SCOPE = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive"
]

def clean_sheet_string(s):
    if not s: return ""
    s = str(s).replace('\xa0', ' ').replace('\u200b', '').strip()
    return s

def get_client():
    # 優先檢查 Render Secret Files
    secret_path = '/etc/secrets/service_account.json'
    if os.path.exists(secret_path):
        creds = ServiceAccountCredentials.from_json_keyfile_name(secret_path, SCOPE)
        return gspread.authorize(creds)

    # 檢查環境變數
    json_key_env = os.getenv('GOOGLE_JSON_KEY')
    if json_key_env:
        try:
            creds_dict = json.loads(json_key_env)
            creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, SCOPE)
            return gspread.authorize(creds)
        except: pass

    # 本地檔案
    if os.path.exists('service_account.json'):
        creds = ServiceAccountCredentials.from_json_keyfile_name('service_account.json', SCOPE)
        return gspread.authorize(creds)

    raise Exception("找不到 Google 憑證")

def write_log(level, message):
    try:
        client = get_client()
        spreadsheet = client.open("公堂壇務運作管理系統")
        try:
            sheet = spreadsheet.worksheet("系統日誌")
        except:
            sheet = spreadsheet.add_worksheet(title="系統日誌", rows=1000, cols=3)
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
        config['ALLOWED_DISTANCE'] = 300
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
                        "radius": int(row[6].strip()) if row[6].strip().isdigit() else int(config.get('ALLOWED_DISTANCE', 300))
                    })
                except: continue
        return config, locations
    except: return {}, []

# --- 核心功能區 ---

def get_all_categories():
    try:
        client = get_client()
        sheet = client.open("公堂壇務運作管理系統").worksheet("了愿項目")
        return [r for r in sheet.col_values(1) if r and r != "項目名稱"]
    except: return []

def add_category_if_new(category):
    try:
        client = get_client()
        try:
            sheet = client.open("公堂壇務運作管理系統").worksheet("了愿項目")
        except:
            return
        existing = sheet.col_values(1)
        if category not in existing:
            sheet.append_row([category])
    except: pass

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

# --- 新增功能區 ---

def get_user_full_profile(user_id):
    """設定頁面與報名用：讀取完整個資"""
    try:
        client = get_client()
        sheet = client.open("公堂壇務運作管理系統").worksheet("道親資料")
        cell = sheet.find(user_id)
        row = sheet.row_values(cell.row)
        # 假設欄位順序: A:ID, B:Name, C:Hall, D:Group, E:Role, F:Goal, G:Status, H:Phone, I:Meal
        # 如果欄位不足會自動補空字串
        def safe_get(idx, default=""):
            return row[idx] if len(row) > idx else default

        return {
            "user_id": user_id,
            "name": safe_get(1),
            "hall": safe_get(2),
            "group": safe_get(3),
            "role": safe_get(4, "組員"),
            "goal": safe_get(5, "0"),
            "phone": safe_get(7),
            "meal": safe_get(8, "素食")
        }
    except: return {"error": "找不到使用者"}

def update_user_profile(user_id, phone, meal, goal):
    """更新個資：只允許更新電話、用餐、目標"""
    try:
        client = get_client()
        sheet = client.open("公堂壇務運作管理系統").worksheet("道親資料")
        cell = sheet.find(user_id)
        
        # F欄(6):目標, H欄(8):電話, I欄(9):用餐
        if goal: sheet.update_cell(cell.row, 6, goal)
        if phone: sheet.update_cell(cell.row, 8, phone)
        if meal: sheet.update_cell(cell.row, 9, meal)
        return True, "更新成功"
    except Exception as e:
        return False, str(e)

def add_task_by_leader(user_id, new_task_name):
    """幹部新增工作項目"""
    try:
        profile = get_user_full_profile(user_id)
        if "error" in profile: return False, "找不到資料"
        
        if profile['role'] not in ["小組長", "組長", "管理員", "區道務部"]:
            return False, "權限不足"
            
        add_category_if_new(new_task_name)
        return True, f"已新增項目：{new_task_name}"
    except Exception as e:
        return False, str(e)

def register_class_signup(user_id, class_date, class_name, note):
    """班程報名 (自動帶入個資)"""
    try:
        client = get_client()
        wb = client.open("公堂壇務運作管理系統")
        
        # 1. 自動查個資
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

        # 3. 檢查重複
        records = sheet.get_all_values()
        for row in records:
            if len(row) > 8 and row[8] == user_id and row[2] == class_name:
                return False, "您已經報名過這個班程囉！"

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # 4. 寫入 (午晚餐皆預設為個人習慣)
        row_data = [
            timestamp, class_date, class_name, user_name, phone, 
            default_meal, default_meal, note, user_id
        ]
        sheet.append_row(row_data)
        return True, "報名成功！"
    except Exception as e:
        write_log("ERROR", f"報名失敗: {e}")
        return False, str(e)

def cancel_class_signup(user_id, class_name):
    """取消報名"""
    try:
        client = get_client()
        sheet = client.open("公堂壇務運作管理系統").worksheet("班程報名紀錄")
        records = sheet.get_all_values()
        
        # 從後面往前找，比較容易處理刪除後的 index 問題，但這裡只刪一筆
        for i, row in enumerate(records):
            if len(row) > 8 and row[8] == user_id and row[2] == class_name:
                sheet.delete_rows(i + 1)
                return True, f"已取消 {class_name} 的報名"
        return False, "找不到您的報名紀錄"
    except Exception as e:
        return False, str(e)

def get_my_signups(user_id):
    """查詢我的報名"""
    try:
        client = get_client()
        sheet = client.open("公堂壇務運作管理系統").worksheet("班程報名紀錄")
        records = sheet.get_all_values()
        my_list = []
        for row in records[1:]:
            if len(row) > 8 and row[8] == user_id:
                my_list.append({
                    "date": row[1],
                    "name": row[2],
                    "status": "已報名"
                })
        return my_list
    except: return []

def get_upcoming_classes():
    """取得近期班程"""
    try:
        client = get_client()
        sheet = client.open("公堂壇務運作管理系統").worksheet("班程資訊")
        data = sheet.get_all_values()
        classes = []
        today = datetime.now().date()
        for row in data[1:]:
            if len(row) >= 2:
                try:
                    c_date = datetime.strptime(row[0], "%Y/%m/%d").date()
                    if c_date >= today:
                        classes.append({"date": row[0], "name": row[1]})
                except: continue
        return sorted(classes, key=lambda x: x['date'])[:10]
    except: return []

def get_group_duties(group_name):
    """輪值邏輯 (Python 版)"""
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
        
        if not target_areas: return {"message": "本週無輪值區域"}

        # 檢查已完成 (這裡簡易判斷，若需要每週重置，建議在打卡紀錄加一個 "輪次" 欄位)
        done_list = []
        try:
            # 讀取最近的打卡紀錄來判斷是否完成
            logs = ss.worksheet("了愿打卡紀錄").get_all_values()
            # 簡易邏輯：讀取所有紀錄，若備註有包含 "輪值完成" + 區域 + 任務
            done_text_set = set()
            for log in logs[1:]:
                if len(log) > 5:
                    done_text_set.add(log[5]) # 備註欄
        except: done_text_set = set()

        final_list = []
        for row in task_data:
            if len(row) < 2: continue
            area = row[0].strip()
            task = row[1].strip()
            if area in target_areas:
                # 檢查備註是否包含關鍵字
                key = f"輪值完成：[{area}] {task}"
                is_done = False
                for d in done_text_set:
                    if key in d: 
                        is_done = True
                        break
                
                final_list.append({"area": area, "task": task, "done": is_done})
                
        return {"group_name": gn, "target_areas": target_areas, "tasks": final_list}
    except Exception as e:
        return {"error": str(e)}

def get_dashboard_data(user_id):
    """個人儀表板資料 (含組別)"""
    profile = get_user_full_profile(user_id)
    if "error" in profile: return {"error": "未註冊"}
    
    # 簡易統計 (可依需求擴充)
    return {
        "name": profile['name'],
        "group": profile['group'],
        "goal": profile['goal'],
        "actual": 0 # 需另外實作統計邏輯
    }

def append_fix_report(user_id, item, desc, photo_url):
    """報修 (移除 Telegram)"""
    try:
        client = get_client()
        try:
            sheet = client.open("公堂壇務運作管理系統").worksheet("故障報修紀錄")
        except:
            sheet = client.open("公堂壇務運作管理系統").add_worksheet(title="故障報修紀錄", rows=1000, cols=7)
            sheet.append_row(["ID", "時間", "申報人ID", "項目", "描述", "照片連結", "處理狀態"])

        user_profile = get_user_full_profile(user_id)
        user_name = user_profile.get("name", "未知名稱")
        
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        sheet.append_row([str(uuid.uuid4()), timestamp, user_id, item, desc, photo_url, "待處理"])
        return True, "申報成功"
    except Exception as e:
        return False, str(e)