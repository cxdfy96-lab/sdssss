import os
import random
import asyncio
import datetime
import json
from telethon import TelegramClient, events, functions
from telethon.sessions import StringSession
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
    waiting_for_publish_text = State()
    waiting_for_dev_forced_channel = State()
    waiting_for_destroy_timer = State()

def safe_get(data_dict, key, default=None):
    if isinstance(data_dict, dict):
        return data_dict.get(key, default)
    return default

def get_main_menu_keyboard(user_id):
    kb = [
        [types.InlineKeyboardButton(text="🚀 تفعيل الاشتراك المجاني (شهر)", callback_data="free_subscription")],
        [types.InlineKeyboardButton(text="⚙️ لوحة التحكم والإعدادات", callback_data="my_settings")],
        [types.InlineKeyboardButton(text="📚 تعليمات استخدام البوت", callback_data="bot_instructions")],
        [types.InlineKeyboardButton(text="👨‍💻 مراسلة المطور", url=f"https://t.me/{DEV_USER.replace('@','')}")]
    ]
    if user_id == DEV_ID:
        kb.append([types.InlineKeyboardButton(text="🛠 لوحة تحكم المطور", callback_data="dev_admin_panel")])
    return types.InlineKeyboardMarkup(inline_keyboard=kb)

def get_control_panel_keyboard(bot_info):
    forced = safe_get(bot_info, "forced_channel") or "غير محددة"
    clock_st = "مفعل" if safe_get(bot_info, "clock_enabled", True) else "متوقف"
    filter_st = "مفعل" if safe_get(bot_info, "filter_enabled", True) else "متوقف"
    save_st = "مفعل" if safe_get(bot_info, "save_media_enabled", True) else "متوقف"
    lock_st = "مقفل" if safe_get(bot_info, "lock_private_enabled", False) else "مفتوح"
    destroy_st = "مفعل" if safe_get(bot_info, "destroy_messages_enabled", False) else "متوقف"
    spam_st = "مفعل" if safe_get(bot_info, "spam_protection_enabled", False) else "متوقف"
    publish_st = "مفعل" if safe_get(bot_info, "auto_publish_enabled", False) else "متوقف"
    current_font = safe_get(bot_info, "clock_font", "circle")

    kb = [
        [types.InlineKeyboardButton(text=f"🔇 الكتم والحظر", callback_data="mute_ban_menu")],
        [types.InlineKeyboardButton(text=f"🗑 تدمير الرسائل: {destroy_st}", callback_data="destroy_messages_menu")],
        [types.InlineKeyboardButton(text=f"📢 النشر التلقائي: {publish_st}", callback_data="auto_publish_menu")],
        [types.InlineKeyboardButton(text=f"🛡 الحماية من السبام: {spam_st}", callback_data="toggle_spam")],
        [types.InlineKeyboardButton(text=f"🔒 قفل الخاص: {lock_st}", callback_data="toggle_lock_private"),
         types.InlineKeyboardButton(text=f"🚫 فلتر الكلمات: {filter_st}", callback_data="toggle_filter")],
        [types.InlineKeyboardButton(text=f"⏰ الساعة: {clock_st}", callback_data="toggle_clock"),
         types.InlineKeyboardButton(text=f"🔤 الخط: {current_font}", callback_data="choose_font")],
        [types.InlineKeyboardButton(text=f"💾 الوسائط: {save_st}", callback_data="toggle_save_media"),
         types.InlineKeyboardButton(text="➕ كلمة محظورة", callback_data="add_bad_word")],
        [types.InlineKeyboardButton(text="🤖 الردود", callback_data="set_auto_reply"),
         types.InlineKeyboardButton(text="🗑 حذف الردود", callback_data="del_auto_reply")],
        [types.InlineKeyboardButton(text="📢 الاشتراك الاجباري", callback_data="set_forced"),
         types.InlineKeyboardButton(text="🚫 إيقافه", callback_data="off_forced")],
        [types.InlineKeyboardButton(text="👋 الترحيب", callback_data="set_welcome"),
         types.InlineKeyboardButton(text="🔄 تحديث", callback_data="refresh_bot")],
        [types.InlineKeyboardButton(text="🏠 الرئيسية", callback_data="main_menu")]
    ]
    return types.InlineKeyboardMarkup(inline_keyboard=kb)

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    user_id = message.from_user.id
    try:
        res = supabase.table("user_bots").select("*").or_(f"user_id.eq.{user_id},account_id.eq.{user_id}").execute()
        
        if res.data and res.data[0].get("session_string"):
            bot_info = res.data[0]
            await show_control_panel(message, bot_info)
            return

        welcome_text = (
            "مرحباً بك في النظام الذكي لإدارة الحسابات\n\n"
            "الاشتراك مجاني بالكامل لمدة شهر\n\n"
            "المميزات:\n"
            "- ساعة حية بتوقيت بغداد\n"
            "- حفظ الوسائط الوقتية\n"
            "- أرشفة رسائل الخاص\n"
            "- كتم وحظر المستخدمين\n"
            "- نشر تلقائي للقنوات\n"
            "- تدمير الرسائل\n"
            "- حماية من السبام\n\n"
            "اضغط على الزر للبدء:"
        )
        await message.answer(welcome_text, reply_markup=get_main_menu_keyboard(user_id))
    except Exception as e:
        print(f"[ERROR] cmd_start: {e}")
        await message.answer("حدث خطأ، يرجى المحاولة لاحقاً")

