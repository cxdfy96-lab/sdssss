import os
import random
import asyncio
import datetime
import json
import re
import signal
from telethon import TelegramClient, events, functions
from telethon.sessions import StringSession
from telethon.tl.types import MessageMediaPhoto, MessageMediaDocument
from telethon.errors import FloodWaitError
from supabase import create_client, Client

# ==================== الإعدادات ====================
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

LOCK_PHOTOS = {}
LOCK_VIDEOS = {}
LOCK_STICKERS = {}
LOCK_LINKS = {}
LOCK_FILES = {}
LOCK_AUDIO = {}
LOCK_GIFS = {}
LOCK_FORWARDS = {}
LOCK_NUMBERS = {}
LOCK_ENGLISH = {}

BUSY_MODE = {}
BUSY_MESSAGE = {}

CLOCK_FONTS = {
    "circle": ("0123456789", "⓪①②③④⑤⑥⑦⑧⑨"),
    "bold": ("0123456789", "𝟎𝟏𝟐𝟑𝟒𝟓𝟔𝟕𝟖𝟗"),
    "sans": ("0123456789", "𝟶𝟷𝟸𝟹𝟺𝟻𝟼𝟽𝟾𝟿"),
    "normal": ("0123456789", "0123456789")
}

# ==================== بوت الإدارة ====================
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

def get_main_menu_keyboard(user_id):
    kb = []
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

    kb = [
        [types.InlineKeyboardButton(text="الكتم والحظر", callback_data="mute_ban_menu")],
        [types.InlineKeyboardButton(text=f"الارشيف: {archive_st}", callback_data="toggle_archive")],
        [types.InlineKeyboardButton(text="اقفال الحماية", callback_data="locks_menu")],
        [types.InlineKeyboardButton(text=f"حفظ الوسائط الوقتية: {save_st}", callback_data="toggle_save_media"),
         types.InlineKeyboardButton(text=f"الساعة: {clock_st}", callback_data="toggle_clock")],
        [types.InlineKeyboardButton(text="الاوامر", callback_data="bot_instructions"),
         types.InlineKeyboardButton(text="تحديث", callback_data="refresh_bot")],
        [types.InlineKeyboardButton(text="حذف التنصيب", callback_data="delete_install"),
         types.InlineKeyboardButton(text="الرئيسية", callback_data="main_menu")]
    ]
    return types.InlineKeyboardMarkup(inline_keyboard=kb)

async def is_user_admin(client, chat_id, user_id):
    try:
        p = await client.get_permissions(chat_id, user_id)
        return p.is_admin or p.is_creator or (hasattr(p, 'admin_rights') and p.admin_rights)
    except:
        return False

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
        "اوامر الترفيه - للكل:\n- غنيلي - شعر - مزج - ميمز - قرآن\n- يوت اسم\n\n"
        "الكتم والحظر:\n- كتم / فك كتم\n- كتم ايدي / @يوزر\n- حظر / فك حظر\n- حظر ايدي / @يوزر\n\n"
        "الاقفال:\n- قفل صور/فيديو/ملصقات/روابط/ملفات/صوت/متحركة/توجيه/ارقام/انجليزي\n"
        "- فتح صور/فيديو/ملصقات/روابط/ملفات/صوت/متحركة/توجيه/ارقام/انجليزي\n\n"
        "الارسال:\n- كرر عدد نص\n- اذاعة نص\n- بعد ثواني نص\n\n"
        "الحالة:\n- مشغول / متاح\n\n"
        "الحساب:\n- تعيين صورة (رد)\n- حذف صورة\n- تغيير اسم\n- تغيير بايو\n- احصائياتي\n- حالتي\n- فحص"
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
    await callback.message.edit_text(f"المستخدمين: {len(res.data) if res.data else 0}\nيعملون: {len(ACTIVE_CLIENTS)}", reply_markup=kb)
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
    await callback.message.edit_text(f"الاجمالي: {len(res.data) if res.data else 0}\nيعملون: {len(ACTIVE_CLIENTS)}",
        reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[
            [types.InlineKeyboardButton(text="رجوع", callback_data="dev_admin_panel")]
        ]))
    await callback.answer()

