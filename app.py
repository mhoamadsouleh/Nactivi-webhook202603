import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, Update
from flask import Flask, request, jsonify, render_template, abort
import requests
import time
import threading
import json
import os
from datetime import datetime, timedelta
from functools import wraps

# ==================== Flask App ====================
app = Flask(__name__)

# ==================== كاش الـ DB في الذاكرة ====================
_db_cache = None
_db_lock = threading.Lock()

# ==================== إعدادات البوت ====================
BOT_TOKEN = os.environ.get('BOT_TOKEN', '8668060570:AAEeED_4VOiyX82dhmaq0CjeE6A-iSHC4hc')
WEBHOOK_URL = os.environ.get('WEBHOOK_URL', 'https://nactivi-webhook202603-3.onrender.com')  # مثال: https://your-app.onrender.com
ADMIN_SECRET = os.environ.get('ADMIN_SECRET', 'Nactividzd')  # كلمة سر لوحة التحكم

bot = telebot.TeleBot(BOT_TOKEN)

STICKER_ID = 'CAACAgIAAxkBAAIMcmjDndyMvCb2OBQhIGobGVZU4f6JAAK0IwACmEspSN65vs0qW-TZNgQ'
START_PHOTO = 'https://t.me/Nactivi_video/3'

CHANNEL_1 = '@Nactivi_2'
CHANNEL_2 = '@Nactivi_video'
CHANNEL_1_URL = 'https://t.me/Nactivi_2'
CHANNEL_2_URL = 'https://t.me/Nactivi_video'
VETREX_DEV = 'https://t.me/Moh_Ntx'
BOT_LINK = f'https://t.me/Nactivi_video_bot'

OWNER_ID = 6186106102

# ==================== قاعدة البيانات ====================
DB_FILE = 'nactivi_db.json'

def load_db():
    global _db_cache
    with _db_lock:
        if _db_cache is not None:
            return _db_cache
        if os.path.exists(DB_FILE):
            with open(DB_FILE, 'r', encoding='utf-8') as f:
                _db_cache = json.load(f)
        else:
            _db_cache = {
                'users': {},
                'promo_codes': {},
                'settings': {'points_per_video': 1, 'free_videos': 2},
                'broadcast_log': []
            }
        return _db_cache

def save_db(db):
    global _db_cache
    with _db_lock:
        _db_cache = db
        with open(DB_FILE, 'w', encoding='utf-8') as f:
            json.dump(db, f, ensure_ascii=False, indent=2)

def get_user(user_id):
    db = load_db()
    uid = str(user_id)
    if uid not in db['users']:
        db['users'][uid] = {
            'points': 0,
            'free_videos': db['settings']['free_videos'],
            'total_videos': 0,
            'referrals': 0,
            'referred_by': None,
            'state': None,
            'images': [],
            'joined_at': datetime.now().isoformat(),
            'last_active': datetime.now().isoformat(),
            'username': None,
            'first_name': None
        }
        save_db(db)
    return db['users'][uid]

def save_user(user_id, data):
    db = load_db()
    db['users'][str(user_id)] = data
    save_db(db)

def get_all_users():
    db = load_db()
    return list(db['users'].keys())

def get_settings():
    db = load_db()
    return db.get('settings', {'points_per_video': 1, 'free_videos': 2})

def save_settings(settings):
    db = load_db()
    db['settings'] = settings
    save_db(db)

def get_promo_codes():
    db = load_db()
    return db.get('promo_codes', {})

def save_promo_codes(codes):
    db = load_db()
    db['promo_codes'] = codes
    save_db(db)

# ==================== Auth للـ API ====================
def require_admin(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        secret = request.headers.get('X-Admin-Secret') or request.args.get('secret')
        if secret != ADMIN_SECRET:
            return jsonify({'error': 'Unauthorized'}), 401
        return f(*args, **kwargs)
    return decorated

# ==================== دوال مساعدة ====================
def check_subscription(user_id):
    try:
        m1 = bot.get_chat_member(CHANNEL_1, user_id)
        sub1 = m1.status in ['member', 'administrator', 'creator']
    except:
        sub1 = False
    try:
        m2 = bot.get_chat_member(CHANNEL_2, user_id)
        sub2 = m2.status in ['member', 'administrator', 'creator']
    except:
        sub2 = False
    return sub1, sub2

def can_use_bot(user_id):
    sub1, sub2 = check_subscription(user_id)
    missing = []
    if not sub1:
        missing.append(('قناة Nactivi_2', CHANNEL_1_URL))
    if not sub2:
        missing.append(('قناة Nactivi_video', CHANNEL_2_URL))
    return len(missing) == 0, missing

def get_subscription_keyboard(missing_channels):
    markup = InlineKeyboardMarkup()
    for name, url in missing_channels:
        markup.add(InlineKeyboardButton(f'📢 اشترك في {name}', url=url))
    markup.add(InlineKeyboardButton('✅ تحققت من الاشتراك', callback_data='check_sub'))
    return markup

def has_enough_credits(user_id):
    user = get_user(user_id)
    settings = get_settings()
    return user['free_videos'] > 0 or user['points'] >= settings['points_per_video']

def deduct_credit(user_id):
    user = get_user(user_id)
    settings = get_settings()
    if user['free_videos'] > 0:
        user['free_videos'] -= 1
    else:
        user['points'] -= settings['points_per_video']
    user['total_videos'] = user.get('total_videos', 0) + 1
    user['last_active'] = datetime.now().isoformat()
    save_user(user_id, user)

def no_credits_keyboard():
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton('🔗 احصل على نقاط بالدعوة', callback_data='get_invite'))
    markup.add(InlineKeyboardButton('🏷 إدخال كود نقاط', callback_data='enter_promo'))
    markup.add(InlineKeyboardButton('• رجوع •', callback_data='back'))
    return markup