async def show_control_panel(message, bot_info):
    markup = get_control_panel_keyboard(bot_info)
    forced = safe_get(bot_info, "forced_channel") or "غير محددة"
    destroy_st = "مفعل" if safe_get(bot_info, "destroy_messages_enabled", False) else "متوقف"
    spam_st = "مفعل" if safe_get(bot_info, "spam_protection_enabled", False) else "متوقف"
    publish_st = "مفعل" if safe_get(bot_info, "auto_publish_enabled", False) else "متوقف"
    
    await message.answer(
        f"لوحة التحكم الشاملة\n\n"
        f"قناة الاشتراك: @{forced}\n"
        f"تدمير الرسائل: {destroy_st}\n"
        f"النشر التلقائي: {publish_st}\n"
        f"الحماية من السبام: {spam_st}",
        reply_markup=markup
    )

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
        print(f"[DB ERROR]: {e}")
    
    contact_kb = types.ReplyKeyboardMarkup(
        keyboard=[[types.KeyboardButton(text="مشاركة رقم الهاتف", request_contact=True)]],
        resize_keyboard=True,
        one_time_keyboard=True
    )
    
    await callback.message.answer(
        "تم تفعيل اشتراكك المجاني\n\n"
        "اضغط على زر مشاركة رقم الهاتف\n"
        "أو اكتب رقمك مع رمز الدولة",
        reply_markup=contact_kb
    )
    await state.set_state(LoginState.waiting_for_phone)

# ==================== قائمة الكتم والحظر ====================
@dp.callback_query(F.data == "mute_ban_menu")
async def mute_ban_menu(callback: types.CallbackQuery):
    kb = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="➕ كتم مستخدم", callback_data="mute_user"),
         types.InlineKeyboardButton(text="➕ حظر مستخدم", callback_data="ban_user")],
        [types.InlineKeyboardButton(text="📋 قائمة المكتمين", callback_data="list_muted"),
         types.InlineKeyboardButton(text="📋 قائمة المحظورين", callback_data="list_banned")],
        [types.InlineKeyboardButton(text="🔙 رجوع", callback_data="my_settings")]
    ])
    await callback.message.edit_text("إدارة الكتم والحظر:", reply_markup=kb)
    await callback.answer()

