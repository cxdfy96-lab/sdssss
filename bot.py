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
from aiogram import Bot, Dispatcher, types
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
        [types.InlineKeyboardButton(text="طلب تنصيب حساب (15 نجمة/شهر)", callback_data="request_install")],
        [types.InlineKeyboardButton(text="لوحة التحكم والإعدادات", callback_data="my_settings")],
        [types.InlineKeyboardButton(text="تعليمات استخدام البوت والخصوصية", callback_data="bot_instructions")],
        [types.InlineKeyboardButton(text="مراسلة المطور للدفع", url=f"https://t.me/{DEV_USER.replace('@','')}")]
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
        [types.InlineKeyboardButton(text=f"الساعة الحية (بغداد): {clock_st}", callback_data="toggle_clock"), types.InlineKeyboardButton(text=f"خط الساعة: {current_font}", callback_data="choose_font")],
        [types.InlineKeyboardButton(text=f"حفظ المؤقتة: {save_st}", callback_data="toggle_save_media"), types.InlineKeyboardButton(text="إضافة كلمة محظورة", callback_data="add_bad_word")],
        [types.InlineKeyboardButton(text="الردود التلقائية", callback_data="set_auto_reply"), types.InlineKeyboardButton(text="حذف الردود", callback_data="del_auto_reply")],
        [types.InlineKeyboardButton(text="الاشتراك الاجباري", callback_data="set_forced"), types.InlineKeyboardButton(text="إيقاف الاشتراك", callback_data="off_forced")],
        [types.InlineKeyboardButton(text="رسالة الترحيب", callback_data="set_welcome"), types.InlineKeyboardButton(text="الترتيب والاختصارات", callback_data="act_shortcuts")],
        [types.InlineKeyboardButton(text="رجوع للقائمة الرئيسية", callback_data="main_menu")]
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
            f"حالة الساعة الحية (بتوقيت بغداد): {clock_st} (الخط: {current_font})\n"
            f"فلتر المحظورة: {filter_st}\n"
            f"حفظ المؤقتة: {save_st}\n"
            f"قفل الخاص: {lock_st}",
            reply_markup=markup
        )
        return

    welcome_text = (
        "مرحباً بك في النظام الذكي لإدارة الحسابات واليوزربوت (AutoPro Bot).\n\n"
        "المميزات:\n"
        "• ساعة حية بتوقيت بغداد المحلي بجانب الاسم.\n"
        "• حفظ إجباري للوسائط الوقتية وذاتية التدمير وحدها في المحفوظات دون باقي الملفات.\n"
        "• كتم حقيقي للمقابل فقط (بحيث يستطيع هو الإرسال وتُحذف رسائله ولا يتأثر حسابك أنت).\n"
        "• أرشفة كافة الرسائل في قناة الأرشيف مع إمكانية إدارة وحذف الردود والاشتراك الإجباري.\n"
    )
    await message.answer(welcome_text, reply_markup=get_main_menu_keyboard(user_id))

@dp.callback_query(lambda c: c.data == "bot_instructions")
async def bot_instructions(callback: types.CallbackQuery):
    text = (
        "تعليمات التشغيل والأوامر:\n"
        "1. اضغط على 'طلب تنصيب حساب' وقم بتحويل 15 نجمة للمطور.\n"
        "2. بعد موافقة المطور، اضغط على زر 'مشاركة رقم الهاتف'.\n"
        "3. الأوامر المتاحة:\n"
        "   - (غنيلي، شعر، مزج، ميمز، قرآن)\n"
        "   - (يوت + اسم الأغنية للبحث والتحميل)\n"
        "   - (كتم) لكتم المقابل وحذف رسائله وحدها / (فك كتم) لإلغاء الكتم\n"
        "   - (حظر) / (الغاء حظر) بالرد على رسالة المستخدم"
    )
    kb = types.InlineKeyboardMarkup(inline_keyboard=[[types.InlineKeyboardButton(text="رجوع", callback_data="main_menu")]])
    await callback.message.edit_text(text, reply_markup=kb)
    await callback.answer()

