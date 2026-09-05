import os
import random
import asyncio
import datetime
import json
import traceback
from telethon import TelegramClient, events, functions
from telethon.sessions import StringSession
from telethon.tl.types import MessageMediaPhoto, MessageMediaDocument
from supabase import create_client, Client

# ==================== إعدادات البيئة وقاعدة البيانات ====================
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
PROCESSED_MESSAGES = set()  # لمنع التكرار
DEFAULT_BAD_WORDS = ["وهابي", "عفن", "سخيف", "كلب", "انقلع"]

CLOCK_FONTS = {
    "circle": ("0123456789", "⓪①②③④⑤⑥⑦⑧⑨"),
    "bold": ("0123456789", "𝟎𝟏𝟐𝟑𝟒𝟓𝟔𝟕𝟖𝟗"),
    "sans": ("0123456789", "𝟶𝟷𝟸𝟹𝟺𝟻𝟼𝟽𝟾𝟿"),
    "normal": ("0123456789", "0123456789")
}

# ==================== بوت الإدارة والتنصيب ====================
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

def get_main_menu_keyboard(user_id):
    kb = [
        [types.InlineKeyboardButton(text="تفعيل الاشتراك المجاني", callback_data="free_subscription")],
        [types.InlineKeyboardButton(text="لوحة التحكم", callback_data="my_settings")],
        [types.InlineKeyboardButton(text="تعليمات", callback_data="bot_instructions")],
        [types.InlineKeyboardButton(text="مراسلة المطور", url=f"https://t.me/{DEV_USER.replace('@','')}")]
    ]
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

    kb = [
        [types.InlineKeyboardButton(text="الكتم والحظر", callback_data="mute_ban_menu")],
        [types.InlineKeyboardButton(text=f"تدمير الرسائل: {destroy_st}", callback_data="destroy_messages_menu")],
        [types.InlineKeyboardButton(text=f"النشر التلقائي: {publish_st}", callback_data="auto_publish_menu")],
        [types.InlineKeyboardButton(text=f"حماية السبام: {spam_st}", callback_data="toggle_spam")],
        [types.InlineKeyboardButton(text=f"قفل الخاص: {lock_st}", callback_data="toggle_lock_private"),
         types.InlineKeyboardButton(text=f"فلتر الكلمات: {filter_st}", callback_data="toggle_filter")],
        [types.InlineKeyboardButton(text=f"الساعة: {clock_st}", callback_data="toggle_clock"),
         types.InlineKeyboardButton(text=f"الخط: {current_font}", callback_data="choose_font")],
        [types.InlineKeyboardButton(text=f"حفظ الوسائط الوقتية: {save_st}", callback_data="toggle_save_media"),
         types.InlineKeyboardButton(text="اضافة كلمة محظورة", callback_data="add_bad_word")],
        [types.InlineKeyboardButton(text="الردود التلقائية", callback_data="set_auto_reply"),
         types.InlineKeyboardButton(text="حذف الردود", callback_data="del_auto_reply")],
        [types.InlineKeyboardButton(text="الاشتراك الاجباري", callback_data="set_forced"),
         types.InlineKeyboardButton(text="ايقاف الاشتراك", callback_data="off_forced")],
        [types.InlineKeyboardButton(text="رسالة الترحيب", callback_data="set_welcome"),
         types.InlineKeyboardButton(text="تحديث", callback_data="refresh_bot")],
        [types.InlineKeyboardButton(text="القائمة الرئيسية", callback_data="main_menu")]
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

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    user_id = message.from_user.id
    try:
        res = supabase.table("user_bots").select("*").or_(f"user_id.eq.{user_id},account_id.eq.{user_id}").execute()
        
        if res.data and res.data[0].get("session_string"):
            bot_info = res.data[0]
            markup = get_control_panel_keyboard(bot_info)
            forced = safe_get(bot_info, "forced_channel") or "غير محددة"
            
            await message.answer(
                f"لوحة التحكم الشاملة\n\n"
                f"قناة الاشتراك: @{forced}\n"
                f"اختر من الازرار:",
                reply_markup=markup
            )
            return

        welcome_text = (
            "مرحباً بك في النظام الذكي\n\n"
            "الاشتراك مجاني لمدة شهر\n\n"
            "المميزات:\n"
            "- ساعة حية\n"
            "- حفظ الوسائط الوقتية\n"
            "- ارشفة الرسائل\n"
            "- كتم وحظر\n"
            "- نشر تلقائي\n"
            "- تدمير الرسائل\n"
            "- حماية من السبام\n\n"
            "اضغط للبدء:"
        )
        await message.answer(welcome_text, reply_markup=get_main_menu_keyboard(user_id))
    except Exception as e:
        print(f"ERROR start: {e}")
        await message.answer("حدث خطأ، حاول لاحقاً")

@dp.callback_query(F.data == "free_subscription")
async def free_subscription(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer("جاري التفعيل...")
    await state.clear()
    
    user_id = callback.from_user.id
    
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
    
    await callback.message.answer(
        "تم التفعيل بنجاح\n\n"
        "اضغط زر مشاركة رقم الهاتف\n"
        "او اكتب رقمك مع رمز الدولة",
        reply_markup=contact_kb
    )
    await state.set_state(LoginState.waiting_for_phone)

@dp.callback_query(F.data == "bot_instructions")
async def bot_instructions(callback: types.CallbackQuery):
    text = (
        "التعليمات:\n\n"
        "1. اربط البوت بوضع السكرتير\n\n"
        "الاوامر:\n"
        "- غنيلي - شعر - مزج - ميمز - قرآن\n"
        "- يوت اسم الاغنية\n"
        "- كتم - فك كتم\n"
        "- كتم ايدي - فك كتم ايدي\n"
        "- حظر - فك حظر\n"
        "- حظر ايدي - فك حظر ايدي"
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
            await message.answer("لم يتم استلام رقم الهاتف")
            return
        
        if not phone.startswith("+"):
            phone = "+" + phone
        
        await state.update_data(phone=phone)
        
        client = TelegramClient(StringSession(), API_ID, API_HASH)
        await client.connect()
        
        try:
            sent = await client.send_code_request(phone)
            await state.update_data(phone_code_hash=sent.phone_code_hash, client=client)
            
            await message.answer(
                "تم ارسال رمز التحقق\n\n"
                "ارسل الرمز الآن:",
                reply_markup=types.ReplyKeyboardRemove()
            )
            await state.set_state(LoginState.waiting_for_code)
            
        except Exception as e:
            error_str = str(e)
            if "FLOOD" in error_str or "flood" in error_str:
                await message.answer("انتظر قليلاً ثم حاول مرة اخرى")
            else:
                await message.answer(f"خطأ: {e}")
            
            try:
                await client.disconnect()
            except:
                pass
            await state.clear()
            
    except Exception as e:
        print(f"ERROR contact: {e}")
        await message.answer("حدث خطأ في معالجة جهة الاتصال")

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
            
            await message.answer(
                "تم ارسال رمز التحقق\n\n"
                "ارسل الرمز الآن:",
                reply_markup=types.ReplyKeyboardRemove()
            )
            await state.set_state(LoginState.waiting_for_code)
            
        except Exception as e:
            error_str = str(e)
            if "FLOOD" in error_str or "flood" in error_str:
                await message.answer("انتظر قليلاً ثم حاول مرة اخرى")
            else:
                await message.answer(f"خطأ: {e}")
            
            try:
                await client.disconnect()
            except:
                pass
            await state.clear()
            
    except Exception as e:
        print(f"ERROR phone: {e}")
        await message.answer("حدث خطأ في معالجة الرقم")

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
    code = message.text.strip().replace(" ", "")
    data = await state.get_data()
    phone = data.get('phone')
    phone_code_hash = data.get('phone_code_hash')
    client = data.get('client')
    
    if not client:
        await message.answer("انتهت الجلسة، ارسل رقمك مجدداً")
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
            "is_approved": True
        }
        
        supabase.table("user_bots").upsert(bot_data, on_conflict="user_id").execute()
        
        markup = get_control_panel_keyboard(bot_data)
        
        await message.answer(
            f"تم التنصيب بنجاح\n\n"
            f"الاسم: {me.first_name}",
            reply_markup=markup
        )
        
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
        await message.answer("حدث خطأ، اعد المحاولة")
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
            "is_approved": True
        }
        
        supabase.table("user_bots").upsert(bot_data, on_conflict="user_id").execute()
        
        markup = get_control_panel_keyboard(bot_data)
        
        await message.answer(
            f"تم التفعيل بنجاح\n\n"
            f"الاسم: {me.first_name}",
            reply_markup=markup
        )
        
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
        await callback.answer("مخصص للمطور فقط")
        return
    
    try:
        res = supabase.table("user_bots").select("*").execute()
        total = len(res.data) if res.data else 0
        active = sum(1 for x in (res.data or []) if x.get("is_active"))
        running = len(ACTIVE_CLIENTS)
        
        kb = types.InlineKeyboardMarkup(inline_keyboard=[
            [types.InlineKeyboardButton(text="قائمة المستخدمين", callback_data="dev_list_users")],
            [types.InlineKeyboardButton(text="الاحصائيات", callback_data="dev_stats")],
            [types.InlineKeyboardButton(text="تشغيل الكل", callback_data="dev_start_all")],
            [types.InlineKeyboardButton(text="القائمة الرئيسية", callback_data="main_menu")]
        ])
        
        await callback.message.edit_text(
            f"لوحة المطور:\n\n"
            f"اجمالي المستخدمين: {total}\n"
            f"النشطين: {active}\n"
            f"اليعملون حالياً: {running}",
            reply_markup=kb
        )
    except Exception as e:
        print(f"ERROR dev panel: {e}")
        await callback.answer("خطأ في جلب البيانات")
    await callback.answer()

@dp.callback_query(F.data == "dev_start_all")
async def dev_start_all(callback: types.CallbackQuery):
    if callback.from_user.id != DEV_ID:
        return
    
    try:
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
        
        await callback.answer(f"تم تشغيل {started} يوزربوت")
    except Exception as e:
        print(f"ERROR start all: {e}")
        await callback.answer("خطأ")
    
    await dev_admin_panel(callback)

@dp.callback_query(F.data == "dev_list_users")
async def dev_list_users(callback: types.CallbackQuery):
    if callback.from_user.id != DEV_ID:
        return
    
    try:
        res = supabase.table("user_bots").select("user_id, account_id, is_active, is_approved").execute()
        
        if not res.data:
            await callback.message.edit_text(
                "لا يوجد مستخدمين",
                reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[
                    [types.InlineKeyboardButton(text="رجوع", callback_data="dev_admin_panel")]
                ])
            )
            await callback.answer()
            return
        
        kb = []
        for row in res.data[:10]:
            uid = row.get("user_id")
            status = "نشط" if row.get("is_active") else "متوقف"
            running = "يعمل" if row.get("account_id") in ACTIVE_CLIENTS else "واقف"
            kb.append([types.InlineKeyboardButton(text=f"ايدي: {uid} - {status} - {running}", callback_data=f"dev_user_{uid}")])
        
        kb.append([types.InlineKeyboardButton(text="رجوع", callback_data="dev_admin_panel")])
        
        await callback.message.edit_text(
            f"المستخدمين ({len(res.data)}):",
            reply_markup=types.InlineKeyboardMarkup(inline_keyboard=kb)
        )
    except Exception as e:
        print(f"ERROR dev list: {e}")
        await callback.answer("خطأ في جلب البيانات")
    await callback.answer()