@dp.callback_query(F.data == "mute_user")
async def mute_user(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer("أرسل أيدي المستخدم الذي تريد كتمه:")
    await state.set_state(SettingsState.waiting_for_mute_user_id)
    await callback.answer()

@dp.message(SettingsState.waiting_for_mute_user_id)
async def save_muted_user(message: types.Message, state: FSMContext):
    try:
        muted_id = int(message.text.strip())
        user_id = message.from_user.id
        
        # حفظ في قاعدة البيانات
        supabase.table("muted_users").upsert({
            "user_id": user_id,
            "muted_user_id": muted_id
        }, on_conflict="user_id,muted_user_id").execute()
        
        # تحديث الكاش
        if user_id not in MUTED_USERS_CACHE:
            MUTED_USERS_CACHE[user_id] = set()
        MUTED_USERS_CACHE[user_id].add(muted_id)
        
        await message.answer(f"تم كتم المستخدم: {muted_id}")
        await state.clear()
    except:
        await message.answer("أرسل أيدي صحيح (رقم فقط)")
        await state.clear()

@dp.callback_query(F.data == "ban_user")
async def ban_user(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer("أرسل أيدي المستخدم الذي تريد حظره:")
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
        await message.answer("أرسل أيدي صحيح (رقم فقط)")
        await state.clear()

@dp.callback_query(F.data == "list_muted")
async def list_muted(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    res = supabase.table("muted_users").select("*").eq("user_id", user_id).execute()
    
    if not res.data:
        await callback.message.edit_text("لا يوجد مستخدمين مكتمين", reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[
            [types.InlineKeyboardButton(text="🔙 رجوع", callback_data="mute_ban_menu")]
        ]))
    else:
        text = "قائمة المكتمين:\n\n"
        kb = []
        for row in res.data:
            text += f"- {row['muted_user_id']}\n"
            kb.append([types.InlineKeyboardButton(text=f"فك كتم: {row['muted_user_id']}", callback_data=f"unmute_{row['muted_user_id']}")])
        kb.append([types.InlineKeyboardButton(text="🔙 رجوع", callback_data="mute_ban_menu")])
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
        await callback.message.edit_text("لا يوجد مستخدمين محظورين", reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[
            [types.InlineKeyboardButton(text="🔙 رجوع", callback_data="mute_ban_menu")]
        ]))
    else:
        text = "قائمة المحظورين:\n\n"
        kb = []
        for row in res.data:
            text += f"- {row['banned_user_id']}\n"
            kb.append([types.InlineKeyboardButton(text=f"فك حظر: {row['banned_user_id']}", callback_data=f"unban_{row['banned_user_id']}")])
        kb.append([types.InlineKeyboardButton(text="🔙 رجوع", callback_data="mute_ban_menu")])
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

# ==================== تدمير الرسائل ====================
@dp.callback_query(F.data == "destroy_messages_menu")
async def destroy_messages_menu(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    res = supabase.table("user_bots").select("destroy_messages_enabled, destroy_messages_timer").or_(f"user_id.eq.{user_id},account_id.eq.{user_id}").execute()
    
    if res.data:
        enabled = res.data[0].get("destroy_messages_enabled", False)
        timer = res.data[0].get("destroy_messages_timer", 5)
        
        kb = types.InlineKeyboardMarkup(inline_keyboard=[
            [types.InlineKeyboardButton(text=f"تفعيل/إيقاف: {'مفعل' if enabled else 'متوقف'}", callback_data="toggle_destroy")],
            [types.InlineKeyboardButton(text=f"المدة: {timer} ثانية", callback_data="set_destroy_timer")],
            [types.InlineKeyboardButton(text="🔙 رجوع", callback_data="my_settings")]
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
    await callback.message.answer("أرسل المدة بالثواني لتدمير الرسائل:")
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
        await message.answer("أرسل رقم صحيح")
        await state.clear()

# ==================== النشر التلقائي ====================
@dp.callback_query(F.data == "auto_publish_menu")
async def auto_publish_menu(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    res = supabase.table("user_bots").select("*").or_(f"user_id.eq.{user_id},account_id.eq.{user_id}").execute()
    
    if res.data:
        enabled = res.data[0].get("auto_publish_enabled", False)
        channels = res.data[0].get("publish_channels", [])
        
        kb = types.InlineKeyboardMarkup(inline_keyboard=[
            [types.InlineKeyboardButton(text=f"تفعيل/إيقاف: {'مفعل' if enabled else 'متوقف'}", callback_data="toggle_publish")],
            [types.InlineKeyboardButton(text="➕ إضافة قناة", callback_data="add_publish_channel")],
            [types.InlineKeyboardButton(text="📋 القنوات المضافة", callback_data="list_publish_channels")],
            [types.InlineKeyboardButton(text="🔙 رجوع", callback_data="my_settings")]
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
    await callback.message.answer("أرسل معرف القناة أو الكروب (بدون @):")
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
    
    await message.answer(f"تمت إضافة القناة: @{channel}")
    await state.clear()

@dp.callback_query(F.data == "list_publish_channels")
async def list_publish_channels(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    res = supabase.table("user_bots").select("publish_channels").or_(f"user_id.eq.{user_id},account_id.eq.{user_id}").execute()
    
    if res.data:
        channels = res.data[0].get("publish_channels", [])
        if not channels:
            await callback.message.edit_text("لا توجد قنوات مضافة", reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[
                [types.InlineKeyboardButton(text="🔙 رجوع", callback_data="auto_publish_menu")]
            ]))
        else:
            text = "القنوات المضافة:\n\n"
            kb = []
            for chan in channels:
                text += f"- @{chan}\n"
                kb.append([types.InlineKeyboardButton(text=f"حذف: {chan}", callback_data=f"del_publish_{chan}")])
            kb.append([types.InlineKeyboardButton(text="🔙 رجوع", callback_data="auto_publish_menu")])
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

# ==================== الحماية من السبام ====================
@dp.callback_query(F.data == "toggle_spam")
async def toggle_spam(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    res = supabase.table("user_bots").select("spam_protection_enabled").or_(f"user_id.eq.{user_id},account_id.eq.{user_id}").execute()
    
    if res.data:
        current = res.data[0].get("spam_protection_enabled", False)
        supabase.table("user_bots").update({"spam_protection_enabled": not current}).or_(f"user_id.eq.{user_id},account_id.eq.{user_id}").execute()
    
    await callback.answer("تم التحديث")
    await settings_menu(callback)

# ==================== لوحة المطور المتقدمة ====================
@dp.callback_query(F.data == "dev_admin_panel")
async def dev_admin_panel(callback: types.CallbackQuery):
    if callback.from_user.id != DEV_ID:
        await callback.answer("مخصص للمطور فقط")
        return
    
    kb = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="👥 قائمة المستخدمين", callback_data="dev_list_users")],
        [types.InlineKeyboardButton(text="📢 إذاعة للكل", callback_data="dev_broadcast")],
        [types.InlineKeyboardButton(text="📢 قناة الاشتراك الإجباري", callback_data="dev_forced_channel")],
        [types.InlineKeyboardButton(text="📊 الإحصائيات", callback_data="dev_stats")],
        [types.InlineKeyboardButton(text="🔙 رجوع", callback_data="main_menu")]
    ])
    
    await callback.message.edit_text("لوحة تحكم المطور:", reply_markup=kb)
    await callback.answer()

@dp.callback_query(F.data == "dev_forced_channel")
async def dev_forced_channel(callback: types.CallbackQuery):
    if callback.from_user.id != DEV_ID:
        return
    
    # جلب القناة الحالية من الإعدادات
    res = supabase.table("bot_settings").select("*").eq("setting_key", "global_forced_channel").execute()
    current_channel = None
    if res.data:
        current_channel = res.data[0].get("setting_value", {}).get("channel")
    
    kb = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="➕ إضافة قناة", callback_data="dev_add_forced")],
        [types.InlineKeyboardButton(text="🗑 حذف القناة", callback_data="dev_delete_forced")],
        [types.InlineKeyboardButton(text="🔙 رجوع", callback_data="dev_admin_panel")]
    ])
    
    await callback.message.edit_text(
        f"إدارة قناة الاشتراك الإجباري:\n\n"
        f"القناة الحالية: @{current_channel or 'غير محددة'}",
        reply_markup=kb
    )
    await callback.answer()