def get_main_keyboard(user_id):
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton('• إنشاء صورة •', callback_data='create_image'))
    markup.add(InlineKeyboardButton('• تعديل صورة •', callback_data='edit_image'))
    markup.add(InlineKeyboardButton('• إنشاء فيديو •', callback_data='create_video'))
    markup.add(InlineKeyboardButton('• تحريك صورة •', callback_data='animate_image'))
    markup.add(InlineKeyboardButton('🏷 إدخال كود نقاط', callback_data='enter_promo'))
    markup.add(InlineKeyboardButton('🔗 دعوة أصدقاء', callback_data='get_invite'))
    markup.add(
        InlineKeyboardButton('• القناة •', url=CHANNEL_2_URL),
        InlineKeyboardButton('• المطور •', url=VETREX_DEV)
    )
    if user_id == OWNER_ID:
        markup.add(InlineKeyboardButton('⚙️ لوحة تحكم', callback_data='admin_panel'))
    return markup

def get_back_keyboard():
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton('• رجوع •', callback_data='back'))
    return markup

def get_admin_keyboard():
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton('🎁 إرسال نقاط لمستخدم', callback_data='admin_give_points'))
    markup.add(InlineKeyboardButton('📢 إعلان للمستخدمين', callback_data='admin_broadcast'))
    markup.add(InlineKeyboardButton('🏷 إنشاء كود نقاط', callback_data='admin_create_code'))
    markup.add(InlineKeyboardButton('⚙️ إعدادات البوت', callback_data='admin_settings'))
    markup.add(InlineKeyboardButton('📊 إحصائيات', callback_data='admin_stats'))
    markup.add(InlineKeyboardButton('• رجوع •', callback_data='back'))
    return markup

# ==================== حالات المستخدمين ====================
user_states = {}

def get_state(user_id):
    return user_states.get(user_id, {'state': None, 'images': [], 'data': {}})

def set_state(user_id, state, images=None, data=None):
    user_states[user_id] = {
        'state': state,
        'images': images or [],
        'data': data or {}
    }

def clear_state(user_id):
    user_states[user_id] = {'state': None, 'images': [], 'data': {}}

# ==================== معالجة المحتوى ====================
def process_image(chat_id, prompt, url, payload, user_id, deduct=False):
    wait = bot.send_sticker(chat_id, STICKER_ID)
    try:
        r = requests.post(url, json=payload, timeout=15).json()
        if r.get("status") == "pending":
            task = r["task_id"]
            while True:
                time.sleep(0.1)
                g = requests.get(f"https://vetrex.site/v1/images/results/{task}", timeout=15).json()
                if g.get("status") == "completed":
                    img = g["data"][0]["url"]
                    bot.send_photo(chat_id, img, caption=f"<b>{prompt}</b>", parse_mode="HTML", reply_markup=get_back_keyboard())
                    break
                if g.get("status") == "failed":
                    bot.send_message(chat_id, "• فشل إنشاء الصورة", reply_markup=get_back_keyboard())
                    break
        elif r.get("url"):
            bot.send_photo(chat_id, r["url"], caption=f"<b>{prompt}</b>", parse_mode="HTML", reply_markup=get_back_keyboard())
    except Exception as e:
        bot.send_message(chat_id, f"• خطأ: {str(e)}", reply_markup=get_back_keyboard())
    finally:
        try:
            bot.delete_message(chat_id, wait.message_id)
        except:
            pass

