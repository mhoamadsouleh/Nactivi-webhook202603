# 🎬 Nactivi Video Bot — دليل الرفع على Render

## الملفات المطلوبة
```
nactivi_bot/
├── app.py              ← البوت + Flask + لوحة التحكم
├── requirements.txt    ← المكتبات
├── render.yaml         ← إعدادات Render
└── templates/
    └── index.html      ← لوحة التحكم الويب
```

---

## 🚀 خطوات الرفع على Render

### 1. رفع الملفات على GitHub
```bash
git init
git add .
git commit -m "Nactivi Bot"
git remote add origin https://github.com/username/nactivi-bot.git
git push -u origin main
```

### 2. إنشاء Web Service على Render
1. روح على [render.com](https://render.com) وسجل دخول
2. اضغط **New → Web Service**
3. ربط الـ GitHub repo
4. اختر:
   - **Environment**: Python
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `gunicorn app:app --bind 0.0.0.0:$PORT --workers 2 --timeout 120`

### 3. إضافة متغيرات البيئة
في صفحة الـ Service على Render → **Environment**:

| المفتاح | القيمة |
|---------|--------|
| `BOT_TOKEN` | توكن البوت |
| `WEBHOOK_URL` | رابط التطبيق (بعد الرفع) |
| `ADMIN_SECRET` | كلمة سر لوحة التحكم |

### 4. إضافة Disk (لحفظ قاعدة البيانات)
- **Render → Settings → Disks**
- اضغط **Add Disk**
- Mount Path: `/opt/render/project/src`
- Size: **1 GB**

### 5. ضبط الـ Webhook
بعد رفع التطبيق:
1. افتح لوحة التحكم: `https://your-app.onrender.com`
2. أدخل كلمة السر (ADMIN_SECRET)
3. روح لصفحة **Webhook**
4. أدخل رابط تطبيقك واضغط "ضبط الـ Webhook"

---

## 🔒 لوحة التحكم الويب
- **الرابط**: `https://your-app.onrender.com`
- **كلمة السر**: القيمة في `ADMIN_SECRET`

### الميزات:
- 📊 إحصائيات لحظية
- ⚡ إجراءات سريعة
- 👥 إدارة المستخدمين
- 🏷 إنشاء/حذف أكواد النقاط
- 📢 إرسال إعلانات
- ⚙️ ضبط إعدادات البوت
- 🔗 ضبط الـ Webhook

---

## 📌 ملاحظات مهمة
- غيّر `ADMIN_SECRET` لكلمة سر قوية
- الـ Free Plan على Render ينام بعد 15 دقيقة من عدم النشاط
- استخدم UptimeRobot لإبقاء البوت يقظاً: أضف `/health` كـ monitor
