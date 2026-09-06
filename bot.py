import os
import random
import asyncio
import datetime
import json
import re
from telethon import TelegramClient, events, functions
from telethon.sessions import StringSession
from telethon.tl.types import MessageMediaPhoto, MessageMediaDocument, DialogFilter, TextWithEntities
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
ARCHIVE_CHANNELS = {}
ARCHIVE_ENABLED = {}
DEFAULT_BAD_WORDS = ["وهابي", "عفن", "سخيف", "كلب", "انقلع"]

LOCK_PHOTOS = {}
LOCK_VIDEOS = {}
LOCK_STICKERS = {}
LOCK_LINKS = {}
LOCK_FILES = {}

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

def safe_get(data_dict, key, default=None):
    if isinstance(data_dict, dict):
        return data_dict.get(key, default)
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
        kb.append([types.InlineKeyboardButton(text="الاوامر والشرح", callback_data="bot_instructions")])
    else:
        kb.append([types.InlineKeyboardButton(text="تفعيل وتنصيب", callback_data="free_subscription")])
        kb.append([types.InlineKeyboardButton(text="الاوامر والشرح", callback_data="bot_instructions")])
    
    kb.append([types.InlineKeyboardButton(text="المطور", url=f"https://t.me/{DEV_USER.replace('@','')}")])
    
    if user_id == DEV_ID:
        kb.append([types.InlineKeyboardButton(text="لوحة المطور", callback_data="dev_admin_panel")])
    
    return types.InlineKeyboardMarkup(inline_keyboard=kb)

def get_control_panel_keyboard(bot_info):
    destroy_st = "مفعل" if safe_get(bot_info, "destroy_messages_enabled", False) else "متوقف"
    spam_st = "مفعل" if safe_get(bot_info, "spam_protection_enabled", False) else "متوقف"
    publish_st = "مفعل" if safe_get(bot_info, "auto_publish_enabled", False) else "متوقف"
    clock_st = "مفعل" if safe_get(bot_info, "clock_enabled", True) else "متوقف"
    filter_st = "مفعل" if safe_get(bot_info, "filter_enabled", True) else "متوقف"
    save_st = "مفعل" if safe_get(bot_info, "save_media_enabled", True) else "متوقف"
    lock_st = "مقفل" if safe_get(bot_info, "lock_private_enabled", False) else "مفتوح"
    current_font = safe_get(bot_info, "clock_font", "circle")
    archive_st = "مفعل" if safe_get(bot_info, "archive_enabled", False) else "متوقف"

    kb = [
        [types.InlineKeyboardButton(text="الكتم والحظر", callback_data="mute_ban_menu")],
        [types.InlineKeyboardButton(text=f"الارشيف: {archive_st}", callback_data="toggle_archive")],
        [types.InlineKeyboardButton(text=f"تدمير الرسائل: {destroy_st}", callback_data="destroy_messages_menu"),
         types.InlineKeyboardButton(text=f"النشر: {publish_st}", callback_data="auto_publish_menu")],
        [types.InlineKeyboardButton(text=f"حماية السبام: {spam_st}", callback_data="toggle_spam"),
         types.InlineKeyboardButton(text=f"قفل الخاص: {lock_st}", callback_data="toggle_lock_private")],
        [types.InlineKeyboardButton(text=f"فلتر الكلمات: {filter_st}", callback_data="toggle_filter"),
         types.InlineKeyboardButton(text=f"الساعة: {clock_st}", callback_data="toggle_clock")],
        [types.InlineKeyboardButton(text=f"حفظ الوسائط الوقتية: {save_st}", callback_data="toggle_save_media"),
         types.InlineKeyboardButton(text=f"الخط: {current_font}", callback_data="choose_font")],
        [types.InlineKeyboardButton(text="اقفال الحماية", callback_data="locks_menu")],
        [types.InlineKeyboardButton(text="الردود التلقائية", callback_data="set_auto_reply"),
         types.InlineKeyboardButton(text="حذف الردود", callback_data="del_auto_reply")],
        [types.InlineKeyboardButton(text="اشتراك اجباري", callback_data="set_forced"),
         types.InlineKeyboardButton(text="ايقافه", callback_data="off_forced")],
        [types.InlineKeyboardButton(text="رسالة الترحيب", callback_data="set_welcome"),
         types.InlineKeyboardButton(text="كلمة محظورة", callback_data="add_bad_word")],
        [types.InlineKeyboardButton(text="الاوامر", callback_data="bot_instructions"),
         types.InlineKeyboardButton(text="تحديث", callback_data="refresh_bot")],
        [types.InlineKeyboardButton(text="حذف التنصيب", callback_data="delete_install"),
         types.InlineKeyboardButton(text="الرئيسية", callback_data="main_menu")]
    ]
    return types.InlineKeyboardMarkup(inline_keyboard=kb)

async def is_user_admin(client, chat_id, user_id):
    try:
        participant = await client.get_permissions(chat_id, user_id)
        if participant.is_admin or participant.is_creator:
            return True
        if hasattr(participant, 'admin_rights') and participant.admin_rights:
            return True
        return False
    except:
        return False

