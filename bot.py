import os
import random
import asyncio
import datetime
import json
import re
import sys
import traceback
from telethon import TelegramClient, events, functions
from telethon.sessions import StringSession
from telethon.tl.types import MessageMediaPhoto, MessageMediaDocument
from telethon.errors import FloodWaitError
from supabase import create_client, Client

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
BUSY_MODE = {}
BUSY_MESSAGE = {}

# ==================== نظام الاشتراك ====================
SUBSCRIPTIONS = {}
FREE_TRIAL_DAYS = 30

def check_subscription(user_id):
    if user_id == DEV_ID:
        return True, "مطور", None
    
    if user_id not in SUBSCRIPTIONS:
        return False, "غير مشترك", None
    
    sub = SUBSCRIPTIONS[user_id]
    end_date = datetime.datetime.fromisoformat(sub["end_date"])
    
    if datetime.datetime.now() < end_date:
        days_left = (end_date - datetime.datetime.now()).days
        return True, f"مشترك متبقي {days_left} يوم", days_left
    else:
        return False, "انتهى الاشتراك", None

def create_free_trial(user_id):
    now = datetime.datetime.now()
    end_date = now + datetime.timedelta(days=FREE_TRIAL_DAYS)
    
    SUBSCRIPTIONS[user_id] = {
        "start_date": now.isoformat(),
        "end_date": end_date.isoformat(),
        "status": "active"
    }
    
    try:
        supabase.table("subscriptions").upsert({
            "user_id": user_id,
            "start_date": now.isoformat(),
            "end_date": end_date.isoformat(),
            "status": "active",
            "is_free_trial": True
        }, on_conflict="user_id").execute()
    except:
        pass
    
    return end_date

# ==================== نظام التخصيص ====================
CUSTOM_SETTINGS = {}

CUSTOM_OPTIONS = {
    "اسم البوت": "بوتي",
    "رسالة الترحيب": "مرحباً",
    "رسالة الوداع": "وداعاً",
    "الردود التلقائية": True
}