@dp.callback_query(F.data == "dev_add_forced")
async def dev_add_forced(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer("أرسل معرف القناة (بدون @):")
    await state.set_state(SettingsState.waiting_for_dev_forced_channel)
    await callback.answer()

@dp.message(SettingsState.waiting_for_dev_forced_channel)
async def save_dev_forced_channel(message: types.Message, state: FSMContext):
    channel = message.text.strip().replace("@", "")
    
    # حفظ في الإعدادات العامة
    supabase.table("bot_settings").upsert({
        "setting_key": "global_forced_channel",
        "setting_value": {"channel": channel}
    }, on_conflict="setting_key").execute()
    
    await message.answer(f"تم تعيين القناة: @{channel}")
    await state.clear()

@dp.callback_query(F.data == "dev_delete_forced")
async def dev_delete_forced(callback: types.CallbackQuery):
    # حذف القناة
    supabase.table("bot_settings").delete().eq("setting_key", "global_forced_channel").execute()
    
    await callback.answer("تم حذف القناة")
    await dev_forced_channel(callback)

@dp.callback_query(F.data == "dev_stats")
async def dev_stats(callback: types.CallbackQuery):
    if callback.from_user.id != DEV_ID:
        return
    
    res = supabase.table("user_bots").select("*").execute()
    total = len(res.data) if res.data else 0
    active = sum(1 for x in (res.data or []) if x.get("is_active"))
    
    kb = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="🔙 رجوع", callback_data="dev_admin_panel")]
    ])
    
    await callback.message.edit_text(
        f"الإحصائيات:\n\n"
        f"إجمالي المستخدمين: {total}\n"
        f"النشطين: {active}",
        reply_markup=kb
    )
    await callback.answer()