def process_video(chat_id, prompt, url, payload, user_id):
    deduct_credit(user_id)
    wait = bot.send_sticker(chat_id, STICKER_ID)
    try:
        r = requests.post(url, json=payload, timeout=20).json()
        if r.get("status") == "pending":
            task = r["task_id"]
            while True:
                time.sleep(0.1)
                g = requests.get(f"https://vetrex.site/v1/videos/results/{task}", timeout=20).json()
                if g.get("status") == "completed":
                    vid = g["data"][0]["url"]
                    user = get_user(user_id)
                    markup = InlineKeyboardMarkup()
                    markup.add(InlineKeyboardButton('• رجوع •', callback_data='back'))
                    bot.send_video(
                        chat_id, vid,
                        caption=f"<b>{prompt}</b>\n\n🎁 فيديوهات مجانية: {user['free_videos']}\n💰 نقاطك: {user['points']}",
                        parse_mode="HTML",
                        reply_markup=markup
                    )
                    break
                if g.get("status") == "failed":
                    bot.send_message(chat_id, "• فشل إنشاء الفيديو", reply_markup=get_back_keyboard())
                    break
        elif r.get("url"):
            bot.send_video(chat_id, r["url"], caption=f"<b>{prompt}</b>", parse_mode="HTML", reply_markup=get_back_keyboard())
    except Exception as e:
        bot.send_message(chat_id, f"• خطأ: {str(e)}", reply_markup=get_back_keyboard())
    finally:
        try:
            bot.delete_message(chat_id, wait.message_id)
        except:
            pass

# ==================== Handlers بوت ====================
def send_main_menu(chat_id, user_id, first_name, from_id):
    user = get_user(user_id)
    settings = get_settings()
    s = f"[{first_name}](tg://user?id={from_id})"
    text = f"""• مرحبا {s}
• Nactivi video 🎬
• إنشاء الصور والفيديوهات بالذكاء الاصطناعي

🎁 فيديوهات مجانية: `{user['free_videos']}`
💰 نقاطك: `{user['points']}`
📌 نقاط لكل فيديو: `{settings['points_per_video']}`"""
    bot.send_photo(chat_id, START_PHOTO, caption=text, parse_mode='Markdown', reply_markup=get_main_keyboard(user_id))

@bot.message_handler(commands=['start'])
def start_command(message):
    user_id = message.from_user.id
    first_name = message.from_user.first_name
    chat_id = message.chat.id

    args = message.text.split()
    if len(args) > 1:
        try:
            ref_id = int(args[1].replace('ref_', ''))
            if ref_id != user_id:
                user = get_user(user_id)
                if user.get('referred_by') is None:
                    user['referred_by'] = ref_id
                    save_user(user_id, user)
                    ref_user = get_user(ref_id)
                    ref_user['points'] = ref_user.get('points', 0) + 1
                    ref_user['referrals'] = ref_user.get('referrals', 0) + 1
                    save_user(ref_id, ref_user)
                    try:
                        bot.send_message(ref_id, f"🎉 انضم مستخدم جديد عبر رابط دعوتك!\n💰 حصلت على نقطة!")
                    except:
                        pass
        except:
            pass

    u = get_user(user_id)
    u['first_name'] = message.from_user.first_name
    u['username'] = message.from_user.username
    u['last_active'] = datetime.now().isoformat()
    save_user(user_id, u)

    ok, missing = can_use_bot(user_id)
    if not ok:
        bot.send_message(chat_id, "⚠️ يجب الاشتراك في القنوات التالية لاستخدام البوت:", reply_markup=get_subscription_keyboard(missing))
        return

    send_main_menu(chat_id, user_id, first_name, user_id)