async def resolve_identifier(client, identifier):
    try:
        identifier = str(identifier).strip()
        if identifier.startswith("@"):
            entity = await client.get_entity(identifier)
            return entity.id
        elif identifier.isdigit():
            return int(identifier)
        else:
            entity = await client.get_entity(identifier)
            return entity.id
    except:
        return None

# ==================== زر الأرشيف ====================
@dp.callback_query(F.data == "toggle_archive")
async def toggle_archive(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    
    is_installed, bot_info = is_user_installed(user_id)
    if not is_installed:
        await callback.answer("يجب التنصيب اولاً")
        return
    
    account_id = bot_info.get("account_id")
    
    current = ARCHIVE_ENABLED.get(account_id, False)
    ARCHIVE_ENABLED[account_id] = not current
    
    supabase.table("user_bots").update({"archive_enabled": not current}).eq("account_id", account_id).execute()
    
    await callback.answer(f"الارشيف {'مفعل' if not current else 'متوقف'}")
    await settings_menu(callback)

# ==================== حذف التنصيب ====================
@dp.callback_query(F.data == "delete_install")
async def delete_install(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    
    kb = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="نعم احذف", callback_data="confirm_delete_install")],
        [types.InlineKeyboardButton(text="لا الغي", callback_data="main_menu")]
    ])
    
    await callback.message.edit_text("هل انت متاكد من حذف التنصيب؟", reply_markup=kb)
    await callback.answer()

@dp.callback_query(F.data == "confirm_delete_install")
async def confirm_delete_install(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    
    try:
        res = supabase.table("user_bots").select("*").or_(f"user_id.eq.{user_id},account_id.eq.{user_id}").execute()
        
        if res.data:
            row = res.data[0]
            account_id = row.get("account_id")
            
            if account_id in ACTIVE_CLIENTS:
                try:
                    await ACTIVE_CLIENTS[account_id].disconnect()
                except:
                    pass
                del ACTIVE_CLIENTS[account_id]
            
            supabase.table("user_bots").update({
                "session_string": None,
                "is_active": False
            }).eq("user_id", user_id).execute()
        
        await callback.message.edit_text("تم حذف التنصيب\n\nاضغط /start", reply_markup=get_main_menu_keyboard(user_id))
    except Exception as e:
        print(f"ERROR: {e}")
        await callback.message.answer("خطأ")
    
    await callback.answer()

# ==================== Start ====================
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    user_id = message.from_user.id
    
    is_installed, bot_info = is_user_installed(user_id)
    
    if is_installed and bot_info:
        markup = get_control_panel_keyboard(bot_info)
        await message.answer("لوحة التحكم", reply_markup=markup)
        return
    
    await message.answer(
        "مرحباً بك\n\nاضغط على زر التفعيل للبدء:",
        reply_markup=get_main_menu_keyboard(user_id)
    )

@dp.callback_query(F.data == "free_subscription")
async def free_subscription(callback: types.CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    
    is_installed, _ = is_user_installed(user_id)
    if is_installed:
        await callback.answer("انت منصب بالفعل!")
        await callback.message.answer("انت منصب بالفعل", reply_markup=get_main_menu_keyboard(user_id))
        return
    
    await callback.answer("جاري التفعيل...")
    await state.clear()
    
    try:
        supabase.table("user_bots").upsert({
            "user_id": user_id,
            "is_approved": True,
            "account_id": user_id,
            "is_active": True
        }, on_conflict="user_id").execute()
    except Exception as e:
        print(f"DB ERROR: {e}")
    
    contact_kb = types.ReplyKeyboardMarkup(
        keyboard=[[types.KeyboardButton(text="مشاركة رقم الهاتف", request_contact=True)]],
        resize_keyboard=True,
        one_time_keyboard=True
    )
    
    await callback.message.answer("اضغط زر مشاركة رقم الهاتف او اكتب رقمك", reply_markup=contact_kb)
    await state.set_state(LoginState.waiting_for_phone)

@dp.callback_query(F.data == "bot_instructions")
async def bot_instructions(callback: types.CallbackQuery):
    text = (
        "اوامر الترفيه - تشتغل للكل:\n"
        "- غنيلي - شعر - مزج - ميمز - قرآن\n"
        "- يوت اسم الاغنية\n\n"
        "اوامر المنصب - فقط صاحب الحساب:\n"
        "- كتم - كتم المحادثة\n"
        "- كتم ايدي - كتم بالايدي\n"
        "- كتم @يوزر - كتم باليوزر\n"
        "- فك كتم - فك كتم المحادثة\n"
        "- حظر - حظر المحادثة\n"
        "- حظر ايدي - حظر بالايدي\n"
        "- حظر @يوزر - حظر باليوزر\n"
        "- فك حظر - فك حظر المحادثة\n"
        "- قفل صور / فتح صور\n"
        "- قفل فيديو / فتح فيديو\n"
        "- قفل ملصقات / فتح ملصقات\n"
        "- قفل روابط / فتح روابط\n"
        "- قفل ملفات / فتح ملفات\n"
        "- تعيين صورة (رد على صورة)\n"
        "- حذف صورة\n"
        "- تغيير اسم <الاسم>\n"
        "- تغيير بايو <النص>\n"
        "- احصائياتي\n"
        "- حالتي\n"
        "- فحص\n\n"
        "ملاحظة:\n"
        "اوامر الترفيه تشتغل بالخاص للكل\n"
        "وبالقنوات والجروبات للمشرفين فقط\n"
        "اوامر المنصب تشتغل فقط لصاحب الحساب"
    )
    
    kb = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="رجوع", callback_data="main_menu")]
    ])
    
    await callback.message.edit_text(text, reply_markup=kb)
    await callback.answer()

