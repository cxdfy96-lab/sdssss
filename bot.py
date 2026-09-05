import os
import random
import asyncio
import datetime
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
DEFAULT_BAD_WORDS = ["وهابي", "عفن", "سخيف", "كلب", "انقلع"]

CLOCK_FONTS = {
    "circle": ("0123456789", "⓪①②③④⑤⑥⑦⑧⑨"),
    "bold": ("0123456789", "𝟎𝟏𝟐𝟑𝟒𝟓𝟔𝟕𝟖𝟗"),
    "sans": ("0123456789", "𝟶𝟷𝟸𝟹𝟺𝟻𝟼𝟽𝟾𝟿"),
    "normal": ("0123456789", "0123456789")
}

# ==================== بوت الإدارة والتنصيب (Bot API) ====================
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

def get_main_menu_keyboard(user_id):
    kb = [
        [types.InlineKeyboardButton(text="تفعيل الاشتراك المجاني (شهر)", callback_data="free_subscription")],
        [types.InlineKeyboardButton(text="لوحة التحكم والإعدادات", callback_data="my_settings")],
        [types.InlineKeyboardButton(text="تعليمات استخدام البوت", callback_data="bot_instructions")],
        [types.InlineKeyboardButton(text="مراسلة المطور", url=f"https://t.me/{DEV_USER.replace('@','')}")]
    ]
    if user_id == DEV_ID:
        kb.append([types.InlineKeyboardButton(text="لوحة تحكم المطور والإحصائيات", callback_data="dev_admin_panel")])
    return types.InlineKeyboardMarkup(inline_keyboard=kb)

def get_control_panel_keyboard(bot_info):
    forced = bot_info.get("forced_channel") or "غير محددة"
    clock_st = "مفعل" if bot_info.get("clock_enabled") else "متوقف"
    filter_st = "مفعل" if bot_info.get("filter_enabled") else "متوقف"
    save_st = "مفعل" if bot_info.get("save_media_enabled", True) else "متوقف"
    lock_st = "مقفل" if bot_info.get("lock_private_enabled", False) else "مفتوح"
    current_font = bot_info.get("clock_font", "circle")

    kb = [
        [types.InlineKeyboardButton(text=f"قفل الخاص: {lock_st}", callback_data="toggle_lock_private"), types.InlineKeyboardButton(text=f"فلتر الكلمات: {filter_st}", callback_data="toggle_filter")],
        [types.InlineKeyboardButton(text=f"الساعة الحية: {clock_st}", callback_data="toggle_clock"), types.InlineKeyboardButton(text=f"خط الساعة: {current_font}", callback_data="choose_font")],
        [types.InlineKeyboardButton(text=f"حفظ الوسائط: {save_st}", callback_data="toggle_save_media"), types.InlineKeyboardButton(text="إضافة كلمة محظورة", callback_data="add_bad_word")],
        [types.InlineKeyboardButton(text="الردود التلقائية", callback_data="set_auto_reply"), types.InlineKeyboardButton(text="حذف الردود", callback_data="del_auto_reply")],
        [types.InlineKeyboardButton(text="الاشتراك الاجباري (تعيين)", callback_data="set_forced"), types.InlineKeyboardButton(text="إيقاف الاشتراك", callback_data="off_forced")],
        [types.InlineKeyboardButton(text="رسالة الترحيب", callback_data="set_welcome"), types.InlineKeyboardButton(text="رجوع للقائمة الرئيسية", callback_data="main_menu")]
    ]
    return types.InlineKeyboardMarkup(inline_keyboard=kb), forced, clock_st, filter_st, save_st, lock_st, current_font

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    user_id = message.from_user.id
    res = supabase.table("user_bots").select("*").or_(f"user_id.eq.{user_id},account_id.eq.{user_id}").execute()
    if res.data and res.data[0].get("session_string"):
        bot_info = res.data[0]
        markup, forced, clock_st, filter_st, save_st, lock_st, current_font = get_control_panel_keyboard(bot_info)
        await message.answer(
            f"مرحباً بك مجدداً في لوحة التحكم الشاملة لإدارة حسابك:\n\n"
            f"قناة الاشتراك الإجباري: @{forced}\n"
            f"حالة الساعة الحية: {clock_st} (الخط: {current_font})\n"
            f"فلتر المحظورة: {filter_st}\n"
            f"حفظ الوسائط: {save_st}\n"
            f"قفل الخاص: {lock_st}",
            reply_markup=markup
        )
        return

    welcome_text = (
        "مرحباً بك في النظام الذكي لإدارة الحسابات واليوزربوت (AutoPro Bot).\n\n"
        "الاشتراك مجاني بالكامل لمدة شهر!\n"
        "المميزات الفعالة:\n"
        "• ساعة حية بتوقيت بغداد بجانب الاسم.\n"
        "• حفظ فوري وطبيعي لكافة الوسائط الواردة (صور، فيديوهات) في المحفوظات.\n"
        "• أرشفة رسائل الخاص في قناة مخصصة.\n"
        "• كتم حقيقي للمقابل أو عبر الآيدي وحذف رسائله تلقائياً.\n"
    )
    await message.answer(welcome_text, reply_markup=get_main_menu_keyboard(user_id))