# ==================== الاقفال ====================
LOCKS = {
    'photos': {},
    'videos': {},
    'stickers': {},
    'links': {},
    'audio': {},
    'forwards': {},
    'files': {},
    'gifs': {},
    'numbers': {},
    'english': {},
    'private': {},
    'webpage': {},
    'hashtag': {},
    'mention': {}
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

def get_user_setting(user_id, setting, default=None):
    if user_id in CUSTOM_SETTINGS:
        return CUSTOM_SETTINGS[user_id].get(setting, default)
    return default

def set_user_setting(user_id, setting, value):
    if user_id not in CUSTOM_SETTINGS:
        CUSTOM_SETTINGS[user_id] = {}
    CUSTOM_SETTINGS[user_id][setting] = value
    try:
        supabase.table("user_settings").upsert({
            "user_id": user_id,
            "settings": CUSTOM_SETTINGS[user_id]
        }, on_conflict="user_id").execute()
    except:
        pass

# ==================== كيبوردات ====================
def get_main_menu_keyboard(user_id):
    kb = []
    is_installed, _ = is_user_installed(user_id)
    is_subscribed, sub_status, days_left = check_subscription(user_id)
    
    status_text = "مشترك" if is_subscribed else "غير مشترك"
    if days_left:
        status_text = f"متبقي {days_left} يوم"
    
    if is_installed:
        kb.append([types.InlineKeyboardButton(text="لوحة التحكم", callback_data="my_settings")])
        kb.append([types.InlineKeyboardButton(text="تخصيص البوت", callback_data="custom_settings")])
        kb.append([types.InlineKeyboardButton(text=f"الاشتراك: {status_text}", callback_data="subscription_status")])
        kb.append([types.InlineKeyboardButton(text="حذف التنصيب", callback_data="delete_install")])
        kb.append([types.InlineKeyboardButton(text="الاوامر", callback_data="bot_instructions")])
    else:
        kb.append([types.InlineKeyboardButton(text="تفعيل مجاني شهر", callback_data="free_subscription")])
        kb.append([types.InlineKeyboardButton(text="الاوامر", callback_data="bot_instructions")])
    
    kb.append([types.InlineKeyboardButton(text="المطور", url=f"https://t.me/{DEV_USER.replace('@','')}")])
    
    if user_id == DEV_ID:
        kb.append([types.InlineKeyboardButton(text="لوحة المطور", callback_data="dev_admin_panel")])
    
    return types.InlineKeyboardMarkup(inline_keyboard=kb)

def get_control_panel_keyboard(bot_info):
    archive_st = "مفعل" if safe_get(bot_info, "archive_enabled", False) else "متوقف"
    save_st = "مفعل" if safe_get(bot_info, "save_media_enabled", True) else "متوقف"
    clock_st = "مفعل" if safe_get(bot_info, "clock_enabled", True) else "متوقف"

    kb = []
    kb.append([types.InlineKeyboardButton(text="الكتم والحظر", callback_data="mute_ban_menu")])
    kb.append([types.InlineKeyboardButton(text="اقفال الحماية", callback_data="locks_menu")])
    kb.append([types.InlineKeyboardButton(text=f"الارشيف: {archive_st}", callback_data="toggle_archive")])
    kb.append([types.InlineKeyboardButton(text=f"حفظ الوسائط: {save_st}", callback_data="toggle_save_media")])
    kb.append([types.InlineKeyboardButton(text=f"الساعة: {clock_st}", callback_data="toggle_clock")])
    kb.append([types.InlineKeyboardButton(text="تخصيص البوت", callback_data="custom_settings")])
    kb.append([types.InlineKeyboardButton(text="الاشتراك", callback_data="subscription_status")])
    kb.append([types.InlineKeyboardButton(text="الاوامر", callback_data="bot_instructions")])
    kb.append([types.InlineKeyboardButton(text="تحديث", callback_data="refresh_bot")])
    kb.append([types.InlineKeyboardButton(text="حذف التنصيب", callback_data="delete_install")])
    kb.append([types.InlineKeyboardButton(text="الرئيسية", callback_data="main_menu")])
    
    return types.InlineKeyboardMarkup(inline_keyboard=kb)

def get_custom_settings_keyboard(user_id):
    kb = []
    
    for setting, default in CUSTOM_OPTIONS.items():
        current = get_user_setting(user_id, setting, default)
        if isinstance(current, bool):
            status = "مفعل" if current else "متوقف"
            kb.append([types.InlineKeyboardButton(
                text=f"{setting}: {status}",
                callback_data=f"custom_toggle_{setting}"
            )])
        else:
            kb.append([types.InlineKeyboardButton(
                text=f"{setting}: {current}",
                callback_data=f"custom_set_{setting}"
            )])
    
    kb.append([types.InlineKeyboardButton(text="استعادة الافتراضي", callback_data="custom_reset")])
    kb.append([types.InlineKeyboardButton(text="رجوع", callback_data="my_settings")])
    
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

# ==================== الاشتراك ====================
@dp.callback_query(F.data == "free_subscription")
async def free_subscription(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    
    is_subscribed, status, _ = check_subscription(user_id)
    if is_subscribed:
        await callback.answer(f"انت مشترك بالفعل")
        return
    
    end_date = create_free_trial(user_id)
    await callback.answer("تم تفعيل الاشتراك المجاني لمدة شهر")
    await callback.message.edit_text(
        f"تم تفعيل الاشتراك المجاني بنجاح\n\n"
        f"ينتهي في: {end_date.strftime('%Y-%m-%d')}\n"
        f"يمكنك الان تنصيب البوت من القائمة الرئيسية",
        reply_markup=get_main_menu_keyboard(user_id)
    )

@dp.callback_query(F.data == "subscription_status")
async def subscription_status(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    is_subscribed, status, days_left = check_subscription(user_id)
    
    text = "حالة الاشتراك:\n\n"
    if is_subscribed:
        text += f"الحالة: {status}\n"
        if days_left:
            text += f"متبقي: {days_left} يوم\n"
    else:
        text += f"الحالة: {status}\n"
        text += "يمكنك تفعيل الاشتراك المجاني لمدة شهر من القائمة الرئيسية"
    
    await callback.message.edit_text(
        text,
        reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[
            [types.InlineKeyboardButton(text="رجوع", callback_data="my_settings")]
        ])
    )
    await callback.answer()

# ==================== التخصيص ====================
@dp.callback_query(F.data == "custom_settings")
async def custom_settings(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    await callback.message.edit_text(
        "تخصيص البوت:",
        reply_markup=get_custom_settings_keyboard(user_id)
    )
    await callback.answer()

@dp.callback_query(F.data.startswith("custom_set_"))
async def custom_set(callback: types.CallbackQuery, state: FSMContext):
    setting = callback.data.replace("custom_set_", "")
    user_id = callback.from_user.id
    
    if setting in ["اسم البوت", "رسالة الترحيب", "رسالة الوداع"]:
        await callback.message.answer(f"ارسل قيمة جديدة لـ {setting}:")
        await state.set_state(f"waiting_{setting}")
        await callback.answer()

@dp.callback_query(F.data.startswith("custom_toggle_"))
async def custom_toggle(callback: types.CallbackQuery):
    setting = callback.data.replace("custom_toggle_", "")
    user_id = callback.from_user.id
    
    current = get_user_setting(user_id, setting, True)
    set_user_setting(user_id, setting, not current)
    
    await callback.answer(f"تم {'تفعيل' if not current else 'ايقاف'} {setting}")
    await custom_settings(callback)

@dp.callback_query(F.data == "custom_reset")
async def custom_reset(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    
    if user_id in CUSTOM_SETTINGS:
        del CUSTOM_SETTINGS[user_id]
    
    try:
        supabase.table("user_settings").delete().eq("user_id", user_id).execute()
    except:
        pass
    
    await callback.answer("تم استعادة الاعدادات الافتراضية")
    await custom_settings(callback)

@dp.message(lambda m: m.text)
async def handle_custom_text(message: types.Message, state: FSMContext):
    current_state = await state.get_state()
    if not current_state or not current_state.startswith("waiting_"):
        return
    
    setting = current_state.replace("waiting_", "")
    user_id = message.from_user.id
    value = message.text.strip()
    
    set_user_setting(user_id, setting, value)
    await message.answer(f"تم تعيين {setting} = {value}")
    await state.clear()
    await custom_settings(message)

# ==================== تنصيب البوت ====================
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    print(f"✅ Start received from {message.from_user.id}")
    user_id = message.from_user.id
    is_installed, bot_info = is_user_installed(user_id)
    
    if is_installed and bot_info:
        await message.answer("لوحة التحكم", reply_markup=get_control_panel_keyboard(bot_info))
        return
    
    is_subscribed, status, _ = check_subscription(user_id)
    if is_subscribed:
        await message.answer(
            f"مرحباً بك\nاشتراكك نشط: {status}\n\n"
            "يمكنك تنصيب البوت من القائمة",
            reply_markup=get_main_menu_keyboard(user_id)
        )
    else:
        await message.answer(
            "مرحباً بك\n\n"
            "يمكنك تفعيل الاشتراك المجاني لمدة شهر اولاً",
            reply_markup=get_main_menu_keyboard(user_id)
        )

@dp.message(Command("test"))
async def test_bot(message: types.Message):
    await message.answer("✅ البوت شغال!")

@dp.callback_query(F.data == "free_subscription_install")
async def free_subscription_install(callback: types.CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    
    is_subscribed, status, _ = check_subscription(user_id)
    if not is_subscribed:
        await callback.answer("يجب تفعيل الاشتراك اولاً")
        return
    
    is_installed, _ = is_user_installed(user_id)
    if is_installed:
        await callback.answer("انت منصب بالفعل")
        return
    
    await callback.answer("جاري التفعيل")
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
    await callback.message.answer(
        "اضغط مشاركة رقم الهاتف للبدء",
        reply_markup=contact_kb
    )
    await state.set_state(LoginState.waiting_for_phone)

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
        await message.answer("ارسل الرمز", reply_markup=types.ReplyKeyboardRemove())
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
            "is_approved": True, "archive_enabled": False
        }
        supabase.table("user_bots").upsert(bot_data, on_conflict="user_id").execute()
        await message.answer(
            f"تم التنصيب\nالاسم: {me.first_name}",
            reply_markup=get_control_panel_keyboard(bot_data)
        )
        asyncio.create_task(start_userbot(session_str, me.id))
        await client.disconnect()
        await state.clear()
    except Exception as e:
        if "Password" in str(e):
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
            "is_approved": True, "archive_enabled": False
        }
        supabase.table("user_bots").upsert(bot_data, on_conflict="user_id").execute()
        await message.answer(
            f"تم التفعيل\nالاسم: {me.first_name}",
            reply_markup=get_control_panel_keyboard(bot_data)
        )
        asyncio.create_task(start_userbot(session_str, me.id))
        await client.disconnect()
        await state.clear()
    except Exception as e:
        await message.answer(f"خطأ: {e}")
        try: await client.disconnect()
        except: pass
        await state.clear()

# ==================== الاوامر ====================
@dp.callback_query(F.data == "bot_instructions")
async def bot_instructions(callback: types.CallbackQuery):
    text = (
        "قائمة الاوامر:\n\n"
        "اوامر الترفيه:\n"
        "غنيلي - شعر - مزج - ميمز - قرآن\n"
        "يوت اسم\n\n"
        "الكتم والحظر:\n"
        "كتم / فك كتم\n"
        "حظر / فك حظر\n\n"
        "الاقفال:\n"
        "قفل/فتح صور/فيديو/ملصقات/روابط/صوت/توجيه\n"
        "قفل/فتح ملفات/متحركة/ارقام/انجليزي/خاص/ويب/هاشتاق/منشن\n\n"
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
        "حالتي\n"
        "احصائياتي\n"
        "فحص"
    )
    await callback.message.edit_text(
        text,
        reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[
            [types.InlineKeyboardButton(text="رجوع", callback_data="main_menu")]
        ])
    )
    await callback.answer()

# ==================== لوحة التحكم ====================
@dp.callback_query(F.data == "my_settings")
async def settings_menu(callback: types.CallbackQuery):
    uid = callback.from_user.id
    is_installed, bot_info = is_user_installed(uid)
    if not is_installed:
        await callback.answer("يجب التنصيب اولاً")
        return
    await callback.message.edit_text(
        "لوحة التحكم:",
        reply_markup=get_control_panel_keyboard(bot_info)
    )
    await callback.answer()

@dp.callback_query(F.data == "main_menu")
async def back_to_main(callback: types.CallbackQuery):
    await callback.message.edit_text(
        "القائمة الرئيسية:",
        reply_markup=get_main_menu_keyboard(callback.from_user.id)
    )
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
    await callback.message.edit_text("متاكد من حذف التنصيب؟", reply_markup=kb)
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
    await callback.message.edit_text(
        "تم حذف التنصيب",
        reply_markup=get_main_menu_keyboard(uid)
    )
    await callback.answer()

# ==================== الاقفال ====================
@dp.callback_query(F.data == "locks_menu")
async def locks_menu(callback: types.CallbackQuery):
    uid = callback.from_user.id
    await callback.message.edit_text(
        "اقفال الحماية:",
        reply_markup=get_locks_keyboard(uid)
    )
    await callback.answer()

@dp.callback_query(F.data.startswith("toggle_lock_"))
async def toggle_lock(callback: types.CallbackQuery):
    lock_type = callback.data.replace("toggle_lock_", "")
    uid = callback.from_user.id
    LOCKS[lock_type][uid] = not LOCKS[lock_type].get(uid, False)
    await locks_menu(callback)

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
    await state.set_state("waiting_for_mute_user_id")
    await callback.answer()

@dp.callback_query(F.data == "unmute_user")
async def unmute_user(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer("ارسل ايدي او @يوزر:")
    await state.set_state("waiting_for_unmute_user_id")
    await callback.answer()

@dp.callback_query(F.data == "ban_user")
async def ban_user(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer("ارسل ايدي او @يوزر:")
    await state.set_state("waiting_for_ban_user_id")
    await callback.answer()

@dp.callback_query(F.data == "unban_user")
async def unban_user(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer("ارسل ايدي او @يوزر:")
    await state.set_state("waiting_for_unban_user_id")
    await callback.answer()

@dp.message(lambda m: m.text)
async def handle_mute_ban(message: types.Message, state: FSMContext):
    current_state = await state.get_state()
    if not current_state:
        return
    
    target = message.text.strip()
    uid = message.from_user.id
    
    if current_state == "waiting_for_mute_user_id":
        supabase.table("muted_users").upsert({"user_id": uid, "muted_user_id": target}, on_conflict="user_id,muted_user_id").execute()
        MUTED_USERS_CACHE.setdefault(uid, set()).add(target)
        await message.answer(f"تم كتم: {target}")
        await state.clear()
    
    elif current_state == "waiting_for_unmute_user_id":
        MUTED_USERS_CACHE.get(uid, set()).discard(target)
        supabase.table("muted_users").delete().eq("user_id", uid).eq("muted_user_id", target).execute()
        await message.answer(f"تم فك كتم: {target}")
        await state.clear()
    
    elif current_state == "waiting_for_ban_user_id":
        supabase.table("banned_users").upsert({"user_id": uid, "banned_user_id": target}, on_conflict="user_id,banned_user_id").execute()
        BANNED_USERS_CACHE.setdefault(uid, set()).add(target)
        await message.answer(f"تم حظر: {target}")
        await state.clear()
    
    elif current_state == "waiting_for_unban_user_id":
        BANNED_USERS_CACHE.get(uid, set()).discard(target)
        supabase.table("banned_users").delete().eq("user_id", uid).eq("banned_user_id", target).execute()
        await message.answer(f"تم فك حظر: {target}")
        await state.clear()

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
    MUTED_USERS_CACHE.get(uid, set()).discard(target)
    supabase.table("muted_users").delete().eq("user_id", uid).eq("muted_user_id", target).execute()
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
    BANNED_USERS_CACHE.get(uid, set()).discard(target)
    supabase.table("banned_users").delete().eq("user_id", uid).eq("banned_user_id", target).execute()
    await list_banned(callback)

# ==================== تبديلات بسيطة ====================
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
    await callback.answer("تم التبديل")
    await settings_menu(callback)

@dp.callback_query(F.data == "toggle_clock")
async def toggle_clock(callback: types.CallbackQuery):
    uid = callback.from_user.id
    res = supabase.table("user_bots").select("clock_enabled").or_(f"user_id.eq.{uid},account_id.eq.{uid}").execute()
    if res.data:
        cur = res.data[0].get("clock_enabled", True)
        supabase.table("user_bots").update({"clock_enabled": not cur}).or_(f"user_id.eq.{uid},account_id.eq.{uid}").execute()
    await callback.answer("تم التبديل")
    await settings_menu(callback)

# ==================== لوحة المطور ====================
@dp.callback_query(F.data == "dev_admin_panel")
async def dev_admin_panel(callback: types.CallbackQuery):
    if callback.from_user.id != DEV_ID:
        await callback.answer("مخصص للمطور")
        return
    res = supabase.table("user_bots").select("*").execute()
    sub_res = supabase.table("subscriptions").select("*").execute()
    
    kb = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="المستخدمين", callback_data="dev_list_users"),
         types.InlineKeyboardButton(text="الاحصائيات", callback_data="dev_stats")],
        [types.InlineKeyboardButton(text="الاشتراكات", callback_data="dev_subscriptions")],
        [types.InlineKeyboardButton(text="تشغيل الكل", callback_data="dev_start_all")],
        [types.InlineKeyboardButton(text="الرئيسية", callback_data="main_menu")]
    ])
    await callback.message.edit_text(
        f"لوحة المطور\n\n"
        f"المستخدمين: {len(res.data) if res.data else 0}\n"
        f"يعملون: {len(ACTIVE_CLIENTS)}\n"
        f"الاشتراكات: {len(sub_res.data) if sub_res.data else 0}",
        reply_markup=kb
    )
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
    sub_res = supabase.table("subscriptions").select("*").execute()
    await callback.message.edit_text(
        f"الاحصائيات:\n"
        f"الاجمالي: {len(res.data) if res.data else 0}\n"
        f"يعملون: {len(ACTIVE_CLIENTS)}\n"
        f"الاشتراكات: {len(sub_res.data) if sub_res.data else 0}",
        reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[
            [types.InlineKeyboardButton(text="رجوع", callback_data="dev_admin_panel")]
        ])
    )
    await callback.answer()