# ==================== معالجة جهة الاتصال ====================
@dp.message(lambda message: message.contact is not None)
async def handle_contact(message: types.Message, state: FSMContext):
    try:
        phone = message.contact.phone_number
        if not phone:
            await message.answer("لم يتم استلام الرقم")
            return
        if not phone.startswith("+"):
            phone = "+" + phone
        
        await state.update_data(phone=phone)
        client = TelegramClient(StringSession(), API_ID, API_HASH)
        await client.connect()
        
        try:
            sent = await client.send_code_request(phone)
            await state.update_data(phone_code_hash=sent.phone_code_hash, client=client)
            await message.answer("تم ارسال رمز التحقق\n\nارسل الرمز\nمثال: 1 2 3 4 5", reply_markup=types.ReplyKeyboardRemove())
            await state.set_state(LoginState.waiting_for_code)
        except Exception as e:
            await message.answer(f"خطأ: {e}")
            try:
                await client.disconnect()
            except:
                pass
            await state.clear()
    except Exception as e:
        await message.answer("حدث خطأ")

@dp.message(lambda message: message.text and message.text.startswith("+"))
async def handle_phone_text(message: types.Message, state: FSMContext):
    try:
        phone = message.text.strip()
        if not phone.startswith("+"):
            phone = "+" + phone
        
        await state.update_data(phone=phone)
        client = TelegramClient(StringSession(), API_ID, API_HASH)
        await client.connect()
        
        try:
            sent = await client.send_code_request(phone)
            await state.update_data(phone_code_hash=sent.phone_code_hash, client=client)
            await message.answer("تم ارسال رمز التحقق\n\nارسل الرمز\nمثال: 1 2 3 4 5", reply_markup=types.ReplyKeyboardRemove())
            await state.set_state(LoginState.waiting_for_code)
        except Exception as e:
            await message.answer(f"خطأ: {e}")
            try:
                await client.disconnect()
            except:
                pass
            await state.clear()
    except Exception as e:
        await message.answer("حدث خطأ")

@dp.message(LoginState.waiting_for_phone)
async def handle_phone_waiting(message: types.Message, state: FSMContext):
    if message.contact:
        await handle_contact(message, state)
    elif message.text and message.text.startswith("+"):
        await handle_phone_text(message, state)
    else:
        await message.answer("ارسل رقم الهاتف مع رمز الدولة\nمثال: +9647700000000")

@dp.message(LoginState.waiting_for_code)
async def process_code(message: types.Message, state: FSMContext):
    code = clean_code(message.text)
    
    data = await state.get_data()
    phone = data.get('phone')
    phone_code_hash = data.get('phone_code_hash')
    client = data.get('client')
    
    if not client:
        await message.answer("انتهت الجلسة")
        await state.clear()
        return

    try:
        await client.sign_in(phone=phone, code=code, phone_code_hash=phone_code_hash)
        session_str = client.session.save()
        me = await client.get_me()
        
        bot_data = {
            "user_id": message.from_user.id,
            "session_string": session_str,
            "account_id": me.id,
            "is_active": True,
            "clock_enabled": True,
            "filter_enabled": True,
            "save_media_enabled": True,
            "lock_private_enabled": False,
            "clock_font": "circle",
            "is_approved": True,
            "archive_enabled": False
        }
        
        supabase.table("user_bots").upsert(bot_data, on_conflict="user_id").execute()
        
        markup = get_control_panel_keyboard(bot_data)
        
        await message.answer(f"تم التنصيب بنجاح\n\nالاسم: {me.first_name}", reply_markup=markup)
        asyncio.create_task(start_userbot(session_str, me.id))
        
        await client.disconnect()
        await state.clear()
    except Exception as e:
        error_str = str(e)
        if "Two-steps verification" in error_str or "SessionPasswordNeededError" in error_str or "Password" in error_str:
            await state.update_data(client=client)
            await message.answer("حسابك محمي بتحقق بخطوتين\n\nارسل كلمة المرور:")
            await state.set_state(LoginState.waiting_for_password)
        else:
            await message.answer(f"خطأ: {e}")
            try:
                await client.disconnect()
            except:
                pass
            await state.clear()