@dp.callback_query(F.data.startswith("dev_user_"))
async def dev_manage_user(callback: types.CallbackQuery):
    if callback.from_user.id != DEV_ID:
        return
    
    target_uid = int(callback.data.replace("dev_user_", ""))
    
    kb = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="تشغيل", callback_data=f"dev_start_{target_uid}")],
        [types.InlineKeyboardButton(text="ايقاف", callback_data=f"dev_stop_{target_uid}")],
        [types.InlineKeyboardButton(text="حذف", callback_data=f"dev_del_{target_uid}")],
        [types.InlineKeyboardButton(text="رجوع", callback_data="dev_list_users")]
    ])
    
    await callback.message.edit_text(
        f"ادارة المستخدم: {target_uid}",
        reply_markup=kb
    )
    await callback.answer()

@dp.callback_query(F.data.startswith("dev_start_"))
async def dev_start_user(callback: types.CallbackQuery):
    if callback.from_user.id != DEV_ID:
        return
    
    target_uid = int(callback.data.replace("dev_start_", ""))
    
    try:
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
            else:
                await callback.answer("لا يوجد session")
        else:
            await callback.answer("المستخدم غير موجود")
    except Exception as e:
        print(f"ERROR dev start: {e}")
        await callback.answer("خطأ")
    
    await dev_list_users(callback)

