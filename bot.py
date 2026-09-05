import os
import random
import asyncio
import datetime
import json
from telethon import TelegramClient, events, functions
from telethon.sessions import StringSession
from telethon.tl.types import MessageMediaPhoto, MessageMediaDocument
from supabase import create_client, Client

# ==================== الإعدادات ====================
API_ID = int(os.environ.get("API_ID", 0))
API_HASH = os.environ.get("API_HASH", "")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "")
WEB_APP_URL = os.environ.get("WEB_APP_URL", "https://your-app.vercel.app")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

DEV_ID = 5126968608
DEV_USER = "@toe7e"
MAX_USERS = 300

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

DEFAULT_BAD_WORDS = ["وهابي", "عفن", "سخيف", "كلب", "انقلع"]

CLOCK_FONTS = {
    "circle": ("0123456789", "⓪①②③④⑤⑥⑦⑧⑨"),
    "bold": ("0123456789", "𝟎𝟏𝟐𝟑𝟒𝟓𝟔𝟕𝟖𝟗"),
    "sans": ("0123456789", "𝟶𝟷𝟸𝟹𝟺𝟻𝟼𝟽𝟾𝟿"),
    "normal": ("0123456789", "0123456789")
}

# ==================== إعدادات قابلة للتخصيص ====================
def get_setting(key, default=None):
    try:
        res = supabase.table("bot_settings").select("*").eq("setting_key", key).execute()
        if res.data:
            return res.data[0].get("setting_value", default)
        return default
    except:
        return default

def save_setting(key, value):
    try:
        supabase.table("bot_settings").upsert({
            "setting_key": key,
            "setting_value": value
        }, on_conflict="setting_key").execute()
        return True
    except:
        return False

def check_subscription(user_id):
    try:
        res = supabase.table("subscriptions").select("*").eq("user_id", user_id).execute()
        if not res.data:
            return False, "لا يوجد اشتراك"
        sub = res.data[0]
        if not sub.get("is_active", False):
            return False, "الاشتراك موقوف"
        if sub.get("is_permanent", False):
            return True, "اشتراك دائم"
        expiry = sub.get("expiry_date")
        if expiry:
            expiry_date = datetime.datetime.fromisoformat(expiry)
            if expiry_date < datetime.datetime.now():
                supabase.table("subscriptions").update({"is_active": False}).eq("user_id", user_id).execute()
                return False, "انتهى الاشتراك"
        return True, "اشتراك فعال"
    except:
        return False, "خطأ"

def get_subscription_info(user_id):
    try:
        res = supabase.table("subscriptions").select("*").eq("user_id", user_id).execute()
        if res.data:
            sub = res.data[0]
            if sub.get("is_permanent"):
                return "دائم"
            expiry = sub.get("expiry_date")
            if expiry:
                return f"حتى {expiry[:10]}"
            return "غير محدد"
        return "لا يوجد"
    except:
        return "خطأ"

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
    waiting_for_grant_user_id = State()
    waiting_for_grant_days = State()
    waiting_for_block_user_id = State()
    waiting_for_broadcast_text = State()
    waiting_for_admins = State()

def safe_get(data_dict, key, default=None):
    if isinstance(data_dict, dict):
        return data_dict.get(key, default)
    return default

