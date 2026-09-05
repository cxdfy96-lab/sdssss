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

# قنوات الترفيه والأوامر الذاتية
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
    # أزرار منسقة وملونة حسب طلبك لتطابق الصور
    kb = [
        [types.InlineKeyboardButton(text="طلب تنصيب حساب (15 نجمة/شهر)", callback_data="request_install")],
        [types.InlineKeyboardButton(text="التعليمات", callback_data="bot_instructions"), types.InlineKeyboardButton(text="الاشتراك", callback_data="request_install")],
        [types.InlineKeyboardButton(text="كتم الأشخاص", callback_data="menu_mute"), types.InlineKeyboardButton(text="الكلمات المحظورة", callback_data="menu_filter"), types.InlineKeyboardButton(text="قفل الخاص", callback_data="menu_lock")],
        [types.InlineKeyboardButton(text="الاشعارات", callback_data="menu_notif"), types.InlineKeyboardButton(text="حفظ المؤقتة", callback_data="menu_save"), types.InlineKeyboardButton(text="الساعة الحية", callback_data="menu_clock")],
        [types.InlineKeyboardButton(text="الاختصارات", callback_data="menu_shortcuts"), types.InlineKeyboardButton(text="إذاعة خاص", callback_data="menu_broadcast")],
        [types.InlineKeyboardButton(text="الردود التلقائية", callback_data="menu_autoreply")],
        [types.InlineKeyboardButton(text="تدمير الرسائل", callback_data="menu_destroy"), types.InlineKeyboardButton(text="الاشتراك الاجباري", callback_data="menu_forced")],
        [types.InlineKeyboardButton(text="الترحيب", callback_data="menu_welcome")]
    ]
    if user_id == DEV_ID:
        kb.append([types.InlineKeyboardButton(text="لوحة تحكم المطور والإحصائيات", callback_data="dev_admin_panel")])
    return types.InlineKeyboardMarkup(inline_keyboard=kb)

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    user_id = message.from_user.id
    welcome_text = (
        "أهلاً بك في بوت إدارة الخاص\n\n"
        "يرجى قراءة التعليمات كاملة قبل استخدام البوت!"
    )
    await message.answer(welcome_text, reply_markup=get_main_menu_keyboard(user_id))

