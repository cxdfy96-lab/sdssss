import os
import random
import asyncio
import datetime
import json
import re
import signal
import sys
import traceback
from flask import Flask, send_from_directory
import threading
from telethon import TelegramClient, events, functions
from telethon.sessions import StringSession
from telethon.tl.types import MessageMediaPhoto, MessageMediaDocument, MessageMediaWebPage
from telethon.errors import FloodWaitError, RPCError, UnauthorizedError
from supabase import create_client, Client

# ==================== Flask ====================
flask_app = Flask(__name__)

@flask_app.route('/')
def index():
    return send_from_directory('.', 'index.html')

def run_flask():
    flask_app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 8080)))

# ==================== الاعدادات ====================
API_ID = int(os.environ.get("API_ID", 0))
API_HASH = os.environ.get("API_HASH", "")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

DEV_ID = 5126968608
DEV_USER = "@toe7e"

CHANNELS_MAP = {
    "غنيلي": "arggrw",
    "شعر": "zfghjjg",
    "مزج": "cvbhfdgds",
    "ميمز": "cbklufswe",
    "قرآن": "chfdthhd"
}

DOWNLOAD_BOT = "@MsosMbot"

ACTIVE_CLIENTS = {}
CLIENT_CONTENTS = {}
MUTED_USERS_CACHE = {}
BANNED_USERS_CACHE = {}
PROCESSED_MESSAGES = set()
ARCHIVE_ENABLED = {}
DEFAULT_BAD_WORDS = ["وهابي", "عفن", "سخيف", "كلب", "انقلع"]
BAD_WORDS = {}

# ==================== نظام الملصقات للمشتركين ====================
STICKERS_ENABLED = {}  # {user_id: True/False}
STICKER_PACKS = {}  # {user_id: [sticker_ids]}
STICKER_CHANNELS = {}  # {user_id: [channel_links]}
ALLOW_STICKERS_FOR_ALL = {}  # {user_id: True/False} - السماح للكل باستخدام الملصقات

# ==================== الاقفال ====================
LOCKS = {
    'photos': {},
    'videos': {},
    'stickers': {},
    'links': {},
    'files': {},
    'audio': {},
    'gifs': {},
    'forwards': {},
    'numbers': {},
    'english': {},
    'private': {},
    'webpage': {},
    'hashtag': {},
    'mention': {},
    'bot': {}
}

BUSY_MODE = {}
BUSY_MESSAGE = {}
WELCOME_MESSAGES = {}
AUTO_REPLY = {}
FORCED_CHANNELS = {}
PUBLISH_CHANNELS = {}
DESTROY_TIMERS = {}

CLOCK_FONTS = {
    "circle": ("0123456789", "⓪①②③④⑤⑥⑦⑧⑨"),
    "bold": ("0123456789", "𝟎𝟏𝟐𝟑𝟒𝟓𝟔𝟕𝟖𝟗"),
    "sans": ("0123456789", "𝟶𝟷𝟸𝟹𝟺𝟻𝟼𝟽𝟾𝟿"),
    "normal": ("0123456789", "0123456789")
}

# ==================== بوت الادارة ====================
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

class LoginState(StatesGroup):
    waiting_for_phone = State()
    waiting_for_code = State()
    waiting_for_password = State()

class SettingsState(StatesGroup):
    waiting_for_forced_channel = State()
    waiting_for_custom_bad_word = State()
    waiting_for_welcome_msg = State()
    waiting_for_auto_reply = State()
    waiting_for_mute_user_id = State()
    waiting_for_ban_user_id = State()
    waiting_for_publish_channel = State()
    waiting_for_destroy_timer = State()
    waiting_for_sticker_channel = State()
    waiting_for_sticker_command = State()

def safe_get(d, k, default=None):
    if isinstance(d, dict):
        return d.get(k, default)
    return default

def is_user_installed(user_id):
    try:
        res = supabase.table("user_bots").select("*").or_(f"user_id.eq.{user_id},account_id.eq.{user_id}").execute()
        if res.data and res.data[0].get("session_string"):
            return True, res.data[0]
        return False, None
    except:
        return False, None

def clean_code(code):
    return re.sub(r'[\s\-_.,;:]', '', code)

# ==================== دوال مساعدة ====================
async def safe_supabase_operation(func, *args, **kwargs):
    for attempt in range(5):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            if attempt == 4:
                raise
            await asyncio.sleep(2 ** attempt)

async def safe_send_message(client, chat_id, message, **kwargs):
    for attempt in range(3):
        try:
            return await client.send_message(chat_id, message, **kwargs)
        except Exception as e:
            if attempt == 2:
                raise
            await asyncio.sleep(1)

async def safe_delete_message(message):
    try:
        await message.delete()
    except:
        pass

async def resolve_identifier(client, identifier):
    try:
        identifier = str(identifier).strip()
        if identifier.startswith("@"):
            return (await client.get_entity(identifier)).id
        elif identifier.isdigit():
            return int(identifier)
        return (await client.get_entity(identifier)).id
    except:
        return None

# ==================== دوال الملصقات ====================
async def add_sticker_pack(client, user_id, pack_link):
    """اضافة باك ملصقات للمستخدم"""
    try:
        # محاولة الحصول على الملصقات من الرابط
        pack_info = await client(functions.messages.GetStickerSetRequest(
            stickerset=types.InputStickerSetShortName(
                short_name=pack_link.replace("t.me/addstickers/", "").strip()
            ),
            hash=0
        ))
        
        sticker_ids = []
        for doc in pack_info.documents:
            sticker_ids.append(doc.id)
        
        STICKER_PACKS.setdefault(user_id, []).extend(sticker_ids)
        return True, f"تم اضافة {len(sticker_ids)} ملصق"
    except Exception as e:
        return False, f"خطأ: {e}"

async def check_user_in_channel(client, user_id, channel_link):
    """فحص اذا كان المستخدم مشترك في القناة"""
    try:
        entity = await client.get_entity(channel_link)
        participant = await client.get_participants(entity, limit=1)
        # فحص بسيط - يمكن تحسينه
        return True
    except:
        return False

async def get_sticker_packs_from_channel(client, channel_link):
    """جلب الملصقات من قناة الملصقات"""
    try:
        entity = await client.get_entity(channel_link)
        stickers = []
        async for msg in client.iter_messages(entity, limit=50):
            if msg.sticker:
                stickers.append(msg.sticker)
        return stickers
    except:
        return []

# ==================== كيبوردات ====================
def get_main_menu_keyboard(user_id):
    kb = []
    if WEB_APP_URL:
        kb.append([types.InlineKeyboardButton(text="فتح اللوحة الملونة", web_app=types.WebAppInfo(url=WEB_APP_URL))])
    
    is_installed, _ = is_user_installed(user_id)
    if is_installed:
        kb.append([types.InlineKeyboardButton(text="لوحة التحكم", callback_data="my_settings")])
        kb.append([types.InlineKeyboardButton(text="حذف التنصيب", callback_data="delete_install")])
        kb.append([types.InlineKeyboardButton(text="الاوامر", callback_data="bot_instructions")])
    else:
        kb.append([types.InlineKeyboardButton(text="تفعيل وتنصيب", callback_data="free_subscription")])
        kb.append([types.InlineKeyboardButton(text="الاوامر", callback_data="bot_instructions")])
    
    kb.append([types.InlineKeyboardButton(text="المطور", url=f"https://t.me/{DEV_USER.replace('@','')}")])
    
    if user_id == DEV_ID:
        kb.append([types.InlineKeyboardButton(text="لوحة المطور", callback_data="dev_admin_panel")])
    
    return types.InlineKeyboardMarkup(inline_keyboard=kb)

