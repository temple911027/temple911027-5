import os
import time
import uuid
from datetime import datetime
from flask import Flask, request, abort, render_template, jsonify, make_response
import line_bot_logic
import sheets_handler
import drive_handler
from config import Settings

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'static', 'uploads')

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

def create_app():
    app = Flask(__name__)
    app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
    
    settings = Settings()
    line_bot_logic.init_bot(settings)

    @app.route("/callback", methods=['POST'])
    def callback():
        signature = request.headers['X-Line-Signature']
        body = request.get_data(as_text=True)
        try:
            events = line_bot_logic.parser.parse(body, signature)
        except Exception as e:
            abort(400)
        for event in events:
            line_bot_logic.handle_event(event)
        return 'OK'

    # --- LIFF 頁面路由 ---
    @app.route("/", strict_slashes=False)
    @app.route("/liff", strict_slashes=False)
    def liff_page():
        page = request.args.get('page', 'index')
        liff_id = settings.LIFF_ID
        template_context = {"liff_id": liff_id}

        if page == 'checkin':
            template_name = "checkin.html"
            template_context["categories"] = sheets_handler.get_all_categories()

        elif page == 'class_center': # 新增：班程中心
            template_name = "class_center.html"

        elif page == 'duty': # 新增：輪值表
            template_name = "duty_roster.html"

        elif page == 'settings': # 新增：設定頁
            template_name = "settings.html"

        elif page == 'fix':
            template_name = "fix_report.html"
            
        elif page == 'query':
            template_name = "data_query.html"
            
        elif page == 'class_info':
            template_name = "class_info.html"
            template_context["classes"] = sheets_handler.get_upcoming_classes()
            
        else:
            template_name = "index.html"

        return make_response(render_template(template_name, **template_context))

    # --- API 區域 ---
    
    # 1. 班程相關
    @app.route("/api/classes")
    def api_get_classes_new():
        return jsonify(sheets_handler.get_upcoming_classes())

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

    # 2. 輪值相關
    @app.route("/api/my_duty")
    def api_my_duty():
        user_id = request.args.get('user_id')
        user_data = sheets_handler.get_dashboard_data(user_id)
        if "error" in user_data: return jsonify({"tasks": [], "group": "未註冊"})
        
        duty_data = sheets_handler.get_group_duties(user_data.get('group'))
        return jsonify({
            "user_name": user_data.get('name'),
            "group": user_data.get('group'),
            "tasks": duty_data.get("tasks", [])
        })

    @app.route("/api/complete_task", methods=['POST'])
    def api_complete_task():
        d = request.json
        note = f"輪值完成：[{d['area']}] {d['task']}"
        success, msg = sheets_handler.append_checkin_data(d['user_id'], "自動(輪值)", "公務", note)
        return jsonify({"success": success, "message": msg})

    # 3. 設定與個資
    @app.route("/api/profile", methods=['GET', 'POST'])
    def api_profile():
        if request.method == 'GET':
            return jsonify(sheets_handler.get_user_full_profile(request.args.get('user_id')))
        else:
            d = request.json
            success, msg = sheets_handler.update_user_profile(
                d['user_id'], d['phone'], d['meal'], d['goal']
            )
            return jsonify({'success': success, 'message': msg})

    @app.route("/api/leader/add_task", methods=['POST'])
    def api_leader_add_task():
        d = request.json
        success, msg = sheets_handler.add_task_by_leader(d['user_id'], d['task_name'])
        return jsonify({'success': success, 'message': msg})

    # 4. 圖片上傳 (保留)
    @app.route("/upload", methods=['POST'])
    def upload_image():
        if 'file' not in request.files: return jsonify({'error': '沒有檔案'}), 400
        file = request.files['file']
        folder_id = request.form.get('folder_id')
        
        config, _ = sheets_handler.get_system_settings()
        gas_url = config.get('WEB_APP_URL')
        
        # 移除 config 裡的 API KEY，因為 GAS 端通常設為開放或用 token
        if not folder_id: folder_id = config.get('ROOT_FOLDER_ID')

        if file:
            ext = os.path.splitext(file.filename)[1].lower()
            if not ext: ext = ".jpg"
            unique_filename = f"{int(time.time())}_{uuid.uuid4().hex[:8]}{ext}"
            
            try:
                # 簡化呼叫，移除 api_key 參數
                image_url = drive_handler.upload_file_to_drive(
                    file.stream, unique_filename, file.mimetype,
                    parent_id=folder_id, gas_url=gas_url
                )
                return jsonify({'url': image_url})
            except Exception as e:
                return jsonify({'error': str(e)}), 500
        return jsonify({'error': '上傳失敗'}), 400

    return app