def get_main_menu_keyboard(user_id):
    kb = [
        [types.InlineKeyboardButton(text="فتح اللوحة الملونة", web_app=types.WebAppInfo(url=WEB_APP_URL))],
        [types.InlineKeyboardButton(text="🚀 تفعيل الاشتراك", callback_data="free_subscription"),
         types.InlineKeyboardButton(text="⚙️ لوحة التحكم", callback_data="my_settings")],
        [types.InlineKeyboardButton(text="📚 تعليمات", callback_data="bot_instructions"),
         types.InlineKeyboardButton(text="👨‍💻 المطور", url=f"https://t.me/{DEV_USER.replace('@','')}")]
    ]
    if user_id == DEV_ID:
        kb.append([types.InlineKeyboardButton(text="🛠 لوحة المطور", callback_data="dev_admin_panel")])
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
        [types.InlineKeyboardButton(text="فتح اللوحة الملونة", web_app=types.WebAppInfo(url=WEB_APP_URL))],
        [types.InlineKeyboardButton(text="🔇 الكتم والحظر", callback_data="mute_ban_menu")],
        [types.InlineKeyboardButton(text=f"🗑 تدمير: {destroy_st}", callback_data="destroy_messages_menu"),
         types.InlineKeyboardButton(text=f"📢 نشر: {publish_st}", callback_data="auto_publish_menu")],
        [types.InlineKeyboardButton(text=f"🛡 حماية: {spam_st}", callback_data="toggle_spam"),
         types.InlineKeyboardButton(text=f"🔒 الخاص: {lock_st}", callback_data="toggle_lock_private")],
        [types.InlineKeyboardButton(text=f"🚫 فلتر: {filter_st}", callback_data="toggle_filter"),
         types.InlineKeyboardButton(text=f"⏰ ساعة: {clock_st}", callback_data="toggle_clock")],
        [types.InlineKeyboardButton(text=f"💾 وسائط: {save_st}", callback_data="toggle_save_media"),
         types.InlineKeyboardButton(text=f"🔤 خط: {current_font}", callback_data="choose_font")],
        [types.InlineKeyboardButton(text="🤖 ردود", callback_data="set_auto_reply"),
         types.InlineKeyboardButton(text="🗑 حذف ردود", callback_data="del_auto_reply")],
        [types.InlineKeyboardButton(text="📢 اشتراك إجباري", callback_data="set_forced"),
         types.InlineKeyboardButton(text="🚫 إيقافه", callback_data="off_forced")],
        [types.InlineKeyboardButton(text="👋 ترحيب", callback_data="set_welcome"),
         types.InlineKeyboardButton(text="🔄 تحديث", callback_data="refresh_bot")],
        [types.InlineKeyboardButton(text="🏠 الرئيسية", callback_data="main_menu")]
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

# ==================== معالجة Web App ====================
@dp.message(lambda message: message.web_app_data is not None)
async def handle_web_app(message: types.Message):
    data = message.web_app_data.data
    user_id = message.from_user.id
    
    if user_id != DEV_ID:
        await message.answer("هذه اللوحة مخصصة للمطور فقط")
        return
    
    if data == "dev_panel":
        await dev_admin_panel_from_message(message)
    elif data == "subscription":
        await message.answer("اضغط /start للبدء")
    elif data == "settings":
        await show_settings_from_message(message)
    elif data == "instructions":
        await message.answer("التعليمات:\n\n- غنيلي - شعر - مزج - ميمز - قرآن\n- يوت اسم الأغنية\n- كتم - فك كتم\n- حظر - فك حظر")
    elif data == "contact":
        await message.answer(f"تواصل مع المطور: {DEV_USER}")
    elif data == "mute_menu":
        await show_mute_menu(message)
    elif data == "ban_menu":
        await show_ban_menu(message)
    elif data == "destroy":
        await show_destroy_menu(message)
    elif data == "publish":
        await show_publish_menu(message)