# ==================== الكتم والحظر ====================
@dp.callback_query(F.data == "mute_ban_menu")
async def mute_ban_menu(callback: types.CallbackQuery):
    kb = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="كتم", callback_data="mute_user"),
         types.InlineKeyboardButton(text="حظر", callback_data="ban_user")],
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

@dp.callback_query(F.data == "list_muted")
async def list_muted(callback: types.CallbackQuery):
    uid = callback.from_user.id
    res = supabase.table("muted_users").select("*").eq("user_id", uid).execute()
    if not res.data:
        await callback.message.edit_text("لا يوجد", reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[
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
        await callback.message.edit_text("لا يوجد", reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[
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

# ==================== الأقفال ====================
@dp.callback_query(F.data == "locks_menu")
async def locks_menu(callback: types.CallbackQuery):
    uid = callback.from_user.id
    kb = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text=f"صور: {'مقفل' if LOCK_PHOTOS.get(uid) else 'مفتوح'}", callback_data="toggle_lock_photos"),
         types.InlineKeyboardButton(text=f"فيديو: {'مقفل' if LOCK_VIDEOS.get(uid) else 'مفتوح'}", callback_data="toggle_lock_videos")],
        [types.InlineKeyboardButton(text=f"ملصقات: {'مقفل' if LOCK_STICKERS.get(uid) else 'مفتوح'}", callback_data="toggle_lock_stickers"),
         types.InlineKeyboardButton(text=f"روابط: {'مقفل' if LOCK_LINKS.get(uid) else 'مفتوح'}", callback_data="toggle_lock_links")],
        [types.InlineKeyboardButton(text=f"صوت: {'مقفل' if LOCK_AUDIO.get(uid) else 'مفتوح'}", callback_data="toggle_lock_audio"),
         types.InlineKeyboardButton(text=f"توجيه: {'مقفل' if LOCK_FORWARDS.get(uid) else 'مفتوح'}", callback_data="toggle_lock_forwards")],
        [types.InlineKeyboardButton(text="رجوع", callback_data="my_settings")]
    ])
    await callback.message.edit_text("الأقفال:", reply_markup=kb)
    await callback.answer()

@dp.callback_query(F.data == "toggle_lock_photos")
async def tlp(callback: types.CallbackQuery):
    LOCK_PHOTOS[callback.from_user.id] = not LOCK_PHOTOS.get(callback.from_user.id, False)
    await locks_menu(callback)

@dp.callback_query(F.data == "toggle_lock_videos")
async def tlv(callback: types.CallbackQuery):
    LOCK_VIDEOS[callback.from_user.id] = not LOCK_VIDEOS.get(callback.from_user.id, False)
    await locks_menu(callback)

@dp.callback_query(F.data == "toggle_lock_stickers")
async def tls(callback: types.CallbackQuery):
    LOCK_STICKERS[callback.from_user.id] = not LOCK_STICKERS.get(callback.from_user.id, False)
    await locks_menu(callback)

@dp.callback_query(F.data == "toggle_lock_links")
async def tll(callback: types.CallbackQuery):
    LOCK_LINKS[callback.from_user.id] = not LOCK_LINKS.get(callback.from_user.id, False)
    await locks_menu(callback)

@dp.callback_query(F.data == "toggle_lock_audio")
async def tla(callback: types.CallbackQuery):
    LOCK_AUDIO[callback.from_user.id] = not LOCK_AUDIO.get(callback.from_user.id, False)
    await locks_menu(callback)

@dp.callback_query(F.data == "toggle_lock_forwards")
async def tlf(callback: types.CallbackQuery):
    LOCK_FORWARDS[callback.from_user.id] = not LOCK_FORWARDS.get(callback.from_user.id, False)
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

# ==================== مراقب الحالة - كل ثانية ====================
async def keep_alive_monitor():
    """مراقبة مستمرة - يتحقق كل 5 ثواني ويعيد التشغيل إذا توقف"""
    while True:
        try:
            # جلب الحسابات النشطة
            res = supabase.table("user_bots").select("*").eq("is_active", True).execute()
            if res.data:
                for row in res.data:
                    if row.get("session_string"):
                        aid = row.get("account_id")
                        # إذا الحساب مو شغال - شغله
                        if aid not in ACTIVE_CLIENTS:
                            print(f"Restarting userbot: {aid}")
                            asyncio.create_task(start_userbot(row["session_string"], aid))
            
            # التحقق من العملاء النشطين
            for aid, client in list(ACTIVE_CLIENTS.items()):
                if not client.is_connected():
                    print(f"Reconnecting: {aid}")
                    try:
                        await client.connect()
                    except:
                        del ACTIVE_CLIENTS[aid]
                        # إعادة تشغيل
                        res2 = supabase.table("user_bots").select("session_string").eq("account_id", aid).execute()
                        if res2.data and res2.data[0].get("session_string"):
                            asyncio.create_task(start_userbot(res2.data[0]["session_string"], aid))
            
        except Exception as e:
            print(f"Monitor error: {e}")
        
        await asyncio.sleep(5)  # كل 5 ثواني