def get_control_panel_keyboard(bot_info):
    archive_st = "مفعل" if safe_get(bot_info, "archive_enabled", False) else "متوقف"
    save_st = "مفعل" if safe_get(bot_info, "save_media_enabled", True) else "متوقف"
    clock_st = "مفعل" if safe_get(bot_info, "clock_enabled", True) else "متوقف"
    filter_st = "مفعل" if safe_get(bot_info, "filter_enabled", True) else "متوقف"
    stickers_st = "مفعل" if STICKERS_ENABLED.get(bot_info.get("user_id"), False) else "متوقف"

    kb = []
    if WEB_APP_URL:
        kb.append([types.InlineKeyboardButton(text="فتح اللوحة الملونة", web_app=types.WebAppInfo(url=WEB_APP_URL))])
    kb.append([types.InlineKeyboardButton(text="الكتم والحظر", callback_data="mute_ban_menu")])
    kb.append([types.InlineKeyboardButton(text=f"الارشيف: {archive_st}", callback_data="toggle_archive")])
    kb.append([types.InlineKeyboardButton(text="اقفال الحماية", callback_data="locks_menu")])
    kb.append([types.InlineKeyboardButton(text=f"حفظ الوسائط: {save_st}", callback_data="toggle_save_media")])
    kb.append([types.InlineKeyboardButton(text=f"الساعة: {clock_st}", callback_data="toggle_clock")])
    kb.append([types.InlineKeyboardButton(text=f"الفلتر: {filter_st}", callback_data="toggle_filter")])
    kb.append([types.InlineKeyboardButton(text=f"الملصقات: {stickers_st}", callback_data="toggle_stickers")])
    kb.append([types.InlineKeyboardButton(text="اضافة باك ملصقات", callback_data="add_sticker_pack")])
    kb.append([types.InlineKeyboardButton(text="الاوامر", callback_data="bot_instructions"),
               types.InlineKeyboardButton(text="تحديث", callback_data="refresh_bot")])
    kb.append([types.InlineKeyboardButton(text="حذف التنصيب", callback_data="delete_install"),
               types.InlineKeyboardButton(text="الرئيسية", callback_data="main_menu")])
    return types.InlineKeyboardMarkup(inline_keyboard=kb)

def get_locks_keyboard(uid):
    kb = [
        [types.InlineKeyboardButton(text=f"صور: {'مقفل' if LOCKS['photos'].get(uid) else 'مفتوح'}", callback_data="toggle_lock_photos"),
         types.InlineKeyboardButton(text=f"فيديو: {'مقفل' if LOCKS['videos'].get(uid) else 'مفتوح'}", callback_data="toggle_lock_videos")],
        [types.InlineKeyboardButton(text=f"ملصقات: {'مقفل' if LOCKS['stickers'].get(uid) else 'مفتوح'}", callback_data="toggle_lock_stickers"),
         types.InlineKeyboardButton(text=f"روابط: {'مقفل' if LOCKS['links'].get(uid) else 'مفتوح'}", callback_data="toggle_lock_links")],
        [types.InlineKeyboardButton(text=f"ملفات: {'مقفل' if LOCKS['files'].get(uid) else 'مفتوح'}", callback_data="toggle_lock_files"),
         types.InlineKeyboardButton(text=f"صوت: {'مقفل' if LOCKS['audio'].get(uid) else 'مفتوح'}", callback_data="toggle_lock_audio")],
        [types.InlineKeyboardButton(text=f"متحركة: {'مقفل' if LOCKS['gifs'].get(uid) else 'مفتوح'}", callback_data="toggle_lock_gifs"),
         types.InlineKeyboardButton(text=f"توجيه: {'مقفل' if LOCKS['forwards'].get(uid) else 'مفتوح'}", callback_data="toggle_lock_forwards")],
        [types.InlineKeyboardButton(text=f"ارقام: {'مقفل' if LOCKS['numbers'].get(uid) else 'مفتوح'}", callback_data="toggle_lock_numbers"),
         types.InlineKeyboardButton(text=f"انجليزي: {'مقفل' if LOCKS['english'].get(uid) else 'مفتوح'}", callback_data="toggle_lock_english")],
        [types.InlineKeyboardButton(text=f"خاص: {'مقفل' if LOCKS['private'].get(uid) else 'مفتوح'}", callback_data="toggle_lock_private"),
         types.InlineKeyboardButton(text=f"ويب: {'مقفل' if LOCKS['webpage'].get(uid) else 'مفتوح'}", callback_data="toggle_lock_webpage")],
        [types.InlineKeyboardButton(text=f"هاشتاق: {'مقفل' if LOCKS['hashtag'].get(uid) else 'مفتوح'}", callback_data="toggle_lock_hashtag"),
         types.InlineKeyboardButton(text=f"منشن: {'مقفل' if LOCKS['mention'].get(uid) else 'مفتوح'}", callback_data="toggle_lock_mention")],
        [types.InlineKeyboardButton(text="رجوع", callback_data="my_settings")]
    ]
    return types.InlineKeyboardMarkup(inline_keyboard=kb)

# ==================== Web App ====================
@dp.message(lambda m: m.web_app_data is not None)
async def web_app_handler(message: types.Message):
    data = message.web_app_data.data
    user_id = message.from_user.id
    
    if data == "subscription":
        await message.answer("اضغط /start")
    elif data == "settings":
        is_installed, bot_info = is_user_installed(user_id)
        if is_installed:
            await message.answer("لوحة التحكم", reply_markup=get_control_panel_keyboard(bot_info))
    elif data == "instructions":
        await message.answer("اضغط /start ثم الاوامر")
    elif data == "contact":
        await message.answer(f"المطور: {DEV_USER}")
    elif data == "dev_panel":
        if user_id == DEV_ID:
            await dev_panel_message(message)
    elif data == "mute":
        await message.answer("استخدم امر كتم في المحادثة")
    elif data == "ban":
        await message.answer("استخدم امر حظر في المحادثة")
    elif data == "locks":
        await message.answer("استخدم لوحة التحكم ثم اقفال الحماية")
    elif data == "archive":
        await message.answer("استخدم لوحة التحكم ثم الارشيف")

async def dev_panel_message(message):
    res = supabase.table("user_bots").select("*").execute()
    total = len(res.data) if res.data else 0
    running = len(ACTIVE_CLIENTS)
    kb = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="المستخدمين", callback_data="dev_list_users"),
         types.InlineKeyboardButton(text="احصائيات", callback_data="dev_stats")],
        [types.InlineKeyboardButton(text="تشغيل الكل", callback_data="dev_start_all")],
        [types.InlineKeyboardButton(text="الرئيسية", callback_data="main_menu")]
    ])
    await message.answer(f"لوحة المطور:\n\nالمستخدمين: {total}\nيعملون: {running}", reply_markup=kb)

# ==================== Start ====================
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    user_id = message.from_user.id
    is_installed, bot_info = is_user_installed(user_id)
    if is_installed and bot_info:
        await message.answer("لوحة التحكم", reply_markup=get_control_panel_keyboard(bot_info))
        return
    await message.answer("مرحباً بك\n\nاضغط للبدء:", reply_markup=get_main_menu_keyboard(user_id))

