from flask import Flask, render_template
import threading
import requests
import time

app = Flask(__name__)

# ===== ضع رابط تطبيقك هنا =====
APP_URL = 'https://your-app.onrender.com/ping'

@app.route('/')
def webapp():
    return render_template('webapp.html')

@app.route('/ping')
def ping():
    return 'ok', 200

def keep_alive():
    """كل 10 دقائق يرسل طلب للسيرفر حتى لا ينام"""
    while True:
        time.sleep(600)  # 10 دقائق
        try:
            requests.get(APP_URL, timeout=10)
            print("✅ keep_alive ping sent")
        except Exception as e:
            print(f"⚠️ keep_alive error: {e}")

# تشغيل keep_alive في خيط منفصل
t = threading.Thread(target=keep_alive, daemon=True)
t.start()

if __name__ == '__main__':
    app.run()