# ==================== زر التحديث ====================
@dp.callback_query(F.data == "refresh_bot")
async def refresh_bot(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    
    try:
        # إعادة تحميل البيانات
        res = supabase.table("user_bots").select("*").or_(f"user_id.eq.{user_id},account_id.eq.{user_id}").execute()
        
        if res.data:
            bot_info = res.data[0]
            # إعادة تشغيل اليوزربوت
            if bot_info.get("account_id") in ACTIVE_CLIENTS:
                try:
                    await ACTIVE_CLIENTS[bot_info["account_id"]].disconnect()
                except:
                    pass
                del ACTIVE_CLIENTS[bot_info["account_id"]]
            
            if bot_info.get("session_string"):
                asyncio.create_task(start_userbot(bot_info["session_string"], bot_info["account_id"]))
            
            await callback.answer("تم التحديث بنجاح")
            await settings_menu(callback)
        else:
            await callback.answer("لا يوجد حساب منصب")
    except Exception as e:
        print(f"[ERROR] refresh: {e}")
        await callback.answer("حدث خطأ في التحديث")

# ==================== باقي الأزرار ====================
@dp.callback_query(F.data == "my_settings")
async def settings_menu(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    res = supabase.table("user_bots").select("*").or_(f"user_id.eq.{user_id},account_id.eq.{user_id}").execute()
    
    if not res.data:
        await callback.message.answer("لم تقم بتنصيب أي حساب")
        await callback.answer()
        return
    
    bot_info = res.data[0]
    markup = get_control_panel_keyboard(bot_info)
    
    await callback.message.edit_text(
        f"لوحة التحكم والإعدادات\n\n"
        f"اضغط على الأزرار للتعديل:",
        reply_markup=markup
    )
    await callback.answer()

@dp.callback_query(F.data == "main_menu")
async def back_to_main(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    res = supabase.table("user_bots").select("*").or_(f"user_id.eq.{user_id},account_id.eq.{user_id}").execute()
    
    if res.data and res.data[0].get("session_string"):
        await settings_menu(callback)
    else:
        await callback.message.edit_text(
            "القائمة الرئيسية:",
            reply_markup=get_main_menu_keyboard(user_id)
        )
    await callback.answer()

# ==================== تشغيل اليوزربوت ====================
async def start_userbot(session_str, client_id):
    try:
        client = TelegramClient(StringSession(session_str), API_ID, API_HASH)
        await client.start()
        ACTIVE_CLIENTS[client_id] = client
        
        # تحميل المحتوى
        for cat, chan in CHANNELS_MAP.items():
            asyncio.create_task(load_channel_messages(client, chan, cat, client_id))

        # تحميل المكتمين والمحظورين من قاعدة البيانات
        res_muted = supabase.table("muted_users").select("*").eq("user_id", client_id).execute()
        if res_muted.data:
            MUTED_USERS_CACHE[client_id] = {row['muted_user_id'] for row in res_muted.data}
        
        res_banned = supabase.table("banned_users").select("*").eq("user_id", client_id).execute()
        if res_banned.data:
            BANNED_USERS_CACHE[client_id] = {row['banned_user_id'] for row in res_banned.data}

        asyncio.create_task(update_name_with_clock(client, client_id))
        asyncio.create_task(auto_publish_loop(client, client_id))

        archive_channel = None
        try:
            dialogs = await client.get_dialogs()
            for d in dialogs:
                if d.name == "أرشيف رسائل الخاص":
                    archive_channel = d.entity
                    break
        except:
            pass

        @client.on(events.NewMessage(incoming=True))
        async def incoming_handler(event):
            try:
                if not event.is_private:
                    # حذف رسائل غير المشرفين في القنوات
                    if event.is_channel:
                        try:
                            chat = await event.get_chat()
                            sender = await event.get_sender()
                            if not sender or not getattr(sender, 'admin_rights', None):
                                await event.delete()
                                return
                        except:
                            pass
                    return
                
                sender = await event.get_sender()
                if sender and getattr(sender, 'bot', False):
                    return
                
                sender_id = event.sender_id
                if sender_id == client_id:
                    return

                # التحقق من الكتم
                if client_id in MUTED_USERS_CACHE and sender_id in MUTED_USERS_CACHE[client_id]:
                    try:
                        await event.delete()
                        return
                    except:
                        pass

                # التحقق من الحظر
                if client_id in BANNED_USERS_CACHE and sender_id in BANNED_USERS_CACHE[client_id]:
                    try:
                        await event.delete()
                        await event.reply("أنت محظور من هذا الحساب")
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
                    async def destroy_message():
                        await asyncio.sleep(timer)
                        try:
                            await event.delete()
                        except:
                            pass
                    asyncio.create_task(destroy_message())

                # الحماية من السبام
                if bot_config.get("spam_protection_enabled", False):
                    # تنفيذ حماية السبام هنا
                    pass

                # حفظ الوسائط الوقتية
                if bot_config.get("save_media_enabled", True) and event.message.media:
                    msg_media = event.message.media
                    is_ttl = getattr(event.message, 'ttl_period', None) is not None
                    
                    if is_ttl:
                        try:
                            file_path = await event.message.download_media()
                            if file_path:
                                await client.send_file('me', file_path)
                                os.remove(file_path)
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
                print(f"[ERROR] incoming: {ex}")

        @client.on(events.NewMessage(incoming=True, outgoing=True))
        async def commands_handler(event):
            try:
                chat_id = event.chat_id
                text_raw = event.raw_text.strip()
                text_lower = text_raw.lower()

                # أوامر الكتم
                if text_raw == "كتم":
                    try:
                        await event.delete()
                        if client_id not in MUTED_USERS_CACHE:
                            MUTED_USERS_CACHE[client_id] = set()
                        MUTED_USERS_CACHE[client_id].add(chat_id)
                        supabase.table("muted_users").upsert({
                            "user_id": client_id,
                            "muted_user_id": chat_id
                        }, on_conflict="user_id,muted_user_id").execute()
                        await event.respond("تم كتم المستخدم")
                    except:
                        pass
                    return

                if text_raw == "فك كتم":
                    try:
                        await event.delete()
                        if client_id in MUTED_USERS_CACHE and chat_id in MUTED_USERS_CACHE[client_id]:
                            MUTED_USERS_CACHE[client_id].remove(chat_id)
                        supabase.table("muted_users").delete().eq("user_id", client_id).eq("muted_user_id", chat_id).execute()
                        await event.respond("تم فك كتم المستخدم")
                    except:
                        pass
                    return

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
                        await event.respond(f"تم كتم المستخدم: {target_id}")
                    except:
                        pass
                    return

                # أوامر الحظر
                if text_raw == "حظر":
                    try:
                        await event.delete()
                        if client_id not in BANNED_USERS_CACHE:
                            BANNED_USERS_CACHE[client_id] = set()
                        BANNED_USERS_CACHE[client_id].add(chat_id)
                        supabase.table("banned_users").upsert({
                            "user_id": client_id,
                            "banned_user_id": chat_id
                        }, on_conflict="user_id,banned_user_id").execute()
                        await event.respond("تم حظر المستخدم")
                    except:
                        pass
                    return

                if text_raw == "فك حظر":
                    try:
                        await event.delete()
                        if client_id in BANNED_USERS_CACHE and chat_id in BANNED_USERS_CACHE[client_id]:
                            BANNED_USERS_CACHE[client_id].remove(chat_id)
                        supabase.table("banned_users").delete().eq("user_id", client_id).eq("banned_user_id", chat_id).execute()
                        await event.respond("تم فك حظر المستخدم")
                    except:
                        pass
                    return

                # بقية الأوامر (المحتوى، يوتيوب، الخ...)
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

            except Exception as cmd_err:
                print(f"[ERROR] commands: {cmd_err}")

        await client.run_until_disconnected()
        
    except Exception as client_err:
        print(f"[CRITICAL] userbot: {client_err}")
    finally:
        if client_id in ACTIVE_CLIENTS:
            del ACTIVE_CLIENTS[client_id]

async def auto_publish_loop(client, client_id):
    """حلقة النشر التلقائي"""
    while True:
        try:
            res = supabase.table("user_bots").select("*").eq("account_id", client_id).execute()
            if res.data:
                bot_config = res.data[0]
                
                if bot_config.get("auto_publish_enabled", False):
                    channels = bot_config.get("publish_channels", [])
                    
                    if channels:
                        # اختيار محتوى عشوائي
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
                
        except Exception as e:
            print(f"[ERROR] auto publish: {e}")
            interval = 3600
        
        await asyncio.sleep(interval)

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
        print(f"[ERROR] load channel: {e}")

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

async def restore_sessions():
    try:
        res = supabase.table("user_bots").select("*").eq("is_active", True).execute()
        if res.data:
            for row in res.data:
                if row.get("session_string"):
                    asyncio.create_task(start_userbot(row["session_string"], row["account_id"]))
    except Exception as e:
        print(f"[WARNING] restore: {e}")

async def main():
    await restore_sessions()
    print("[INFO] Bot started")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