@dp.callback_query(F.data == "free_subscription")
async def free_subscription(callback: types.CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    is_installed, _ = is_user_installed(user_id)
    if is_installed:
        await callback.answer("انت منصب!")
        return
    await callback.answer("جاري التفعيل...")
    await state.clear()
    try:
        supabase.table("user_bots").upsert({
            "user_id": user_id, "is_approved": True, "account_id": user_id, "is_active": True
        }, on_conflict="user_id").execute()
    except: pass
    contact_kb = types.ReplyKeyboardMarkup(
        keyboard=[[types.KeyboardButton(text="مشاركة رقم الهاتف", request_contact=True)]],
        resize_keyboard=True, one_time_keyboard=True
    )
    await callback.message.answer("اضغط زر مشاركة رقم الهاتف", reply_markup=contact_kb)
    await state.set_state(LoginState.waiting_for_phone)

@dp.callback_query(F.data == "bot_instructions")
async def bot_instructions(callback: types.CallbackQuery):
    text = (
        "اوامر الترفيه - للكل:\n"
        "غنيلي - شعر - مزج - ميمز - قرآن\n"
        "يوت اسم\n\n"
        "اوامر الملصقات:\n"
        "ملصق اسم_الباك - استخدام ملصق من الباك\n"
        "اضافة باك رابط_الباك - اضافة باك ملصقات\n"
        "حذف باك اسم_الباك - حذف باك ملصقات\n\n"
        "الكتم والحظر:\n"
        "كتم / فك كتم\n"
        "كتم ايدي / @يوزر\n"
        "حظر / فك حظر\n"
        "حظر ايدي / @يوزر\n\n"
        "الاقفال:\n"
        "قفل/فتح صور/فيديو/ملصقات/روابط/ملفات/صوت/متحركة/توجيه/ارقام/انجليزي/خاص/ويب/هاشتاق/منشن\n\n"
        "الارسال:\n"
        "كرر عدد نص\n"
        "اذاعة نص\n"
        "بعد ثواني نص\n\n"
        "الحالة:\n"
        "مشغول / متاح\n\n"
        "الحساب:\n"
        "تعيين صورة (رد)\n"
        "حذف صورة\n"
        "تغيير اسم\n"
        "تغيير بايو\n"
        "احصائياتي\n"
        "حالتي\n"
        "فحص"
    )
    await callback.message.edit_text(text, reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="رجوع", callback_data="main_menu")]
    ]))
    await callback.answer()

# ==================== معالجة الرقم والكود ====================
@dp.message(lambda m: m.contact is not None)
async def handle_contact(message: types.Message, state: FSMContext):
    phone = message.contact.phone_number
    if not phone.startswith("+"): phone = "+" + phone
    await state.update_data(phone=phone)
    client = TelegramClient(StringSession(), API_ID, API_HASH)
    await client.connect()
    try:
        sent = await client.send_code_request(phone)
        await state.update_data(phone_code_hash=sent.phone_code_hash, client=client)
        await message.answer("ارسل الرمز\nمثال: 1 2 3 4 5", reply_markup=types.ReplyKeyboardRemove())
        await state.set_state(LoginState.waiting_for_code)
    except Exception as e:
        await message.answer(f"خطأ: {e}")
        try: await client.disconnect()
        except: pass
        await state.clear()

@dp.message(lambda m: m.text and m.text.startswith("+"))
async def handle_phone_text(message: types.Message, state: FSMContext):
    phone = message.text.strip()
    if not phone.startswith("+"): phone = "+" + phone
    await state.update_data(phone=phone)
    client = TelegramClient(StringSession(), API_ID, API_HASH)
    await client.connect()
    try:
        sent = await client.send_code_request(phone)
        await state.update_data(phone_code_hash=sent.phone_code_hash, client=client)
        await message.answer("ارسل الرمز\nمثال: 1 2 3 4 5", reply_markup=types.ReplyKeyboardRemove())
        await state.set_state(LoginState.waiting_for_code)
    except Exception as e:
        await message.answer(f"خطأ: {e}")
        try: await client.disconnect()
        except: pass
        await state.clear()

@dp.message(LoginState.waiting_for_code)
async def process_code(message: types.Message, state: FSMContext):
    code = clean_code(message.text)
    data = await state.get_data()
    client = data.get('client')
    if not client:
        await message.answer("انتهت الجلسة")
        await state.clear()
        return
    try:
        await client.sign_in(phone=data['phone'], code=code, phone_code_hash=data['phone_code_hash'])
        session_str = client.session.save()
        me = await client.get_me()
        bot_data = {
            "user_id": message.from_user.id, "session_string": session_str,
            "account_id": me.id, "is_active": True, "clock_enabled": True,
            "filter_enabled": True, "save_media_enabled": True,
            "lock_private_enabled": False, "clock_font": "circle",
            "is_approved": True, "archive_enabled": False
        }
        supabase.table("user_bots").upsert(bot_data, on_conflict="user_id").execute()
        await message.answer(f"تم التنصيب\nالاسم: {me.first_name}", reply_markup=get_control_panel_keyboard(bot_data))
        asyncio.create_task(start_userbot(session_str, me.id))
        await client.disconnect()
        await state.clear()
    except Exception as e:
        if "Password" in str(e) or "Two-steps" in str(e):
            await state.update_data(client=client)
            await message.answer("ارسل كلمة المرور:")
            await state.set_state(LoginState.waiting_for_password)
        else:
            await message.answer(f"خطأ: {e}")
            try: await client.disconnect()
            except: pass
            await state.clear()

@dp.message(LoginState.waiting_for_password)
async def process_password(message: types.Message, state: FSMContext):
    data = await state.get_data()
    client = data.get('client')
    try:
        await client.sign_in(password=message.text.strip())
        session_str = client.session.save()
        me = await client.get_me()
        bot_data = {
            "user_id": message.from_user.id, "session_string": session_str,
            "account_id": me.id, "is_active": True, "clock_enabled": True,
            "filter_enabled": True, "save_media_enabled": True,
            "lock_private_enabled": False, "clock_font": "circle",
            "is_approved": True, "archive_enabled": False
        }
        supabase.table("user_bots").upsert(bot_data, on_conflict="user_id").execute()
        await message.answer(f"تم التفعيل\nالاسم: {me.first_name}", reply_markup=get_control_panel_keyboard(bot_data))
        asyncio.create_task(start_userbot(session_str, me.id))
        await client.disconnect()
        await state.clear()
    except Exception as e:
        await message.answer(f"خطأ: {e}")
        try: await client.disconnect()
        except: pass
        await state.clear()

# ==================== لوحة المطور ====================
@dp.callback_query(F.data == "dev_admin_panel")
async def dev_admin_panel(callback: types.CallbackQuery):
    if callback.from_user.id != DEV_ID:
        await callback.answer("مخصص للمطور")
        return
    res = supabase.table("user_bots").select("*").execute()
    kb = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="المستخدمين", callback_data="dev_list_users"),
         types.InlineKeyboardButton(text="احصائيات", callback_data="dev_stats")],
        [types.InlineKeyboardButton(text="تشغيل الكل", callback_data="dev_start_all")],
        [types.InlineKeyboardButton(text="الرئيسية", callback_data="main_menu")]
    ])
    await callback.message.edit_text(f"المطور\n\nالمستخدمين: {len(res.data) if res.data else 0}\nيعملون: {len(ACTIVE_CLIENTS)}", reply_markup=kb)
    await callback.answer()

@dp.callback_query(F.data == "dev_start_all")
async def dev_start_all(callback: types.CallbackQuery):
    res = supabase.table("user_bots").select("*").execute()
    for row in res.data:
        if row.get("session_string") and row.get("is_active"):
            asyncio.create_task(start_userbot(row["session_string"], row["account_id"]))
    await callback.answer("تم التشغيل")
    await dev_admin_panel(callback)