@dp.callback_query(F.data.startswith("dev_stop_"))
async def dev_stop_user(callback: types.CallbackQuery):
    if callback.from_user.id != DEV_ID:
        return
    
    target_uid = int(callback.data.replace("dev_stop_", ""))
    
    try:
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
        else:
            await callback.answer("المستخدم غير موجود")
    except Exception as e:
        print(f"ERROR dev stop: {e}")
        await callback.answer("خطأ")
    
    await dev_list_users(callback)

@dp.callback_query(F.data.startswith("dev_del_"))
async def dev_delete_user(callback: types.CallbackQuery):
    if callback.from_user.id != DEV_ID:
        return
    
    target_uid = int(callback.data.replace("dev_del_", ""))
    
    try:
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
    except Exception as e:
        print(f"ERROR dev delete: {e}")
        await callback.answer("خطأ في الحذف")
    
    await dev_list_users(callback)

@dp.callback_query(F.data == "dev_stats")
async def dev_stats(callback: types.CallbackQuery):
    if callback.from_user.id != DEV_ID:
        return
    
    try:
        res = supabase.table("user_bots").select("*").execute()
        total = len(res.data) if res.data else 0
        active = sum(1 for x in (res.data or []) if x.get("is_active"))
        approved = sum(1 for x in (res.data or []) if x.get("is_approved"))
        running = len(ACTIVE_CLIENTS)
        
        kb = types.InlineKeyboardMarkup(inline_keyboard=[
            [types.InlineKeyboardButton(text="رجوع", callback_data="dev_admin_panel")]
        ])
        
        await callback.message.edit_text(
            f"الاحصائيات:\n\n"
            f"الاجمالي: {total}\n"
            f"المفعلين: {approved}\n"
            f"المسجلين كنشطين: {active}\n"
            f"اليعملون حالياً: {running}",
            reply_markup=kb
        )
    except Exception as e:
        print(f"ERROR dev stats: {e}")
        await callback.answer("خطأ")
    await callback.answer()

# ==================== قائمة الكتم والحظر ====================
@dp.callback_query(F.data == "mute_ban_menu")
async def mute_ban_menu(callback: types.CallbackQuery):
    kb = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="كتم مستخدم", callback_data="mute_user"),
         types.InlineKeyboardButton(text="حظر مستخدم", callback_data="ban_user")],
        [types.InlineKeyboardButton(text="قائمة المكتمين", callback_data="list_muted"),
         types.InlineKeyboardButton(text="قائمة المحظورين", callback_data="list_banned")],
        [types.InlineKeyboardButton(text="رجوع", callback_data="my_settings")]
    ])
    await callback.message.edit_text("ادارة الكتم والحظر:", reply_markup=kb)
    await callback.answer()