@dp.callback_query(F.data == "free_subscription")
async def free_subscription(callback: types.CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    supabase.table("user_bots").upsert({
        "user_id": user_id,
        "is_approved": True,
        "account_id": user_id
    }, on_conflict="user_id").execute()
    
    # تفعيل فوري وطلب رقم الهاتف بالزر أو الكتابة
    contact_kb = types.ReplyKeyboardMarkup(
        keyboard=[[types.KeyboardButton(text="مشاركة رقم الهاتف", request_contact=True)]],
        resize_keyboard=True,
        one_time_keyboard=True
    )
    await callback.message.answer(
        "تم تفعيل اشتراكك المجاني لمدة شهر بنجاح!\n\nاضغط على زر (مشاركة رقم الهاتف) أدناه أو اكتب رقمك مع رمز الدولة (مثال: +9647700000000):",
        reply_markup=contact_kb
    )
    await state.set_state(LoginState.waiting_for_phone)
    await callback.answer()

@dp.callback_query(F.data == "bot_instructions")
async def bot_instructions(callback: types.CallbackQuery):
    text = (
        "تعليمات التشغيل والأوامر:\n"
        "1. ربط البوت عبر وضع السكرتير (Secretary Mode) في البوت فادر.\n"
        "2. الأوامر المتاحة:\n"
        "   - (غنيلي، شعر، مزج، ميمز، قرآن)\n"
        "   - (يوت + اسم الأغنية للبحث والتحميل)\n"
        "   - (كتم) أو (كتم الأيدي <الآيدي>) لكتم المقابل وحذف رسائله\n"
        "   - (فك كتم) أو (فك كتم الأيدي <الآيدي>) لإلغاء الكتم"
    )
    kb = types.InlineKeyboardMarkup(inline_keyboard=[[types.InlineKeyboardButton(text="رجوع", callback_data="main_menu")]])
    await callback.message.edit_text(text, reply_markup=kb)
    await callback.answer()

@dp.callback_query(F.data == "dev_admin_panel")
async def dev_admin_panel(callback: types.CallbackQuery):
    if callback.from_user.id != DEV_ID:
        await callback.answer("هذا مخصص للمطور فقط!", show_alert=True)
        return
    res = supabase.table("user_bots").select("*").execute()
    total_users = len(res.data) if res.data else 0
    active_bots = sum(1 for x in (res.data or []) if x.get("is_active"))
    
    kb = [
        [types.InlineKeyboardButton(text="قائمة المستخدمين", callback_data="dev_list_users")],
        [types.InlineKeyboardButton(text="رجوع للقائمة الرئيسية", callback_data="main_menu")]
    ]
    await callback.message.edit_text(f"لوحة تحكم المطور:\nإجمالي المسجلين: {total_users}\nاليوزربوتات النشطة: {active_bots}", reply_markup=types.InlineKeyboardMarkup(inline_keyboard=kb))
    await callback.answer()

@dp.callback_query(F.data == "dev_list_users")
async def dev_list_users(callback: types.CallbackQuery):
    if callback.from_user.id != DEV_ID:
        return
    res = supabase.table("user_bots").select("user_id, account_id, is_active").execute()
    if not res.data:
        await callback.answer("لا يوجد مستخدمين مسجلين.", show_alert=True)
        return
    kb = []
    for row in res.data:
        uid = row.get("user_id")
        status = "نشط" if row.get("is_active") else "متوقف"
        kb.append([types.InlineKeyboardButton(text=f"أيدي: {uid} ({status})", callback_data=f"dev_user_{uid}")])
    kb.append([types.InlineKeyboardButton(text="رجوع", callback_data="dev_admin_panel")])
    await callback.message.edit_text("اختر المستخدم لإدارة حالته أو إلغاء تنصيبه:", reply_markup=types.InlineKeyboardMarkup(inline_keyboard=kb))
    await callback.answer()

@dp.callback_query(F.data.startswith("dev_user_"))
async def dev_manage_user(callback: types.CallbackQuery):
    if callback.from_user.id != DEV_ID:
        return
    target_uid = int(callback.data.replace("dev_user_", ""))
    kb = [
        [types.InlineKeyboardButton(text="إلغاء تنصيب وحذف الحساب", callback_data=f"dev_del_{target_uid}")],
        [types.InlineKeyboardButton(text="رجوع", callback_data="dev_list_users")]
    ]
    await callback.message.edit_text(f"إدارة المستخدم ذو الأيدي: {target_uid}", reply_markup=types.InlineKeyboardMarkup(inline_keyboard=kb))
    await callback.answer()

@dp.callback_query(F.data.startswith("dev_del_"))
async def dev_delete_user(callback: types.CallbackQuery):
    if callback.from_user.id != DEV_ID:
        return
    target_uid = int(callback.data.replace("dev_del_", ""))
    supabase.table("user_bots").delete().eq("user_id", target_uid).execute()
    await callback.answer("تم حذف وإلغاء تنصيب المستخدم بنجاح!", show_alert=True)
    await dev_admin_panel(callback)

@dp.message(lambda message: message.contact or (message.text and message.text.startswith("+")))
async def handle_phone_input(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    phone = message.contact.phone_number if message.contact else message.text.strip()
    if not phone.startswith("+"):
        phone = "+" + phone

    supabase.table("user_bots").upsert({
        "user_id": user_id,
        "is_approved": True,
        "account_id": user_id
    }, on_conflict="user_id").execute()

    await state.update_data(phone=phone)
    client = TelegramClient(StringSession(), API_ID, API_HASH)
    await client.connect()
    try:
        sent = await client.send_code_request(phone)
        await state.update_data(phone_code_hash=sent.phone_code_hash, client=client)
        await message.answer("تم إرسال رمز التحقق إلى تلجرام. أرسل الرمز الآن:", reply_markup=types.ReplyKeyboardRemove())
        await state.set_state(LoginState.waiting_for_code)
    except Exception as e:
        await message.answer(f"خطأ: {e}")
        try: await client.disconnect()
        except: pass
        await state.clear()

@dp.message(LoginState.waiting_for_phone)
async def handle_phone_text(message: types.Message, state: FSMContext):
    await handle_phone_input(message, state)

@dp.message(LoginState.waiting_for_code)
async def process_code(message: types.Message, state: FSMContext):
    code = message.text.strip().replace(" ", "")
    data = await state.get_data()
    phone = data.get('phone')
    phone_code_hash = data.get('phone_code_hash')
    client = data.get('client')
    
    if not client:
        await message.answer("انتهت الجلسة المؤقتة، أرسل رقمك مجدداً.")
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
        
        markup, forced, clock_st, filter_st, save_st, lock_st, current_font = get_control_panel_keyboard(bot_data)
        await message.answer(f"تم تنصيب الحساب وتفعيل اليوزربوت بنجاح!\nالاسم: {me.first_name}", reply_markup=markup)
        asyncio.create_task(start_userbot(session_str, me.id))
        await client.disconnect()
        await state.clear()
    except Exception as e:
        if "Password" in str(e) or "SessionPasswordNeededError" in str(e):
            await state.update_data(client=client)
            await message.answer("الحساب محمي بالتحقق بخطوتين. أرسل كلمة المرور الخاصة بك الآن:")
            await state.set_state(LoginState.waiting_for_password)
        else:
            await message.answer(f"خطأ في الرمز: {e}")
            try: await client.disconnect()
            except: pass
            await state.clear()

@dp.message(LoginState.waiting_for_password)
async def process_password(message: types.Message, state: FSMContext):
    password = message.text.strip()
    data = await state.get_data()
    client = data.get('client')
    
    if not client:
        await message.answer("حدث خطأ، أعد المحاولة.")
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
        
        markup, forced, clock_st, filter_st, save_st, lock_st, current_font = get_control_panel_keyboard(bot_data)
        await message.answer(f"تم تفعيل الحساب بنجاح!\nالاسم: {me.first_name}", reply_markup=markup)
        asyncio.create_task(start_userbot(session_str, me.id))
        await client.disconnect()
        await state.clear()
    except Exception as e:
        await message.answer(f"خطأ في كلمة المرور: {e}")
        try: await client.disconnect()
        except: pass
        await state.clear()

@dp.callback_query(F.data == "my_settings")
async def settings_menu(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    res = supabase.table("user_bots").select("*").or_(f"user_id.eq.{user_id},account_id.eq.{user_id}").execute()
    if not res.data:
        await callback.message.answer("لم تقم بتنصيب أي حساب بعد.")
        await callback.answer()
        return
    bot_info = res.data[0]
    markup, forced, clock_st, filter_st, save_st, lock_st, current_font = get_control_panel_keyboard(bot_info)
    await callback.message.edit_text(f"لوحة التحكم والإعدادات:\n\nقناة الاشتراك الإجباري: @{forced}\nالساعة الحية: {clock_st}\nفلتر المحظورة: {filter_st}\nحفظ الوسائط: {save_st}\nقفل الخاص: {lock_st}", reply_markup=markup)
    await callback.answer()

@dp.callback_query(F.data == "choose_font")
async def choose_font_menu(callback: types.CallbackQuery):
    kb = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="① دائري أنيق", callback_data="font_circle")],
        [types.InlineKeyboardButton(text="𝟏 بارز عريض", callback_data="font_bold")],
        [types.InlineKeyboardButton(text="رجوع للإعدادات", callback_data="my_settings")]
    ])
    await callback.message.edit_text("اختر خط الساعة الحية:", reply_markup=kb)
    await callback.answer()