@bot.message_handler(content_types=['text'])
def handle_text(message):
    chat_id = message.chat.id
    user_id = message.from_user.id
    text = message.text

    if text.startswith('/'):
        return

    state_data = get_state(user_id)
    state = state_data.get('state')

    if state is None:
        ok, missing = can_use_bot(user_id)
        if not ok:
            bot.send_message(chat_id, "⚠️ يجب الاشتراك في القنوات أولاً:", reply_markup=get_subscription_keyboard(missing))
            return
        bot.send_message(chat_id, "• استخدم الأزرار أدناه 👇", reply_markup=get_main_keyboard(user_id))
        return

    elif state == 'admin_give_points_id':
        try:
            target_id = int(text.strip())
            set_state(user_id, 'admin_give_points_amount', data={'target_id': target_id})
            bot.send_message(chat_id, f"✅ المستخدم: `{target_id}`\nأرسل عدد النقاط:", parse_mode='Markdown', reply_markup=get_back_keyboard())
        except:
            bot.send_message(chat_id, "❌ أرسل ID صحيح:", reply_markup=get_back_keyboard())

    elif state == 'admin_give_points_amount':
        try:
            amount = int(text.strip())
            target_id = state_data['data']['target_id']
            target_user = get_user(target_id)
            target_user['points'] = target_user.get('points', 0) + amount
            save_user(target_id, target_user)
            clear_state(user_id)
            bot.send_message(chat_id, f"✅ تم إرسال {amount} نقطة للمستخدم `{target_id}`", parse_mode='Markdown', reply_markup=get_admin_keyboard())
            try:
                bot.send_message(target_id, f"🎁 حصلت على {amount} نقطة من المشرف!\n💰 رصيدك الآن: {target_user['points']}")
            except:
                pass
        except:
            bot.send_message(chat_id, "❌ أرسل عدداً صحيحاً:", reply_markup=get_back_keyboard())

    elif state == 'admin_broadcast':
        clear_state(user_id)
        users = get_all_users()
        success = 0
        fail = 0
        msg = bot.send_message(chat_id, f"⏳ جاري الإرسال لـ {len(users)} مستخدم...")
        for uid in users:
            try:
                bot.send_message(int(uid), f"📢 إعلان:\n\n{text}")
                success += 1
            except:
                fail += 1
            time.sleep(0.1)
        bot.edit_message_text(f"✅ تم الإرسال!\n✔️ نجح: {success}\n❌ فشل: {fail}", chat_id, msg.message_id)
        bot.send_message(chat_id, "العودة للوحة التحكم:", reply_markup=get_admin_keyboard())

    elif state == 'admin_create_code_name':
        code_name = text.strip()
        set_state(user_id, 'admin_create_code_points', data={'code_name': code_name})
        bot.send_message(chat_id, f"🏷 الكود: `{code_name}`\nأرسل عدد النقاط:", parse_mode='Markdown', reply_markup=get_back_keyboard())

    elif state == 'admin_create_code_points':
        try:
            points = int(text.strip())
            data = state_data['data']
            data['points'] = points
            set_state(user_id, 'admin_create_code_uses', data=data)
            bot.send_message(chat_id, f"💰 النقاط: {points}\nأرسل عدد مرات الاستخدام:", reply_markup=get_back_keyboard())
        except:
            bot.send_message(chat_id, "❌ أرسل عدداً صحيحاً:", reply_markup=get_back_keyboard())

    elif state == 'admin_create_code_uses':
        try:
            uses = int(text.strip())
            data = state_data['data']
            codes = get_promo_codes()
            expiry = (datetime.now() + timedelta(minutes=5)).isoformat()
            codes[data['code_name']] = {
                'points': data['points'],
                'uses': uses,
                'used_by': [],
                'expiry': expiry
            }
            save_promo_codes(codes)
            clear_state(user_id)
            bot.send_message(
                chat_id,
                f"✅ تم إنشاء الكود!\n🏷 الكود: `{data['code_name']}`\n💰 النقاط: {data['points']}\n👥 الاستخدامات: {uses}\n⏳ الصلاحية: 5 دقائق",
                parse_mode='Markdown',
                reply_markup=get_admin_keyboard()
            )
        except:
            bot.send_message(chat_id, "❌ أرسل عدداً صحيحاً:", reply_markup=get_back_keyboard())

    elif state == 'admin_settings_free_videos':
        try:
            fv = int(text.strip())
            settings = get_settings()
            settings['free_videos'] = fv
            save_settings(settings)
            clear_state(user_id)
            bot.send_message(chat_id, f"✅ تم تغيير الفيديوهات المجانية إلى {fv}", reply_markup=get_admin_keyboard())
        except:
            bot.send_message(chat_id, "❌ أرسل عدداً صحيحاً:", reply_markup=get_back_keyboard())

    elif state == 'admin_settings_points_per_video':
        try:
            ppv = int(text.strip())
            settings = get_settings()
            settings['points_per_video'] = ppv
            save_settings(settings)
            clear_state(user_id)
            bot.send_message(chat_id, f"✅ تم تغيير نقاط الفيديو إلى {ppv}", reply_markup=get_admin_keyboard())
        except:
            bot.send_message(chat_id, "❌ أرسل عدداً صحيحاً:", reply_markup=get_back_keyboard())

    elif state == 'enter_promo':
        code = text.strip()
        codes = get_promo_codes()
        clear_state(user_id)

        if code not in codes:
            bot.send_message(chat_id, "❌ الكود غير موجود أو منتهي الصلاحية.", reply_markup=get_main_keyboard(user_id))
            return

        c = codes[code]
        try:
            expiry = datetime.fromisoformat(c['expiry'])
            if datetime.now() > expiry:
                del codes[code]
                save_promo_codes(codes)
                bot.send_message(chat_id, "❌ انتهت صلاحية الكود.", reply_markup=get_main_keyboard(user_id))
                return
        except:
            pass

        if str(user_id) in c.get('used_by', []):
            bot.send_message(chat_id, "❌ لقد استخدمت هذا الكود من قبل.", reply_markup=get_main_keyboard(user_id))
            return

        if c['uses'] <= 0:
            bot.send_message(chat_id, "❌ الكود استُنفد.", reply_markup=get_main_keyboard(user_id))
            return

        user = get_user(user_id)
        user['points'] = user.get('points', 0) + c['points']
        save_user(user_id, user)

        c['used_by'].append(str(user_id))
        c['uses'] -= 1
        if c['uses'] <= 0:
            del codes[code]
        else:
            codes[code] = c
        save_promo_codes(codes)

        bot.send_message(chat_id, f"✅ تم تفعيل الكود!\n💰 حصلت على {c['points']} نقطة\nرصيدك الآن: {user['points']}", reply_markup=get_main_keyboard(user_id))

    elif state == 'create_image':
        ok, missing = can_use_bot(user_id)
        if not ok:
            bot.send_message(chat_id, "⚠️ اشترك أولاً:", reply_markup=get_subscription_keyboard(missing))
            return
        clear_state(user_id)
        payload = {"prompt": message.text, "model": "nano-banana-2"}
        threading.Thread(target=process_image, args=(chat_id, message.text, "https://vetrex.site/v1/images/generations", payload, user_id, False)).start()

    elif state == 'edit_image':
        images = state_data.get('images', [])
        if len(images) == 0:
            bot.send_message(chat_id, "• أرسل صورة أولاً", reply_markup=get_back_keyboard())
            return
        ok, missing = can_use_bot(user_id)
        if not ok:
            bot.send_message(chat_id, "⚠️ اشترك أولاً:", reply_markup=get_subscription_keyboard(missing))
            return
        clear_state(user_id)
        payload = {"prompt": message.text, "model": "nano-banana-2", "images": images}
        threading.Thread(target=process_image, args=(chat_id, message.text, "https://vetrex.site/v1/images/edits", payload, user_id, False)).start()

    elif state == 'create_video':
        ok, missing = can_use_bot(user_id)
        if not ok:
            bot.send_message(chat_id, "⚠️ اشترك أولاً:", reply_markup=get_subscription_keyboard(missing))
            return
        if not has_enough_credits(user_id):
            settings = get_settings()
            bot.send_message(chat_id, f"⚠️ ليس لديك رصيد كافٍ!\nتحتاج {settings['points_per_video']} نقطة لإنشاء فيديو.", reply_markup=no_credits_keyboard())
            return
        clear_state(user_id)
        payload = {"prompt": message.text, "model": "sora-2-pro", "aspect_ratio": "16:9", "duration": 30}
        threading.Thread(target=process_video, args=(chat_id, message.text, "https://vetrex.site/v1/videos/generations", payload, user_id)).start()

    elif state == 'animate_image':
        images = state_data.get('images', [])
        if len(images) == 0:
            bot.send_message(chat_id, "• أرسل صورة أولاً", reply_markup=get_back_keyboard())
            return
        ok, missing = can_use_bot(user_id)
        if not ok:
            bot.send_message(chat_id, "⚠️ اشترك أولاً:", reply_markup=get_subscription_keyboard(missing))
            return
        if not has_enough_credits(user_id):
            settings = get_settings()
            bot.send_message(chat_id, f"⚠️ ليس لديك رصيد كافٍ!\nتحتاج {settings['points_per_video']} نقطة لتحريك الصورة.", reply_markup=no_credits_keyboard())
            return
        clear_state(user_id)
        payload = {"prompt": message.text, "model": "sora-2-pro", "aspect_ratio": "16:9", "images": images, "duration": 30}
        threading.Thread(target=process_video, args=(chat_id, message.text, "https://vetrex.site/v1/videos/edits", payload, user_id)).start()
    else:
        bot.send_message(chat_id, "• استخدم الأزرار أدناه 👇", reply_markup=get_main_keyboard(user_id))

