import os
from flask import Flask, request, abort, render_template, jsonify, make_response
import line_bot_logic
import sheets_handler
import drive_handler

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'static', 'uploads')
if not os.path.exists(UPLOAD_FOLDER): os.makedirs(UPLOAD_FOLDER)

def create_app():
    app = Flask(__name__)
    app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

    @app.route("/callback", methods=['POST'])
    def callback():
        signature = request.headers['X-Line-Signature']
        body = request.get_data(as_text=True)
        try:
            events = line_bot_logic.parser.parse(body, signature)
        except: abort(400)
        for event in events:
            line_bot_logic.handle_event(event)
        return 'OK'

    @app.route("/", strict_slashes=False)
    @app.route("/liff", strict_slashes=False)
    def liff_page():
        page = request.args.get('page', 'index')
        liff_id = line_bot_logic.get_liff_id()
        context = {"liff_id": liff_id}

        if page == 'checkin':
            context["categories"] = sheets_handler.get_all_categories()
            return render_template("checkin.html", **context)
        elif page == 'class_center':
            return render_template("class_center.html", **context)
        elif page == 'duty':
            return render_template("duty_roster.html", **context)
        elif page == 'settings':
            return render_template("settings.html", **context)
        elif page == 'fix':
            return render_template("fix_report.html", **context)
        elif page == 'class_info':
            return render_template("class_info.html", **context)
        else:
            return "頁面不存在", 404

    # --- API ---
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

    @app.route("/api/classes")
    def api_get_classes_new():
        return jsonify(sheets_handler.get_upcoming_classes())

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

    @app.route("/submit_fix", methods=['POST'])
    def submit_fix():
        d = request.json
        s, m = sheets_handler.append_fix_report(d['userId'], d['userName'], d['item'], d['desc'], d['photoUrl'])
        return jsonify({'success': s, 'message': m})

    @app.route("/upload", methods=['POST'])
    def upload():
        # 簡化版上傳
        if 'file' not in request.files: return jsonify({'error': '無檔案'}), 400
        file = request.files['file']
        # 這裡請確保 drive_handler 正常運作，或依照您原本的邏輯
        try:
            url = drive_handler.upload_file_to_drive(file.stream, file.filename, file.mimetype)
            return jsonify({'url': url})
        except Exception as e: return jsonify({'error': str(e)}), 500

    return app