@dp.callback_query(F.data == "dev_subscriptions")
async def dev_subscriptions(callback: types.CallbackQuery):
    res = supabase.table("subscriptions").select("*").execute()
    if not res.data:
        await callback.message.edit_text("لا يوجد اشتراكات")
    else:
        text = "الاشتراكات:\n\n"
        for row in res.data[:10]:
            text += f"المستخدم: {row['user_id']}\n"
            text += f"ينتهي: {row['end_date'][:10]}\n"
            text += f"الحالة: {row['status']}\n\n"
        await callback.message.edit_text(
            text,
            reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[
                [types.InlineKeyboardButton(text="رجوع", callback_data="dev_admin_panel")]
            ])
        )
    await callback.answer()

# ==================== اليوزربوت ====================
async def load_channel_messages(client, chan, cat, cid):
    try:
        msgs = []
        async for m in client.iter_messages(chan, limit=100):
            if m.text or m.media:
                msgs.append(m)
        CLIENT_CONTENTS.setdefault(cid, {})[cat] = msgs
    except: pass

async def start_userbot(session_str, client_id):
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
                    
                    if is_private:
                        for cmd in CHANNELS_MAP:
                            if text_raw == cmd:
                                try: await event.delete()
                                except: pass
                                msgs = CLIENT_CONTENTS.get(client_id, {}).get(cmd, [])
                                if msgs:
                                    s = random.choice(msgs)
                                    try:
                                        if s.media:
                                            await client.send_file(chat_id, s.media, caption=s.text or "")
                                        elif s.text:
                                            await client.send_message(chat_id, s.text)
                                    except: pass
                                return
                        
                        if text_lower.startswith("يوت "):
                            q = text_raw[4:].strip()
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
                        
                        if text_raw == "مشغول":
                            BUSY_MODE[client_id] = True
                            BUSY_MESSAGE[client_id] = "مشغول"
                            await event.respond("تم")
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
                        
                        if text_raw == "حالتي":
                            me = await client.get_me()
                            await event.respond(f"الاسم: {me.first_name}\nالايدي: {me.id}")
                            return
                        
                        if text_raw == "فحص":
                            await event.respond("الحساب شغال")
                            return
                        
                        if text_raw == "احصائياتي":
                            await event.respond(f"المكتمين: {len(MUTED_USERS_CACHE.get(client_id, set()))}\nالمحظورين: {len(BANNED_USERS_CACHE.get(client_id, set()))}")
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
                            
                            if LOCKS.get('photos', {}).get(client_id) and isinstance(msg_media, MessageMediaPhoto):
                                try: await event.delete()
                                except: pass
                                return
                            if LOCKS.get('videos', {}).get(client_id) and isinstance(msg_media, MessageMediaDocument):
                                doc = msg_media.document
                                if doc and doc.mime_type and "video" in doc.mime_type:
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
                            if LOCKS.get('webpage', {}).get(client_id) and isinstance(msg_media, MessageMediaDocument):
                                doc = msg_media.document
                                if doc and doc.mime_type and "webpage" in doc.mime_type:
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
                
                except Exception as ex:
                    pass

            await client.run_until_disconnected()
            
        except FloodWaitError as e:
            await asyncio.sleep(e.seconds)
            continue
        except Exception as e:
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
    # منع التعارض - حذف الويب هوك
    try:
        await bot.delete_webhook(drop_pending_updates=True)
        print("✅ Webhook cleared")
    except Exception as e:
        print(f"⚠️ Webhook error: {e}")
    
    # استعادة الجلسات
    await restore_sessions()
    
    print("✅ Bot started successfully!")
    
    # بدء البولينغ
    try:
        await dp.start_polling(bot)
    except Exception as e:
        print(f"❌ Polling error: {e}")
        await asyncio.sleep(5)
        await main()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Bot stopped")
    except Exception as e:
        print(f"❌ Fatal error: {e}")
        asyncio.run(main())