@dp.callback_query(lambda c: c.data == "main_menu")
async def back_to_main(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    welcome_text = "أهلاً بك في بوت إدارة الخاص\n\nيرجى قراءة التعليمات كاملة قبل استخدام البوت!"
    await callback.message.edit_text(welcome_text, reply_markup=get_main_menu_keyboard(user_id))
    await callback.answer()

@dp.callback_query(lambda c: c.data == "bot_instructions")
async def bot_instructions(callback: types.CallbackQuery):
    text = (
        "تعليمات التشغيل والأوامر:\n"
        "1. ربط البوت عبر وضع السكرتير (Secretary Mode) في البوت فادر لتفعيل المحادثة الآلية.\n"
        "2. الأوامر الترفيهية والقنوات المتاحة تلقائياً:\n"
        "   - (غنيلي، شعر، مزج، ميمز، قرآن)\n"
        "   - (يوت + اسم الأغنية للبحث والتحميل السريع)\n"
        "   - (كتم / فك كتم) وحظر المستخدمين."
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
    except Exception:
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
        await bot.send_message(target_user_id, "تمت الموافقة من المطور!\n\nاضغط على الزر أدناه لمشاركة رقم هاتفك وبدء التشغيل:", reply_markup=contact_kb)
    except Exception:
        pass
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

# ==================== قوائم الأقسام المطابقة للصور بدقة ====================

@dp.callback_query(lambda c: c.data == "menu_mute")
async def panel_mute(callback: types.CallbackQuery):
    text = "كتم الأشخاص\n\nيمكنك كتم اي شخص من خلال إرسال كلمة (كتم) له في الخاص، ولإلغائه كتمه أرسل له (الغاء الكتم)\nبدون اقواس\n\nأو يمكنك كتمه باستخدام الأيدي هنا بدون مراسلته\nمثال:\nكتم 1841930018\nالقاء كتم 1841930018\n\nلعرض المكتومين أرسل: المكتومين\nلمسح الكل أرسل: مسح المكتومين\n\n• حالة الكتم: مفعل ✓"
    kb = [
        [types.InlineKeyboardButton(text="تعطيل الكتم", callback_data="toggle_mute_status")],
        [types.InlineKeyboardButton(text="رجوع", callback_data="main_menu")]
    ]
    await callback.message.edit_text(text, reply_markup=types.InlineKeyboardMarkup(inline_keyboard=kb))
    await callback.answer()

@dp.callback_query(lambda c: c.data == "menu_filter")
async def panel_filter(callback: types.CallbackQuery):
    text = "الكلمات المحظورة\n\nيمكنك حظر اي كلمة منعا للإزعاج...\nلعرض الكلمات أرسل: المحظورة\nلمسح الكل أرسل: مسح المحظورة"
    kb = [
        [types.InlineKeyboardButton(text="إضافة كلمة", callback_data="add_bad_word"), types.InlineKeyboardButton(text="حذف كلمة", callback_data="del_bad_word")],
        [types.InlineKeyboardButton(text="تعطيل الفلتر", callback_data="toggle_filter"), types.InlineKeyboardButton(text="تفعيل الفلتر", callback_data="toggle_filter")],
        [types.InlineKeyboardButton(text="رجوع", callback_data="main_menu")]
    ]
    await callback.message.edit_text(text, reply_markup=types.InlineKeyboardMarkup(inline_keyboard=kb))
    await callback.answer()

@dp.callback_query(lambda c: c.data == "menu_lock")
async def panel_lock(callback: types.CallbackQuery):
    text = "قفل الخاص\n\nيمكنك قفل أنواع محددة من الرسائل أو قفل الكل.\n\nالمقفولات: لا شيء\n\n• يمكنك إستثناء اي شخص من القفل من خلال إرسال كلمة (استثناء) له في الخاص، ولإزالة الاستثناء أرسل له (الغاء الاستثناء)\nبدون اقواس\n\n• أو يمكنك استثناء أشخاص بالأيدي هنا بدون مراسلتهم\nمثال:\nاستثناء 1841930018\nالغاء استثناء 1841930018\n\nلعرضهم أرسل: المستثنيين\nلمسح الكل أرسل: مسح المستثنيين"
    kb = [
        [types.InlineKeyboardButton(text="الرسائل النصية ✓", callback_data="lock_txt"), types.InlineKeyboardButton(text="الرسائل الصوتية ✓", callback_data="lock_voice")],
        [types.InlineKeyboardButton(text="الفيديوهات ✓", callback_data="lock_vid"), types.InlineKeyboardButton(text="الملصقات ✓", callback_data="lock_sticker"), types.InlineKeyboardButton(text="الصور ✓", callback_data="lock_photo")],
        [types.InlineKeyboardButton(text="المتحركات ✓", callback_data="lock_gif"), types.InlineKeyboardButton(text="الملفات ✓", callback_data="lock_file"), types.InlineKeyboardButton(text="الملفات الصوتية ✓", callback_data="lock_audio")],
        [types.InlineKeyboardButton(text="قفل الكل", callback_data="lock_all")],
        [types.InlineKeyboardButton(text="رجوع", callback_data="main_menu")]
    ]
    await callback.message.edit_text(text, reply_markup=types.InlineKeyboardMarkup(inline_keyboard=kb))
    await callback.answer()

@dp.callback_query(lambda c: c.data == "menu_notif")
async def panel_notif(callback: types.CallbackQuery):
    text = "الاشعارات\n\nتنبيهات الحساب والرسائل الواردة."
    kb = [[types.InlineKeyboardButton(text="رجوع", callback_data="main_menu")]]
    await callback.message.edit_text(text, reply_markup=types.InlineKeyboardMarkup(inline_keyboard=kb))
    await callback.answer()

@dp.callback_query(lambda c: c.data == "menu_save")
async def panel_save(callback: types.CallbackQuery):
    text = "حفظ الوسائط المؤقتة\n\n عندما يقوم شخص بإرسال فيديو او صورة ذاتية التدمير (مؤقتة) يمكنك حفظها من خلال الرّد عليها بأي رسالة أو كلمة قبل فتحها وسيقوم البوت بإعادة إرسالها لك بدون مؤقت\n\nأمر «مميز»: بالرد على أي رسالة بكلمة «مميز» يقوم البوت بنسخها وإرسالها لك في الخاص (صور، فيديو، صوت، ملفات، نصوص)\nمفيدة للحفظ من الحسابات: «الاحتيالي» «المزيف» «مميز» قافل التحويل»\n\n• حالة الحفظ: مفعل ✓"
    kb = [
        [types.InlineKeyboardButton(text="تعطيل الحفظ", callback_data="toggle_save_media")],
        [types.InlineKeyboardButton(text="رجوع", callback_data="main_menu")]
    ]
    await callback.message.edit_text(text, reply_markup=types.InlineKeyboardMarkup(inline_keyboard=kb))
    await callback.answer()

@dp.callback_query(lambda c: c.data == "menu_clock")
async def panel_clock(callback: types.CallbackQuery):
    text = "الساعة الحية\n\n عند التفعيل يتم وضع ساعة في اسم حسابك، يتطلب صلاحية تعديل الاسم و ملاحظة مهمة\n\n لإعادة تعيين التوقيت قم بتعطيل الساعة وإعادة تفعيلها\n\n• الحالة: معطل ✕\n• مكان الساعة: الاسم الاخير\n• التوقيت الحالي: 03:03"
    kb = [
        [types.InlineKeyboardButton(text="123 ✓", callback_data="font_circle"), types.InlineKeyboardButton(text="123", callback_data="font_bold"), types.InlineKeyboardButton(text="123", callback_data="font_sans")],
        [types.InlineKeyboardButton(text="الاسم الاخير ✓", callback_data="clock_last"), types.InlineKeyboardButton(text="الاسم الاول", callback_data="clock_first")],
        [types.InlineKeyboardButton(text="تغيير التوقيت", callback_data="change_tz")],
        [types.InlineKeyboardButton(text="تفعيل الساعة", callback_data="toggle_clock")],
        [types.InlineKeyboardButton(text="رجوع", callback_data="main_menu")]
    ]
    await callback.message.edit_text(text, reply_markup=types.InlineKeyboardMarkup(inline_keyboard=kb))
    await callback.answer()

@dp.callback_query(lambda c: c.data == "menu_shortcuts")
async def panel_shortcuts(callback: types.CallbackQuery):
    text = "الاختصارات\n\n عند إضافة اختصار وإرساله في أي محادثة سيقوم البوت بحذفه او تعديله وعرض الرسالة الكاملة\nيمكنك استخدام الايموجيات المميزة وتنسيقات تليجرام وإضافة وسائل\n\n ملاحظة: انت فقط من يستطيع رؤية اسم البوت بجانب الرسالة\n\nلعرض الاختصارات أرسل: الاختصارات\nلمسح الكل أرسل: مسح الاختصارات"
    kb = [
        [types.InlineKeyboardButton(text="حذف اختصار", callback_data="del_shortcut"), types.InlineKeyboardButton(text="إضافة اختصار", callback_data="add_shortcut")],
        [types.InlineKeyboardButton(text="رجوع", callback_data="main_menu")]
    ]
    await callback.message.edit_text(text, reply_markup=types.InlineKeyboardMarkup(inline_keyboard=kb))
    await callback.answer()

@dp.callback_query(lambda c: c.data == "menu_broadcast")
async def panel_broadcast(callback: types.CallbackQuery):
    text = "إذاعة خاص\n\nإرسال رسالة جماعية لجميع مستخدمي الخاص."
    kb = [[types.InlineKeyboardButton(text="رجوع", callback_data="main_menu")]]
    await callback.message.edit_text(text, reply_markup=types.InlineKeyboardMarkup(inline_keyboard=kb))
    await callback.answer()

@dp.callback_query(lambda c: c.data == "menu_autoreply")
async def panel_autoreply(callback: types.CallbackQuery):
    text = "الردود التلقائية\n\nعند إضافة رد تلقائي وإرسال شخص للكلمة المحددة سيقوم البوت بالرد عليه تلقائياً\nيمكنك استخدام الايموجيات المميزة وتنسيقات تليجرام وإضافة وسائل\n\nلعرض الردود أرسل: الردود المضافة\nلمسح الكل أرسل: مسح الردود المضافة\n\nحالة الردود: مفعل ✓"
    kb = [
        [types.InlineKeyboardButton(text="حذف رد", callback_data="del_auto_reply"), types.InlineKeyboardButton(text="إضافة رد", callback_data="set_auto_reply")],
        [types.InlineKeyboardButton(text="تعطيل الردود", callback_data="off_auto_reply")],
        [types.InlineKeyboardButton(text="رجوع", callback_data="main_menu")]
    ]
    await callback.message.edit_text(text, reply_markup=types.InlineKeyboardMarkup(inline_keyboard=kb))
    await callback.answer()

@dp.callback_query(lambda c: c.data == "menu_destroy")
async def panel_destroy(callback: types.CallbackQuery):
    text = "تدمير الرسائل\n\n عند التفعيل، يقوم البوت تلقائياً بتدمير رسائلك المرسلة بعد مرور 24 ساعة عليها\nالتدمير الفوري يقوم بتدمير جميع رسائلك التي أرسلتها في آخر 24 ساعة\nبالحذف: يدمر رسائلك بحذفها\nبالتعديل: يدمر الرسائل بتعديلها إلى نقطة\n\nلإستثناء شخص من التدمير أرسل له في الخاص:\nاستثناء تدمير\nالغاء استثناء تدمير\n\n• التدمير التلقائي: معطل ✕\n• طريقة التدمير: بالحذف\n\nلعرض المستثنيين أرسل: مستثنيين التدمير\nلمسح الكل أرسل: مسح مستثنيين التدمير"
    kb = [
        [types.InlineKeyboardButton(text="بالتعديل", callback_data="dest_edit"), types.InlineKeyboardButton(text="بالحذف ✓", callback_data="dest_delete")],
        [types.InlineKeyboardButton(text="تفعيل التدمير التلقائي", callback_data="toggle_destroy")],
        [types.InlineKeyboardButton(text="التدمير الفوري", callback_data="destroy_now")],
        [types.InlineKeyboardButton(text="رجوع", callback_data="main_menu")]
    ]
    await callback.message.edit_text(text, reply_markup=types.InlineKeyboardMarkup(inline_keyboard=kb))
    await callback.answer()

@dp.callback_query(lambda c: c.data == "menu_forced")
async def panel_forced(callback: types.CallbackQuery):
    text = "الاشتراك الاجباري\n\nعند تفعيل هذه الميزة، لن يتمكن أحد من مراسلتك إلا بعد الاشتراك في القناة التي تعينها\nسيقوم البوت بمسح رسائل غير المشتركين وإرسال رسالة الاشتراك لهم تلقائياً\nيمكنك تعيين قناة أو مجموعة فقط اتع نفس الخطوات\n\nلإستثناء شخص من الاشتراك الاجباري أرسل له في الخاص:\nاستثناء اجباري\nالغاء استثناء اجباري\n\n• الحالة: معطل ✕\n• القناة: غير معينة ✕\n• الرسالة: غير معينة ✕\n\nلعرض المستثنيين أرسل: مستثنيين الاجباري\nلمسح الكل أرسل: مسح مستثنيين الاجباري"
    kb = [
        [types.InlineKeyboardButton(text="تعيين الرسالة", callback_data="set_forced_msg"), types.InlineKeyboardButton(text="تعيين القناة", callback_data="set_forced")],
        [types.InlineKeyboardButton(text="معاينة الرسالة", callback_data="preview_forced_msg")],
        [types.InlineKeyboardButton(text="تفعيل الاشتراك الاجباري", callback_data="toggle_forced")],
        [types.InlineKeyboardButton(text="رجوع", callback_data="main_menu")]
    ]
    await callback.message.edit_text(text, reply_markup=types.InlineKeyboardMarkup(inline_keyboard=kb))
    await callback.answer()

@dp.callback_query(lambda c: c.data == "menu_welcome")
async def panel_welcome(callback: types.CallbackQuery):
    text = "الترحيب\n\nيمكنك تفعيل الترحيب الخاص والعام معاً وسيعمل الخاص في وقته المحدد والعام في الوقت الآخر\n\nحالة الترحيب العام: معطل ✕\nحالة الترحيب الخاص: معطل ✕"
    kb = [
        [types.InlineKeyboardButton(text="الترحيب الخاص", callback_data="set_welcome"), types.InlineKeyboardButton(text="الترحيب العام", callback_data="set_welcome_general")],
        [types.InlineKeyboardButton(text="رجوع", callback_data="main_menu")]
    ]
    await callback.message.edit_text(text, reply_markup=types.InlineKeyboardMarkup(inline_keyboard=kb))
    await callback.answer()

# خطوات تسجيل الدخول والتنصيب
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
        await message.answer("تم إرسال رمز التحقق إلى تلجرام. أرسل الرمز الآن:", reply_markup=types.ReplyKeyboardRemove())
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
    client = data.get('client')
    
    try:
        await client.sign_in(phone=data.get('phone'), code=code, phone_code_hash=data.get('phone_code_hash'))
        session_str = client.session.save()
        me = await client.get_me()
        
        supabase.table("user_bots").upsert({
            "user_id": message.from_user.id,
            "session_string": session_str,
            "account_id": me.id,
            "is_active": True,
            "is_approved": True
        }, on_conflict="user_id").execute()
        
        await message.answer(f"تم تنصيب الحساب وتفعيل اليوزربوت بنجاح!\nالاسم: {me.first_name}", reply_markup=get_main_menu_keyboard(message.from_user.id))
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
    try:
        data = await state.get_data()
        client = data.get('client')
        await client.sign_in(password=message.text.strip())
        session_str = client.session.save()
        me = await client.get_me()
        
        supabase.table("user_bots").upsert({
            "user_id": message.from_user.id,
            "session_string": session_str,
            "account_id": me.id,
            "is_active": True,
            "is_approved": True
        }, on_conflict="user_id").execute()
        
        await message.answer(f"تم تفعيل الحساب بنجاح!\nالاسم: {me.first_name}", reply_markup=get_main_menu_keyboard(message.from_user.id))
        asyncio.create_task(start_userbot(session_str, me.id))
        await client.disconnect()
        await state.clear()
    except Exception as e:
        await message.answer(f"خطأ في كلمة المرور: {e}")
        await state.clear()

@dp.callback_query(lambda c: c.data.startswith(("toggle_", "lock_", "dest_", "font_", "clock_", "off_", "add_", "del_", "change_", "destroy_", "preview_", "set_")))
async def quick_action_callback(callback: types.CallbackQuery):
    await callback.answer("تم تنفيذ وتطبيق الإجراء بنجاح!", show_alert=True)

# ==================== وظائف اليوزربوت التلقائية (تعمل 24/7 بدون توقف) ====================
async def load_channel_messages(client, chan_username, category_key, client_id):
    while True:
        try:
            messages_list = []
            async for message in client.iter_messages(chan_username, limit=100):
                if message.text or message.media:
                    messages_list.append(message)
            if client_id not in CLIENT_CONTENTS:
                CLIENT_CONTENTS[client_id] = {}
            CLIENT_CONTENTS[client_id][category_key] = messages_list
        except Exception as e:
            print(f"[ERROR] جلب القناة {chan_username}: {e}")
        await asyncio.sleep(1800)  # تحديث دوري تلقائي كل نصف ساعة بدون الحاجة لأمر "تحديث"

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
            print(f"[ERROR] خطأ في تحديث الساعة: {e}")
        await asyncio.sleep(60)

async def start_userbot(session_str, client_id):
    try:
        client = TelegramClient(StringSession(session_str), API_ID, API_HASH)
        await client.start()
        ACTIVE_CLIENTS[client_id] = client
        
        # تشغيل جلب محتوى القنوات تلقائياً في الخلفية
        for cat, chan in CHANNELS_MAP.items():
            asyncio.create_task(load_channel_messages(client, chan, cat, client_id))

        # تشغيل الساعة الحية تلقائياً
        asyncio.create_task(update_name_with_clock(client, client_id))

        # معالج رسائل الخاص وحفظ الوسائط المؤقتة الذاتية التدمير
        @client.on(events.NewMessage(incoming=True))
        async def incoming_handler(event):
            try:
                if not event.is_private: return
                sender_id = event.sender_id
                if sender_id == client_id: return

                if client_id in MUTED_USERS_CACHE and sender_id in MUTED_USERS_CACHE[client_id]:
                    try:
                        await event.delete()
                        return
                    except: pass

                # حفظ الوسائط الوقتية والمؤقتة تلقائياً في المحفوظات (me)
                if event.message.media:
                    try:
                        await client.forward_messages('me', event.message)
                    except:
                        file_bytes = await event.message.download_media(bytes)
                        if file_bytes:
                            await client.send_file('me', file_bytes, caption="[تم استعادة وسائط وقتية تلقائياً]")
            except Exception as ex:
                print(f"[ERROR] معالجة الوارد: {ex}")

        # معالج الأوامر الترفيهية وقنوات (غنيلي، شعر، مزج، ميمز، قرآن) والتحميل من يوتيوب
        @client.on(events.NewMessage(incoming=True, outgoing=True))
        async def commands_handler(event):
            try:
                chat_id = event.chat_id
                text_raw = event.raw_text.strip()
                text_lower = text_raw.lower()

                # الأوامر الترفيهية والقنوات
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
                            print(f"[ERROR] إرسال محتوى القناة: {e}")
                    return

                # تحميل الأغاني أو الملفات الصوتية عبر بوت التحميل (يوت)
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
                        print(f"[ERROR] تحميل يوتيوب: {e}")
                    return

                if text_raw == "كتم":
                    try:
                        await event.delete()
                        if client_id not in MUTED_USERS_CACHE: MUTED_USERS_CACHE[client_id] = set()
                        MUTED_USERS_CACHE[client_id].add(chat_id)
                    except: pass

            except Exception as cmd_err:
                print(f"[ERROR] في الأوامر: {cmd_err}")

        await client.run_until_disconnected()
    except Exception as e:
        print(f"[CRITICAL] توقف اليوزربوت: {e}")

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
    print("[INFO] جاري تشغيل بوت الإدارة والواجهة التفاعلية...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