async def dev_admin_panel_from_message(message: types.Message):
    try:
        users_res = supabase.table("user_bots").select("*").execute()
        total = len(users_res.data) if users_res.data else 0
        running = len(ACTIVE_CLIENTS)
        
        subs_res = supabase.table("subscriptions").select("*").execute()
        active_subs = sum(1 for x in (subs_res.data or []) if x.get("is_active"))
        
        kb = types.InlineKeyboardMarkup(inline_keyboard=[
            [types.InlineKeyboardButton(text="👥 المستخدمين", callback_data="dev_list_users"),
             types.InlineKeyboardButton(text="📢 إذاعة", callback_data="dev_broadcast")],
            [types.InlineKeyboardButton(text="💳 الاشتراكات", callback_data="dev_subscriptions"),
             types.InlineKeyboardButton(text="🚫 المحظورين", callback_data="dev_blocked_list")],
            [types.InlineKeyboardButton(text="👑 الأدمنية", callback_data="dev_admins"),
             types.InlineKeyboardButton(text="📊 إحصائيات", callback_data="dev_stats")],
            [types.InlineKeyboardButton(text="🛠 إعدادات", callback_data="dev_bot_settings"),
             types.InlineKeyboardButton(text="▶️ تشغيل الكل", callback_data="dev_start_all")],
            [types.InlineKeyboardButton(text="🏠 الرئيسية", callback_data="main_menu")]
        ])
        
        await message.answer(
            f"🛠 لوحة المطور:\n\n"
            f"👥 المستخدمين: {total}\n"
            f"⚡ يعملون: {running}\n"
            f"💳 اشتراكات نشطة: {active_subs}",
            reply_markup=kb
        )
    except Exception as e:
        print(f"ERROR: {e}")
        await message.answer("خطأ")

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    user_id = message.from_user.id
    
    # التحقق من الحظر
    try:
        blocked = supabase.table("blocked_users").select("*").eq("user_id", user_id).execute()
        if blocked.data:
            await message.answer("أنت محظور من استخدام البوت")
            return
    except:
        pass
    
    # التحقق من الأدمنية
    is_admin = False
    try:
        admins = get_setting("admins", [DEV_ID])
        if user_id in admins:
            is_admin = True
    except:
        pass
    
    if user_id == DEV_ID or is_admin:
        # مطور أو أدمن
        try:
            res = supabase.table("user_bots").select("*").or_(f"user_id.eq.{user_id},account_id.eq.{user_id}").execute()
            
            if res.data and res.data[0].get("session_string"):
                bot_info = res.data[0]
                markup = get_control_panel_keyboard(bot_info)
                sub_info = get_subscription_info(user_id)
                
                await message.answer(
                    f"لوحة التحكم\n\n"
                    f"اشتراكك: {sub_info}",
                    reply_markup=markup
                )
                return
            
            await message.answer("مرحباً بك", reply_markup=get_main_menu_keyboard(user_id))
        except Exception as e:
            print(f"ERROR: {e}")
            await message.answer("حدث خطأ")
    else:
        # مستخدم عادي
        is_valid, msg = check_subscription(user_id)
        if not is_valid:
            kb = types.InlineKeyboardMarkup(inline_keyboard=[
                [types.InlineKeyboardButton(text="🚀 طلب اشتراك", callback_data="free_subscription")],
                [types.InlineKeyboardButton(text="👨‍💻 المطور", url=f"https://t.me/{DEV_USER.replace('@','')}")]
            ])
            await message.answer(
                f"مرحباً بك\n\n"
                f"للاستفادة من البوت تحتاج اشتراك\n"
                f"سبب الرفض: {msg}",
                reply_markup=kb
            )
            return
        
        try:
            res = supabase.table("user_bots").select("*").or_(f"user_id.eq.{user_id},account_id.eq.{user_id}").execute()
            
            if res.data and res.data[0].get("session_string"):
                bot_info = res.data[0]
                markup = get_control_panel_keyboard(bot_info)
                sub_info = get_subscription_info(user_id)
                
                await message.answer(
                    f"لوحة التحكم\n\n"
                    f"اشتراكك: {sub_info}",
                    reply_markup=markup
                )
                return
            
            await message.answer("مرحباً بك", reply_markup=get_main_menu_keyboard(user_id))
        except Exception as e:
            print(f"ERROR: {e}")
            await message.answer("حدث خطأ")