@bot.message_handler(content_types=['photo'])
def handle_photo(message):
    chat_id = message.chat.id
    user_id = message.from_user.id
    state_data = get_state(user_id)
    state = state_data.get('state')

    if state in ['edit_image', 'animate_image']:
        images = state_data.get('images', [])
        if state == 'edit_image' and len(images) >= 9:
            return
        if state == 'animate_image' and len(images) >= 1:
            bot.reply_to(message, "• تم إرسال صورة مسبقاً، أرسل النص الآن", reply_markup=get_back_keyboard())
            return
        file_id = message.photo[-1].file_id
        file_info = bot.get_file(file_id)
        url = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file_info.file_path}"
        images.append(url)
        set_state(user_id, state, images=images)
        if len(images) == 1:
            bot.reply_to(message, "• الآن أرسل النص", reply_markup=get_back_keyboard())
    else:
        bot.send_message(chat_id, "• استخدم الأزرار أدناه 👇", reply_markup=get_main_keyboard(user_id))

@bot.callback_query_handler(func=lambda call: True)
def callback_query(call):
    chat_id = call.message.chat.id
    user_id = call.from_user.id
    first_name = call.from_user.first_name

    if call.data == 'check_sub':
        ok, missing = can_use_bot(user_id)
        if ok:
            bot.answer_callback_query(call.id, "✅ تم التحقق!")
            try:
                bot.delete_message(chat_id, call.message.message_id)
            except:
                pass
            send_main_menu(chat_id, user_id, first_name, user_id)
        else:
            bot.answer_callback_query(call.id, "❌ لم تشترك بعد!")
            bot.edit_message_reply_markup(chat_id, call.message.message_id, reply_markup=get_subscription_keyboard(missing))
        return

    if call.data not in ['check_sub']:
        ok, missing = can_use_bot(user_id)
        if not ok:
            bot.answer_callback_query(call.id, "❌ يجب الاشتراك أولاً!")
            bot.send_message(chat_id, "⚠️ يجب الاشتراك في القنوات أولاً:", reply_markup=get_subscription_keyboard(missing))
            return

    bot.answer_callback_query(call.id)

    if call.data == 'back':
        clear_state(user_id)
        user = get_user(user_id)
        settings = get_settings()
        s = f"[{first_name}](tg://user?id={user_id})"
        text = f"""• مرحبا {s}
• Nactivi video 🎬
• إنشاء الصور والفيديوهات بالذكاء الاصطناعي

🎁 فيديوهات مجانية: `{user['free_videos']}`
💰 نقاطك: `{user['points']}`
📌 نقاط لكل فيديو: `{settings['points_per_video']}`"""
        try:
            bot.edit_message_caption(caption=text, chat_id=chat_id, message_id=call.message.message_id, parse_mode='Markdown', reply_markup=get_main_keyboard(user_id))
        except:
            try:
                bot.delete_message(chat_id, call.message.message_id)
            except:
                pass
            send_main_menu(chat_id, user_id, first_name, user_id)

    elif call.data == 'create_image':
        set_state(user_id, 'create_image')
        try:
            bot.edit_message_caption(caption="• أرسل النص لإنشاء الصورة 🎨", chat_id=chat_id, message_id=call.message.message_id, reply_markup=get_back_keyboard())
        except:
            bot.send_message(chat_id, "• أرسل النص لإنشاء الصورة 🎨", reply_markup=get_back_keyboard())

    elif call.data == 'edit_image':
        set_state(user_id, 'edit_image')
        try:
            bot.edit_message_caption(caption="• أرسل حتى 9 صور للتعديل", chat_id=chat_id, message_id=call.message.message_id, reply_markup=get_back_keyboard())
        except:
            bot.send_message(chat_id, "• أرسل حتى 9 صور للتعديل", reply_markup=get_back_keyboard())

    elif call.data == 'create_video':
        if not has_enough_credits(user_id):
            settings = get_settings()
            bot.send_message(chat_id, f"⚠️ ليس لديك رصيد كافٍ!\nتحتاج {settings['points_per_video']} نقطة لإنشاء فيديو.", reply_markup=no_credits_keyboard())
            return
        set_state(user_id, 'create_video')
        try:
            bot.edit_message_caption(caption="• أرسل النص لإنشاء الفيديو 🎬", chat_id=chat_id, message_id=call.message.message_id, reply_markup=get_back_keyboard())
        except:
            bot.send_message(chat_id, "• أرسل النص لإنشاء الفيديو 🎬", reply_markup=get_back_keyboard())

    elif call.data == 'animate_image':
        if not has_enough_credits(user_id):
            settings = get_settings()
            bot.send_message(chat_id, f"⚠️ ليس لديك رصيد كافٍ!\nتحتاج {settings['points_per_video']} نقطة لتحريك الصورة.", reply_markup=no_credits_keyboard())
            return
        set_state(user_id, 'animate_image')
        try:
            bot.edit_message_caption(caption="• أرسل صورة واحدة لتحريكها 🖼️", chat_id=chat_id, message_id=call.message.message_id, reply_markup=get_back_keyboard())
        except:
            bot.send_message(chat_id, "• أرسل صورة واحدة لتحريكها 🖼️", reply_markup=get_back_keyboard())

    elif call.data == 'get_invite':
        user = get_user(user_id)
        invite_link = f"{BOT_LINK}?start=ref_{user_id}"
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton('• رجوع •', callback_data='back'))
        bot.send_message(
            chat_id,
            f"🔗 رابط دعوتك الخاص:\n`{invite_link}`\n\n💰 ستحصل على نقطة لكل صديق يدخل عبر رابطك!\n👥 عدد الدعوات: {user.get('referrals', 0)}",
            parse_mode='Markdown',
            reply_markup=markup
        )

    elif call.data == 'enter_promo':
        set_state(user_id, 'enter_promo')
        bot.send_message(chat_id, "🏷 أرسل كود النقاط:", reply_markup=get_back_keyboard())

    elif call.data == 'admin_panel':
        if user_id != OWNER_ID:
            return
        bot.send_message(chat_id, "⚙️ لوحة التحكم:", reply_markup=get_admin_keyboard())

    elif call.data == 'admin_give_points':
        if user_id != OWNER_ID:
            return
        set_state(user_id, 'admin_give_points_id')
        bot.send_message(chat_id, "🎁 أرسل ID المستخدم:", reply_markup=get_back_keyboard())

    elif call.data == 'admin_broadcast':
        if user_id != OWNER_ID:
            return
        set_state(user_id, 'admin_broadcast')
        bot.send_message(chat_id, "📢 أرسل رسالة الإعلان:", reply_markup=get_back_keyboard())

    elif call.data == 'admin_create_code':
        if user_id != OWNER_ID:
            return
        set_state(user_id, 'admin_create_code_name')
        bot.send_message(chat_id, "🏷 أرسل اسم الكود:", reply_markup=get_back_keyboard())

    elif call.data == 'admin_settings':
        if user_id != OWNER_ID:
            return
        settings = get_settings()
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton('🎁 تغيير الفيديوهات المجانية', callback_data='admin_set_free_videos'))
        markup.add(InlineKeyboardButton('💰 تغيير نقاط الفيديو', callback_data='admin_set_points_per_video'))
        markup.add(InlineKeyboardButton('• رجوع •', callback_data='back'))
        bot.send_message(chat_id, f"⚙️ الإعدادات:\n🎁 فيديوهات مجانية: {settings['free_videos']}\n💰 نقاط لكل فيديو: {settings['points_per_video']}", reply_markup=markup)

    elif call.data == 'admin_set_free_videos':
        if user_id != OWNER_ID:
            return
        set_state(user_id, 'admin_settings_free_videos')
        bot.send_message(chat_id, "🎁 أرسل عدد الفيديوهات المجانية:", reply_markup=get_back_keyboard())

    elif call.data == 'admin_set_points_per_video':
        if user_id != OWNER_ID:
            return
        set_state(user_id, 'admin_settings_points_per_video')
        bot.send_message(chat_id, "💰 أرسل عدد النقاط للفيديو:", reply_markup=get_back_keyboard())

    elif call.data == 'admin_stats':
        if user_id != OWNER_ID:
            return
        db = load_db()
        total_users = len(db['users'])
        total_videos = sum(u.get('total_videos', 0) for u in db['users'].values())
        active_codes = len(get_promo_codes())
        bot.send_message(
            chat_id,
            f"📊 إحصائيات البوت:\n👥 إجمالي المستخدمين: {total_users}\n🎬 إجمالي الفيديوهات: {total_videos}\n🏷 الأكواد النشطة: {active_codes}",
            reply_markup=get_admin_keyboard()
        )