@dp.callback_query(F.data.startswith("font_"))
async def set_clock_font(callback: types.CallbackQuery):
    font_name = callback.data.replace("font_", "")
    user_id = callback.from_user.id
    supabase.table("user_bots").update({"clock_font": font_name}).or_(f"user_id.eq.{user_id},account_id.eq.{user_id}").execute()
    await callback.answer(f"تم تغيير الخط إلى: {font_name}", show_alert=True)
    await settings_menu(callback)

@dp.callback_query(F.data == "main_menu")
async def back_to_main(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    await callback.message.edit_text("مرحباً بك في القائمة الرئيسية:", reply_markup=get_main_menu_keyboard(user_id))
    await callback.answer()

@dp.callback_query(F.data == "set_forced")
async def ask_forced_channel(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer("أرسل معرف القناة للاشتراك الإجباري (بدون علامة @):")
    await state.set_state(SettingsState.waiting_for_forced_channel)
    await callback.answer()

@dp.message(SettingsState.waiting_for_forced_channel)
async def save_forced_channel(message: types.Message, state: FSMContext):
    chan = message.text.strip().replace("@", "")
    user_id = message.from_user.id
    supabase.table("user_bots").update({"forced_channel": chan}).or_(f"user_id.eq.{user_id},account_id.eq.{user_id}").execute()
    await message.answer(f"تم تعيين قناة الاشتراك الإجباري: @{chan}", reply_markup=get_main_menu_keyboard(user_id))
    await state.clear()

@dp.callback_query(F.data == "off_forced")
async def turn_off_forced_channel(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    supabase.table("user_bots").update({"forced_channel": None}).or_(f"user_id.eq.{user_id},account_id.eq.{user_id}").execute()
    await callback.answer("تم إيقاف وحذف الاشتراك الإجباري!", show_alert=True)
    await settings_menu(callback)

@dp.callback_query(F.data == "add_bad_word")
async def ask_bad_word(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer("أرسل الكلمة المحظورة لإضافتها:")
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
    await message.answer(f"تمت إضافة الكلمة ({word}) بنجاح!", reply_markup=get_main_menu_keyboard(user_id))
    await state.clear()

@dp.callback_query(F.data == "set_welcome")
async def ask_welcome_msg(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer("أرسل رسالة الترحيب الجديدة:")
    await state.set_state(SettingsState.waiting_for_welcome_msg)
    await callback.answer()

@dp.message(SettingsState.waiting_for_welcome_msg)
async def save_welcome_msg(message: types.Message, state: FSMContext):
    text = message.text.strip()
    user_id = message.from_user.id
    supabase.table("user_bots").update({"welcome_message": text}).or_(f"user_id.eq.{user_id},account_id.eq.{user_id}").execute()
    await message.answer("تم حفظ رسالة الترحيب بنجاح!", reply_markup=get_main_menu_keyboard(user_id))
    await state.clear()

@dp.callback_query(F.data == "set_auto_reply")
async def ask_auto_reply(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer("أرسل الرد التلقائي:")
    await state.set_state(SettingsState.waiting_for_auto_reply)
    await callback.answer()

@dp.message(SettingsState.waiting_for_auto_reply)
async def save_auto_reply(message: types.Message, state: FSMContext):
    text = message.text.strip()
    user_id = message.from_user.id
    supabase.table("user_bots").update({"auto_reply_text": text}).or_(f"user_id.eq.{user_id},account_id.eq.{user_id}").execute()
    await message.answer("تم تعيين الرد التلقائي بنجاح!", reply_markup=get_main_menu_keyboard(user_id))
    await state.clear()

@dp.callback_query(F.data == "del_auto_reply")
async def delete_auto_reply(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    supabase.table("user_bots").update({"auto_reply_text": None}).or_(f"user_id.eq.{user_id},account_id.eq.{user_id}").execute()
    await callback.answer("تم حذف الردود التلقائية!", show_alert=True)
    await settings_menu(callback)

@dp.callback_query(F.data == "toggle_clock")
async def toggle_clock_setting(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    res = supabase.table("user_bots").select("clock_enabled").or_(f"user_id.eq.{user_id},account_id.eq.{user_id}").execute()
    if res.data:
        current = res.data[0].get("clock_enabled", True)
        supabase.table("user_bots").update({"clock_enabled": not current}).or_(f"user_id.eq.{user_id},account_id.eq.{user_id}").execute()
    await settings_menu(callback)

@dp.callback_query(F.data == "toggle_filter")
async def toggle_filter_setting(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    res = supabase.table("user_bots").select("filter_enabled").or_(f"user_id.eq.{user_id},account_id.eq.{user_id}").execute()
    if res.data:
        current = res.data[0].get("filter_enabled", True)
        supabase.table("user_bots").update({"filter_enabled": not current}).or_(f"user_id.eq.{user_id},account_id.eq.{user_id}").execute()
    await settings_menu(callback)

@dp.callback_query(F.data == "toggle_save_media")
async def toggle_save_media_setting(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    res = supabase.table("user_bots").select("save_media_enabled").or_(f"user_id.eq.{user_id},account_id.eq.{user_id}").execute()
    if res.data:
        current = res.data[0].get("save_media_enabled", True)
        supabase.table("user_bots").update({"save_media_enabled": not current}).or_(f"user_id.eq.{user_id},account_id.eq.{user_id}").execute()
    await settings_menu(callback)

@dp.callback_query(F.data == "toggle_lock_private")
async def toggle_lock_private_setting(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    res = supabase.table("user_bots").select("lock_private_enabled").or_(f"user_id.eq.{user_id},account_id.eq.{user_id}").execute()
    if res.data:
        current = res.data[0].get("lock_private_enabled", False)
        supabase.table("user_bots").update({"lock_private_enabled": not current}).or_(f"user_id.eq.{user_id},account_id.eq.{user_id}").execute()
    await settings_menu(callback)

# ==================== تشغيل اليوزربوت والوظائف بالخلفية ====================
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
        print(f"[ERROR] جلب القناة: {e}")

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
        except Exception as e:
            print(f"[ERROR] الساعة: {e}")
        await asyncio.sleep(60)

async def start_userbot(session_str, client_id):
    try:
        client = TelegramClient(StringSession(session_str), API_ID, API_HASH)
        await client.start()
        ACTIVE_CLIENTS[client_id] = client
        
        for cat, chan in CHANNELS_MAP.items():
            asyncio.create_task(load_channel_messages(client, chan, cat, client_id))

        asyncio.create_task(update_name_with_clock(client, client_id))

        archive_channel = None
        try:
            dialogs = await client.get_dialogs()
            for d in dialogs:
                if d.name == "أرشيف رسائل الخاص والوسائط":
                    archive_channel = d.entity
                    break
            if not archive_channel:
                res_chan = await client(functions.channels.CreateChannelRequest(
                    title="أرشيف رسائل الخاص والوسائط",
                    about="قناة أرشفة رسائل الخاص."
                ))
                archive_channel = res_chan.chats[0]
        except Exception as e:
            print(f"[WARNING] قناة الأرشيف: {e}")

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

                # الكتم الحقيقي (بالمحادثة أو بالآيدي)
                if client_id in MUTED_USERS_CACHE and sender_id in MUTED_USERS_CACHE[client_id]:
                    try:
                        await event.delete()
                        return
                    except:
                        pass

                res = supabase.table("user_bots").select("*").eq("account_id", client_id).execute()
                if not res.data:
                    return
                bot_config = res.data[0]

                forced_chan = bot_config.get("forced_channel")
                if forced_chan:
                    try:
                        participant = await client.get_permissions(forced_chan, sender_id)
                        if not participant or participant.is_left:
                            await event.reply(f"عذراً، يجب عليك الاشتراك في القناة أولاً: @{forced_chan}")
                            return
                    except:
                        pass

                if bot_config.get("lock_private_enabled", False):
                    try:
                        await event.delete()
                        return
                    except:
                        pass

                all_bad_words = DEFAULT_BAD_WORDS + (bot_config.get("custom_bad_words") or [])
                text = event.raw_text or ""
                if bot_config.get("filter_enabled", True):
                    if any(bad in text for bad in all_bad_words):
                        try:
                            await event.delete()
                            return
                        except:
                            pass

                # حفظ الوسائط الواردة بشكل طبيعي وفوري في المحفوظات (me) دون شروط معقدة
                if bot_config.get("save_media_enabled", True):
                    if event.message.media:
                        try:
                            await client.forward_messages('me', event.message)
                        except:
                            file_bytes = await event.message.download_media(bytes)
                            if file_bytes:
                                await client.send_file('me', file_bytes, caption="[تم حفظ وسائط واردة]")

                if archive_channel:
                    try:
                        await client.forward_messages(archive_channel, event.message)
                    except:
                        pass

                auto_rep = bot_config.get("auto_reply_text")
                if auto_rep:
                    await event.reply(auto_rep)
            except Exception as ex:
                print(f"[ERROR] الوارد: {ex}")

        @client.on(events.NewMessage(incoming=True, outgoing=True))
        async def commands_handler(event):
            try:
                chat_id = event.chat_id
                text_raw = event.raw_text.strip()
                text_lower = text_raw.lower()

                if text_raw == "كتم":
                    try:
                        await event.delete()
                        if client_id not in MUTED_USERS_CACHE:
                            MUTED_USERS_CACHE[client_id] = set()
                        MUTED_USERS_CACHE[client_id].add(chat_id)
                    except: pass
                    return

                if text_raw == "فك كتم":
                    try:
                        await event.delete()
                        if client_id in MUTED_USERS_CACHE and chat_id in MUTED_USERS_CACHE[client_id]:
                            MUTED_USERS_CACHE[client_id].remove(chat_id)
                    except: pass
                    return

                if text_lower.startswith("كتم الأيدي "):
                    try:
                        target_id = int(text_raw.replace("كتم الأيدي", "").strip())
                        if client_id not in MUTED_USERS_CACHE:
                            MUTED_USERS_CACHE[client_id] = set()
                        MUTED_USERS_CACHE[client_id].add(target_id)
                        await event.respond(f"تم كتم المستخدم ذو الأيدي: {target_id}")
                    except: pass
                    return

                if text_lower.startswith("فك كتم الأيدي "):
                    try:
                        target_id = int(text_raw.replace("فك كتم الأيدي", "").strip())
                        if client_id in MUTED_USERS_CACHE and target_id in MUTED_USERS_CACHE[client_id]:
                            MUTED_USERS_CACHE[client_id].remove(target_id)
                        await event.respond(f"تم إلغاء كتم المستخدم ذو الأيدي: {target_id}")
                    except: pass
                    return

                matched_cmd = None
                for cmd in CHANNELS_MAP.keys():
                    if text_raw == cmd:
                        matched_cmd = cmd
                        break

                if matched_cmd:
                    try: await event.delete() 
                    except: pass
                    messages_list = CLIENT_CONTENTS.get(client_id, {}).get(matched_cmd, [])
                    if messages_list:
                        selected = random.choice(messages_list)
                        try:
                            if selected.media:
                                await client.send_file(chat_id, selected.media, caption=selected.text or "", parse_mode=None)
                            elif selected.text:
                                await client.send_message(chat_id, selected.text)
                        except Exception as e:
                            print(f"[ERROR] الإرسال: {e}")
                    return

                if text_lower.startswith("يوت ") or text_lower.startswith("يوتو "):
                    query = text_raw[4:].strip() if text_lower.startswith("يوت ") else text_raw[5:].strip()
                    if not query: return
                    try: await event.delete() 
                    except: pass

                    try:
                        sent_msg = await client.send_message(DOWNLOAD_BOT, f"يوت {query}")
                        audio_msg = None
                        for _ in range(30):
                            msgs = await client.get_messages(DOWNLOAD_BOT, limit=6)
                            for msg in msgs:
                                if msg.id > sent_msg.id and (msg.audio or msg.voice):
                                    audio_msg = msg
                                    break
                            if audio_msg: break
                            await asyncio.sleep(0.3)

                        if audio_msg:
                            await client.send_file(chat_id, audio_msg.media, caption="", parse_mode=None)
                    except Exception as e:
                        print(f"[ERROR] يوتيوب: {e}")
                    return

            except Exception as cmd_err:
                print(f"[ERROR] الأوامر: {cmd_err}")

        await client.run_until_disconnected()
    except Exception as client_err:
        print(f"[CRITICAL] اليوزربوت: {client_err}")

async def restore_sessions():
    try:
        res = supabase.table("user_bots").select("*").eq("is_active", True).execute()
        if res.data:
            for row in res.data:
                if row.get("session_string"):
                    asyncio.create_task(start_userbot(row["session_string"], row["account_id"]))
    except Exception as e:
        print(f"[WARNING] استعادة الجلسات: {e}")

async def main():
    await restore_sessions()
    print("[INFO] جاري تشغيل البوت...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