@dp.message(LoginState.waiting_for_password)
async def process_password(message: types.Message, state: FSMContext):
    password = message.text.strip()
    data = await state.get_data()
    client = data.get('client')
    
    if not client:
        await message.answer("حدث خطأ")
        await state.clear()
        return

    try:
        await client.sign_in(password=password)
        session_str = client.session.save()
        me = await client.get_me()
        
        bot_data = {
            "user_id": message.from_user.id,
            "session_string": session_str,
            "account_id": me.id,
            "is_active": True,
            "clock_enabled": True,
            "filter_enabled": True,
            "save_media_enabled": True,
            "lock_private_enabled": False,
            "clock_font": "circle",
            "is_approved": True,
            "archive_enabled": False
        }
        
        supabase.table("user_bots").upsert(bot_data, on_conflict="user_id").execute()
        
        markup = get_control_panel_keyboard(bot_data)
        
        await message.answer(f"تم التفعيل\n\nالاسم: {me.first_name}", reply_markup=markup)
        asyncio.create_task(start_userbot(session_str, me.id))
        
        await client.disconnect()
        await state.clear()
    except Exception as e:
        error_str = str(e)
        if "PASSWORD_HASH_INVALID" in error_str or "invalid" in error_str.lower():
            await message.answer("كلمة المرور غير صحيحة، حاول مرة اخرى:")
        else:
            await message.answer(f"خطأ: {e}")
            try:
                await client.disconnect()
            except:
                pass
            await state.clear()

# ==================== لوحة المطور ====================
@dp.callback_query(F.data == "dev_admin_panel")
async def dev_admin_panel(callback: types.CallbackQuery):
    if callback.from_user.id != DEV_ID:
        await callback.answer("مخصص للمطور")
        return
    
    res = supabase.table("user_bots").select("*").execute()
    total = len(res.data) if res.data else 0
    running = len(ACTIVE_CLIENTS)
    
    kb = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="المستخدمين", callback_data="dev_list_users"),
         types.InlineKeyboardButton(text="احصائيات", callback_data="dev_stats")],
        [types.InlineKeyboardButton(text="تشغيل الكل", callback_data="dev_start_all")],
        [types.InlineKeyboardButton(text="الرئيسية", callback_data="main_menu")]
    ])
    
    await callback.message.edit_text(f"لوحة المطور:\n\nالمستخدمين: {total}\nيعملون: {running}", reply_markup=kb)
    await callback.answer()

@dp.callback_query(F.data == "dev_start_all")
async def dev_start_all(callback: types.CallbackQuery):
    if callback.from_user.id != DEV_ID:
        return
    
    res = supabase.table("user_bots").select("*").execute()
    started = 0
    
    for row in res.data:
        if row.get("session_string") and row.get("is_active"):
            account_id = row.get("account_id")
            
            if account_id in ACTIVE_CLIENTS:
                try:
                    await ACTIVE_CLIENTS[account_id].disconnect()
                except:
                    pass
                del ACTIVE_CLIENTS[account_id]
            
            asyncio.create_task(start_userbot(row["session_string"], account_id))
            started += 1
    
    await callback.answer(f"تم تشغيل {started}")
    await dev_admin_panel(callback)

@dp.callback_query(F.data == "dev_list_users")
async def dev_list_users(callback: types.CallbackQuery):
    if callback.from_user.id != DEV_ID:
        return
    
    res = supabase.table("user_bots").select("user_id, account_id, is_active").execute()
    
    if not res.data:
        await callback.message.edit_text("لا يوجد", reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[
            [types.InlineKeyboardButton(text="رجوع", callback_data="dev_admin_panel")]
        ]))
    else:
        kb = []
        for row in res.data[:10]:
            uid = row.get("user_id")
            status = "نشط" if row.get("is_active") else "موقوف"
            running = "يعمل" if row.get("account_id") in ACTIVE_CLIENTS else "واقف"
            kb.append([types.InlineKeyboardButton(text=f"{uid} - {status} - {running}", callback_data=f"dev_user_{uid}")])
        kb.append([types.InlineKeyboardButton(text="رجوع", callback_data="dev_admin_panel")])
        await callback.message.edit_text(f"المستخدمين ({len(res.data)}):", reply_markup=types.InlineKeyboardMarkup(inline_keyboard=kb))
    await callback.answer()

@dp.callback_query(F.data.startswith("dev_user_"))
async def dev_manage_user(callback: types.CallbackQuery):
    target_uid = int(callback.data.replace("dev_user_", ""))
    
    kb = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="تشغيل", callback_data=f"dev_start_{target_uid}"),
         types.InlineKeyboardButton(text="ايقاف", callback_data=f"dev_stop_{target_uid}")],
        [types.InlineKeyboardButton(text="حذف", callback_data=f"dev_del_{target_uid}")],
        [types.InlineKeyboardButton(text="رجوع", callback_data="dev_list_users")]
    ])
    
    await callback.message.edit_text(f"ادارة: {target_uid}", reply_markup=kb)
    await callback.answer()