@dp.callback_query(F.data == "mute_user")
async def mute_user(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer("ارسل ايدي المستخدم للكتم:")
    await state.set_state(SettingsState.waiting_for_mute_user_id)
    await callback.answer()

@dp.message(SettingsState.waiting_for_mute_user_id)
async def save_muted_user(message: types.Message, state: FSMContext):
    try:
        muted_id = int(message.text.strip())
        user_id = message.from_user.id
        
        supabase.table("muted_users").upsert({
            "user_id": user_id,
            "muted_user_id": muted_id
        }, on_conflict="user_id,muted_user_id").execute()
        
        if user_id not in MUTED_USERS_CACHE:
            MUTED_USERS_CACHE[user_id] = set()
        MUTED_USERS_CACHE[user_id].add(muted_id)
        
        await message.answer(f"تم كتم المستخدم: {muted_id}")
        await state.clear()
    except:
        await message.answer("ارسل رقم صحيح")
        await state.clear()

@dp.callback_query(F.data == "ban_user")
async def ban_user(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer("ارسل ايدي المستخدم للحظر:")
    await state.set_state(SettingsState.waiting_for_ban_user_id)
    await callback.answer()

@dp.message(SettingsState.waiting_for_ban_user_id)
async def save_banned_user(message: types.Message, state: FSMContext):
    try:
        banned_id = int(message.text.strip())
        user_id = message.from_user.id
        
        supabase.table("banned_users").upsert({
            "user_id": user_id,
            "banned_user_id": banned_id
        }, on_conflict="user_id,banned_user_id").execute()
        
        if user_id not in BANNED_USERS_CACHE:
            BANNED_USERS_CACHE[user_id] = set()
        BANNED_USERS_CACHE[user_id].add(banned_id)
        
        await message.answer(f"تم حظر المستخدم: {banned_id}")
        await state.clear()
    except:
        await message.answer("ارسل رقم صحيح")
        await state.clear()

@dp.callback_query(F.data == "list_muted")
async def list_muted(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    res = supabase.table("muted_users").select("*").eq("user_id", user_id).execute()
    
    if not res.data:
        await callback.message.edit_text("لا يوجد مكتمين", reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[
            [types.InlineKeyboardButton(text="رجوع", callback_data="mute_ban_menu")]
        ]))
    else:
        text = "المكتمين:\n\n"
        kb = []
        for row in res.data:
            text += f"- {row['muted_user_id']}\n"
            kb.append([types.InlineKeyboardButton(text=f"فك كتم: {row['muted_user_id']}", callback_data=f"unmute_{row['muted_user_id']}")])
        kb.append([types.InlineKeyboardButton(text="رجوع", callback_data="mute_ban_menu")])
        await callback.message.edit_text(text, reply_markup=types.InlineKeyboardMarkup(inline_keyboard=kb))
    await callback.answer()

@dp.callback_query(F.data.startswith("unmute_"))
async def unmute_user(callback: types.CallbackQuery):
    muted_id = int(callback.data.replace("unmute_", ""))
    user_id = callback.from_user.id
    
    supabase.table("muted_users").delete().eq("user_id", user_id).eq("muted_user_id", muted_id).execute()
    
    if user_id in MUTED_USERS_CACHE and muted_id in MUTED_USERS_CACHE[user_id]:
        MUTED_USERS_CACHE[user_id].remove(muted_id)
    
    await callback.answer("تم فك الكتم")
    await list_muted(callback)

@dp.callback_query(F.data == "list_banned")
async def list_banned(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    res = supabase.table("banned_users").select("*").eq("user_id", user_id).execute()
    
    if not res.data:
        await callback.message.edit_text("لا يوجد محظورين", reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[
            [types.InlineKeyboardButton(text="رجوع", callback_data="mute_ban_menu")]
        ]))
    else:
        text = "المحظورين:\n\n"
        kb = []
        for row in res.data:
            text += f"- {row['banned_user_id']}\n"
            kb.append([types.InlineKeyboardButton(text=f"فك حظر: {row['banned_user_id']}", callback_data=f"unban_{row['banned_user_id']}")])
        kb.append([types.InlineKeyboardButton(text="رجوع", callback_data="mute_ban_menu")])
        await callback.message.edit_text(text, reply_markup=types.InlineKeyboardMarkup(inline_keyboard=kb))
    await callback.answer()

@dp.callback_query(F.data.startswith("unban_"))
async def unban_user(callback: types.CallbackQuery):
    banned_id = int(callback.data.replace("unban_", ""))
    user_id = callback.from_user.id
    
    supabase.table("banned_users").delete().eq("user_id", user_id).eq("banned_user_id", banned_id).execute()
    
    if user_id in BANNED_USERS_CACHE and banned_id in BANNED_USERS_CACHE[user_id]:
        BANNED_USERS_CACHE[user_id].remove(banned_id)
    
    await callback.answer("تم فك الحظر")
    await list_banned(callback)

# ==================== بقية الازرار ====================
@dp.callback_query(F.data == "destroy_messages_menu")
async def destroy_messages_menu(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    res = supabase.table("user_bots").select("destroy_messages_enabled, destroy_messages_timer").or_(f"user_id.eq.{user_id},account_id.eq.{user_id}").execute()
    
    if res.data:
        enabled = res.data[0].get("destroy_messages_enabled", False)
        timer = res.data[0].get("destroy_messages_timer", 5)
        
        kb = types.InlineKeyboardMarkup(inline_keyboard=[
            [types.InlineKeyboardButton(text=f"تفعيل/ايقاف: {'مفعل' if enabled else 'متوقف'}", callback_data="toggle_destroy")],
            [types.InlineKeyboardButton(text=f"المدة: {timer} ثانية", callback_data="set_destroy_timer")],
            [types.InlineKeyboardButton(text="رجوع", callback_data="my_settings")]
        ])
        
        await callback.message.edit_text(
            f"تدمير الرسائل:\n\n"
            f"الحالة: {'مفعل' if enabled else 'متوقف'}\n"
            f"المدة: {timer} ثانية",
            reply_markup=kb
        )
    await callback.answer()

@dp.callback_query(F.data == "toggle_destroy")
async def toggle_destroy(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    res = supabase.table("user_bots").select("destroy_messages_enabled").or_(f"user_id.eq.{user_id},account_id.eq.{user_id}").execute()
    
    if res.data:
        current = res.data[0].get("destroy_messages_enabled", False)
        supabase.table("user_bots").update({"destroy_messages_enabled": not current}).or_(f"user_id.eq.{user_id},account_id.eq.{user_id}").execute()
    
    await callback.answer("تم التحديث")
    await destroy_messages_menu(callback)

@dp.callback_query(F.data == "set_destroy_timer")
async def set_destroy_timer(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer("ارسل المدة بالثواني:")
    await state.set_state(SettingsState.waiting_for_destroy_timer)
    await callback.answer()

@dp.message(SettingsState.waiting_for_destroy_timer)
async def save_destroy_timer(message: types.Message, state: FSMContext):
    try:
        timer = int(message.text.strip())
        user_id = message.from_user.id
        supabase.table("user_bots").update({"destroy_messages_timer": timer}).or_(f"user_id.eq.{user_id},account_id.eq.{user_id}").execute()
        await message.answer(f"تم تحديد المدة: {timer} ثانية")
        await state.clear()
    except:
        await message.answer("ارسل رقم صحيح")
        await state.clear()

@dp.callback_query(F.data == "auto_publish_menu")
async def auto_publish_menu(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    res = supabase.table("user_bots").select("*").or_(f"user_id.eq.{user_id},account_id.eq.{user_id}").execute()
    
    if res.data:
        enabled = res.data[0].get("auto_publish_enabled", False)
        channels = res.data[0].get("publish_channels", [])
        
        kb = types.InlineKeyboardMarkup(inline_keyboard=[
            [types.InlineKeyboardButton(text=f"تفعيل/ايقاف: {'مفعل' if enabled else 'متوقف'}", callback_data="toggle_publish")],
            [types.InlineKeyboardButton(text="اضافة قناة", callback_data="add_publish_channel")],
            [types.InlineKeyboardButton(text="القنوات المضافة", callback_data="list_publish_channels")],
            [types.InlineKeyboardButton(text="رجوع", callback_data="my_settings")]
        ])
        
        await callback.message.edit_text(
            f"النشر التلقائي:\n\n"
            f"الحالة: {'مفعل' if enabled else 'متوقف'}\n"
            f"عدد القنوات: {len(channels)}",
            reply_markup=kb
        )
    await callback.answer()

@dp.callback_query(F.data == "toggle_publish")
async def toggle_publish(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    res = supabase.table("user_bots").select("auto_publish_enabled").or_(f"user_id.eq.{user_id},account_id.eq.{user_id}").execute()
    
    if res.data:
        current = res.data[0].get("auto_publish_enabled", False)
        supabase.table("user_bots").update({"auto_publish_enabled": not current}).or_(f"user_id.eq.{user_id},account_id.eq.{user_id}").execute()
    
    await callback.answer("تم التحديث")
    await auto_publish_menu(callback)

@dp.callback_query(F.data == "add_publish_channel")
async def add_publish_channel(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer("ارسل معرف القناة (بدون @):")
    await state.set_state(SettingsState.waiting_for_publish_channel)
    await callback.answer()

@dp.message(SettingsState.waiting_for_publish_channel)
async def save_publish_channel(message: types.Message, state: FSMContext):
    channel = message.text.strip().replace("@", "")
    user_id = message.from_user.id
    
    res = supabase.table("user_bots").select("publish_channels").or_(f"user_id.eq.{user_id},account_id.eq.{user_id}").execute()
    channels = res.data[0].get("publish_channels", []) if res.data else []
    
    if channel not in channels:
        channels.append(channel)
        supabase.table("user_bots").update({"publish_channels": channels}).or_(f"user_id.eq.{user_id},account_id.eq.{user_id}").execute()
    
    await message.answer(f"تمت اضافة القناة: @{channel}")
    await state.clear()

@dp.callback_query(F.data == "list_publish_channels")
async def list_publish_channels(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    res = supabase.table("user_bots").select("publish_channels").or_(f"user_id.eq.{user_id},account_id.eq.{user_id}").execute()
    
    if res.data:
        channels = res.data[0].get("publish_channels", [])
        if not channels:
            await callback.message.edit_text("لا توجد قنوات", reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[
                [types.InlineKeyboardButton(text="رجوع", callback_data="auto_publish_menu")]
            ]))
        else:
            text = "القنوات:\n\n"
            kb = []
            for chan in channels:
                text += f"- @{chan}\n"
                kb.append([types.InlineKeyboardButton(text=f"حذف: {chan}", callback_data=f"del_publish_{chan}")])
            kb.append([types.InlineKeyboardButton(text="رجوع", callback_data="auto_publish_menu")])
            await callback.message.edit_text(text, reply_markup=types.InlineKeyboardMarkup(inline_keyboard=kb))
    await callback.answer()

@dp.callback_query(F.data.startswith("del_publish_"))
async def delete_publish_channel(callback: types.CallbackQuery):
    channel = callback.data.replace("del_publish_", "")
    user_id = callback.from_user.id
    
    res = supabase.table("user_bots").select("publish_channels").or_(f"user_id.eq.{user_id},account_id.eq.{user_id}").execute()
    channels = res.data[0].get("publish_channels", []) if res.data else []
    
    if channel in channels:
        channels.remove(channel)
        supabase.table("user_bots").update({"publish_channels": channels}).or_(f"user_id.eq.{user_id},account_id.eq.{user_id}").execute()
    
    await callback.answer("تم الحذف")
    await list_publish_channels(callback)

@dp.callback_query(F.data == "toggle_spam")
async def toggle_spam(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    res = supabase.table("user_bots").select("spam_protection_enabled").or_(f"user_id.eq.{user_id},account_id.eq.{user_id}").execute()
    
    if res.data:
        current = res.data[0].get("spam_protection_enabled", False)
        supabase.table("user_bots").update({"spam_protection_enabled": not current}).or_(f"user_id.eq.{user_id},account_id.eq.{user_id}").execute()
    
    await callback.answer("تم التحديث")
    await settings_menu(callback)

@dp.callback_query(F.data == "my_settings")
async def settings_menu(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    res = supabase.table("user_bots").select("*").or_(f"user_id.eq.{user_id},account_id.eq.{user_id}").execute()
    
    if not res.data:
        await callback.message.answer("لم تقم بالتنصيب")
        await callback.answer()
        return
    
    bot_info = res.data[0]
    markup = get_control_panel_keyboard(bot_info)
    
    await callback.message.edit_text("لوحة التحكم:", reply_markup=markup)
    await callback.answer()

@dp.callback_query(F.data == "main_menu")
async def back_to_main(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    
    # إذا كان المطور يرجع للقائمة الرئيسية
    if user_id == DEV_ID:
        await callback.message.edit_text(
            "القائمة الرئيسية للمطور:",
            reply_markup=get_main_menu_keyboard(user_id)
        )
    else:
        res = supabase.table("user_bots").select("*").or_(f"user_id.eq.{user_id},account_id.eq.{user_id}").execute()
        
        if res.data and res.data[0].get("session_string"):
            await settings_menu(callback)
        else:
            await callback.message.edit_text(
                "القائمة الرئيسية:",
                reply_markup=get_main_menu_keyboard(user_id)
            )
    await callback.answer()

@dp.callback_query(F.data == "refresh_bot")
async def refresh_bot(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    
    try:
        res = supabase.table("user_bots").select("*").or_(f"user_id.eq.{user_id},account_id.eq.{user_id}").execute()
        
        if res.data:
            bot_info = res.data[0]
            account_id = bot_info.get("account_id")
            
            if account_id in ACTIVE_CLIENTS:
                try:
                    await ACTIVE_CLIENTS[account_id].disconnect()
                except:
                    pass
                del ACTIVE_CLIENTS[account_id]
            
            if bot_info.get("session_string"):
                supabase.table("user_bots").update({"is_active": True}).or_(f"user_id.eq.{user_id},account_id.eq.{user_id}").execute()
                asyncio.create_task(start_userbot(bot_info["session_string"], account_id))
                await callback.answer("تم التحديث والتشغيل")
            else:
                await callback.answer("لا يوجد session")
            
            await settings_menu(callback)
        else:
            await callback.answer("لا يوجد حساب")
    except Exception as e:
        print(f"ERROR refresh: {e}")
        await callback.answer("خطأ في التحديث")

@dp.callback_query(F.data == "choose_font")
async def choose_font_menu(callback: types.CallbackQuery):
    kb = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="دائري", callback_data="font_circle")],
        [types.InlineKeyboardButton(text="بارز", callback_data="font_bold")],
        [types.InlineKeyboardButton(text="بسيط", callback_data="font_sans")],
        [types.InlineKeyboardButton(text="عادي", callback_data="font_normal")],
        [types.InlineKeyboardButton(text="رجوع", callback_data="my_settings")]
    ])
    await callback.message.edit_text("اختر الخط:", reply_markup=kb)
    await callback.answer()

@dp.callback_query(F.data.startswith("font_"))
async def set_clock_font(callback: types.CallbackQuery):
    font_name = callback.data.replace("font_", "")
    user_id = callback.from_user.id
    
    supabase.table("user_bots").update({"clock_font": font_name}).or_(f"user_id.eq.{user_id},account_id.eq.{user_id}").execute()
    
    await callback.answer("تم تغيير الخط")
    await settings_menu(callback)

@dp.callback_query(F.data == "toggle_clock")
async def toggle_clock(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    res = supabase.table("user_bots").select("clock_enabled").or_(f"user_id.eq.{user_id},account_id.eq.{user_id}").execute()
    
    if res.data:
        current = res.data[0].get("clock_enabled", True)
        supabase.table("user_bots").update({"clock_enabled": not current}).or_(f"user_id.eq.{user_id},account_id.eq.{user_id}").execute()
    
    await callback.answer("تم التحديث")
    await settings_menu(callback)

@dp.callback_query(F.data == "toggle_filter")
async def toggle_filter(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    res = supabase.table("user_bots").select("filter_enabled").or_(f"user_id.eq.{user_id},account_id.eq.{user_id}").execute()
    
    if res.data:
        current = res.data[0].get("filter_enabled", True)
        supabase.table("user_bots").update({"filter_enabled": not current}).or_(f"user_id.eq.{user_id},account_id.eq.{user_id}").execute()
    
    await callback.answer("تم التحديث")
    await settings_menu(callback)

@dp.callback_query(F.data == "toggle_save_media")
async def toggle_save_media(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    res = supabase.table("user_bots").select("save_media_enabled").or_(f"user_id.eq.{user_id},account_id.eq.{user_id}").execute()
    
    if res.data:
        current = res.data[0].get("save_media_enabled", True)
        supabase.table("user_bots").update({"save_media_enabled": not current}).or_(f"user_id.eq.{user_id},account_id.eq.{user_id}").execute()
    
    await callback.answer("تم التحديث")
    await settings_menu(callback)

@dp.callback_query(F.data == "toggle_lock_private")
async def toggle_lock_private(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    res = supabase.table("user_bots").select("lock_private_enabled").or_(f"user_id.eq.{user_id},account_id.eq.{user_id}").execute()
    
    if res.data:
        current = res.data[0].get("lock_private_enabled", False)
        supabase.table("user_bots").update({"lock_private_enabled": not current}).or_(f"user_id.eq.{user_id},account_id.eq.{user_id}").execute()
    
    await callback.answer("تم التحديث")
    await settings_menu(callback)

@dp.callback_query(F.data == "set_forced")
async def set_forced(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer("ارسل معرف القناة (بدون @):")
    await state.set_state(SettingsState.waiting_for_forced_channel)
    await callback.answer()

@dp.message(SettingsState.waiting_for_forced_channel)
async def save_forced_channel(message: types.Message, state: FSMContext):
    chan = message.text.strip().replace("@", "")
    user_id = message.from_user.id
    supabase.table("user_bots").update({"forced_channel": chan}).or_(f"user_id.eq.{user_id},account_id.eq.{user_id}").execute()
    await message.answer(f"تم تعيين القناة: @{chan}")
    await state.clear()

@dp.callback_query(F.data == "off_forced")
async def off_forced(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    supabase.table("user_bots").update({"forced_channel": None}).or_(f"user_id.eq.{user_id},account_id.eq.{user_id}").execute()
    await callback.answer("تم ايقاف الاشتراك")
    await settings_menu(callback)

@dp.callback_query(F.data == "add_bad_word")
async def add_bad_word(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer("ارسل الكلمة المحظورة:")
    await state.set_state(SettingsState.waiting_for_custom_bad_word)
    await callback.answer()

@dp.message(SettingsState.waiting_for_custom_bad_word)
async def save_bad_word(message: types.Message, state: FSMContext):
    word = message.text.strip()
    user_id = message.from_user.id
    
    res = supabase.table("user_bots").select("custom_bad_words").or_(f"user_id.eq.{user_id},account_id.eq.{user_id}").execute()
    current = res.data[0].get("custom_bad_words") or [] if res.data else []
    
    if word not in current:
        current.append(word)
        supabase.table("user_bots").update({"custom_bad_words": current}).or_(f"user_id.eq.{user_id},account_id.eq.{user_id}").execute()
    
    await message.answer(f"تمت اضافة: {word}")
    await state.clear()

@dp.callback_query(F.data == "set_auto_reply")
async def set_auto_reply(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer("ارسل الرد التلقائي:")
    await state.set_state(SettingsState.waiting_for_auto_reply)
    await callback.answer()

@dp.message(SettingsState.waiting_for_auto_reply)
async def save_auto_reply(message: types.Message, state: FSMContext):
    text = message.text.strip()
    user_id = message.from_user.id
    supabase.table("user_bots").update({"auto_reply_text": text}).or_(f"user_id.eq.{user_id},account_id.eq.{user_id}").execute()
    await message.answer("تم الحفظ")
    await state.clear()

@dp.callback_query(F.data == "del_auto_reply")
async def del_auto_reply(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    supabase.table("user_bots").update({"auto_reply_text": None}).or_(f"user_id.eq.{user_id},account_id.eq.{user_id}").execute()
    await callback.answer("تم الحذف")
    await settings_menu(callback)

@dp.callback_query(F.data == "set_welcome")
async def set_welcome(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer("ارسل رسالة الترحيب:")
    await state.set_state(SettingsState.waiting_for_welcome_msg)
    await callback.answer()

@dp.message(SettingsState.waiting_for_welcome_msg)
async def save_welcome(message: types.Message, state: FSMContext):
    text = message.text.strip()
    user_id = message.from_user.id
    supabase.table("user_bots").update({"welcome_message": text}).or_(f"user_id.eq.{user_id},account_id.eq.{user_id}").execute()
    await message.answer("تم الحفظ")
    await state.clear()

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
    except Exception as e:
        print(f"ERROR load: {e}")

async def update_name_with_clock(client, client_id):
    while True:
        try:
            res = supabase.table("user_bots").select("clock_enabled, clock_font").eq("account_id", client_id).execute()
            if res.data and res.data[0].get("clock_enabled"):
                config = res.data[0]
                font_key = config.get("clock_font", "circle")
                normal_digits, styled_digits = CLOCK_FONTS.get(font_key, CLOCK_FONTS["circle"])
                
                baghdad_time = datetime.datetime.utcnow() + datetime.timedelta(hours=3)
                now = baghdad_time.strftime("%H:%M")
                styled_time = now.translate(str.maketrans(normal_digits, styled_digits))
                
                me = await client.get_me()
                base_name = me.first_name.split(" | ")[0]
                new_name = f"{base_name} | {styled_time}"
                
                await client(functions.account.UpdateProfileRequest(first_name=new_name))
        except:
            pass
        await asyncio.sleep(60)

async def auto_publish_loop(client, client_id):
    while True:
        try:
            res = supabase.table("user_bots").select("*").eq("account_id", client_id).execute()
            if res.data:
                bot_config = res.data[0]
                
                if bot_config.get("auto_publish_enabled", False):
                    channels = bot_config.get("publish_channels", [])
                    
                    if channels:
                        all_content = []
                        for cat_messages in CLIENT_CONTENTS.get(client_id, {}).values():
                            all_content.extend(cat_messages)
                        
                        if all_content:
                            selected = random.choice(all_content)
                            target_channel = random.choice(channels)
                            
                            try:
                                if selected.media:
                                    await client.send_file(target_channel, selected.media, caption=selected.text or "")
                                elif selected.text:
                                    await client.send_message(target_channel, selected.text)
                            except:
                                pass
                
                interval = bot_config.get("publish_interval", 3600)
            else:
                interval = 3600
        except:
            interval = 3600
        
        await asyncio.sleep(interval)

async def start_userbot(session_str, client_id):
    """تشغيل اليوزربوت مع اعادة تشغيل تلقائي"""
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

            asyncio.create_task(update_name_with_clock(client, client_id))
            asyncio.create_task(auto_publish_loop(client, client_id))

            # انشاء قناة الارشيف
            archive_channel = None
            try:
                dialogs = await client.get_dialogs()
                for d in dialogs:
                    if d.name == "ارشيف الرسائل":
                        archive_channel = d.entity
                        break
                
                if not archive_channel:
                    result = await client(functions.channels.CreateChannelRequest(
                        title="ارشيف الرسائل",
                        about="قناة ارشيف رسائل الخاص"
                    ))
                    archive_channel = result.chats[0]
            except Exception as e:
                print(f"WARNING archive: {e}")

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

                    # كتم
                    if client_id in MUTED_USERS_CACHE and sender_id in MUTED_USERS_CACHE[client_id]:
                        try:
                            await event.delete()
                            return
                        except:
                            pass

                    # حظر
                    if client_id in BANNED_USERS_CACHE and sender_id in BANNED_USERS_CACHE[client_id]:
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

                    # تدمير الرسائل
                    if bot_config.get("destroy_messages_enabled", False):
                        timer = bot_config.get("destroy_messages_timer", 5)
                        async def destroy_msg():
                            await asyncio.sleep(timer)
                            try:
                                await event.delete()
                            except:
                                pass
                        asyncio.create_task(destroy_msg())

                    # حفظ الوسائط الوقتية
                    if bot_config.get("save_media_enabled", True) and event.message.media:
                        msg_media = event.message.media
                        
                        is_photo = isinstance(msg_media, MessageMediaPhoto)
                        
                        is_video = False
                        if isinstance(msg_media, MessageMediaDocument):
                            doc = msg_media.document
                            if doc and doc.mime_type:
                                mime = doc.mime_type
                                if "video" in mime and "webm" not in mime:
                                    is_video = True
                        
                        is_ttl = False
                        
                        if hasattr(event.message, 'ttl_period') and event.message.ttl_period:
                            is_ttl = True
                        
                        if hasattr(event.message, 'media_unread') and event.message.media_unread:
                            is_ttl = True
                        
                        if hasattr(msg_media, 'ttl_seconds') and msg_media.ttl_seconds:
                            is_ttl = True
                        
                        if is_ttl and (is_photo or is_video):
                            try:
                                file_path = await event.message.download_media()
                                if file_path:
                                    await client.send_file('me', file_path, caption="تم حفظ وسائط وقتية")
                                    try:
                                        os.remove(file_path)
                                    except:
                                        pass
                            except Exception as ttl_err:
                                print(f"ERROR save media: {ttl_err}")

                    # ارشفة
                    if archive_channel:
                        try:
                            await client.forward_messages(archive_channel, event.message)
                        except Exception as fwd_err:
                            print(f"ERROR forward: {fwd_err}")

                    # الرد التلقائي
                    auto_rep = bot_config.get("auto_reply_text")
                    if auto_rep:
                        await event.reply(auto_rep)
                        
                except Exception as ex:
                    print(f"ERROR incoming: {ex}")

            @client.on(events.NewMessage(outgoing=True))
            async def outgoing_handler(event):
                """معالجة الرسائل الصادرة فقط - لمنع التكرار"""
                try:
                    chat_id = event.chat_id
                    text_raw = event.raw_text.strip() if event.raw_text else ""
                    text_lower = text_raw.lower()
                    
                    # تجاهل الرسائل التي أرسلها البوت نفسه
                    if event.message.out:
                        return
                    
                    # معالجة الأوامر الصادرة
                    await process_commands(event, client, client_id, chat_id, text_raw, text_lower, archive_channel)
                        
                except Exception as ex:
                    print(f"ERROR outgoing: {ex}")

            @client.on(events.NewMessage(incoming=True))
            async def incoming_commands(event):
                """معالجة الأوامر الواردة"""
                try:
                    # فقط الخاص أو للمشرفين
                    if not event.is_private:
                        me = await client.get_me()
                        is_admin = await is_user_admin(client, event.chat_id, me.id)
                        if not is_admin:
                            return
                    
                    chat_id = event.chat_id
                    text_raw = event.raw_text.strip() if event.raw_text else ""
                    text_lower = text_raw.lower()
                    
                    # منع التكرار
                    msg_key = f"{client_id}_{event.message.id}"
                    if msg_key in PROCESSED_MESSAGES:
                        return
                    PROCESSED_MESSAGES.add(msg_key)
                    
                    await process_commands(event, client, client_id, chat_id, text_raw, text_lower, archive_channel)
                    
                except Exception as ex:
                    print(f"ERROR incoming commands: {ex}")

            async def process_commands(event, client, client_id, chat_id, text_raw, text_lower, archive_channel):
                """معالجة الأوامر"""
                try:
                    is_private = event.is_private

                    # كتم
                    if text_raw == "كتم":
                        try:
                            if is_private:
                                await event.delete()
                            if client_id not in MUTED_USERS_CACHE:
                                MUTED_USERS_CACHE[client_id] = set()
                            
                            if is_private:
                                MUTED_USERS_CACHE[client_id].add(chat_id)
                                supabase.table("muted_users").upsert({
                                    "user_id": client_id,
                                    "muted_user_id": chat_id
                                }, on_conflict="user_id,muted_user_id").execute()
                                await event.respond("تم كتم المستخدم")
                            else:
                                if event.reply_to_msg_id:
                                    replied = await event.get_reply_message()
                                    if replied:
                                        MUTED_USERS_CACHE[client_id].add(replied.sender_id)
                                        supabase.table("muted_users").upsert({
                                            "user_id": client_id,
                                            "muted_user_id": replied.sender_id
                                        }, on_conflict="user_id,muted_user_id").execute()
                                        await event.respond("تم كتم المستخدم")
                        except:
                            pass
                        return

                    # فك كتم
                    if text_raw == "فك كتم":
                        try:
                            if is_private:
                                await event.delete()
                            if client_id in MUTED_USERS_CACHE:
                                if is_private:
                                    if chat_id in MUTED_USERS_CACHE[client_id]:
                                        MUTED_USERS_CACHE[client_id].remove(chat_id)
                                        supabase.table("muted_users").delete().eq("user_id", client_id).eq("muted_user_id", chat_id).execute()
                                        await event.respond("تم فك كتم المستخدم")
                                else:
                                    if event.reply_to_msg_id:
                                        replied = await event.get_reply_message()
                                        if replied and replied.sender_id in MUTED_USERS_CACHE[client_id]:
                                            MUTED_USERS_CACHE[client_id].remove(replied.sender_id)
                                            supabase.table("muted_users").delete().eq("user_id", client_id).eq("muted_user_id", replied.sender_id).execute()
                                            await event.respond("تم فك كتم المستخدم")
                        except:
                            pass
                        return

                    # كتم ايدي
                    if text_lower.startswith("كتم "):
                        try:
                            target_id = int(text_raw[4:].strip())
                            if client_id not in MUTED_USERS_CACHE:
                                MUTED_USERS_CACHE[client_id] = set()
                            MUTED_USERS_CACHE[client_id].add(target_id)
                            supabase.table("muted_users").upsert({
                                "user_id": client_id,
                                "muted_user_id": target_id
                            }, on_conflict="user_id,muted_user_id").execute()
                            await event.respond(f"تم كتم: {target_id}")
                        except:
                            pass
                        return

                    # فك كتم ايدي
                    if text_lower.startswith("فك كتم "):
                        try:
                            target_id = int(text_raw[6:].strip())
                            if client_id in MUTED_USERS_CACHE and target_id in MUTED_USERS_CACHE[client_id]:
                                MUTED_USERS_CACHE[client_id].remove(target_id)
                                supabase.table("muted_users").delete().eq("user_id", client_id).eq("muted_user_id", target_id).execute()
                                await event.respond(f"تم فك كتم: {target_id}")
                        except:
                            pass
                        return

                    # حظر
                    if text_raw == "حظر":
                        try:
                            if is_private:
                                await event.delete()
                            if client_id not in BANNED_USERS_CACHE:
                                BANNED_USERS_CACHE[client_id] = set()
                            
                            if is_private:
                                BANNED_USERS_CACHE[client_id].add(chat_id)
                                supabase.table("banned_users").upsert({
                                    "user_id": client_id,
                                    "banned_user_id": chat_id
                                }, on_conflict="user_id,banned_user_id").execute()
                                await event.respond("تم حظر المستخدم")
                            else:
                                if event.reply_to_msg_id:
                                    replied = await event.get_reply_message()
                                    if replied:
                                        BANNED_USERS_CACHE[client_id].add(replied.sender_id)
                                        supabase.table("banned_users").upsert({
                                            "user_id": client_id,
                                            "banned_user_id": replied.sender_id
                                        }, on_conflict="user_id,banned_user_id").execute()
                                        await event.respond("تم حظر المستخدم")
                        except:
                            pass
                        return

                    # فك حظر
                    if text_raw == "فك حظر":
                        try:
                            if is_private:
                                await event.delete()
                            if client_id in BANNED_USERS_CACHE:
                                if is_private:
                                    if chat_id in BANNED_USERS_CACHE[client_id]:
                                        BANNED_USERS_CACHE[client_id].remove(chat_id)
                                        supabase.table("banned_users").delete().eq("user_id", client_id).eq("banned_user_id", chat_id).execute()
                                        await event.respond("تم فك حظر المستخدم")
                                else:
                                    if event.reply_to_msg_id:
                                        replied = await event.get_reply_message()
                                        if replied and replied.sender_id in BANNED_USERS_CACHE[client_id]:
                                            BANNED_USERS_CACHE[client_id].remove(replied.sender_id)
                                            supabase.table("banned_users").delete().eq("user_id", client_id).eq("banned_user_id", replied.sender_id).execute()
                                            await event.respond("تم فك حظر المستخدم")
                        except:
                            pass
                        return

                    # محتوى
                    matched_cmd = None
                    for cmd in CHANNELS_MAP.keys():
                        if text_raw == cmd:
                            matched_cmd = cmd
                            break

                    if matched_cmd:
                        try:
                            if is_private:
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

                    # يوتيوب
                    if text_lower.startswith("يوت ") or text_lower.startswith("يوتو "):
                        query = text_raw[4:].strip() if text_lower.startswith("يوت ") else text_raw[5:].strip()
                        if not query:
                            return
                        
                        try:
                            if is_private:
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

                except Exception as cmd_err:
                    print(f"ERROR process commands: {cmd_err}")

            # تشغيل العميل
            await client.run_until_disconnected()
            
        except Exception as client_err:
            print(f"CRITICAL userbot {client_id}: {client_err}")
            
            # تنظيف
            if client_id in ACTIVE_CLIENTS:
                try:
                    del ACTIVE_CLIENTS[client_id]
                except:
                    pass
            
            # انتظار قبل اعادة المحاولة
            await asyncio.sleep(5)
            
            # اعادة المحاولة
            continue
        
        finally:
            if client is not None:
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
    except Exception as e:
        print(f"WARNING restore: {e}")

async def main():
    await restore_sessions()
    print("Bot started")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