@dp.callback_query(F.data == "free_subscription")
async def free_subscription(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer("جاري التفعيل...")
    await state.clear()
    
    user_id = callback.from_user.id
    
    try:
        res = supabase.table("subscriptions").select("user_id").execute()
        if len(res.data or []) >= MAX_USERS:
            await callback.message.answer("وصلنا للحد الأقصى، راسل المطور")
            return
    except:
        pass
    
    try:
        supabase.table("subscriptions").upsert({
            "user_id": user_id,
            "subscription_type": "trial",
            "start_date": datetime.datetime.now().isoformat(),
            "expiry_date": (datetime.datetime.now() + datetime.timedelta(days=7)).isoformat(),
            "is_permanent": False,
            "is_active": True
        }, on_conflict="user_id").execute()
        
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
        "تم تفعيل اشتراك تجريبي 7 أيام\n\n"
        "اضغط زر مشاركة رقم الهاتف",
        reply_markup=contact_kb
    )
    await state.set_state(LoginState.waiting_for_phone)

# ==================== لوحة المطور ====================
@dp.callback_query(F.data == "dev_admin_panel")
async def dev_admin_panel(callback: types.CallbackQuery):
    if callback.from_user.id != DEV_ID:
        # التحقق من الأدمنية
        admins = get_setting("admins", [DEV_ID])
        if callback.from_user.id not in admins:
            await callback.answer("مخصص للمطور فقط")
            return
    
    try:
        users_res = supabase.table("user_bots").select("*").execute()
        total = len(users_res.data) if users_res.data else 0
        running = len(ACTIVE_CLIENTS)
        
        subs_res = supabase.table("subscriptions").select("*").execute()
        active_subs = sum(1 for x in (subs_res.data or []) if x.get("is_active"))
        
        blocked_res = supabase.table("blocked_users").select("*").execute()
        blocked_count = len(blocked_res.data) if blocked_res.data else 0
        
        kb = types.InlineKeyboardMarkup(inline_keyboard=[
            [types.InlineKeyboardButton(text="👥 المستخدمين", callback_data="dev_list_users"),
             types.InlineKeyboardButton(text="📢 إذاعة", callback_data="dev_broadcast")],
            [types.InlineKeyboardButton(text="💳 الاشتراكات", callback_data="dev_subscriptions"),
             types.InlineKeyboardButton(text="🚫 المحظورين", callback_data="dev_blocked_list")],
            [types.InlineKeyboardButton(text="👑 الأدمنية", callback_data="dev_admins"),
             types.InlineKeyboardButton(text="📊 إحصائيات", callback_data="dev_stats")],
            [types.InlineKeyboardButton(text="🛠 إعدادات", callback_data="dev_bot_settings"),
             types.InlineKeyboardButton(text="▶️ تشغيل الكل", callback_data="dev_start_all")],
            [types.InlineKeyboardButton(text="🏠 الرئيسية", callback_data="main_menu")]
        ])
        
        await callback.message.edit_text(
            f"🛠 لوحة المطور:\n\n"
            f"👥 المستخدمين: {total}\n"
            f"⚡ يعملون: {running}\n"
            f"💳 اشتراكات نشطة: {active_subs}\n"
            f"🚫 محظورين: {blocked_count}",
            reply_markup=kb
        )
    except Exception as e:
        print(f"ERROR: {e}")
        await callback.answer("خطأ")
    await callback.answer()

# ==================== الأدمنية ====================
@dp.callback_query(F.data == "dev_admins")
async def dev_admins(callback: types.CallbackQuery):
    if callback.from_user.id != DEV_ID:
        await callback.answer("مخصص للمطور فقط")
        return
    
    admins = get_setting("admins", [DEV_ID])
    
    text = "👑 الأدمنية:\n\n"
    kb = []
    for admin_id in admins:
        text += f"- {admin_id}\n"
        kb.append([types.InlineKeyboardButton(text=f"إزالة: {admin_id}", callback_data=f"dev_remove_admin_{admin_id}")])
    
    kb.append([types.InlineKeyboardButton(text="➕ إضافة أدمن", callback_data="dev_add_admin")])
    kb.append([types.InlineKeyboardButton(text="🔙 رجوع", callback_data="dev_admin_panel")])
    
    await callback.message.edit_text(text, reply_markup=types.InlineKeyboardMarkup(inline_keyboard=kb))
    await callback.answer()