# ==================== Flask Routes ====================

@app.route(f'/webhook/{BOT_TOKEN}', methods=['POST'])
def webhook():
    if request.headers.get('content-type') == 'application/json':
        json_string = request.get_data().decode('utf-8')
        update = Update.de_json(json_string)
        bot.process_new_updates([update])
        return jsonify({'ok': True})
    abort(403)

@app.route('/')
def dashboard():
    return render_template('index.html')

@app.route('/api/stats', methods=['GET'])
@require_admin
def api_stats():
    db = load_db()
    users = db['users']
    total_users = len(users)
    total_videos = sum(u.get('total_videos', 0) for u in users.values())
    total_points = sum(u.get('points', 0) for u in users.values())
    total_referrals = sum(u.get('referrals', 0) for u in users.values())
    active_codes = len(get_promo_codes())
    settings = get_settings()

    # أكثر المستخدمين نشاطاً
    top_users = sorted(
        [{'id': uid, **u} for uid, u in users.items()],
        key=lambda x: x.get('total_videos', 0),
        reverse=True
    )[:5]

    return jsonify({
        'total_users': total_users,
        'total_videos': total_videos,
        'total_points': total_points,
        'total_referrals': total_referrals,
        'active_codes': active_codes,
        'settings': settings,
        'top_users': top_users
    })

