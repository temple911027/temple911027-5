# wsgi.py
from main import init_full_application

# 呼叫 main.py 裡面的共用初始化函式
# 這會執行：
# 1. 載入 Settings (從環境變數)
# 2. 初始化 LINE Bot (解決機器人不回話的問題)
# 3. 更新 Rich Menu (圖文選單)
# 4. 回傳 app 給 Render 的 Gunicorn 使用

app, _ = init_full_application()

if __name__ == "__main__":
    app.run()