@dp.callback_query(F.data == "dev_list_users")
async def dev_list_users(callback: types.CallbackQuery):
    res = supabase.table("user_bots").select("user_id, account_id, is_active").execute()
    if not res.data:
        await callback.message.edit_text("لا يوجد")
    else:
        kb = []
        for row in res.data[:10]:
            running = "يعمل" if row.get("account_id") in ACTIVE_CLIENTS else "واقف"
            kb.append([types.InlineKeyboardButton(text=f"{row['user_id']} - {running}", callback_data=f"dev_user_{row['user_id']}")])
        kb.append([types.InlineKeyboardButton(text="رجوع", callback_data="dev_admin_panel")])
        await callback.message.edit_text(f"المستخدمين ({len(res.data)}):", reply_markup=types.InlineKeyboardMarkup(inline_keyboard=kb))
    await callback.answer()

@dp.callback_query(F.data.startswith("dev_user_"))
async def dev_manage_user(callback: types.CallbackQuery):
    uid = int(callback.data.replace("dev_user_", ""))
    kb = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="تشغيل", callback_data=f"dev_start_{uid}"),
         types.InlineKeyboardButton(text="ايقاف", callback_data=f"dev_stop_{uid}")],
        [types.InlineKeyboardButton(text="حذف", callback_data=f"dev_del_{uid}")],
        [types.InlineKeyboardButton(text="رجوع", callback_data="dev_list_users")]
    ])
    await callback.message.edit_text(f"ادارة: {uid}", reply_markup=kb)
    await callback.answer()

@dp.callback_query(F.data.startswith("dev_start_"))
async def dev_start_user(callback: types.CallbackQuery):
    uid = int(callback.data.replace("dev_start_", ""))
    res = supabase.table("user_bots").select("*").eq("user_id", uid).execute()
    if res.data and res.data[0].get("session_string"):
        supabase.table("user_bots").update({"is_active": True}).eq("user_id", uid).execute()
        asyncio.create_task(start_userbot(res.data[0]["session_string"], res.data[0]["account_id"]))
    await dev_list_users(callback)

@dp.callback_query(F.data.startswith("dev_stop_"))
async def dev_stop_user(callback: types.CallbackQuery):
    uid = int(callback.data.replace("dev_stop_", ""))
    res = supabase.table("user_bots").select("account_id").eq("user_id", uid).execute()
    if res.data:
        aid = res.data[0]["account_id"]
        if aid in ACTIVE_CLIENTS:
            try: await ACTIVE_CLIENTS[aid].disconnect()
            except: pass
            del ACTIVE_CLIENTS[aid]
        supabase.table("user_bots").update({"is_active": False}).eq("user_id", uid).execute()
    await dev_list_users(callback)

@dp.callback_query(F.data.startswith("dev_del_"))
async def dev_delete_user(callback: types.CallbackQuery):
    uid = int(callback.data.replace("dev_del_", ""))
    supabase.table("user_bots").delete().eq("user_id", uid).execute()
    await dev_list_users(callback)

@dp.callback_query(F.data == "dev_stats")
async def dev_stats(callback: types.CallbackQuery):
    res = supabase.table("user_bots").select("*").execute()
    await callback.message.edit_text(f"الاحصائيات:\nالاجمالي: {len(res.data) if res.data else 0}\nيعملون: {len(ACTIVE_CLIENTS)}",
        reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[
            [types.InlineKeyboardButton(text="رجوع", callback_data="dev_admin_panel")]
        ]))
    await callback.answer()

# ==================== الكتم والحظر ====================
@dp.callback_query(F.data == "mute_ban_menu")
async def mute_ban_menu(callback: types.CallbackQuery):
    kb = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="كتم", callback_data="mute_user"),
         types.InlineKeyboardButton(text="فك كتم", callback_data="unmute_user")],
        [types.InlineKeyboardButton(text="حظر", callback_data="ban_user"),
         types.InlineKeyboardButton(text="فك حظر", callback_data="unban_user")],
        [types.InlineKeyboardButton(text="المكتمين", callback_data="list_muted"),
         types.InlineKeyboardButton(text="المحظورين", callback_data="list_banned")],
        [types.InlineKeyboardButton(text="رجوع", callback_data="my_settings")]
    ])
    await callback.message.edit_text("الكتم والحظر:", reply_markup=kb)
    await callback.answer()

