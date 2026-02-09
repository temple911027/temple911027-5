import os
import json
import requests
import base64
import io
from PIL import Image  # 需要安裝 Pillow 套件 (pip install Pillow)
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
from googleapiclient.errors import HttpError
from oauth2client.service_account import ServiceAccountCredentials

# ==========================================
#  【資安優化】
#   GAS_API_KEY 已移除，改由函式參數動態傳入
# ==========================================

# 設定權限範圍
SCOPES = ['https://www.googleapis.com/auth/drive']


def get_drive_service():
    """建立 Google Drive 服務連線 (使用 Service Account)"""
    creds = ServiceAccountCredentials.from_json_keyfile_name('service_account.json', SCOPES)
    return build('drive', 'v3', credentials=creds)


def compress_image(file_stream, max_size=(1024, 1024), quality=80):
    """
    圖片壓縮功能：
    將手機拍攝的大尺寸照片縮小至 1024px 寬度，並將品質降至 80%。
    這能顯著提高 GAS 轉傳的成功率。
    """
    try:
        # 讀取圖片
        image = Image.open(file_stream)

        # 如果不是 RGB (例如 PNG 透明圖)，轉為 RGB 以存為 JPEG
        if image.mode in ("RGBA", "P"):
            image = image.convert("RGB")

        # 計算縮放比例 (保持長寬比)
        image.thumbnail(max_size, Image.LANCZOS)

        # 存入記憶體
        output_stream = io.BytesIO()
        image.save(output_stream, format='JPEG', quality=quality)
        output_stream.seek(0)

        print(f"📉 圖片壓縮完成 (原始格式: {image.format})")
        return output_stream, 'image/jpeg'
    except Exception as e:
        print(f"⚠️ 圖片壓縮失敗 (可能是非圖片檔)，將使用原檔上傳: {e}")
        file_stream.seek(0)
        return file_stream, None


def create_subfolder(folder_name, parent_id, gas_url=None, api_key=None):
    """
    建立子資料夾
    新增參數: api_key (從 Sheets 讀取的金鑰，雖然目前此函式未用到，但預留介面)
    """
    if not parent_id:
        raise ValueError("Root Folder ID 未設定，請至後台「系統參數設定」填寫。")

    service = get_drive_service()

    file_metadata = {
        'name': folder_name,
        'mimeType': 'application/vnd.google-apps.folder',
        'parents': [parent_id]
    }

    try:
        # 1. 嘗試建立資料夾
        file = service.files().create(
            body=file_metadata,
            fields='id, webViewLink',
            supportsAllDrives=True
        ).execute()

        folder_id = file.get('id')
        print(f"✅ 已建立子資料夾: {folder_name}, ID: {folder_id}")

        # 2. 嘗試設定權限 (失敗不中斷)
        try:
            permission = {'type': 'anyone', 'role': 'reader'}
            service.permissions().create(
                fileId=folder_id,
                body=permission,
                supportsAllDrives=True
            ).execute()
        except Exception as perm_err:
            print(f"⚠️ 無法設定資料夾公開權限 (可能權限不足，但不影響建立): {perm_err}")

        return folder_id, file.get('webViewLink')

    except Exception as e:
        print(f"❌ 建立資料夾失敗: {e}")
        raise e