@app.route('/api/users', methods=['GET'])
@require_admin
def api_users():
    db = load_db()
    page = int(request.args.get('page', 1))
    per_page = int(request.args.get('per_page', 20))
    search = request.args.get('search', '').lower()

    users = [{'id': uid, **u} for uid, u in db['users'].items()]

    if search:
        users = [u for u in users if search in str(u.get('id', '')) or search in str(u.get('first_name', '')).lower() or search in str(u.get('username', '')).lower()]

    users.sort(key=lambda x: x.get('joined_at', ''), reverse=True)
    total = len(users)
    start = (page - 1) * per_page
    end = start + per_page

    return jsonify({
        'users': users[start:end],
        'total': total,
        'page': page,
        'pages': (total + per_page - 1) // per_page
    })

@app.route('/api/users/<user_id>/points', methods=['POST'])
@require_admin
def api_give_points(user_id):
    data = request.json
    amount = data.get('amount', 0)
    if not amount:
        return jsonify({'error': 'amount required'}), 400

    user = get_user(user_id)
    user['points'] = user.get('points', 0) + amount
    save_user(user_id, user)

    try:
        bot.send_message(int(user_id), f"🎁 حصلت على {amount} نقطة من المشرف!\n💰 رصيدك الآن: {user['points']}")
    except:
        pass

    return jsonify({'ok': True, 'new_balance': user['points']})