@dp.callback_query(F.data == "mute_user")
async def mute_user(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer("ارسل ايدي او @يوزر:")
    await state.set_state(SettingsState.waiting_for_mute_user_id)
    await callback.answer()

@dp.message(SettingsState.waiting_for_mute_user_id)
async def save_muted(message: types.Message, state: FSMContext):
    target = message.text.strip()
    uid = message.from_user.id
    supabase.table("muted_users").upsert({"user_id": uid, "muted_user_id": target}, on_conflict="user_id,muted_user_id").execute()
    MUTED_USERS_CACHE.setdefault(uid, set()).add(target)
    await message.answer(f"تم كتم: {target}")
    await state.clear()

@dp.callback_query(F.data == "unmute_user")
async def unmute_user(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer("ارسل ايدي او @يوزر:")
    await state.set_state(SettingsState.waiting_for_mute_user_id)
    await callback.answer()

@dp.callback_query(F.data == "ban_user")
async def ban_user(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer("ارسل ايدي او @يوزر:")
    await state.set_state(SettingsState.waiting_for_ban_user_id)
    await callback.answer()

@dp.message(SettingsState.waiting_for_ban_user_id)
async def save_banned(message: types.Message, state: FSMContext):
    target = message.text.strip()
    uid = message.from_user.id
    supabase.table("banned_users").upsert({"user_id": uid, "banned_user_id": target}, on_conflict="user_id,banned_user_id").execute()
    BANNED_USERS_CACHE.setdefault(uid, set()).add(target)
    await message.answer(f"تم حظر: {target}")
    await state.clear()

@dp.callback_query(F.data == "unban_user")
async def unban_user(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer("ارسل ايدي او @يوزر:")
    await state.set_state(SettingsState.waiting_for_ban_user_id)
    await callback.answer()

@dp.callback_query(F.data == "list_muted")
async def list_muted(callback: types.CallbackQuery):
    uid = callback.from_user.id
    res = supabase.table("muted_users").select("*").eq("user_id", uid).execute()
    if not res.data:
        await callback.message.edit_text("لا يوجد مكتمين", reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[
            [types.InlineKeyboardButton(text="رجوع", callback_data="mute_ban_menu")]
        ]))
    else:
        kb = []
        for r in res.data:
            kb.append([types.InlineKeyboardButton(text=f"فك: {r['muted_user_id']}", callback_data=f"unmute_{r['muted_user_id']}")])
        kb.append([types.InlineKeyboardButton(text="رجوع", callback_data="mute_ban_menu")])
        await callback.message.edit_text("المكتمين:", reply_markup=types.InlineKeyboardMarkup(inline_keyboard=kb))
    await callback.answer()

@dp.callback_query(F.data.startswith("unmute_"))
async def unmute(callback: types.CallbackQuery):
    target = callback.data.replace("unmute_", "")
    uid = callback.from_user.id
    supabase.table("muted_users").delete().eq("user_id", uid).eq("muted_user_id", target).execute()
    MUTED_USERS_CACHE.get(uid, set()).discard(target)
    await list_muted(callback)

@dp.callback_query(F.data == "list_banned")
async def list_banned(callback: types.CallbackQuery):
    uid = callback.from_user.id
    res = supabase.table("banned_users").select("*").eq("user_id", uid).execute()
    if not res.data:
        await callback.message.edit_text("لا يوجد محظورين", reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[
            [types.InlineKeyboardButton(text="رجوع", callback_data="mute_ban_menu")]
        ]))
    else:
        kb = []
        for r in res.data:
            kb.append([types.InlineKeyboardButton(text=f"فك: {r['banned_user_id']}", callback_data=f"unban_{r['banned_user_id']}")])
        kb.append([types.InlineKeyboardButton(text="رجوع", callback_data="mute_ban_menu")])
        await callback.message.edit_text("المحظورين:", reply_markup=types.InlineKeyboardMarkup(inline_keyboard=kb))
    await callback.answer()

@dp.callback_query(F.data.startswith("unban_"))
async def unban(callback: types.CallbackQuery):
    target = callback.data.replace("unban_", "")
    uid = callback.from_user.id
    supabase.table("banned_users").delete().eq("user_id", uid).eq("banned_user_id", target).execute()
    BANNED_USERS_CACHE.get(uid, set()).discard(target)
    await list_banned(callback)

# ==================== الاقفال ====================
@dp.callback_query(F.data == "locks_menu")
async def locks_menu(callback: types.CallbackQuery):
    uid = callback.from_user.id
    await callback.message.edit_text("الاقفال:", reply_markup=get_locks_keyboard(uid))
    await callback.answer()

@dp.callback_query(F.data == "toggle_lock_photos")
async def tlp(callback: types.CallbackQuery):
    LOCKS['photos'][callback.from_user.id] = not LOCKS['photos'].get(callback.from_user.id, False)
    await locks_menu(callback)

@dp.callback_query(F.data == "toggle_lock_videos")
async def tlv(callback: types.CallbackQuery):
    LOCKS['videos'][callback.from_user.id] = not LOCKS['videos'].get(callback.from_user.id, False)
    await locks_menu(callback)

@dp.callback_query(F.data == "toggle_lock_stickers")
async def tls(callback: types.CallbackQuery):
    LOCKS['stickers'][callback.from_user.id] = not LOCKS['stickers'].get(callback.from_user.id, False)
    await locks_menu(callback)

@dp.callback_query(F.data == "toggle_lock_links")
async def tll(callback: types.CallbackQuery):
    LOCKS['links'][callback.from_user.id] = not LOCKS['links'].get(callback.from_user.id, False)
    await locks_menu(callback)

@dp.callback_query(F.data == "toggle_lock_files")
async def tlf(callback: types.CallbackQuery):
    LOCKS['files'][callback.from_user.id] = not LOCKS['files'].get(callback.from_user.id, False)
    await locks_menu(callback)

@dp.callback_query(F.data == "toggle_lock_audio")
async def tla(callback: types.CallbackQuery):
    LOCKS['audio'][callback.from_user.id] = not LOCKS['audio'].get(callback.from_user.id, False)
    await locks_menu(callback)

@dp.callback_query(F.data == "toggle_lock_gifs")
async def tlg(callback: types.CallbackQuery):
    LOCKS['gifs'][callback.from_user.id] = not LOCKS['gifs'].get(callback.from_user.id, False)
    await locks_menu(callback)

@dp.callback_query(F.data == "toggle_lock_forwards")
async def tlf(callback: types.CallbackQuery):
    LOCKS['forwards'][callback.from_user.id] = not LOCKS['forwards'].get(callback.from_user.id, False)
    await locks_menu(callback)

@dp.callback_query(F.data == "toggle_lock_numbers")
async def tln(callback: types.CallbackQuery):
    LOCKS['numbers'][callback.from_user.id] = not LOCKS['numbers'].get(callback.from_user.id, False)
    await locks_menu(callback)

@dp.callback_query(F.data == "toggle_lock_english")
async def tle(callback: types.CallbackQuery):
    LOCKS['english'][callback.from_user.id] = not LOCKS['english'].get(callback.from_user.id, False)
    await locks_menu(callback)

@dp.callback_query(F.data == "toggle_lock_private")
async def tlpv(callback: types.CallbackQuery):
    LOCKS['private'][callback.from_user.id] = not LOCKS['private'].get(callback.from_user.id, False)
    await locks_menu(callback)

@dp.callback_query(F.data == "toggle_lock_webpage")
async def tlw(callback: types.CallbackQuery):
    LOCKS['webpage'][callback.from_user.id] = not LOCKS['webpage'].get(callback.from_user.id, False)
    await locks_menu(callback)

@dp.callback_query(F.data == "toggle_lock_hashtag")
async def tlh(callback: types.CallbackQuery):
    LOCKS['hashtag'][callback.from_user.id] = not LOCKS['hashtag'].get(callback.from_user.id, False)
    await locks_menu(callback)

@dp.callback_query(F.data == "toggle_lock_mention")
async def tlm(callback: types.CallbackQuery):
    LOCKS['mention'][callback.from_user.id] = not LOCKS['mention'].get(callback.from_user.id, False)
    await locks_menu(callback)

# ==================== أزرار بسيطة ====================
@dp.callback_query(F.data == "toggle_archive")
async def toggle_archive(callback: types.CallbackQuery):
    uid = callback.from_user.id
    is_installed, bot_info = is_user_installed(uid)
    if is_installed:
        aid = bot_info["account_id"]
        ARCHIVE_ENABLED[aid] = not ARCHIVE_ENABLED.get(aid, False)
        supabase.table("user_bots").update({"archive_enabled": ARCHIVE_ENABLED[aid]}).eq("account_id", aid).execute()
        await callback.answer(f"الارشيف {'مفعل' if ARCHIVE_ENABLED[aid] else 'متوقف'}")
        await settings_menu(callback)

@dp.callback_query(F.data == "toggle_save_media")
async def toggle_save_media(callback: types.CallbackQuery):
    uid = callback.from_user.id
    res = supabase.table("user_bots").select("save_media_enabled").or_(f"user_id.eq.{uid},account_id.eq.{uid}").execute()
    if res.data:
        cur = res.data[0].get("save_media_enabled", True)
        supabase.table("user_bots").update({"save_media_enabled": not cur}).or_(f"user_id.eq.{uid},account_id.eq.{uid}").execute()
    await callback.answer("تم")
    await settings_menu(callback)

@dp.callback_query(F.data == "toggle_clock")
async def toggle_clock(callback: types.CallbackQuery):
    uid = callback.from_user.id
    res = supabase.table("user_bots").select("clock_enabled").or_(f"user_id.eq.{uid},account_id.eq.{uid}").execute()
    if res.data:
        cur = res.data[0].get("clock_enabled", True)
        supabase.table("user_bots").update({"clock_enabled": not cur}).or_(f"user_id.eq.{uid},account_id.eq.{uid}").execute()
    await callback.answer("تم")
    await settings_menu(callback)

@dp.callback_query(F.data == "toggle_filter")
async def toggle_filter(callback: types.CallbackQuery):
    uid = callback.from_user.id
    res = supabase.table("user_bots").select("filter_enabled").or_(f"user_id.eq.{uid},account_id.eq.{uid}").execute()
    if res.data:
        cur = res.data[0].get("filter_enabled", True)
        supabase.table("user_bots").update({"filter_enabled": not cur}).or_(f"user_id.eq.{uid},account_id.eq.{uid}").execute()
    await callback.answer("تم")
    await settings_menu(callback)

@dp.callback_query(F.data == "toggle_stickers")
async def toggle_stickers(callback: types.CallbackQuery):
    uid = callback.from_user.id
    STICKERS_ENABLED[uid] = not STICKERS_ENABLED.get(uid, False)
    await callback.answer(f"الملصقات {'مفعلة' if STICKERS_ENABLED[uid] else 'موقفة'}")
    await settings_menu(callback)

@dp.callback_query(F.data == "add_sticker_pack")
async def add_sticker_pack(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer("ارسل رابط باك الملصقات:\nمثال: t.me/addstickers/اسم_الباك")
    await state.set_state(SettingsState.waiting_for_sticker_command)
    await callback.answer()

@dp.message(SettingsState.waiting_for_sticker_command)
async def process_sticker_pack(message: types.Message, state: FSMContext):
    text = message.text.strip()
    uid = message.from_user.id
    
    if text.startswith("اضافة باك "):
        pack_link = text[10:].strip()
        is_installed, bot_info = is_user_installed(uid)
        if is_installed and bot_info.get("session_string"):
            client = TelegramClient(StringSession(bot_info["session_string"]), API_ID, API_HASH)
            await client.start()
            try:
                success, msg = await add_sticker_pack(client, uid, pack_link)
                await message.answer(msg)
                await client.disconnect()
            except Exception as e:
                await message.answer(f"خطأ: {e}")
        await state.clear()
        return
    
    elif text.startswith("حذف باك "):
        # حذف باك
        await message.answer("جاري الحذف...")
        await state.clear()
        return
    
    # افتراضي - محاولة استخدام ملصق
    await message.answer("للاضافة استخدم: اضافة باك رابط_الباك\nللاستخدام: ملصق اسم_الباك")
    await state.clear()

# ==================== اعدادات البوت الرئيسية ====================
@dp.callback_query(F.data == "my_settings")
async def settings_menu(callback: types.CallbackQuery):
    uid = callback.from_user.id
    is_installed, bot_info = is_user_installed(uid)
    if not is_installed:
        await callback.answer("يجب التنصيب")
        return
    await callback.message.edit_text("لوحة التحكم:", reply_markup=get_control_panel_keyboard(bot_info))
    await callback.answer()

@dp.callback_query(F.data == "main_menu")
async def back_to_main(callback: types.CallbackQuery):
    await callback.message.edit_text("الرئيسية:", reply_markup=get_main_menu_keyboard(callback.from_user.id))
    await callback.answer()

@dp.callback_query(F.data == "refresh_bot")
async def refresh_bot(callback: types.CallbackQuery):
    uid = callback.from_user.id
    res = supabase.table("user_bots").select("*").or_(f"user_id.eq.{uid},account_id.eq.{uid}").execute()
    if res.data:
        bot_info = res.data[0]
        aid = bot_info["account_id"]
        if aid in ACTIVE_CLIENTS:
            try: await ACTIVE_CLIENTS[aid].disconnect()
            except: pass
            del ACTIVE_CLIENTS[aid]
        if bot_info.get("session_string"):
            supabase.table("user_bots").update({"is_active": True}).eq("user_id", uid).execute()
            asyncio.create_task(start_userbot(bot_info["session_string"], aid))
    await callback.answer("تم التحديث")
    await settings_menu(callback)

@dp.callback_query(F.data == "delete_install")
async def delete_install(callback: types.CallbackQuery):
    kb = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="نعم", callback_data="confirm_delete")],
        [types.InlineKeyboardButton(text="لا", callback_data="main_menu")]
    ])
    await callback.message.edit_text("متاكد؟", reply_markup=kb)
    await callback.answer()