@dp.callback_query(F.data.startswith("dev_start_"))
async def dev_start_user(callback: types.CallbackQuery):
    target_uid = int(callback.data.replace("dev_start_", ""))
    
    res = supabase.table("user_bots").select("*").eq("user_id", target_uid).execute()
    
    if res.data:
        row = res.data[0]
        account_id = row.get("account_id")
        
        if account_id in ACTIVE_CLIENTS:
            try:
                await ACTIVE_CLIENTS[account_id].disconnect()
            except:
                pass
            del ACTIVE_CLIENTS[account_id]
        
        if row.get("session_string"):
            supabase.table("user_bots").update({"is_active": True}).eq("user_id", target_uid).execute()
            asyncio.create_task(start_userbot(row["session_string"], account_id))
            await callback.answer("تم التشغيل")
    
    await dev_list_users(callback)

@dp.callback_query(F.data.startswith("dev_stop_"))
async def dev_stop_user(callback: types.CallbackQuery):
    target_uid = int(callback.data.replace("dev_stop_", ""))
    
    res = supabase.table("user_bots").select("account_id").eq("user_id", target_uid).execute()
    
    if res.data:
        account_id = res.data[0].get("account_id")
        
        if account_id in ACTIVE_CLIENTS:
            try:
                await ACTIVE_CLIENTS[account_id].disconnect()
            except:
                pass
            del ACTIVE_CLIENTS[account_id]
        
        supabase.table("user_bots").update({"is_active": False}).eq("user_id", target_uid).execute()
        await callback.answer("تم الايقاف")
    
    await dev_list_users(callback)

@dp.callback_query(F.data.startswith("dev_del_"))
async def dev_delete_user(callback: types.CallbackQuery):
    target_uid = int(callback.data.replace("dev_del_", ""))
    
    res = supabase.table("user_bots").select("account_id").eq("user_id", target_uid).execute()
    
    if res.data:
        account_id = res.data[0].get("account_id")
        
        if account_id in ACTIVE_CLIENTS:
            try:
                await ACTIVE_CLIENTS[account_id].disconnect()
            except:
                pass
            del ACTIVE_CLIENTS[account_id]
    
    supabase.table("user_bots").delete().eq("user_id", target_uid).execute()
    await callback.answer("تم الحذف")
    await dev_list_users(callback)

@dp.callback_query(F.data == "dev_stats")
async def dev_stats(callback: types.CallbackQuery):
    if callback.from_user.id != DEV_ID:
        return
    
    res = supabase.table("user_bots").select("*").execute()
    total = len(res.data) if res.data else 0
    active = sum(1 for x in (res.data or []) if x.get("is_active"))
    running = len(ACTIVE_CLIENTS)
    
    kb = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="رجوع", callback_data="dev_admin_panel")]
    ])
    
    await callback.message.edit_text(f"الاحصائيات:\n\nالاجمالي: {total}\nنشطين: {active}\nيعملون: {running}", reply_markup=kb)
    await callback.answer()

# ==================== تشغيل اليوزربوت ====================
async def load_channel_messages(client, chan_username, category_key, client_id):
    try:
        messages_list = []
        async for message in client.iter_messages(chan_username, limit=100):
            if message.text or message.media:
                messages_list.append(message)
        
        if client_id not in CLIENT_CONTENTS:
            CLIENT_CONTENTS[client_id] = {}
        CLIENT_CONTENTS[client_id][category_key] = messages_list
    except:
        pass

