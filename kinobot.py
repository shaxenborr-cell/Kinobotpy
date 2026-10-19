
import os
import time
import sqlite3
import telebot
from telebot import types

# ========== SOZLAMALAR ==========
TOKEN = os.getenv("BOT_TOKEN", "8814766554:AAFgfMqAv4i-GcsbehpA0yDTyyhpblc11yM")
ADMIN_ID = int(os.getenv("ADMIN_ID", "7465934934))
DB_NAME = "Fankinolar_bot"

if TOKEN == "TOKEN_BU_YERGA":
    raise SystemExit("BOT_TOKEN sozlanmagan!")

bot = telebot.TeleBot(TOKEN)
db = sqlite3.connect(DB_NAME, check_same_thread=False)
db.row_factory = sqlite3.Row
cur = db.cursor()

# ========== BAZA ==========
cur.executescript("""
CREATE TABLE IF NOT EXISTS users(
 id INTEGER PRIMARY KEY,
 ref_by INTEGER DEFAULT 0,
 joined INTEGER DEFAULT 0,
 premium_until INTEGER DEFAULT 0
);
CREATE TABLE IF NOT EXISTS movies(
 code TEXT PRIMARY KEY,
 title TEXT NOT NULL,
 description TEXT DEFAULT '',
 genre TEXT DEFAULT '',
 quality TEXT DEFAULT '',
 file_id TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS channels(
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 chat TEXT NOT NULL,
 invite TEXT DEFAULT ''
);
CREATE TABLE IF NOT EXISTS settings(
 key TEXT PRIMARY KEY,
 value TEXT
);
CREATE TABLE IF NOT EXISTS referrals(
 user_id INTEGER PRIMARY KEY,
 referrer INTEGER
);
""")
db.commit()


def setting(key, default="0"):
    row = cur.execute(
        "SELECT value FROM settings WHERE key=?", (key,)
    ).fetchone()
    return row["value"] if row else default


def set_setting(key, value):
    cur.execute(
        "INSERT OR REPLACE INTO settings(key,value) VALUES(?,?)",
        (key, str(value))
    )
    db.commit()


def is_admin(uid):
    return uid == ADMIN_ID


def get_user(uid):
    return cur.execute(
        "SELECT * FROM users WHERE id=?", (uid,)
    ).fetchone()


def main_menu(uid):
    kb = types.ReplyKeyboardMarkup(
        resize_keyboard=True, row_width=2
    )
    kb.add(
        types.KeyboardButton("🎬 Kino qidirish"),
        types.KeyboardButton("👤 Profil"),
        types.KeyboardButton("🎁 Referal"),
        types.KeyboardButton("⭐ Premium")
    )
    if is_admin(uid):
        kb.add(types.KeyboardButton("⚙️ Admin panel"))
    return kb


def admin_menu():
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        types.InlineKeyboardButton(
            "➕ Kino qo‘shish", callback_data="add_help"
        ),
        types.InlineKeyboardButton(
            "🗑 Kino o‘chirish", callback_data="del_help"
        ),
        types.InlineKeyboardButton(
            "📢 Kanallar", callback_data="channels"
        ),
        types.InlineKeyboardButton(
            "🔒 Obunani yoqish/o‘chirish",
            callback_data="toggle_sub"
        ),
        types.InlineKeyboardButton(
            "📊 Statistika", callback_data="stats"
        ),
        types.InlineKeyboardButton(
            "⭐ Premium berish", callback_data="premium_help"
        )
    )
    return kb


def subscription_keyboard():
    kb = types.InlineKeyboardMarkup(row_width=1)
    rows = cur.execute("SELECT * FROM channels").fetchall()

    for row in rows:
        chat = row["chat"]
        invite = row["invite"]

        if chat.startswith("@"):
            url = "https://t.me/" + chat[1:]
        elif invite:
            url = invite
        else:
            continue

        kb.add(types.InlineKeyboardButton(
            "📢 Kanalga obuna bo‘lish", url=url
        ))

    kb.add(types.InlineKeyboardButton(
        "✅ Obunani tekshirish", callback_data="check_sub"
    ))
    return kb


def subscribed(uid):
    if setting("force_sub") != "1":
        return True

    rows = cur.execute("SELECT chat FROM channels").fetchall()
    for row in rows:
        try:
            member = bot.get_chat_member(row["chat"], uid)
            if member.status not in ("creator", "administrator", "member"):
                return False
            if member.status == "restricted" and not member.is_member:
                return False
        except Exception:
            return False

    return True


def check_access(message):
    if subscribed(message.from_user.id):
        return True

    bot.send_message(
        message.chat.id,
        "🔒 Botdan foydalanish uchun quyidagi kanallarga obuna bo‘ling!",
        reply_markup=subscription_keyboard()
    )
    return False


def register_user(uid, referrer=0):
    if get_user(uid):
        return

    if referrer == uid or not get_user(referrer):
        referrer = 0

    cur.execute(
        "INSERT INTO users(id,ref_by,joined) VALUES(?,?,?)",
        (uid, referrer, int(time.time()))
    )

    if referrer:
        cur.execute(
            "INSERT OR IGNORE INTO referrals(user_id,referrer) VALUES(?,?)",
            (uid, referrer)
        )

    db.commit()

    if referrer:
        try:
            bot.send_message(
                referrer,
                "🎉 Yangi foydalanuvchi sizning referal havolangiz orqali kirdi!"
            )
        except Exception:
            pass


# ========== START ==========
@bot.message_handler(commands=["start"])
def start(message):
    uid = message.from_user.id
    args = message.text.split(maxsplit=1)
    ref = 0

    if len(args) > 1 and args[1].startswith("ref"):
        try:
            ref = int(args[1][3:])
        except ValueError:
            pass

    register_user(uid, ref)

    if not check_access(message):
        return

    bot.send_message(
        message.chat.id,
        "👑 AXIY KINO BOT PRO\n\n"
        "🎬 Sevimli kinolaringizni kod orqali toping!\n"
        "🍿 Tezkor qidiruv • Premium • Referal tizimi",
        reply_markup=main_menu(uid)
    )


# ========== OBUNANI TEKSHIRISH ==========
@bot.callback_query_handler(func=lambda c: c.data == "check_sub")
def check_sub_callback(call):
    if subscribed(call.from_user.id):
        bot.answer_callback_query(
            call.id, "✅ Obuna tasdiqlandi!"
        )
        bot.send_message(
            call.message.chat.id,
            "🎬 AXIY KINO BOT PRO ga xush kelibsiz!",
            reply_markup=main_menu(call.from_user.id)
        )
    else:
        bot.answer_callback_query(
            call.id, "❌ Hamma kanallarga obuna bo‘ling!",
            show_alert=True
        )


# ========== KINO QIDIRISH ==========
@bot.message_handler(func=lambda m: m.text == "🎬 Kino qidirish")
def search_movie(message):
    if not check_access(message):
        return

    msg = bot.send_message(
        message.chat.id,
        "🔎 Kino kodini yuboring:"
    )
    bot.register_next_step_handler(msg, find_movie)


def find_movie(message):
    if not check_access(message):
        return

    code = message.text.strip()
    movie = cur.execute(
        "SELECT * FROM movies WHERE code=?", (code,)
    ).fetchone()

    if not movie:
        bot.send_message(
            message.chat.id,
            "❌ Bunday koddagi kino topilmadi. Kodni tekshiring."
        )
        return

    caption = (
        f"🎬 {movie['title']}\n\n"
        f"📝 Tavsif: {movie['description'] or 'Kiritilmagan'}\n"
        f"🎭 Janr: {movie['genre'] or 'Kiritilmagan'}\n"
        f"📺 Sifat: {movie['quality'] or 'Kiritilmagan'}\n"
        f"🔢 Kod: {movie['code']}"
    )

    bot.send_video(
        message.chat.id,
        movie["file_id"],
        caption=caption
    )


# ========== KINO QO‘SHISH ==========
@bot.message_handler(commands=["addmovie"])
def add_movie_command(message):
    if not is_admin(message.from_user.id):
        return

    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        bot.reply_to(
            message,
            "Format: /addmovie KOD\n"
            "Keyin video yuboring.\n\n"
            "Video caption formati:\n"
            "Kino nomi\nTavsif\nJanr\nSifat"
        )
        return

    code = parts[1].strip()
    bot.send_message(
        message.chat.id,
        f"🎬 {code} kodi uchun video yuboring.\n\n"
        "Video izohiga 4 qatorda yozing:\n"
        "1. Kino nomi\n2. Tavsif\n3. Janr\n4. Sifat"
    )
    pending[message.from_user.id] = code


pending = {}


@bot.message_handler(content_types=["video"])
def receive_movie(message):
    uid = message.from_user.id

    if not is_admin(uid) or uid not in pending:
        return

    code = pending[uid]
    lines = (message.caption or "").splitlines()

    title = lines[0].strip() if len(lines) > 0 else ""
    description = lines[1].strip() if len(lines) > 1 else ""
    genre = lines[2].strip() if len(lines) > 2 else ""
    quality = lines[3].strip() if len(lines) > 3 else ""

    if not title:
        bot.reply_to(
            message,
            "❌ Video izohiga kino nomini ham yozing."
        )
        return

    cur.execute("""
        INSERT OR REPLACE INTO movies
        (code,title,description,genre,quality,file_id)
        VALUES(?,?,?,?,?,?)
    """, (
        code, title, description, genre, quality,
        message.video.file_id
    ))
    db.commit()
    del pending[uid]

    bot.reply_to(
        message,
        f"✅ Kino saqlandi!\n🎬 {title}\n🔢 Kod: {code}"
    )


@bot.message_handler(commands=["delmovie"])
def delete_movie(message):
    if not is_admin(message.from_user.id):
        return

    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        bot.reply_to(message, "Format: /delmovie KOD")
        return

    cur.execute("DELETE FROM movies WHERE code=?", (parts[1].strip(),))
    db.commit()
    bot.reply_to(message, "🗑 Kino o‘chirildi (agar kod mavjud bo‘lsa).")


# ========== REFERAL ==========
@bot.message_handler(func=lambda m: m.text == "🎁 Referal")
def referral(message):
    if not check_access(message):
        return

    uid = message.from_user.id
    count = cur.execute(
        "SELECT COUNT(*) AS n FROM referrals WHERE referrer=?",
        (uid,)
    ).fetchone()["n"]

    me = bot.get_me()
    link = f"https://t.me/{me.username}?start=ref{uid}"

    bot.send_message(
        message.chat.id,
        f"🎁 REFERAL TIZIMI\n\n"
        f"👥 Taklif qilganlaringiz: {count}\n\n"
        f"🔗 Sizning havolangiz:\n{link}\n\n"
        "Havolani do‘stlaringizga yuboring!"
    )


# ========== PROFIL ==========
@bot.message_handler(func=lambda m: m.text == "👤 Profil")
def profile(message):
    if not check_access(message):
        return

    uid = message.from_user.id
    user = get_user(uid)
    count = cur.execute(
        "SELECT COUNT(*) AS n FROM referrals WHERE referrer=?",
        (uid,)
    ).fetchone()["n"]

    premium = user["premium_until"] if user else 0
    premium_text = (
        time.strftime("%Y-%m-%d", time.localtime(premium))
        if premium > int(time.time()) else "Faol emas"
    )

    bot.send_message(
        message.chat.id,
        f"👤 PROFIL\n\n🆔 ID: {uid}\n"
        f"🎁 Referallar: {count}\n"
        f"⭐ Premium: {premium_text}"
    )


# ========== PREMIUM ==========
@bot.message_handler(func=lambda m: m.text == "⭐ Premium")
def premium_info(message):
    if not check_access(message):
        return

    bot.send_message(
        message.chat.id,
        "⭐ AXIY PREMIUM\n\n"
        "Premium muddati: 7 kun.\n"
        "Premium olish uchun administrator bilan bog‘laning."
    )


@bot.message_handler(commands=["premium"])
def give_premium(message):
    if not is_admin(message.from_user.id):
        return

    parts = message.text.split()
    if len(parts) < 2:
        bot.reply_to(message, "Format: /premium USER_ID [kun]")
        return

    try:
        uid = int(parts[1])
        days = int(parts[2]) if len(parts) > 2 else 7
        if days < 1 or days > 3650:
            raise ValueError
    except ValueError:
        bot.reply_to(message, "❌ ID yoki kun noto‘g‘ri.")
        return

    if not get_user(uid):
        register_user(uid)

    until = max(
        int(time.time()),
        get_user(uid)["premium_until"]
    ) + days * 86400

    cur.execute(
        "UPDATE users SET premium_until=? WHERE id=?",
        (until, uid)
    )
    db.commit()
    bot.reply_to(message, f"✅ {uid} foydalanuvchiga {days} kun Premium berildi.")

    try:
        bot.send_message(uid, f"⭐ Sizga {days} kun Premium berildi!")
    except Exception:
        pass


# ========== ADMIN PANELI ==========
@bot.message_handler(func=lambda m: m.text == "⚙️ Admin panel")
def admin_panel(message):
    if not is_admin(message.from_user.id):
        return

    bot.send_message(
        message.chat.id,
        "⚙️ AXIY KINO BOT PRO — ADMIN PANEL",
        reply_markup=admin_menu()
    )


@bot.callback_query_handler(func=lambda c: c.data in [
    "add_help", "del_help", "channels",
    "toggle_sub", "stats", "premium_help"
])
def admin_callbacks(call):
    if not is_admin(call.from_user.id):
        bot.answer_callback_query(call.id, "Ruxsat yo‘q!")
        return

    if call.data == "add_help":
        text = (
            "➕ Kino qo‘shish:\n"
            "/addmovie KOD\n"
            "So‘ng videoni 4 qatorli izoh bilan yuboring."
        )

    elif call.data == "del_help":
        text = "🗑 O‘chirish: /delmovie KOD"

    elif call.data == "channels":
        text = (
            "📢 KANALLARNI BOSHQARISH\n\n"
            "Kanal qo‘shish:\n"
            "/addchannel @username\n\n"
            "Yopiq kanal:\n"
            "/addchannel -1001234567890 https://t.me/+TAKLIF\n\n"
            "Kanalni o‘chirish:\n"
            "/delchannel ID\n\n"
            "Ro‘yxat: /channels"
        )

    elif call.data == "toggle_sub":
        new_value = "0" if setting("force_sub") == "1" else "1"
        set_setting("force_sub", new_value)
        text = "🔒 Majburiy obuna YOQILDI." if new_value == "1" else "🔓 Majburiy obuna O‘CHIRILDI."

    elif call.data == "stats":
        users = cur.execute("SELECT COUNT(*) AS n FROM users").fetchone()["n"]
        movies = cur.execute("SELECT COUNT(*) AS n FROM movies").fetchone()["n"]
        channels = cur.execute("SELECT COUNT(*) AS n FROM channels").fetchone()["n"]
        text = (
            f"📊 STATISTIKA\n\n"
            f"👥 Foydalanuvchilar: {users}\n"
            f"🎬 Kinolar: {movies}\n"
            f"📢 Kanallar: {channels}\n"
            f"🔒 Majburiy obuna: {'Yoqilgan' if setting('force_sub') == '1' else 'O‘chirilgan'}"
        )

    else:
        text = "⭐ Premium berish: /premium USER_ID [kun]"

    bot.answer_callback_query(call.id)
    bot.send_message(call.message.chat.id, text)


# ========== KANALLARNI BOSHQARISH ==========
@bot.message_handler(commands=["addchannel"])
def add_channel(message):
    if not is_admin(message.from_user.id):
        return

    parts = message.text.split(maxsplit=2)
    if len(parts) < 2:
        bot.reply_to(message, "Format: /addchannel @username")
        return

    chat = parts[1].strip()
    invite = parts[2].strip() if len(parts) > 2 else ""

    cur.execute(
        "INSERT INTO channels(chat,invite) VALUES(?,?)",
        (chat, invite)
    )
    db.commit()
    bot.reply_to(
        message,
        f"✅ Kanal qo‘shildi.\nID: {cur.lastrowid}\n"
        "Bot kanal a’zoligini tekshira olishi uchun "
        "uni kanalga administrator qilib qo‘ying."
    )


@bot.message_handler(commands=["channels"])
def list_channels(message):
    if not is_admin(message.from_user.id):
        return

    rows = cur.execute("SELECT * FROM channels").fetchall()
    if not rows:
        bot.reply_to(message, "Kanallar ro‘yxati bo‘sh.")
        return

    text = "📢 KANALLAR:\n\n"
    for row in rows:
        text += f"ID: {row['id']} | {row['chat']}\n"
    bot.reply_to(message, text)


@bot.message_handler(commands=["delchannel"])
def delete_channel(message):
    if not is_admin(message.from_user.id):
        return

    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        bot.reply_to(message, "Format: /delchannel ID")
        return

    try:
        channel_id = int(parts[1])
    except ValueError:
        bot.reply_to(message, "❌ Kanal ID raqamini kiriting.")
        return

    cur.execute("DELETE FROM channels WHERE id=?", (channel_id,))
    db.commit()
    bot.reply_to(message, "✅ Kanal o‘chirildi (agar mavjud bo‘lsa).")


@bot.message_handler(commands=["subon"])
def sub_on(message):
    if is_admin(message.from_user.id):
        set_setting("force_sub", "1")
        bot.reply_to(message, "🔒 Majburiy obuna yoqildi.")


@bot.message_handler(commands=["suboff"])
def sub_off(message):
    if is_admin(message.from_user.id):
        set_setting("force_sub", "0")
        bot.reply_to(message, "🔓 Majburiy obuna o‘chirildi.")


# ========== QO‘SHIMCHA BUYRUQLAR ==========
@bot.message_handler(commands=["id"])
def show_id(message):
    bot.reply_to(message, f"Telegram ID: {message.from_user.id}")


@bot.message_handler(commands=["cancel"])
def cancel(message):
    if is_admin(message.from_user.id):
        pending.pop(message.from_user.id, None)
        bot.reply_to(message, "❌ Amal bekor qilindi.")


@bot.message_handler(func=lambda m: m.text == "⚙️ Admin panel", content_types=["text"])
def admin_panel_fallback(message):
    if is_admin(message.from_user.id):
        bot.send_message(message.chat.id, "Admin panel:", reply_markup=admin_menu())


print("AXIY KINO BOT PRO ishga tushmoqda...")
bot.infinity_polling(skip_pending=True, timeout=30, long_polling_timeout=25)