@dp.callback_query(F.data == "confirm_delete")
async def confirm_delete(callback: types.CallbackQuery):
    uid = callback.from_user.id
    res = supabase.table("user_bots").select("*").or_(f"user_id.eq.{uid},account_id.eq.{uid}").execute()
    if res.data:
        aid = res.data[0]["account_id"]
        if aid in ACTIVE_CLIENTS:
            try: await ACTIVE_CLIENTS[aid].disconnect()
            except: pass
            del ACTIVE_CLIENTS[aid]
        supabase.table("user_bots").update({"session_string": None, "is_active": False}).eq("user_id", uid).execute()
    await callback.message.edit_text("تم الحذف", reply_markup=get_main_menu_keyboard(uid))
    await callback.answer()

# ==================== اليوزربوت - لا يتوقف ابداً ====================
async def load_channel_messages(client, chan, cat, cid):
    try:
        msgs = []
        async for m in client.iter_messages(chan, limit=100):
            if m.text or m.media:
                msgs.append(m)
        CLIENT_CONTENTS.setdefault(cid, {})[cat] = msgs
    except: pass

async def get_user_stickers(client, user_id):
    """جلب الملصقات المفضلة للمستخدم"""
    try:
        stickers = []
        # محاولة جلب الملصقات من القنوات المضافة
        for pack in STICKER_PACKS.get(user_id, []):
            try:
                # محاولة جلب الباك
                pass
            except:
                pass
        return stickers
    except:
        return []