@dp.callback_query(F.data == "dev_add_admin")
async def dev_add_admin(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer("ارسل ايدي الأدمن الجديد:")
    await state.set_state(SettingsState.waiting_for_admins)
    await callback.answer()

@dp.message(SettingsState.waiting_for_admins)
async def process_add_admin(message: types.Message, state: FSMContext):
    try:
        admin_id = int(message.text.strip())
        admins = get_setting("admins", [DEV_ID])
        
        if admin_id not in admins:
            admins.append(admin_id)
            save_setting("admins", admins)
        
        await message.answer(f"تمت إضافة الأدمن: {admin_id}")
        await state.clear()
    except:
        await message.answer("ارسل رقم صحيح")
        await state.clear()

@dp.callback_query(F.data.startswith("dev_remove_admin_"))
async def dev_remove_admin(callback: types.CallbackQuery):
    if callback.from_user.id != DEV_ID:
        return
    
    admin_id = int(callback.data.replace("dev_remove_admin_", ""))
    
    admins = get_setting("admins", [DEV_ID])
    if admin_id in admins and admin_id != DEV_ID:
        admins.remove(admin_id)
        save_setting("admins", admins)
    
    await callback.answer("تم الإزالة")
    await dev_admins(callback)

# ==================== الاشتراكات ====================
@dp.callback_query(F.data == "dev_subscriptions")
async def dev_subscriptions(callback: types.CallbackQuery):
    if callback.from_user.id != DEV_ID:
        await callback.answer("مخصص للمطور فقط")
        return
    
    kb = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="💳 منح اشتراك", callback_data="dev_grant_sub")],
        [types.InlineKeyboardButton(text="⏹ إيقاف اشتراك", callback_data="dev_stop_sub")],
        [types.InlineKeyboardButton(text="📋 قائمة الاشتراكات", callback_data="dev_sub_list")],
        [types.InlineKeyboardButton(text="🔙 رجوع", callback_data="dev_admin_panel")]
    ])
    
    await callback.message.edit_text("💳 إدارة الاشتراكات:", reply_markup=kb)
    await callback.answer()

@dp.callback_query(F.data == "dev_grant_sub")
async def dev_grant_sub(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer("ارسل ايدي المستخدم:")
    await state.set_state(SettingsState.waiting_for_grant_user_id)
    await callback.answer()

@dp.message(SettingsState.waiting_for_grant_user_id)
async def process_grant_user_id(message: types.Message, state: FSMContext):
    try:
        target_id = int(message.text.strip())
        await state.update_data(grant_user_id=target_id)
        await message.answer("ارسل عدد الأيام (0 = دائم):")
        await state.set_state(SettingsState.waiting_for_grant_days)
    except:
        await message.answer("ارسل رقم صحيح")
        await state.clear()

@dp.message(SettingsState.waiting_for_grant_days)
async def process_grant_days(message: types.Message, state: FSMContext):
    try:
        days = int(message.text.strip())
        data = await state.get_data()
        target_id = data.get('grant_user_id')
        
        if days == 0:
            supabase.table("subscriptions").upsert({
                "user_id": target_id,
                "subscription_type": "permanent",
                "is_permanent": True,
                "is_active": True
            }, on_conflict="user_id").execute()
            await message.answer(f"✅ تم منح اشتراك دائم للمستخدم: {target_id}")
        else:
            supabase.table("subscriptions").upsert({
                "user_id": target_id,
                "subscription_type": "premium",
                "start_date": datetime.datetime.now().isoformat(),
                "expiry_date": (datetime.datetime.now() + datetime.timedelta(days=days)).isoformat(),
                "is_permanent": False,
                "is_active": True
            }, on_conflict="user_id").execute()
            await message.answer(f"✅ تم منح اشتراك {days} يوم للمستخدم: {target_id}")
        
        await state.clear()
    except:
        await message.answer("ارسل رقم صحيح")
        await state.clear()

@dp.callback_query(F.data == "dev_sub_list")
async def dev_sub_list(callback: types.CallbackQuery):
    if callback.from_user.id != DEV_ID:
        return
    
    try:
        res = supabase.table("subscriptions").select("*").execute()
        
        if not res.data:
            await callback.message.edit_text("لا يوجد اشتراكات", reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[
                [types.InlineKeyboardButton(text="🔙 رجوع", callback_data="dev_subscriptions")]
            ]))
            await callback.answer()
            return
        
        text = "📋 الاشتراكات:\n\n"
        kb = []
        for row in res.data[:20]:
            uid = row.get("user_id")
            sub_type = row.get("subscription_type", "free")
            is_active = "نشط ✅" if row.get("is_active") else "موقوف ❌"
            if row.get("is_permanent"):
                expiry = "دائم"
            else:
                expiry = row.get("expiry_date", "غير محدد")[:10] if row.get("expiry_date") else "غير محدد"
            
            text += f"👤 {uid}: {sub_type} - {is_active} - {expiry}\n"
            kb.append([types.InlineKeyboardButton(text=f"⏹ إيقاف: {uid}", callback_data=f"dev_stop_sub_{uid}")])
        
        kb.append([types.InlineKeyboardButton(text="🔙 رجوع", callback_data="dev_subscriptions")])
        
        await callback.message.edit_text(text, reply_markup=types.InlineKeyboardMarkup(inline_keyboard=kb))
    except Exception as e:
        print(f"ERROR: {e}")
        await callback.answer("خطأ")
    await callback.answer()