@app.route('/api/broadcast', methods=['POST'])
@require_admin
def api_broadcast():
    data = request.json
    message_text = data.get('message', '')
    if not message_text:
        return jsonify({'error': 'message required'}), 400

    users = get_all_users()

    def do_broadcast():
        success = 0
        fail = 0
        for uid in users:
            try:
                bot.send_message(int(uid), f"📢 إعلان:\n\n{message_text}")
                success += 1
            except:
                fail += 1
            time.sleep(0.05)
        # Log broadcast
        db = load_db()
        if 'broadcast_log' not in db:
            db['broadcast_log'] = []
        db['broadcast_log'].append({
            'message': message_text,
            'sent_at': datetime.now().isoformat(),
            'success': success,
            'fail': fail
        })
        save_db(db)

    threading.Thread(target=do_broadcast).start()
    return jsonify({'ok': True, 'total': len(users)})

@app.route('/api/codes', methods=['GET'])
@require_admin
def api_get_codes():
    codes = get_promo_codes()
    result = []
    for code, data in codes.items():
        result.append({
            'code': code,
            'points': data['points'],
            'uses': data['uses'],
            'used_count': len(data.get('used_by', [])),
            'expiry': data.get('expiry'),
            'expired': datetime.now() > datetime.fromisoformat(data['expiry']) if data.get('expiry') else False
        })
    return jsonify(result)

@app.route('/api/codes', methods=['POST'])
@require_admin
def api_create_code():
    data = request.json
    code = data.get('code', '').strip()
    points = data.get('points', 0)
    uses = data.get('uses', 1)
    expiry_minutes = data.get('expiry_minutes', 5)

    if not code or not points:
        return jsonify({'error': 'code and points required'}), 400

    codes = get_promo_codes()
    expiry = (datetime.now() + timedelta(minutes=expiry_minutes)).isoformat()
    codes[code] = {
        'points': points,
        'uses': uses,
        'used_by': [],
        'expiry': expiry
    }
    save_promo_codes(codes)
    return jsonify({'ok': True})

@app.route('/api/codes/<code>', methods=['DELETE'])
@require_admin
def api_delete_code(code):
    codes = get_promo_codes()
    if code in codes:
        del codes[code]
        save_promo_codes(codes)
    return jsonify({'ok': True})

@app.route('/api/settings', methods=['GET'])
@require_admin
def api_get_settings():
    return jsonify(get_settings())

@app.route('/api/settings', methods=['POST'])
@require_admin
def api_update_settings():
    data = request.json
    settings = get_settings()
    if 'free_videos' in data:
        settings['free_videos'] = int(data['free_videos'])
    if 'points_per_video' in data:
        settings['points_per_video'] = int(data['points_per_video'])
    save_settings(settings)
    return jsonify({'ok': True, 'settings': settings})

@app.route('/api/setup-webhook', methods=['POST'])
@require_admin
def setup_webhook():
    webhook_url = request.json.get('url', WEBHOOK_URL)
    if not webhook_url:
        return jsonify({'error': 'WEBHOOK_URL not set'}), 400
    result = bot.set_webhook(url=f"{webhook_url}/webhook/{BOT_TOKEN}")
    return jsonify({'ok': result})

@app.route('/health')
def health():
    return jsonify({'status': 'ok', 'bot': 'Nactivi Video Bot'})

# ==================== تشغيل ====================
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    # ضبط الـ webhook عند التشغيل
    if WEBHOOK_URL:
        try:
            bot.remove_webhook()
            time.sleep(0.5)
            bot.set_webhook(url=f"{WEBHOOK_URL}/webhook/{BOT_TOKEN}")
            print(f"✅ Webhook set: {WEBHOOK_URL}/webhook/{BOT_TOKEN}")
        except Exception as e:
            print(f"❌ Webhook error: {e}")
    
    print(f"✅ Nactivi Dashboard running on port {port}")
    app.run(host='0.0.0.0', port=port, debug=False)