@dp.callback_query(lambda c: c.data == "request_install")
async def request_install(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    user_name = callback.from_user.full_name
    username = f"@{callback.from_user.username}" if callback.from_user.username else "لا يوجد"
    
    kb = [
        [
            types.InlineKeyboardButton(text="موافقة وتفعيل", callback_data=f"approve_install_{user_id}"),
            types.InlineKeyboardButton(text="رفض", callback_data=f"reject_install_{user_id}")
        ]
    ]
    markup = types.InlineKeyboardMarkup(inline_keyboard=kb)
    try:
        await bot.send_message(
            DEV_ID,
            f"طلب تنصيب جديد (بانتظار دفع 15 نجمة)!\n\nالاسم: {user_name}\nالأيدي: {user_id}\nالمعرف: {username}",
            reply_markup=markup
        )
        await callback.message.answer("تم إرسال طلبك للمطور بنجاح. تواصل مع المطور ودفع 15 نجمة ليتم تفعيل حسابك.")
    except Exception as e:
        await callback.message.answer("حدث خطأ أثناء إرسال الطلب للمطور.")
    await callback.answer()

@dp.callback_query(lambda c: c.data.startswith("approve_install_"))
async def admin_approve_action(callback: types.CallbackQuery):
    if callback.from_user.id != DEV_ID:
        await callback.answer("هذا الأمر للمطور فقط!", show_alert=True)
        return
        
    target_user_id = int(callback.data.replace("approve_install_", ""))
    supabase.table("user_bots").upsert({
        "user_id": target_user_id,
        "is_approved": True,
        "session_string": "",
        "account_id": target_user_id
    }, on_conflict="user_id").execute()
    
    try:
        contact_kb = types.ReplyKeyboardMarkup(
            keyboard=[[types.KeyboardButton(text="مشاركة رقم الهاتف", request_contact=True)]],
            resize_keyboard=True,
            one_time_keyboard=True
        )
        await bot.send_message(
            target_user_id, 
            "تمت الموافقة من المطور!\n\nاضغط على الزر أدناه لمشاركة رقم هاتفك وبدء التشغيل:",
            reply_markup=contact_kb
        )
    except Exception as e:
        print(f"[ERROR] إرسال رسالة الموافقة: {e}")
        
    await callback.message.edit_text(f"تمت الموافقة وتفعيل الاشتراك للمستخدم {target_user_id}.")
    await callback.answer()

@dp.callback_query(lambda c: c.data.startswith("reject_install_"))
async def admin_reject_action(callback: types.CallbackQuery):
    if callback.from_user.id != DEV_ID:
        await callback.answer("هذا الأمر للمطور فقط!", show_alert=True)
        return
        
    target_user_id = int(callback.data.replace("reject_install_", ""))
    try:
        await bot.send_message(target_user_id, "عذراً، تم رفض طلب التنصيب لعدم إتمام دفع النجوم.")
    except:
        pass
    await callback.message.edit_text(f"تم رفض المستخدم {target_user_id}.")
    await callback.answer()

@dp.callback_query(lambda c: c.data == "dev_admin_panel")
async def dev_admin_panel(callback: types.CallbackQuery):
    if callback.from_user.id != DEV_ID:
        await callback.answer("هذا مخصص للمطور فقط!", show_alert=True)
        return
        
    res = supabase.table("user_bots").select("*").execute()
    total_users = len(res.data) if res.data else 0
    active_bots = sum(1 for x in (res.data or []) if x.get("is_active"))
    
    kb = [
        [types.InlineKeyboardButton(text="قائمة المستخدمين والمنصبين", callback_data="dev_list_users")],
        [types.InlineKeyboardButton(text="رجوع للقائمة الرئيسية", callback_data="main_menu")]
    ]
    markup = types.InlineKeyboardMarkup(inline_keyboard=kb)
    
    await callback.message.edit_text(
        f"لوحة تحكم المطور الشاملة:\n\n"
        f"إجمالي المسجلين: {total_users}\n"
        f"اليوزربوتات النشطة: {active_bots}",
        reply_markup=markup
    )
    await callback.answer()

@dp.callback_query(lambda c: c.data == "dev_list_users")
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
    kb.append([types.InlineKeyboardButton(text="رجوع لوحة المطور", callback_data="dev_admin_panel")])
    markup = types.InlineKeyboardMarkup(inline_keyboard=kb)
    await callback.message.edit_text("اختر المستخدم لإدارة حالته أو إلغاء تنصيبه:", reply_markup=markup)
    await callback.answer()

@dp.callback_query(lambda c: c.data.startswith("dev_user_"))
async def dev_manage_user(callback: types.CallbackQuery):
    if callback.from_user.id != DEV_ID:
        return
    target_uid = int(callback.data.replace("dev_user_", ""))
    kb = [
        [types.InlineKeyboardButton(text="إلغاء تنصيب وحذف الحساب", callback_data=f"dev_del_{target_uid}")],
        [types.InlineKeyboardButton(text="رجوع للقائمة", callback_data="dev_list_users")]
    ]
    markup = types.InlineKeyboardMarkup(inline_keyboard=kb)
    await callback.message.edit_text(f"إدارة المستخدم ذو الأيدي: {target_uid}", reply_markup=markup)
    await callback.answer()

@dp.callback_query(lambda c: c.data.startswith("dev_del_"))
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
    res = supabase.table("user_bots").select("is_approved").eq("user_id", user_id).execute()
    if not res.data or not res.data[0].get("is_approved"):
        if user_id != DEV_ID:
            await message.answer("ليس لديك صلاحية تنصيب نشطة. تواصل مع المطور لتفعيل الاشتراك.")
            return

    phone = message.contact.phone_number if message.contact else message.text.strip()
    if not phone.startswith("+"):
        phone = "+" + phone

    await state.update_data(phone=phone)
    client = TelegramClient(StringSession(), API_ID, API_HASH)
    await client.connect()
    try:
        sent = await client.send_code_request(phone)
        await state.update_data(phone_code_hash=sent.phone_code_hash, client=client)
        
        remove_kb = types.ReplyKeyboardRemove()
        await message.answer("تم إرسال رمز التحقق إلى تلجرام. أرسل الرمز الآن:", reply_markup=remove_kb)
        await state.set_state(LoginState.waiting_for_code)
    except Exception as e:
        await message.answer(f"خطأ: {e}")
        try: await client.disconnect()
        except: pass
        await state.clear()

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
        await message.answer(
            f"تم تنصيب الحساب وتفعيل اليوزربوت بنجاح!\nالاسم: {me.first_name}\n\nإليك لوحة التحكم:",
            reply_markup=markup
        )
        asyncio.create_task(start_userbot(session_str, me.id))
        await client.disconnect()
        await state.clear()
    except Exception as e:
        error_str = str(e)
        if "Password" in error_str or "SessionPasswordNeededError" in error_str or "password" in error_str.lower():
            await state.update_data(client=client)
            await message.answer("الحساب محمي بالتحقق بخطوتين. أرسل كلمة المرور الخاصة بك الآن:")
            await state.set_state(LoginState.waiting_for_password)
        else:
            await message.answer(f"خطأ في الرمز: {error_str}")
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
        await message.answer(
            f"تم تفعيل الحساب بنجاح!\nالاسم: {me.first_name}\n\nإليك لوحة التحكم:",
            reply_markup=markup
        )
        asyncio.create_task(start_userbot(session_str, me.id))
        await client.disconnect()
        await state.clear()
    except Exception as e:
        await message.answer(f"خطأ في كلمة المرور: {e}")
        try: await client.disconnect()
        except: pass
        await state.clear()

@dp.callback_query(lambda c: c.data == "my_settings")
async def settings_menu(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    res = supabase.table("user_bots").select("*").or_(f"user_id.eq.{user_id},account_id.eq.{user_id}").execute()
    
    if not res.data or len(res.data) == 0:
        await callback.message.answer("لم تقم بتنصيب أي حساب بعد أو لم يتم تفعيل اشتراكك.")
        await callback.answer()
        return

    bot_info = res.data[0]
    markup, forced, clock_st, filter_st, save_st, lock_st, current_font = get_control_panel_keyboard(bot_info)
    
    await callback.message.edit_text(
        f"لوحة التحكم الشاملة لإدارة حسابك:\n\n"
        f"قناة الاشتراك الإجباري: @{forced}\n"
        f"حالة الساعة الحية (بتوقيت بغداد): {clock_st} (الخط: {current_font})\n"
        f"فلتر المحظورة: {filter_st}\n"
        f"حفظ المؤقتة: {save_st}\n"
        f"قفل الخاص: {lock_st}",
        reply_markup=markup
    )
    await callback.answer()

@dp.callback_query(lambda c: c.data == "choose_font")
async def choose_font_menu(callback: types.CallbackQuery):
    kb = [
        [types.InlineKeyboardButton(text="① دائري أنيق (circle)", callback_data="font_circle")],
        [types.InlineKeyboardButton(text="𝟏 بارز عريض (bold)", callback_data="font_bold")],
        [types.InlineKeyboardButton(text="𝟷 مسطح رفيع (sans)", callback_data="font_sans")],
        [types.InlineKeyboardButton(text="1 عادٍ افتراضي (normal)", callback_data="font_normal")],
        [types.InlineKeyboardButton(text="رجوع للإعدادات", callback_data="my_settings")]
    ]
    markup = types.InlineKeyboardMarkup(inline_keyboard=kb)
    await callback.message.edit_text("اختر شكل خط الساعة الذي يعجبك:", reply_markup=markup)
    await callback.answer()

@dp.callback_query(lambda c: c.data.startswith("font_"))
async def set_clock_font(callback: types.CallbackQuery):
    font_name = callback.data.replace("font_", "")
    user_id = callback.from_user.id
    supabase.table("user_bots").update({"clock_font": font_name}).or_(f"user_id.eq.{user_id},account_id.eq.{user_id}").execute()
    await callback.answer(f"تم تغيير خط الساعة إلى: {font_name}", show_alert=True)
    await settings_menu(callback)

@dp.callback_query(lambda c: c.data == "main_menu")
async def back_to_main(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    welcome_text = "مرحباً بك في النظام الذكي لإدارة الحسابات واليوزربوت (AutoPro Bot).\n\nاختر ما يناسبك أدناه:"
    await callback.message.edit_text(welcome_text, reply_markup=get_main_menu_keyboard(user_id))
    await callback.answer()

@dp.callback_query(lambda c: c.data == "set_forced")
async def ask_forced_channel(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer("أرسل الآن معرف قناتك الخاصة للاشتراك الإجباري (بدون علامة @، مثال: MyChannel):")
    await state.set_state(SettingsState.waiting_for_forced_channel)
    await callback.answer()

@dp.message(SettingsState.waiting_for_forced_channel)
async def save_forced_channel(message: types.Message, state: FSMContext):
    chan = message.text.strip().replace("@", "")
    user_id = message.from_user.id
    supabase.table("user_bots").update({"forced_channel": chan}).or_(f"user_id.eq.{user_id},account_id.eq.{user_id}").execute()
    await message.answer(f"تم تعيين قناة الاشتراك الإجباري بنجاح إلى: @{chan}", reply_markup=get_main_menu_keyboard(user_id))
    await state.clear()

@dp.callback_query(lambda c: c.data == "off_forced")
async def turn_off_forced_channel(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    supabase.table("user_bots").update({"forced_channel": None}).or_(f"user_id.eq.{user_id},account_id.eq.{user_id}").execute()
    await callback.answer("تم إيقاف وحذف قناة الاشتراك الإجباري بنجاح!", show_alert=True)
    await settings_menu(callback)

@dp.callback_query(lambda c: c.data == "add_bad_word")
async def ask_bad_word(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer("أرسل الكلمة المحظورة الجديدة لإضافتها إلى الفلتر الخاص بك:")
    await state.set_state(SettingsState.waiting_for_custom_bad_word)
    await callback.answer()

@dp.message(SettingsState.waiting_for_custom_bad_word)
async def save_bad_word(message: types.Message, state: FSMContext):
    word = message.text.strip()
    user_id = message.from_user.id
    res = supabase.table("user_bots").select("custom_bad_words").or_(f"user_id.eq.{user_id},account_id.eq.{user_id}").execute()
    current_words = res.data[0].get("custom_bad_words") or [] if res.data else []
    if word not in current_words:
        current_words.append(word)
        supabase.table("user_bots").update({"custom_bad_words": current_words}).or_(f"user_id.eq.{user_id},account_id.eq.{user_id}").execute()
    await message.answer(f"تمت إضافة الكلمة ({word}) إلى الفلتر بنجاح!", reply_markup=get_main_menu_keyboard(user_id))
    await state.clear()

@dp.callback_query(lambda c: c.data == "set_welcome")
async def ask_welcome_msg(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer("أرسل الآن رسالة الترحيب الجديدة التي ترسل لمن يراسلك لأول مرة:")
    await state.set_state(SettingsState.waiting_for_welcome_msg)
    await callback.answer()

@dp.message(SettingsState.waiting_for_welcome_msg)
async def save_welcome_msg(message: types.Message, state: FSMContext):
    wel_text = message.text.strip()
    user_id = message.from_user.id
    supabase.table("user_bots").update({"welcome_message": wel_text}).or_(f"user_id.eq.{user_id},account_id.eq.{user_id}").execute()
    await message.answer(f"تم حفظ رسالة الترحيب بنجاح!", reply_markup=get_main_menu_keyboard(user_id))
    await state.clear()

@dp.callback_query(lambda c: c.data == "set_auto_reply")
async def ask_auto_reply(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer("أرسل الرد التلقائي الجديد (مثال: أنا مشغول حالياً، سأرد لاحقاً):")
    await state.set_state(SettingsState.waiting_for_auto_reply)
    await callback.answer()

@dp.message(SettingsState.waiting_for_auto_reply)
async def save_auto_reply(message: types.Message, state: FSMContext):
    rep_text = message.text.strip()
    user_id = message.from_user.id
    supabase.table("user_bots").update({"auto_reply_text": rep_text}).or_(f"user_id.eq.{user_id},account_id.eq.{user_id}").execute()
    await message.answer("تم تعيين الرد التلقائي بنجاح!", reply_markup=get_main_menu_keyboard(user_id))
    await state.clear()

@dp.callback_query(lambda c: c.data == "del_auto_reply")
async def delete_auto_reply(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    supabase.table("user_bots").update({"auto_reply_text": None}).or_(f"user_id.eq.{user_id},account_id.eq.{user_id}").execute()
    await callback.answer("تم حذف وإيقاف الردود التلقائية بنجاح!", show_alert=True)
    await settings_menu(callback)

@dp.callback_query(lambda c: c.data == "toggle_clock")
async def toggle_clock_setting(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    res = supabase.table("user_bots").select("clock_enabled").or_(f"user_id.eq.{user_id},account_id.eq.{user_id}").execute()
    if res.data:
        current = res.data[0].get("clock_enabled", True)
        supabase.table("user_bots").update({"clock_enabled": not current}).or_(f"user_id.eq.{user_id},account_id.eq.{user_id}").execute()
    await settings_menu(callback)

@dp.callback_query(lambda c: c.data == "toggle_filter")
async def toggle_filter_setting(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    res = supabase.table("user_bots").select("filter_enabled").or_(f"user_id.eq.{user_id},account_id.eq.{user_id}").execute()
    if res.data:
        current = res.data[0].get("filter_enabled", True)
        supabase.table("user_bots").update({"filter_enabled": not current}).or_(f"user_id.eq.{user_id},account_id.eq.{user_id}").execute()
    await settings_menu(callback)

@dp.callback_query(lambda c: c.data == "toggle_save_media")
async def toggle_save_media_setting(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    res = supabase.table("user_bots").select("save_media_enabled").or_(f"user_id.eq.{user_id},account_id.eq.{user_id}").execute()
    if res.data:
        current = res.data[0].get("save_media_enabled", True)
        supabase.table("user_bots").update({"save_media_enabled": not current}).or_(f"user_id.eq.{user_id},account_id.eq.{user_id}").execute()
    await settings_menu(callback)

@dp.callback_query(lambda c: c.data == "toggle_lock_private")
async def toggle_lock_private_setting(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    res = supabase.table("user_bots").select("lock_private_enabled").or_(f"user_id.eq.{user_id},account_id.eq.{user_id}").execute()
    if res.data:
        current = res.data[0].get("lock_private_enabled", False)
        supabase.table("user_bots").update({"lock_private_enabled": not current}).or_(f"user_id.eq.{user_id},account_id.eq.{user_id}").execute()
    await settings_menu(callback)

@dp.callback_query(lambda c: c.data.startswith("act_"))
async def handle_feature_buttons(callback: types.CallbackQuery):
    await callback.answer("هذه الميزة مفعلة وتعمل بنجاح في الخلفية!", show_alert=True)

# ==================== تشغيل اليوزربوت والوظائف بالخلفية بشكل مستقر ====================
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
            print(f"[ERROR] خطأ في الساعة: {e}")
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
                    about="قناة تلقائية لأرشفة كافة رسائل الخاص والوسائط."
                ))
                archive_channel = res_chan.chats[0]
        except Exception as e:
            print(f"[WARNING] لم يتم إنشاء قناة الأرشيف تلقائياً: {e}")

        # معالج رسائل الخاص
        @client.on(events.NewMessage(incoming=True))
        async def incoming_handler(event):
            try:
                if not event.is_private:
                    return

                sender = await event.get_sender()
                if sender and getattr(sender, 'bot', False):
                    return

                sender_id = event.sender_id
                chat_id = event.chat_id
                text = event.raw_text or ""

                if sender_id == client_id:
                    return

                # الكتم الفعلي والشامل (حذف رسائل الشخص المقابل فقط ودون التأثير على حسابك)
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
                            await event.reply(f"عذراً، يجب عليك الاشتراك في قناة البوت أولاً لتتمكن من مراسلتنا: @{forced_chan}")
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
                if bot_config.get("filter_enabled", True):
                    if any(bad in text for bad in all_bad_words):
                        try:
                            await event.delete()
                            return
                        except:
                            pass

                # الفحص والالتقاط الدقيق للوسائط الوقتية أو ذاتية التدمير (TTL) فقط ودون حفظ الصور العادية كملفات
                is_ttl = getattr(event.message, 'ttl_period', None) is not None or getattr(event.message, 'vieewed', False) or (getattr(event.media, 'ttl_seconds', None) is not None)

                if bot_config.get("save_media_enabled", True) and is_ttl:
                    try:
                        await client.forward_messages('me', event.message)
                    except Exception as force_err:
                        print(f"[ERROR] فشل حفظ الوسائط الوقتية: {force_err}")

                # تحويل كافة رسائل الخاص العادية إلى قناة الأرشيف
                if archive_channel:
                    try:
                        await client.forward_messages(archive_channel, event.message)
                    except Exception as arch_err:
                        print(f"[ERROR] فشل أرشفة الرسالة: {arch_err}")

                auto_rep = bot_config.get("auto_reply_text")
                if auto_rep:
                    await event.reply(auto_rep)

            except Exception as ex:
                print(f"[ERROR] في معالجة الرسالة الواردة: {ex}")

        # معالج الأوامر
        @client.on(events.NewMessage(incoming=True, outgoing=True))
        async def commands_handler(event):
            try:
                chat_id = event.chat_id
                
                if not event.is_private:
                    try:
                        chat = await event.get_chat()
                        if chat.megagroup or chat.broadcast or getattr(chat, 'forum', False):
                            me = await client.get_me()
                            participant = await client.get_permissions(chat, me.id)
                            if not participant or not (participant.is_admin or participant.is_creator):
                                return
                        else:
                            return
                    except Exception:
                        return

                text_raw = event.raw_text.strip()
                text_lower = text_raw.lower()

                if text_raw == "تحديث":
                    try: await event.delete() 
                    except: pass
                    for cat, chan in CHANNELS_MAP.items():
                        await load_channel_messages(client, chan, cat, client_id)
                    await client.send_message(chat_id, "تم تحديث القنوات والمحتوى بنجاح!")
                    return

                if text_raw == "كتم":
                    try:
                        await event.delete()
                        peer_user_id = chat_id
                        if client_id not in MUTED_USERS_CACHE:
                            MUTED_USERS_CACHE[client_id] = set()
                        MUTED_USERS_CACHE[client_id].add(peer_user_id)
                        
                        msg = await client.send_message(chat_id, "تم كتم هذا الشخص وحذف رسائله تلقائياً.")
                        await asyncio.sleep(2)
                        await msg.delete()
                    except Exception as e:
                        print(f"[ERROR] خطأ في الكتم: {e}")
                    return

                if text_raw == "فك كتم":
                    try:
                        await event.delete()
                        peer_user_id = chat_id
                        if client_id in MUTED_USERS_CACHE and peer_user_id in MUTED_USERS_CACHE[client_id]:
                            MUTED_USERS_CACHE[client_id].remove(peer_user_id)
                        
                        msg = await client.send_message(chat_id, "تم إلغاء كتم هذا الشخص بنجاح.")
                        await asyncio.sleep(2)
                        await msg.delete()
                    except Exception as e:
                        print(f"[ERROR] خطأ في فك الكتم: {e}")
                    return

                if text_raw == "حظر" and event.is_reply:
                    try:
                        reply = await event.get_reply_message()
                        await client.block_entity(reply.sender_id)
                        await event.edit("تم حظر المستخدم بنجاح.")
                    except Exception as e:
                        await event.respond(f"خطأ بالحظر: {e}")
                    return

                if text_raw == "الغاء حظر" and event.is_reply:
                    try:
                        reply = await event.get_reply_message()
                        await client(functions.contacts.UnblockRequest(id=reply.sender_id))
                        await event.edit("تم إلغاء حظر المستخدم بنجاح.")
                    except Exception as e:
                        await event.respond(f"خطأ بإلغاء الحظر: {e}")
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
                    query = text_raw[4:].strip() if text_lower.startswith("يوت ") else text_raw.strip()[5:]
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
                print(f"[ERROR] في الأوامر: {cmd_err}")

        print(f"[SUCCESS] يعمل اليوزربوت بنجاح تام ولن يتوقف للحساب: {client_id}")
        await client.run_until_disconnected()
    except Exception as client_id_err:
        print(f"[CRITICAL] توقف اليوزربوت للحساب بسبب: {client_id_err}")

async def restore_sessions():
    try:
        res = supabase.table("user_bots").select("*").eq("is_active", True).execute()
        if res.data:
            for row in res.data:
                if row.get("session_string"):
                    asyncio.create_task(start_userbot(row["session_string"], row["account_id"]))
    except Exception as e:
        print(f"[WARNING] خطأ باستعادة الجلسات: {e}")

async def main():
    await restore_sessions()
    print("[INFO] جاري تشغيل بوت الإدارة والواجهة التفاعلية...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