@dp.callback_query(F.data.startswith("dev_stop_sub_"))
async def dev_stop_sub_user(callback: types.CallbackQuery):
    if callback.from_user.id != DEV_ID:
        return
    
    target_uid = int(callback.data.replace("dev_stop_sub_", ""))
    
    supabase.table("subscriptions").update({"is_active": False}).eq("user_id", target_uid).execute()
    
    await callback.answer("تم إيقاف الاشتراك")
    await dev_sub_list(callback)

# ==================== الإذاعة ====================
@dp.callback_query(F.data == "dev_broadcast")
async def dev_broadcast(callback: types.CallbackQuery, state: FSMContext):
    if callback.from_user.id != DEV_ID:
        await callback.answer("مخصص للمطور فقط")
        return
    
    await callback.message.answer("📢 ارسل نص الإذاعة:")
    await state.set_state(SettingsState.waiting_for_broadcast_text)
    await callback.answer()

@dp.message(SettingsState.waiting_for_broadcast_text)
async def process_broadcast(message: types.Message, state: FSMContext):
    text = message.text.strip()
    
    try:
        res = supabase.table("user_bots").select("user_id").execute()
        sent = 0
        failed = 0
        
        for row in res.data:
            try:
                await bot.send_message(row['user_id'], f"📢 إعلان:\n\n{text}")
                sent += 1
                await asyncio.sleep(0.3)
            except:
                failed += 1
        
        await message.answer(f"📢 تم الإرسال:\n✅ نجح: {sent}\n❌ فشل: {failed}")
    except Exception as e:
        print(f"ERROR: {e}")
        await message.answer("خطأ في الإذاعة")
    
    await state.clear()

# ==================== المحظورين ====================
@dp.callback_query(F.data == "dev_blocked_list")
async def dev_blocked_list(callback: types.CallbackQuery):
    if callback.from_user.id != DEV_ID:
        await callback.answer("مخصص للمطور فقط")
        return    
    try:
        res = supabase.table("blocked_users").select("*").execute()
        
        if not res.data:
            await callback.message.edit_text("لا يوجد محظورين", reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[
                [types.InlineKeyboardButton(text="➕ حظر", callback_data="dev_block_user")],
                [types.InlineKeyboardButton(text="🔙 رجوع", callback_data="dev_admin_panel")]
            ]))
            await callback.answer()
            return
        
        text = "🚫 المحظورين:\n\n"
        kb = []
        for row in res.data:
            uid = row.get("user_id")
            text += f"👤 {uid}\n"
            kb.append([types.InlineKeyboardButton(text=f"✅ فك حظر: {uid}", callback_data=f"dev_unblock_{uid}")])
        
        kb.append([types.InlineKeyboardButton(text="➕ حظر", callback_data="dev_block_user")])
        kb.append([types.InlineKeyboardButton(text="🔙 رجوع", callback_data="dev_admin_panel")])
        
        await callback.message.edit_text(text, reply_markup=types.InlineKeyboardMarkup(inline_keyboard=kb))
    except Exception as e:
        print(f"ERROR: {e}")
        await callback.answer("خطأ")
    await callback.answer()