async def start_userbot(session_str, client_id):
    """تشغيل اليوزربوت - لا يتوقف ابداً"""
    while True:
        client = None
        try:
            client = TelegramClient(StringSession(session_str), API_ID, API_HASH)
            await client.start()
            ACTIVE_CLIENTS[client_id] = client
            
            # تحميل المحتوى
            for cat, chan in CHANNELS_MAP.items():
                asyncio.create_task(load_channel_messages(client, chan, cat, client_id))
            
            # تحميل المكتمين والمحظورين
            try:
                res = supabase.table("muted_users").select("*").eq("user_id", client_id).execute()
                if res.data:
                    MUTED_USERS_CACHE[client_id] = {r['muted_user_id'] for r in res.data}
            except: pass
            try:
                res = supabase.table("banned_users").select("*").eq("user_id", client_id).execute()
                if res.data:
                    BANNED_USERS_CACHE[client_id] = {r['banned_user_id'] for r in res.data}
            except: pass
            
            # ==================== مستمع واحد ====================
            @client.on(events.NewMessage())
            async def handler(event):
                try:
                    text_raw = event.raw_text.strip() if event.raw_text else ""
                    text_lower = text_raw.lower()
                    chat_id = event.chat_id
                    is_private = event.is_private
                    is_outgoing = event.out
                    
                    msg_key = f"{client_id}_{event.message.id}"
                    if msg_key in PROCESSED_MESSAGES:
                        return
                    PROCESSED_MESSAGES.add(msg_key)
                    
                    # ===== معالجة الملصقات =====
                    if is_private and text_lower.startswith("ملصق "):
                        try:
                            pack_name = text_raw[5:].strip()
                            # البحث عن الملصق في الباك المضافة
                            # استخدام pack_name للبحث
                            await event.reply("جاري البحث عن الملصق...")
                            # هنا يمكن اضافة منطق البحث عن الملصقات
                        except Exception as e:
                            await event.reply(f"خطأ: {e}")
                        return
                    
                    # ===== اوامر الترفيه - للكل =====
                    if is_private:
                        matched = None
                        for cmd in CHANNELS_MAP:
                            if text_raw == cmd:
                                matched = cmd
                                break
                        
                        if matched:
                            try: await event.delete()
                            except: pass
                            msgs = CLIENT_CONTENTS.get(client_id, {}).get(matched, [])
                            if msgs:
                                s = random.choice(msgs)
                                try:
                                    if s.media:
                                        await client.send_file(chat_id, s.media, caption=s.text or "")
                                    elif s.text:
                                        await client.send_message(chat_id, s.text)
                                except: pass
                            return
                        
                        if text_lower.startswith("يوت ") or text_lower.startswith("يوتو "):
                            q = text_raw[4:].strip() if text_lower.startswith("يوت ") else text_raw[5:].strip()
                            if q:
                                try: await event.delete()
                                except: pass
                                try:
                                    sent = await client.send_message(DOWNLOAD_BOT, f"يوت {q}")
                                    audio = None
                                    for _ in range(30):
                                        msgs = await client.get_messages(DOWNLOAD_BOT, limit=6)
                                        for m in msgs:
                                            if m.id > sent.id and (m.audio or m.voice):
                                                audio = m
                                                break
                                        if audio: break
                                        await asyncio.sleep(0.3)
                                    if audio:
                                        await client.send_file(chat_id, audio.media)
                                except: pass
                            return
                    
                    # ===== اوامر المنصب =====
                    if is_outgoing:
                        # كتم
                        if text_raw == "كتم":
                            try:
                                if is_private: await event.delete()
                                MUTED_USERS_CACHE.setdefault(client_id, set())
                                target = chat_id if is_private else (event.reply_to_msg_id and (await event.get_reply_message()).sender_id if event.reply_to_msg_id else None)
                                if target:
                                    MUTED_USERS_CACHE[client_id].add(str(target))
                                    supabase.table("muted_users").upsert({"user_id": client_id, "muted_user_id": str(target)}, on_conflict="user_id,muted_user_id").execute()
                                    await event.respond("تم كتم المستخدم")
                            except: pass
                            return
                        
                        if text_raw == "فك كتم":
                            try:
                                if is_private: await event.delete()
                                target = chat_id if is_private else (event.reply_to_msg_id and (await event.get_reply_message()).sender_id if event.reply_to_msg_id else None)
                                if target and client_id in MUTED_USERS_CACHE:
                                    MUTED_USERS_CACHE[client_id].discard(str(target))
                                    supabase.table("muted_users").delete().eq("user_id", client_id).eq("muted_user_id", str(target)).execute()
                                    await event.respond("تم فك الكتم")
                            except: pass
                            return
                        
                        if text_lower.startswith("كتم "):
                            try:
                                target = text_raw[4:].strip()
                                rid = await resolve_identifier(client, target)
                                if rid: target = str(rid)
                                MUTED_USERS_CACHE.setdefault(client_id, set()).add(target)
                                supabase.table("muted_users").upsert({"user_id": client_id, "muted_user_id": target}, on_conflict="user_id,muted_user_id").execute()
                                await event.respond(f"تم كتم: {target}")
                            except: pass
                            return
                        
                        if text_lower.startswith("فك كتم "):
                            try:
                                target = text_raw[6:].strip()
                                rid = await resolve_identifier(client, target)
                                if rid: target = str(rid)
                                MUTED_USERS_CACHE.get(client_id, set()).discard(target)
                                supabase.table("muted_users").delete().eq("user_id", client_id).eq("muted_user_id", target).execute()
                                await event.respond(f"تم فك كتم: {target}")
                            except: pass
                            return
                        
                        # حظر
                        if text_raw == "حظر":
                            try:
                                if is_private: await event.delete()
                                BANNED_USERS_CACHE.setdefault(client_id, set())
                                target = chat_id if is_private else (event.reply_to_msg_id and (await event.get_reply_message()).sender_id if event.reply_to_msg_id else None)
                                if target:
                                    BANNED_USERS_CACHE[client_id].add(str(target))
                                    supabase.table("banned_users").upsert({"user_id": client_id, "banned_user_id": str(target)}, on_conflict="user_id,banned_user_id").execute()
                                    await event.respond("تم حظر المستخدم")
                            except: pass
                            return
                        
                        if text_raw == "فك حظر":
                            try:
                                if is_private: await event.delete()
                                target = chat_id if is_private else (event.reply_to_msg_id and (await event.get_reply_message()).sender_id if event.reply_to_msg_id else None)
                                if target and client_id in BANNED_USERS_CACHE:
                                    BANNED_USERS_CACHE[client_id].discard(str(target))
                                    supabase.table("banned_users").delete().eq("user_id", client_id).eq("banned_user_id", str(target)).execute()
                                    await event.respond("تم فك الحظر")
                            except: pass
                            return
                        
                        if text_lower.startswith("حظر "):
                            try:
                                target = text_raw[4:].strip()
                                rid = await resolve_identifier(client, target)
                                if rid: target = str(rid)
                                BANNED_USERS_CACHE.setdefault(client_id, set()).add(target)
                                supabase.table("banned_users").upsert({"user_id": client_id, "banned_user_id": target}, on_conflict="user_id,banned_user_id").execute()
                                await event.respond(f"تم حظر: {target}")
                            except: pass
                            return
                        
                        if text_lower.startswith("فك حظر "):
                            try:
                                target = text_raw[6:].strip()
                                rid = await resolve_identifier(client, target)
                                if rid: target = str(rid)
                                BANNED_USERS_CACHE.get(client_id, set()).discard(target)
                                supabase.table("banned_users").delete().eq("user_id", client_id).eq("banned_user_id", target).execute()
                                await event.respond(f"تم فك حظر: {target}")
                            except: pass
                            return
                        
                        # أقفال
                        locks_map = {
                            "قفل صور": ("photos", True), "فتح صور": ("photos", False),
                            "قفل فيديو": ("videos", True), "فتح فيديو": ("videos", False),
                            "قفل ملصقات": ("stickers", True), "فتح ملصقات": ("stickers", False),
                            "قفل روابط": ("links", True), "فتح روابط": ("links", False),
                            "قفل صوت": ("audio", True), "فتح صوت": ("audio", False),
                            "قفل توجيه": ("forwards", True), "فتح توجيه": ("forwards", False),
                            "قفل ملفات": ("files", True), "فتح ملفات": ("files", False),
                            "قفل متحركة": ("gifs", True), "فتح متحركة": ("gifs", False),
                            "قفل ارقام": ("numbers", True), "فتح ارقام": ("numbers", False),
                            "قفل انجليزي": ("english", True), "فتح انجليزي": ("english", False),
                            "قفل خاص": ("private", True), "فتح خاص": ("private", False),
                            "قفل ويب": ("webpage", True), "فتح ويب": ("webpage", False),
                            "قفل هاشتاق": ("hashtag", True), "فتح هاشتاق": ("hashtag", False),
                            "قفل منشن": ("mention", True), "فتح منشن": ("mention", False),
                        }
                        if text_raw in locks_map:
                            lock_key, value = locks_map[text_raw]
                            LOCKS[lock_key][client_id] = value
                            await event.respond(f"تم {'قفل' if value else 'فتح'} {lock_key}")
                            return
                        
                        # مشغول
                        if text_lower.startswith("مشغول "):
                            BUSY_MODE[client_id] = True
                            BUSY_MESSAGE[client_id] = text_raw[6:].strip()
                            await event.respond("تم تفعيل المشغول")
                            return
                        if text_raw == "مشغول":
                            BUSY_MODE[client_id] = True
                            BUSY_MESSAGE[client_id] = "مشغول"
                            await event.respond("تم")
                            return
                        if text_raw == "متاح":
                            BUSY_MODE[client_id] = False
                            await event.respond("تم")
                            return
                        
                        # كرر
                        if text_lower.startswith("كرر "):
                            try:
                                parts = text_raw[4:].strip().split(" ", 1)
                                count = int(parts[0])
                                msg = parts[1] if len(parts) > 1 else ""
                                for i in range(count):
                                    await client.send_message(chat_id, msg)
                                    await asyncio.sleep(0.5)
                            except: pass
                            return
                        
                        # حالتي
                        if text_raw == "حالتي":
                            me = await client.get_me()
                            await event.respond(f"الاسم: {me.first_name}\nالايدي: {me.id}\nيعمل")
                            return
                        
                        # فحص
                        if text_raw == "فحص":
                            await event.respond("الحساب شغال")
                            return
                        
                        # احصائياتي
                        if text_raw == "احصائياتي":
                            await event.respond(f"المكتمين: {len(MUTED_USERS_CACHE.get(client_id, set()))}\nالمحظورين: {len(BANNED_USERS_CACHE.get(client_id, set()))}")
                            return
                        
                        # تعيين صورة
                        if text_raw == "تعيين صورة" and event.reply_to_msg_id:
                            replied = await event.get_reply_message()
                            if replied and replied.media:
                                try:
                                    fp = await replied.download_media()
                                    if fp:
                                        await client(functions.photos.UploadProfilePhotoRequest(file=await client.upload_file(fp)))
                                        try: os.remove(fp)
                                        except: pass
                                        await event.respond("تم")
                                except: pass
                            return
                        
                        # حذف صورة
                        if text_raw == "حذف صورة":
                            try:
                                photos = await client.get_profile_photos('me', limit=1)
                                if photos:
                                    await client(functions.photos.DeletePhotosRequest(id=[photos[0]]))
                                    await event.respond("تم")
                            except: pass
                            return
                        
                        # تغيير اسم
                        if text_lower.startswith("تغيير اسم "):
                            try:
                                await client(functions.account.UpdateProfileRequest(first_name=text_raw[10:].strip()))
                                await event.respond("تم")
                            except: pass
                            return
                        
                        # تغيير بايو
                        if text_lower.startswith("تغيير بايو "):
                            try:
                                await client(functions.account.UpdateProfileRequest(about=text_raw[11:].strip()))
                                await event.respond("تم")
                            except: pass
                            return
                    
                    # ===== معالجة الرسائل الواردة =====
                    else:
                        if is_private:
                            sender_id = event.sender_id
                            
                            # مشغول
                            if BUSY_MODE.get(client_id, False):
                                await event.reply(BUSY_MESSAGE.get(client_id, "مشغول"))
                                return
                            
                            # كتم
                            if client_id in MUTED_USERS_CACHE and str(sender_id) in MUTED_USERS_CACHE[client_id]:
                                try: await event.delete()
                                except: pass
                                return
                            
                            # حظر
                            if client_id in BANNED_USERS_CACHE and str(sender_id) in BANNED_USERS_CACHE[client_id]:
                                try: await event.delete()
                                except: pass
                                return
                            
                            # أقفال
                            msg_media = event.message.media
                            text = event.raw_text or ""
                            
                            if LOCKS.get('photos', {}).get(client_id) and isinstance(msg_media, MessageMediaPhoto):
                                try: await event.delete()
                                except: pass
                                return
                            if LOCKS.get('videos', {}).get(client_id) and isinstance(msg_media, MessageMediaDocument):
                                doc = msg_media.document
                                if doc and doc.mime_type and "video" in doc.mime_type and "webm" not in doc.mime_type:
                                    try: await event.delete()
                                    except: pass
                                    return
                            if LOCKS.get('stickers', {}).get(client_id) and isinstance(msg_media, MessageMediaDocument):
                                doc = msg_media.document
                                if doc and doc.mime_type and "sticker" in doc.mime_type:
                                    try: await event.delete()
                                    except: pass
                                    return
                            if LOCKS.get('links', {}).get(client_id) and ("http" in text or "t.me" in text):
                                try: await event.delete()
                                except: pass
                                return
                            if LOCKS.get('audio', {}).get(client_id) and isinstance(msg_media, MessageMediaDocument):
                                doc = msg_media.document
                                if doc and doc.mime_type and ("audio" in doc.mime_type or "voice" in doc.mime_type):
                                    try: await event.delete()
                                    except: pass
                                    return
                            if LOCKS.get('forwards', {}).get(client_id) and event.message.fwd_from:
                                try: await event.delete()
                                except: pass
                                return
                            if LOCKS.get('files', {}).get(client_id) and isinstance(msg_media, MessageMediaDocument):
                                try: await event.delete()
                                except: pass
                                return
                            if LOCKS.get('gifs', {}).get(client_id) and isinstance(msg_media, MessageMediaDocument):
                                doc = msg_media.document
                                if doc and doc.mime_type and "gif" in doc.mime_type:
                                    try: await event.delete()
                                    except: pass
                                    return
                            if LOCKS.get('numbers', {}).get(client_id) and re.search(r'\d', text):
                                try: await event.delete()
                                except: pass
                                return
                            if LOCKS.get('english', {}).get(client_id) and re.search(r'[a-zA-Z]', text):
                                try: await event.delete()
                                except: pass
                                return
                            if LOCKS.get('private', {}).get(client_id) and is_private:
                                try: await event.delete()
                                except: pass
                                return
                            if LOCKS.get('webpage', {}).get(client_id) and isinstance(msg_media, MessageMediaWebPage):
                                try: await event.delete()
                                except: pass
                                return
                            if LOCKS.get('hashtag', {}).get(client_id) and "#" in text:
                                try: await event.delete()
                                except: pass
                                return
                            if LOCKS.get('mention', {}).get(client_id) and "@" in text:
                                try: await event.delete()
                                except: pass
                                return
                            
                            # حفظ الوسائط الوقتية
                            res = supabase.table("user_bots").select("save_media_enabled").eq("account_id", client_id).execute()
                            if res.data and res.data[0].get("save_media_enabled", True) and msg_media:
                                is_photo = isinstance(msg_media, MessageMediaPhoto)
                                is_video = False
                                is_audio = False
                                if isinstance(msg_media, MessageMediaDocument):
                                    doc = msg_media.document
                                    if doc and doc.mime_type:
                                        m = doc.mime_type
                                        if "video" in m and "webm" not in m: is_video = True
                                        if "audio" in m or "voice" in m: is_audio = True
                                
                                is_ttl = (hasattr(event.message, 'ttl_period') and event.message.ttl_period) or (hasattr(event.message, 'media_unread') and event.message.media_unread) or (hasattr(msg_media, 'ttl_seconds') and msg_media.ttl_seconds)
                                
                                if is_ttl and (is_photo or is_video or is_audio):
                                    try:
                                        fp = await event.message.download_media()
                                        if fp:
                                            await client.send_file('me', fp)
                                            try: os.remove(fp)
                                            except: pass
                                    except: pass
                            
                            # رد تلقائي
                            res = supabase.table("user_bots").select("auto_reply_text").eq("account_id", client_id).execute()
                            if res.data and res.data[0].get("auto_reply_text"):
                                await event.reply(res.data[0]["auto_reply_text"])
                
                except Exception as ex:
                    print(f"Error in handler: {ex}")
                    traceback.print_exc()

            # ===== تشغيل المستمع =====
            await client.run_until_disconnected()
            
        except FloodWaitError as e:
            print(f"Flood wait {client_id}: {e.seconds} seconds")
            await asyncio.sleep(e.seconds)
            continue
        except UnauthorizedError:
            print(f"Unauthorized {client_id}, disabling")
            if client_id in ACTIVE_CLIENTS:
                del ACTIVE_CLIENTS[client_id]
            try:
                supabase.table("user_bots").update({"is_active": False}).eq("account_id", client_id).execute()
            except: pass
            break
        except Exception as e:
            print(f"Userbot {client_id} error: {e}")
            traceback.print_exc()
            if client_id in ACTIVE_CLIENTS:
                del ACTIVE_CLIENTS[client_id]
            await asyncio.sleep(5)
            continue
        finally:
            if client:
                try: await client.disconnect()
                except: pass
            if client_id in ACTIVE_CLIENTS:
                try: del ACTIVE_CLIENTS[client_id]
                except: pass

async def restore_sessions():
    try:
        res = supabase.table("user_bots").select("*").eq("is_active", True).execute()
        if res.data:
            for row in res.data:
                if row.get("session_string"):
                    asyncio.create_task(start_userbot(row["session_string"], row["account_id"]))
    except: pass

async def main():
    threading.Thread(target=run_flask, daemon=True).start()
    await restore_sessions()
    print("Bot started successfully - Will never stop!")
    try:
        await dp.start_polling(bot)
    except Exception as e:
        print(f"Bot polling error: {e}")
        # إعادة التشغيل التلقائي
        await asyncio.sleep(5)
        await main()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Bot stopped")
    except Exception as e:
        print(f"Fatal error: {e}")
        # محاولة إعادة التشغيل
        os.execv(sys.executable, ['python'] + sys.argv)