async def start_userbot(session_str, client_id):
    """تشغيل مع اعادة تلقائية مستمرة"""
    while True:
        client = None
        try:
            client = TelegramClient(StringSession(session_str), API_ID, API_HASH)
            await client.start()
            ACTIVE_CLIENTS[client_id] = client
            
            try:
                res = supabase.table("user_bots").select("archive_enabled").eq("account_id", client_id).execute()
                if res.data:
                    ARCHIVE_ENABLED[client_id] = res.data[0].get("archive_enabled", False)
            except:
                pass
            
            for cat, chan in CHANNELS_MAP.items():
                asyncio.create_task(load_channel_messages(client, chan, cat, client_id))

            try:
                res_muted = supabase.table("muted_users").select("*").eq("user_id", client_id).execute()
                if res_muted.data:
                    MUTED_USERS_CACHE[client_id] = {row['muted_user_id'] for row in res_muted.data}
            except:
                pass
            
            try:
                res_banned = supabase.table("banned_users").select("*").eq("user_id", client_id).execute()
                if res_banned.data:
                    BANNED_USERS_CACHE[client_id] = {row['banned_user_id'] for row in res_banned.data}
            except:
                pass

            @client.on(events.NewMessage(incoming=True))
            async def incoming_handler(event):
                try:
                    if not event.is_private:
                        return
                    
                    sender = await event.get_sender()
                    if sender and getattr(sender, 'bot', False):
                        return
                    
                    sender_id = event.sender_id
                    if sender_id == client_id:
                        return

                    if client_id in MUTED_USERS_CACHE:
                        if str(sender_id) in MUTED_USERS_CACHE[client_id]:
                            try:
                                await event.delete()
                                return
                            except:
                                pass

                    if client_id in BANNED_USERS_CACHE:
                        if str(sender_id) in BANNED_USERS_CACHE[client_id]:
                            try:
                                await event.delete()
                                await event.reply("انت محظور")
                                return
                            except:
                                pass

                    res = supabase.table("user_bots").select("*").eq("account_id", client_id).execute()
                    if not res.data:
                        return
                    
                    bot_config = res.data[0]

                    # حفظ الوسائط الوقتية (صور، فيديو، صوت)
                    if bot_config.get("save_media_enabled", True) and event.message.media:
                        msg_media = event.message.media
                        
                        is_photo = isinstance(msg_media, MessageMediaPhoto)
                        is_video = False
                        is_audio = False
                        
                        if isinstance(msg_media, MessageMediaDocument):
                            doc = msg_media.document
                            if doc and doc.mime_type:
                                mime = doc.mime_type
                                if "video" in mime and "webm" not in mime:
                                    is_video = True
                                if "audio" in mime or "voice" in mime:
                                    is_audio = True
                        
                        is_ttl = False
                        
                        if hasattr(event.message, 'ttl_period') and event.message.ttl_period:
                            is_ttl = True
                        
                        if hasattr(event.message, 'media_unread') and event.message.media_unread:
                            is_ttl = True
                        
                        if hasattr(msg_media, 'ttl_seconds') and msg_media.ttl_seconds:
                            is_ttl = True
                        
                        if is_ttl and (is_photo or is_video or is_audio):
                            try:
                                file_path = await event.message.download_media()
                                if file_path:
                                    caption = ""
                                    if is_photo:
                                        caption = "تم حفظ صورة وقتية"
                                    elif is_video:
                                        caption = "تم حفظ فيديو وقتي"
                                    elif is_audio:
                                        caption = "تم حفظ صوت وقتي"
                                    
                                    await client.send_file('me', file_path, caption=caption)
                                    try:
                                        os.remove(file_path)
                                    except:
                                        pass
                            except Exception as e:
                                print(f"Error saving TTL: {e}")

                    # رد تلقائي
                    auto_rep = bot_config.get("auto_reply_text")
                    if auto_rep:
                        await event.reply(auto_rep)
                        
                except Exception as ex:
                    pass

            @client.on(events.NewMessage(incoming=True))
            async def commands_handler(event):
                try:
                    chat_id = event.chat_id
                    text_raw = event.raw_text.strip() if event.raw_text else ""
                    text_lower = text_raw.lower()
                    
                    msg_key = f"{client_id}_{event.message.id}"
                    if msg_key in PROCESSED_MESSAGES:
                        return
                    PROCESSED_MESSAGES.add(msg_key)
                    
                    is_private = event.is_private
                    sender_id = event.sender_id
                    is_owner = (sender_id == client_id)

                    # أوامر الترفيه - للكل بالخاص
                    if is_private:
                        matched_cmd = None
                        for cmd in CHANNELS_MAP.keys():
                            if text_raw == cmd:
                                matched_cmd = cmd
                                break

                        if matched_cmd:
                            try:
                                await event.delete()
                            except:
                                pass
                            
                            messages_list = CLIENT_CONTENTS.get(client_id, {}).get(matched_cmd, [])
                            if messages_list:
                                selected = random.choice(messages_list)
                                try:
                                    if selected.media:
                                        await client.send_file(chat_id, selected.media, caption=selected.text or "")
                                    elif selected.text:
                                        await client.send_message(chat_id, selected.text)
                                except:
                                    pass
                            return

                        if text_lower.startswith("يوت ") or text_lower.startswith("يوتو "):
                            query = text_raw[4:].strip() if text_lower.startswith("يوت ") else text_raw[5:].strip()
                            if not query:
                                return
                            
                            try:
                                await event.delete()
                            except:
                                pass

                            try:
                                sent_msg = await client.send_message(DOWNLOAD_BOT, f"يوت {query}")
                                audio_msg = None
                                
                                for _ in range(30):
                                    msgs = await client.get_messages(DOWNLOAD_BOT, limit=6)
                                    for msg in msgs:
                                        if msg.id > sent_msg.id and (msg.audio or msg.voice):
                                            audio_msg = msg
                                            break
                                    if audio_msg:
                                        break
                                    await asyncio.sleep(0.3)

                                if audio_msg:
                                    await client.send_file(chat_id, audio_msg.media)
                            except:
                                pass
                            return

                    # أوامر المنصب
                    if is_owner:
                        if text_raw == "كتم":
                            try:
                                if is_private:
                                    await event.delete()
                                if client_id not in MUTED_USERS_CACHE:
                                    MUTED_USERS_CACHE[client_id] = set()
                                
                                target_id = chat_id if is_private else (event.reply_to_msg_id and (await event.get_reply_message()).sender_id if event.reply_to_msg_id else None)
                                
                                if target_id:
                                    MUTED_USERS_CACHE[client_id].add(str(target_id))
                                    supabase.table("muted_users").upsert({
                                        "user_id": client_id,
                                        "muted_user_id": str(target_id)
                                    }, on_conflict="user_id,muted_user_id").execute()
                                    await event.respond("تم كتم المستخدم")
                            except:
                                pass
                            return

                        if text_raw == "فك كتم":
                            try:
                                if is_private:
                                    await event.delete()
                                target_id = chat_id if is_private else (event.reply_to_msg_id and (await event.get_reply_message()).sender_id if event.reply_to_msg_id else None)
                                
                                if target_id and client_id in MUTED_USERS_CACHE:
                                    MUTED_USERS_CACHE[client_id].discard(str(target_id))
                                    supabase.table("muted_users").delete().eq("user_id", client_id).eq("muted_user_id", str(target_id)).execute()
                                    await event.respond("تم فك كتم المستخدم")
                            except:
                                pass
                            return

                        if text_lower.startswith("كتم "):
                            try:
                                target = text_raw[4:].strip()
                                resolved_id = await resolve_identifier(client, target)
                                if resolved_id:
                                    target = str(resolved_id)
                                
                                if client_id not in MUTED_USERS_CACHE:
                                    MUTED_USERS_CACHE[client_id] = set()
                                MUTED_USERS_CACHE[client_id].add(target)
                                
                                supabase.table("muted_users").upsert({
                                    "user_id": client_id,
                                    "muted_user_id": target
                                }, on_conflict="user_id,muted_user_id").execute()
                                
                                await event.respond(f"تم كتم: {target}")
                            except:
                                pass
                            return

                        if text_lower.startswith("فك كتم "):
                            try:
                                target = text_raw[6:].strip()
                                resolved_id = await resolve_identifier(client, target)
                                if resolved_id:
                                    target = str(resolved_id)
                                
                                if client_id in MUTED_USERS_CACHE:
                                    MUTED_USERS_CACHE[client_id].discard(target)
                                    supabase.table("muted_users").delete().eq("user_id", client_id).eq("muted_user_id", target).execute()
                                    await event.respond(f"تم فك كتم: {target}")
                            except:
                                pass
                            return

                        if text_raw == "حظر":
                            try:
                                if is_private:
                                    await event.delete()
                                if client_id not in BANNED_USERS_CACHE:
                                    BANNED_USERS_CACHE[client_id] = set()
                                
                                target_id = chat_id if is_private else (event.reply_to_msg_id and (await event.get_reply_message()).sender_id if event.reply_to_msg_id else None)
                                
                                if target_id:
                                    BANNED_USERS_CACHE[client_id].add(str(target_id))
                                    supabase.table("banned_users").upsert({
                                        "user_id": client_id,
                                        "banned_user_id": str(target_id)
                                    }, on_conflict="user_id,banned_user_id").execute()
                                    await event.respond("تم حظر المستخدم")
                            except:
                                pass
                            return

                        if text_raw == "فك حظر":
                            try:
                                if is_private:
                                    await event.delete()
                                target_id = chat_id if is_private else (event.reply_to_msg_id and (await event.get_reply_message()).sender_id if event.reply_to_msg_id else None)
                                
                                if target_id and client_id in BANNED_USERS_CACHE:
                                    BANNED_USERS_CACHE[client_id].discard(str(target_id))
                                    supabase.table("banned_users").delete().eq("user_id", client_id).eq("banned_user_id", str(target_id)).execute()
                                    await event.respond("تم فك حظر المستخدم")
                            except:
                                pass
                            return

                        if text_lower.startswith("حظر "):
                            try:
                                target = text_raw[4:].strip()
                                resolved_id = await resolve_identifier(client, target)
                                if resolved_id:
                                    target = str(resolved_id)
                                
                                if client_id not in BANNED_USERS_CACHE:
                                    BANNED_USERS_CACHE[client_id] = set()
                                BANNED_USERS_CACHE[client_id].add(target)
                                
                                supabase.table("banned_users").upsert({
                                    "user_id": client_id,
                                    "banned_user_id": target
                                }, on_conflict="user_id,banned_user_id").execute()
                                
                                await event.respond(f"تم حظر: {target}")
                            except:
                                pass
                            return

                        if text_lower.startswith("فك حظر "):
                            try:
                                target = text_raw[6:].strip()
                                resolved_id = await resolve_identifier(client, target)
                                if resolved_id:
                                    target = str(resolved_id)
                                
                                if client_id in BANNED_USERS_CACHE:
                                    BANNED_USERS_CACHE[client_id].discard(target)
                                    supabase.table("banned_users").delete().eq("user_id", client_id).eq("banned_user_id", target).execute()
                                    await event.respond(f"تم فك حظر: {target}")
                            except:
                                pass
                            return

                        if text_raw == "قفل صور":
                            LOCK_PHOTOS[client_id] = True
                            await event.respond("تم قفل الصور")
                            return
                        if text_raw == "فتح صور":
                            LOCK_PHOTOS[client_id] = False
                            await event.respond("تم فتح الصور")
                            return
                        if text_raw == "قفل فيديو":
                            LOCK_VIDEOS[client_id] = True
                            await event.respond("تم قفل الفيديو")
                            return
                        if text_raw == "فتح فيديو":
                            LOCK_VIDEOS[client_id] = False
                            await event.respond("تم فتح الفيديو")
                            return
                        if text_raw == "قفل ملصقات":
                            LOCK_STICKERS[client_id] = True
                            await event.respond("تم قفل الملصقات")
                            return
                        if text_raw == "فتح ملصقات":
                            LOCK_STICKERS[client_id] = False
                            await event.respond("تم فتح الملصقات")
                            return
                        if text_raw == "قفل روابط":
                            LOCK_LINKS[client_id] = True
                            await event.respond("تم قفل الروابط")
                            return
                        if text_raw == "فتح روابط":
                            LOCK_LINKS[client_id] = False
                            await event.respond("تم فتح الروابط")
                            return
                        if text_raw == "قفل ملفات":
                            LOCK_FILES[client_id] = True
                            await event.respond("تم قفل الملفات")
                            return
                        if text_raw == "فتح ملفات":
                            LOCK_FILES[client_id] = False
                            await event.respond("تم فتح الملفات")
                            return

                        if text_raw == "تعيين صورة":
                            if event.reply_to_msg_id:
                                replied = await event.get_reply_message()
                                if replied and replied.media:
                                    try:
                                        file_path = await replied.download_media()
                                        if file_path:
                                            await client(functions.photos.UploadProfilePhotoRequest(
                                                file=await client.upload_file(file_path)
                                            ))
                                            try:
                                                os.remove(file_path)
                                            except:
                                                pass
                                            await event.respond("تم تعيين الصورة")
                                    except:
                                        pass
                            return

                        if text_raw == "حذف صورة":
                            try:
                                photos = await client.get_profile_photos('me', limit=1)
                                if photos:
                                    await client(functions.photos.DeletePhotosRequest(id=[photos[0]]))
                                    await event.respond("تم حذف الصورة")
                            except:
                                pass
                            return

                        if text_lower.startswith("تغيير اسم "):
                            new_name = text_raw[10:].strip()
                            try:
                                await client(functions.account.UpdateProfileRequest(first_name=new_name))
                                await event.respond(f"تم تغيير الاسم الى: {new_name}")
                            except:
                                pass
                            return

                        if text_lower.startswith("تغيير بايو "):
                            new_bio = text_raw[11:].strip()
                            try:
                                await client(functions.account.UpdateProfileRequest(about=new_bio))
                                await event.respond("تم تغيير البايو")
                            except:
                                pass
                            return

                        if text_raw == "احصائياتي":
                            muted_count = len(MUTED_USERS_CACHE.get(client_id, set()))
                            banned_count = len(BANNED_USERS_CACHE.get(client_id, set()))
                            await event.respond(f"المكتمين: {muted_count}\nالمحظورين: {banned_count}")
                            return

                        if text_raw == "حالتي":
                            me = await client.get_me()
                            status = "يعمل" if client_id in ACTIVE_CLIENTS else "واقف"
                            await event.respond(f"الاسم: {me.first_name}\nالايدي: {me.id}\nاليوزر: @{me.username or 'بدون'}\nالحالة: {status}")
                            return

                        if text_raw == "فحص":
                            await event.respond("الحساب شغال")
                            return

                        if text_raw == "مساعدة":
                            await event.respond(
                                "اوامر الترفيه:\n- غنيلي - شعر - مزج - ميمز - قرآن\n- يوت اسم\n\n"
                                "اوامر المنصب:\n- كتم / فك كتم\n- كتم ايدي / @يوزر\n- حظر / فك حظر\n- حظر ايدي / @يوزر\n"
                                "- قفل صور / فتح صور\n- قفل فيديو / فتح فيديو\n- قفل ملصقات / فتح ملصقات\n- قفل روابط / فتح روابط\n- قفل ملفات / فتح ملفات\n"
                                "- تعيين صورة (رد)\n- حذف صورة\n- تغيير اسم\n- تغيير بايو\n- احصائياتي\n- حالتي\n- فحص"
                            )
                            return

                except Exception as ex:
                    pass

            await client.run_until_disconnected()
            
        except Exception as e:
            print(f"Userbot {client_id} stopped: {e}")
            
            if client_id in ACTIVE_CLIENTS:
                try:
                    del ACTIVE_CLIENTS[client_id]
                except:
                    pass
            
            await asyncio.sleep(5)
            continue
        
        finally:
            if client:
                try:
                    await client.disconnect()
                except:
                    pass
            
            if client_id in ACTIVE_CLIENTS:
                try:
                    del ACTIVE_CLIENTS[client_id]
                except:
                    pass

async def restore_sessions():
    try:
        res = supabase.table("user_bots").select("*").eq("is_active", True).execute()
        if res.data:
            for row in res.data:
                if row.get("session_string"):
                    asyncio.create_task(start_userbot(row["session_string"], row["account_id"]))
    except:
        pass

async def main():
    await restore_sessions()
    print("Bot started")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