@dp.callback_query(F.data == "dev_block_user")
async def dev_block_user(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer("ارسل ايدي المستخدم للحظر:")
    await state.set_state(SettingsState.waiting_for_block_user_id)
    await callback.answer()

@dp.message(SettingsState.waiting_for_block_user_id)
async def process_block_user(message: types.Message, state: FSMContext):
    try:
        target_id = int(message.text.strip())
        
        supabase.table("blocked_users").upsert({
            "user_id": target_id,
            "blocked_by": message.from_user.id
        }, on_conflict="user_id").execute()
        
        supabase.table("subscriptions").update({"is_active": False}).eq("user_id", target_id).execute()
        
        await message.answer(f"✅ تم حظر المستخدم: {target_id}")
        await state.clear()
    except:
        await message.answer("ارسل رقم صحيح")
        await state.clear()

@dp.callback_query(F.data.startswith("dev_unblock_"))
async def dev_unblock_user(callback: types.CallbackQuery):
    if callback.from_user.id != DEV_ID:
        return
    
    target_uid = int(callback.data.replace("dev_unblock_", ""))
    
    supabase.table("blocked_users").delete().eq("user_id", target_uid).execute()
    
    await callback.answer("✅ تم فك الحظر")
    await dev_blocked_list(callback)

# ==================== إعدادات البوت ====================
@dp.callback_query(F.data == "dev_bot_settings")
async def dev_bot_settings(callback: types.CallbackQuery):
    if callback.from_user.id != DEV_ID:
        await callback.answer("مخصص للمطور فقط")
        return
    
    kb = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="📝 تغيير اسم البوت", callback_data="dev_change_name")],
        [types.InlineKeyboardButton(text="👋 تغيير الترحيب", callback_data="dev_change_welcome")],
        [types.InlineKeyboardButton(text="👥 تغيير الحد الأقصى", callback_data="dev_change_limit")],
        [types.InlineKeyboardButton(text="🔙 رجوع", callback_data="dev_admin_panel")]
    ])
    
    await callback.message.edit_text(
        f"🛠 إعدادات البوت:\n\n"
        f"الحد الأقصى: {MAX_USERS}",
        reply_markup=kb
    )
    await callback.answer()

# ==================== تشغيل اليوزربوت مع عدم التوقف ====================
async def start_userbot(session_str, client_id):
    """تشغيل اليوزربوت مع إعادة تشغيل تلقائي مستمر"""
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

            # إنشاء قناة الأرشيف
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

                    if client_id in MUTED_USERS_CACHE and sender_id in MUTED_USERS_CACHE[client_id]:
                        try:
                            await event.delete()
                            return
                        except:
                            pass

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
                            except:
                                pass

                    # أرشفة
                    if archive_channel:
                        try:
                            await client.forward_messages(archive_channel, event.message)
                        except:
                            pass

                    # الرد التلقائي
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
                    
                    # منع التكرار
                    msg_key = f"{client_id}_{event.message.id}"
                    if msg_key in PROCESSED_MESSAGES:
                        return
                    PROCESSED_MESSAGES.add(msg_key)
                    
                    is_private = event.is_private
                    
                    if not is_private:
                        me = await client.get_me()
                        is_admin = await is_user_admin(client, chat_id, me.id)
                        if not is_admin:
                            return

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