# ==================== تشغيل اليوزربوت ====================
async def load_channel_messages(client, chan, cat, cid):
    try:
        msgs = []
        async for m in client.iter_messages(chan, limit=100):
            if m.text or m.media:
                msgs.append(m)
        CLIENT_CONTENTS.setdefault(cid, {})[cat] = msgs
    except: pass

async def start_userbot(session_str, client_id):
    """لا يتوقف أبداً - مع مراقب خارجي"""
    while True:
        client = None
        try:
            client = TelegramClient(StringSession(session_str), API_ID, API_HASH)
            await client.start()
            ACTIVE_CLIENTS[client_id] = client
            
            for cat, chan in CHANNELS_MAP.items():
                asyncio.create_task(load_channel_messages(client, chan, cat, client_id))
            
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
                    
                    # ===== أوامر الترفيه - للكل =====
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
                    
                    # ===== أوامر المنصب =====
                    if is_outgoing:
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
                            "قفل صور": (LOCK_PHOTOS, "الصور"), "فتح صور": (LOCK_PHOTOS, "الصور"),
                            "قفل فيديو": (LOCK_VIDEOS, "الفيديو"), "فتح فيديو": (LOCK_VIDEOS, "الفيديو"),
                            "قفل ملصقات": (LOCK_STICKERS, "الملصقات"), "فتح ملصقات": (LOCK_STICKERS, "الملصقات"),
                            "قفل روابط": (LOCK_LINKS, "الروابط"), "فتح روابط": (LOCK_LINKS, "الروابط"),
                            "قفل صوت": (LOCK_AUDIO, "الصوت"), "فتح صوت": (LOCK_AUDIO, "الصوت"),
                            "قفل توجيه": (LOCK_FORWARDS, "التوجيه"), "فتح توجيه": (LOCK_FORWARDS, "التوجيه"),
                            "قفل ارقام": (LOCK_NUMBERS, "الارقام"), "فتح ارقام": (LOCK_NUMBERS, "الارقام"),
                            "قفل انجليزي": (LOCK_ENGLISH, "الانجليزي"), "فتح انجليزي": (LOCK_ENGLISH, "الانجليزي"),
                        }
                        if text_raw in locks_map:
                            lock_dict, name = locks_map[text_raw]
                            lock_dict[client_id] = text_raw.startswith("قفل")
                            await event.respond(f"تم {'قفل' if text_raw.startswith('قفل') else 'فتح'} {name}")
                            return
                        
                        if text_lower.startswith("مشغول"):
                            BUSY_MODE[client_id] = True
                            BUSY_MESSAGE[client_id] = text_raw[6:].strip() if len(text_raw) > 6 else "مشغول"
                            await event.respond("تم تفعيل المشغول")
                            return
                        if text_raw == "متاح":
                            BUSY_MODE[client_id] = False
                            await event.respond("تم")
                            return
                        
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
                        
                        if text_lower.startswith("اذاعة "):
                            try:
                                bt = text_raw[5:].strip()
                                dialogs = await client.get_dialogs(limit=50)
                                sent = 0
                                for d in dialogs:
                                    if d.is_user:
                                        try:
                                            await client.send_message(d.entity, bt)
                                            sent += 1
                                            await asyncio.sleep(0.5)
                                        except: pass
                                await event.respond(f"تم الارسال: {sent}")
                            except: pass
                            return
                        
                        if text_lower.startswith("بعد "):
                            try:
                                parts = text_raw[4:].strip().split(" ", 2)
                                secs = int(parts[0])
                                msg = parts[2] if len(parts) > 2 else ""
                                async def delayed():
                                    await asyncio.sleep(secs)
                                    await client.send_message(chat_id, msg)
                                asyncio.create_task(delayed())
                                await event.respond(f"سيتم الارسال بعد {secs} ثانية")
                            except: pass
                            return
                        
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
                        
                        if text_raw == "حذف صورة":
                            try:
                                photos = await client.get_profile_photos('me', limit=1)
                                if photos:
                                    await client(functions.photos.DeletePhotosRequest(id=[photos[0]]))
                                    await event.respond("تم")
                            except: pass
                            return
                        
                        if text_lower.startswith("تغيير اسم "):
                            try:
                                await client(functions.account.UpdateProfileRequest(first_name=text_raw[10:].strip()))
                                await event.respond("تم")
                            except: pass
                            return
                        
                        if text_lower.startswith("تغيير بايو "):
                            try:
                                await client(functions.account.UpdateProfileRequest(about=text_raw[11:].strip()))
                                await event.respond("تم")
                            except: pass
                            return
                        
                        if text_raw == "احصائياتي":
                            await event.respond(f"المكتمين: {len(MUTED_USERS_CACHE.get(client_id, set()))}\nالمحظورين: {len(BANNED_USERS_CACHE.get(client_id, set()))}")
                            return
                        
                        if text_raw == "حالتي":
                            me = await client.get_me()
                            await event.respond(f"الاسم: {me.first_name}\nالايدي: {me.id}\nيعمل")
                            return
                        
                        if text_raw == "فحص":
                            await event.respond("الحساب شغال")
                            return
                    
                    # ===== معالجة الوارد =====
                    else:
                        if is_private:
                            sender_id = event.sender_id
                            
                            if BUSY_MODE.get(client_id, False):
                                await event.reply(BUSY_MESSAGE.get(client_id, "مشغول"))
                                return
                            
                            if client_id in MUTED_USERS_CACHE and str(sender_id) in MUTED_USERS_CACHE[client_id]:
                                try: await event.delete()
                                except: pass
                                return
                            
                            if client_id in BANNED_USERS_CACHE and str(sender_id) in BANNED_USERS_CACHE[client_id]:
                                try: await event.delete()
                                except: pass
                                return
                            
                            msg_media = event.message.media
                            text = event.raw_text or ""
                            
                            if LOCK_PHOTOS.get(client_id) and isinstance(msg_media, MessageMediaPhoto):
                                try: await event.delete()
                                except: pass
                                return
                            if LOCK_VIDEOS.get(client_id) and isinstance(msg_media, MessageMediaDocument):
                                doc = msg_media.document
                                if doc and doc.mime_type and "video" in doc.mime_type and "webm" not in doc.mime_type:
                                    try: await event.delete()
                                    except: pass
                                    return
                            if LOCK_STICKERS.get(client_id) and isinstance(msg_media, MessageMediaDocument):
                                doc = msg_media.document
                                if doc and doc.mime_type and "sticker" in doc.mime_type:
                                    try: await event.delete()
                                    except: pass
                                    return
                            if LOCK_LINKS.get(client_id) and ("http" in text or "t.me" in text):
                                try: await event.delete()
                                except: pass
                                return
                            if LOCK_AUDIO.get(client_id) and isinstance(msg_media, MessageMediaDocument):
                                doc = msg_media.document
                                if doc and doc.mime_type and ("audio" in doc.mime_type or "voice" in doc.mime_type):
                                    try: await event.delete()
                                    except: pass
                                    return
                            if LOCK_FORWARDS.get(client_id) and event.message.fwd_from:
                                try: await event.delete()
                                except: pass
                                return
                            if LOCK_NUMBERS.get(client_id) and any(c.isdigit() for c in text):
                                try: await event.delete()
                                except: pass
                                return
                            if LOCK_ENGLISH.get(client_id) and re.search(r'[a-zA-Z]', text):
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
                    pass

            await client.run_until_disconnected()
            
        except FloodWaitError as e:
            await asyncio.sleep(e.seconds)
            continue
        except Exception as e:
            print(f"Userbot {client_id}: {e}")
            if client_id in ACTIVE_CLIENTS:
                del ACTIVE_CLIENTS[client_id]
            await asyncio.sleep(3)
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
    await restore_sessions()
    # تشغيل المراقب
    asyncio.create_task(keep_alive_monitor())
    print("Bot started")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