def upload_file_to_drive(file_stream, filename, mime_type, parent_id, gas_url=None, api_key=None):
    """
    上傳檔案到 Google Drive (智慧切換模式)
    新增參數: api_key (從 Sheets 讀取的金鑰)
    """
    if not parent_id:
        raise ValueError("未指定上傳目標資料夾 ID")

    # [步驟 1] 自動壓縮圖片
    if mime_type.startswith('image/'):
        print(f"🔄 正在優化圖片大小: {filename}...")
        file_stream, new_mime = compress_image(file_stream)
        if new_mime:
            mime_type = new_mime
            if not filename.lower().endswith('.jpg'):
                filename = filename.rsplit('.', 1)[0] + '.jpg'

    service = get_drive_service()

    file_metadata = {
        'name': filename,
        'parents': [parent_id]
    }

    # 讀取內容至記憶體
    file_content = file_stream.read()

    from io import BytesIO
    media_stream = BytesIO(file_content)
    media = MediaIoBaseUpload(media_stream, mimetype=mime_type, resumable=True)

    try:
        print(f"🚀 嘗試使用 Service Account 上傳: {filename}")

        # [步驟 2] 嘗試直接上傳
        file = service.files().create(
            body=file_metadata,
            media_body=media,
            fields='id',
            supportsAllDrives=True
        ).execute()

        file_id = file.get('id')
        print(f"✅ Service Account 上傳成功 (Parent: {parent_id}), ID: {file_id}")

        try:
            permission = {'type': 'anyone', 'role': 'reader'}
            service.permissions().create(
                fileId=file_id,
                body=permission,
                supportsAllDrives=True
            ).execute()
        except Exception as perm_e:
            print(f"⚠️ 無法設定檔案公開權限 (可忽略): {perm_e}")

        return f"https://drive.google.com/uc?export=view&id={file_id}"

    except HttpError as e:
        error_reason = ""
        try:
            error_content = json.loads(e.content.decode('utf-8'))
            error_reason = error_content.get('error', {}).get('errors', [{}])[0].get('reason', '')
        except:
            pass

        print(f"⚠️ Service Account 上傳失敗 (Reason: {error_reason})")

        # [步驟 3] 判斷是否為配額問題 -> 切換 GAS
        if error_reason == 'storageQuotaExceeded' and gas_url:
            print("🔄 偵測到配額不足，正在切換至 GAS 代理上傳...")

            # [檢查] 若無 API Key 則無法切換
            if not api_key:
                print("❌ 切換失敗：未設定 GAS_API_KEY (請檢查 Google Sheets 系統參數)")
                raise e

            return _upload_via_gas(file_content, filename, mime_type, parent_id, gas_url, api_key)
        else:
            print(f"❌ 上傳發生無法處理的錯誤: {e}")
            raise e

    except Exception as e:
        print(f"❌ 發生未預期錯誤: {e}")
        raise e


def _upload_via_gas(file_content_bytes, filename, mime_type, parent_id, gas_url, api_key):
    """
    內部函式：透過 GAS 上傳
    包含 API_KEY 安全驗證機制 (動態傳入)
    """
    if not gas_url:
        raise ValueError("切換失敗：未設定 GAS URL (WEB_APP_URL)")

    file_b64 = base64.b64encode(file_content_bytes).decode('utf-8')

    payload = {
        "action": "upload_file",
        "folder_id": parent_id,
        "filename": filename,
        "mimetype": mime_type,
        "filedata": file_b64,
        "api_key": api_key  # 使用傳入的參數
    }

    try:
        print(f"📡 呼叫 GAS 代理上傳: {gas_url}")
        # 設定 timeout，避免 GAS 冷啟動過久卡住
        response = requests.post(gas_url, json=payload, allow_redirects=True, timeout=45)

        # 錯誤診斷
        if response.status_code != 200:
            print(f"GAS HTTP Error: {response.status_code}")
            print(f"Response Text: {response.text[:200]}")
            if "google.com" in response.text:
                raise Exception(f"GAS 部署權限錯誤 (HTTP {response.status_code})：請確認部署為「所有人 (Anyone)」")
            raise Exception(f"GAS 伺服器錯誤 (HTTP {response.status_code})")

        try:
            resp_data = response.json()
        except ValueError:
            print(f"❌ GAS 回傳內容非 JSON: {response.text}")
            raise Exception(f"GAS 回應解析失敗，非 JSON 格式。")

        # 寬鬆判斷成功狀態
        is_success = (
                resp_data.get("status") == "success" or
                resp_data.get("success") is True or
                resp_data.get("file_url") is not None
        )

        if is_success:
            print(f"✅ GAS 上傳檔案成功: {filename}")
            # 優先回傳 file_url (直連)，若無則回傳 file_id 組裝
            url = resp_data.get("file_url") or resp_data.get("url")
            if url:
                return url
            elif resp_data.get("file_id"):
                return f"https://drive.google.com/uc?export=view&id={resp_data.get('file_id')}"
            else:
                raise Exception("GAS 上傳成功但未回傳連結 (No file_url)")
        else:
            msg = resp_data.get('message') or resp_data.get('error') or '未知錯誤'
            raise Exception(f"GAS 回傳錯誤: {msg}")

    except Exception as e:
        print(f"❌ GAS 上傳失敗: {e}")
        raise e