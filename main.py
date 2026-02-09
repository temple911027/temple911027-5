import os
import time
import uuid
from datetime import datetime
from urllib.parse import parse_qs, unquote
from flask import Flask, request, abort, render_template, jsonify, make_response
from werkzeug.utils import secure_filename
import line_bot_logic
import sheets_handler
import drive_handler

# 設定圖片上傳路徑
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'static', 'uploads')

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)


def create_app():
    app = Flask(__name__)
    app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

    @app.route("/callback", methods=['POST'])
    def callback():
        signature = request.headers['X-Line-Signature']
        body = request.get_data(as_text=True)
        try:
            events = line_bot_logic.parser.parse(body, signature)
        except Exception as e:
            print(f"解析 Webhook 失敗: {e}")
            abort(400)
        for event in events:
            line_bot_logic.handle_event(event)
        return 'OK'

    # --- LIFF 頁面路由 ---
    @app.route("/", strict_slashes=False)
    @app.route("/liff", strict_slashes=False)
    def liff_page():
        liff_id = line_bot_logic.get_liff_id()
        # 簡單防呆，避免 Render 環境變數沒讀到
        if not liff_id:
            # 嘗試重新載入設定
            import config
            settings = config.Settings()
            liff_id = settings.LIFF_ID

        if not liff_id or "YOUR" in liff_id:
            return "LIFF ID 尚未在 .env 檔案中設定！", 500

        page = request.args.get('page')
        user_id_param = request.args.get('user_id')
        liff_state = request.args.get('liff.state')

        if not page and liff_state:
            try:
                decoded_state = unquote(liff_state)
                if '?' in decoded_state:
                    decoded_state = decoded_state.split('?')[-1]
                params = parse_qs(decoded_state)
                if 'page' in params:
                    page = params['page'][0]
                if 'user_id' in params:
                    user_id_param = params['user_id'][0]
            except Exception as e:
                print(f"⚠️ 解析 liff.state 失敗: {e}")

        template_context = {"liff_id": liff_id}

        if page == 'class_info':
            template_name = "class_info.html"
            try:
                buttons = sheets_handler.get_button_config()
                classes = sheets_handler.get_upcoming_classes()
                template_context["ssr_buttons"] = buttons
                template_context["ssr_classes"] = classes
            except Exception as e:
                template_context["ssr_buttons"] = []
                template_context["ssr_classes"] = []

        # [新增] 結果查詢頁面
        elif page == 'query_result':
            template_name = "query_result.html"
            try:
                options = sheets_handler.get_class_result_links()
                template_context["options"] = options
            except Exception as e:
                template_context["options"] = []

        elif page == 'fix':
            template_name = "fix_report.html"
            try:
                config, locations = sheets_handler.get_system_settings()
                template_context["locations"] = [loc['name'] for loc in locations if loc.get('name')]
            except:
                template_context["locations"] = []

        elif page == 'query':
            template_name = "data_query.html"
            template_context["ssr_data"] = None
            template_context["ssr_percent"] = 0
            if user_id_param:
                try:
                    user_data = sheets_handler.get_dashboard_data(user_id_param)
                    if "error" not in user_data:
                        template_context["ssr_data"] = user_data
                        if user_data.get('target', 0) > 0:
                            pct = int((user_data['actual'] / user_data['target']) * 100)
                            if pct > 100: pct = 100
                        else:
                            pct = 0
                        template_context["ssr_percent"] = pct
                except Exception as e:
                    pass

        elif page == 'checkin':
            template_name = "checkin.html"
            # 傳入類別供選單使用
            try:
                template_context["categories"] = sheets_handler.get_all_categories()
            except:
                template_context["categories"] = []

        elif page == 'class_center':
            template_name = "class_center.html"

        elif page == 'duty':
            template_name = "duty_roster.html"

        elif page == 'settings':
            template_name = "settings.html"

        elif page == 'help':
            template_name = "system_info.html"
        else:
            template_name = "index.html"

        response = make_response(render_template(template_name, **template_context))
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
        return response

    # --- API ---
    @app.route("/api/classes")
    def api_get_classes():
        try:
            classes = sheets_handler.get_upcoming_classes()
            return jsonify(classes)
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    @app.route("/api/buttons")
    def api_get_buttons():
        try:
            buttons = sheets_handler.get_button_config()
            return jsonify(buttons)
        except Exception as e:
            return jsonify([]), 500

    @app.route("/api/query_data")
    def api_query_data():
        user_id = request.args.get('user_id')
        if not user_id: return jsonify({'error': 'no user_id'}), 400
        data = sheets_handler.get_dashboard_data(user_id)
        return jsonify(data)

    @app.route("/api/update_goal", methods=['POST'])
    def api_update_goal():
        data = request.json  # 修正：優先使用 json
        if not data:
            # 相容舊版 form post
            user_id = request.form.get('user_id')
            goal = request.form.get('goal')
        else:
            user_id = data.get('user_id')
            goal = data.get('goal')
            
        if not user_id or not goal: return jsonify({'success': False}), 400
        success = sheets_handler.update_user_goal(user_id, goal)
        return jsonify({'success': success})

    @app.route("/api/categories")
    def get_categories_api():
        try:
            categories = sheets_handler.get_all_categories()
            return jsonify(categories)
        except Exception as e:
            return jsonify([]), 500

    @app.route("/api/create_folder", methods=['POST'])
    def api_create_folder():
        item_name = request.json.get('item_name', '未命名設備')
        date_str = datetime.now().strftime("%Y%m%d")
        folder_name = f"{date_str}_{item_name}"

        try:
            config, _ = sheets_handler.get_system_settings()
            root_id = config.get('ROOT_FOLDER_ID')
            gas_url = config.get('WEB_APP_URL')
            gas_api_key = config.get('API_KEY')

            if not root_id:
                return jsonify({'success': False, 'error': '未設定 Root Folder ID'}), 500

            folder_id, folder_link = drive_handler.create_subfolder(folder_name, root_id, gas_url, gas_api_key)
            return jsonify({'success': True, 'folder_id': folder_id, 'folder_link': folder_link})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route("/api/submit_fix", methods=['POST'])
    def api_submit_fix():
        try:
            data = request.json
            user_id = data.get('userId')
            user_name = data.get('userName', '未知道親')
            hall = data.get('hall', '')
            item = data.get('item')
            desc = data.get('desc')
            display_url = data.get('displayUrl')
            record_url = data.get('recordUrl')

            if not display_url:
                display_url = data.get('primaryUrl')

            success, msg = sheets_handler.append_fix_report(
                user_id, user_name, hall, item, desc, display_url, record_url
            )

            if success:
                return jsonify({'success': True, 'message': msg})
            else:
                return jsonify({'success': False, 'message': msg}), 500
        except Exception as e:
            return jsonify({'success': False, 'message': str(e)}), 500

    @app.route("/api/check_permission", methods=['POST'])
    def api_check_permission():
        try:
            data = request.json
            user_id = data.get('user_id')
            if not user_id: return jsonify({'allowed': False, 'message': '未提供 User ID'}), 400
            is_allowed, admin_url = sheets_handler.check_user_permission(user_id)
            return jsonify({'allowed': is_allowed, 'url': admin_url})
        except Exception as e:
            return jsonify({'allowed': False, 'error': str(e)}), 500

    # --- 新增 API (支援新版功能) ---
    @app.route("/api/register_class", methods=['POST'])
    def api_register_class():
        d = request.json
        success, msg = sheets_handler.register_class_signup(
            d['user_id'], d['class_date'], d['class_name'], d['note']
        )
        return jsonify({'success': success, 'message': msg})

    @app.route("/api/cancel_registration", methods=['POST'])
    def api_cancel_reg():
        d = request.json
        success, msg = sheets_handler.cancel_class_signup(d['user_id'], d['class_name'])
        return jsonify({'success': success, 'message': msg})

    @app.route("/api/my_signups")
    def api_my_signups():
        return jsonify(sheets_handler.get_my_signups(request.args.get('user_id')))

    @app.route("/api/my_duty")
    def api_my_duty():
        uid = request.args.get('user_id')
        user = sheets_handler.get_user_full_profile(uid)
        if "error" in user: return jsonify({"tasks": []})
        duty = sheets_handler.get_group_duties(user.get('group'))
        return jsonify({"user_name": user['name'], "group": user['group'], "tasks": duty.get("tasks", [])})

    @app.route("/api/public_tasks")
    def api_public():
        return jsonify(sheets_handler.get_public_tasks())

    @app.route("/api/claim_public_task", methods=['POST'])
    def api_claim():
        d = request.json
        s, m = sheets_handler.claim_public_task(d['user_id'], d['task_id'], d['task_name'])
        return jsonify({'success': s, 'message': m})

    @app.route("/api/complete_task", methods=['POST'])
    def api_complete():
        d = request.json
        s, m = sheets_handler.append_checkin_data(d['user_id'], "自動", "公務", f"完成：{d['task']}")
        return jsonify({"success": s, "message": m})

    @app.route("/api/profile", methods=['GET', 'POST'])
    def api_profile():
        if request.method == 'GET':
            return jsonify(sheets_handler.get_user_full_profile(request.args.get('user_id')))
        else:
            d = request.json
            s, m = sheets_handler.update_user_profile(d['user_id'], d['phone'], d['meal'], d['goal'])
            return jsonify({'success': s, 'message': m})

    @app.route("/api/leader/add_task", methods=['POST'])
    def api_leader_add():
        d = request.json
        s, m = sheets_handler.add_task_by_leader(d['user_id'], d['task_name'])
        return jsonify({'success': s, 'message': m})

    @app.route("/upload", methods=['POST'])
    def upload_image():
        if 'file' not in request.files:
            return jsonify({'error': '沒有檔案'}), 400

        file = request.files['file']
        folder_id = request.form.get('folder_id')

        config, _ = sheets_handler.get_system_settings()
        gas_url = config.get('WEB_APP_URL')
        gas_api_key = config.get('API_KEY')

        if not folder_id:
            folder_id = config.get('ROOT_FOLDER_ID')

        if file.filename == '':
            return jsonify({'error': '未選擇檔案'}), 400

        if file:
            ext = os.path.splitext(file.filename)[1].lower()
            if not ext: ext = ".jpg"
            unique_filename = f"{int(time.time())}_{uuid.uuid4().hex[:8]}{ext}"

            try:
                image_url = drive_handler.upload_file_to_drive(
                    file.stream,
                    unique_filename,
                    file.mimetype,
                    parent_id=folder_id,
                    gas_url=gas_url,
                    api_key=gas_api_key
                )
                return jsonify({'url': image_url})

            except Exception as e:
                print(f"上傳 Google Drive 失敗: {e}")
                return jsonify({'error': f"上傳失敗: {str(e)}"}), 500

    @app.route("/health")
    def health_check():
        return "OK", 200

    return app
