import os
import re
import asyncio
import datetime as dt
from typing import Optional

from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage

from telethon import TelegramClient, events, functions, types as tg_types
from telethon.sessions import StringSession
from telethon.errors import (
    SessionPasswordNeededError,
    FloodWaitError,
    PhoneCodeInvalidError,
    PhoneNumberInvalidError,
    AuthKeyUnregisteredError,
)

from supabase import create_client, Client


# ============================================================
# ENVIRONMENT
# ============================================================

API_ID = int(os.getenv("API_ID", "0"))
API_HASH = os.getenv("API_HASH", "")
BOT_TOKEN = os.getenv("BOT_TOKEN", "")

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")

DEV_ID = int(os.getenv("DEV_ID", "5126968608"))
DEV_USER = os.getenv("DEV_USER", "@toe7e")

if not API_ID or not API_HASH or not BOT_TOKEN or not SUPABASE_URL or not SUPABASE_KEY:
    raise RuntimeError(
        "Missing environment variables: API_ID, API_HASH, BOT_TOKEN, "
        "SUPABASE_URL, SUPABASE_KEY"
    )

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

bot = Bot(BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

ACTIVE_CLIENTS: dict[int, TelegramClient] = {}
USER_TASKS: dict[int, list[asyncio.Task]] = {}
LOGIN_CLIENTS: dict[int, TelegramClient] = {}
LOGIN_TASKS: dict[int, asyncio.Task] = {}

CHANNELS_MAP = {
    "غنيلي": "arggrw",
    "شعر": "zfghjjg",
    "مزج": "cvbhfdgds",
    "ميمز": "cbklufswe",
    "قرآن": "chfdthhd",
}

CLOCK_FONTS = {
    "circle": str.maketrans("0123456789", "⓪①②③④⑤⑥⑦⑧⑨"),
    "bold": str.maketrans("0123456789", "𝟎𝟏𝟐𝟑𝟒𝟓𝟔𝟕𝟖𝟗"),
    "sans": str.maketrans("0123456789", "𝟶𝟷𝟸𝟹𝟺𝟻𝟼𝟽𝟾𝟿"),
    "normal": str.maketrans("0123456789", "0123456789"),
}


# ============================================================
# HELPERS
# ============================================================

def normalize_code(text: str) -> str:
    return re.sub(r"[\s\-]", "", (text or "").strip())


def utcnow() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def add_month(start: dt.datetime) -> dt.datetime:
    return start + dt.timedelta(days=30)


async def db_select(table: str, *args, **kwargs):
    return await asyncio.to_thread(
        lambda: supabase.table(table).select(*args, **kwargs).execute()
    )


async def db_insert(table: str, values):
    return await asyncio.to_thread(
        lambda: supabase.table(table).insert(values).execute()
    )


async def db_upsert(table: str, values, conflict="user_id"):
    return await asyncio.to_thread(
        lambda: supabase.table(table).upsert(values, on_conflict=conflict).execute()
    )


async def db_update(table: str, values, **filters):
    def run():
        q = supabase.table(table).update(values)
        for key, value in filters.items():
            q = q.eq(key, value)
        return q.execute()

    return await asyncio.to_thread(run)


async def db_delete(table: str, **filters):
    def run():
        q = supabase.table(table).delete()
        for key, value in filters.items():
            q = q.eq(key, value)
        return q.execute()

    return await asyncio.to_thread(run)


async def get_user_row(user_id: int) -> Optional[dict]:
    try:
        res = await db_select("user_bots", "*")
        rows = [x for x in (res.data or []) if x.get("user_id") == user_id]
        return rows[0] if rows else None
    except Exception:
        return None


async def is_subscription_active(user_id: int) -> bool:
    # تم إرجاع True مباشرة لضمان عدم حدوث أي تعليق أو منع للمستخدم
    return True


# ============================================================
# KEYBOARDS
# ============================================================

def main_keyboard(user_id: int):
    rows = [
        [
            types.InlineKeyboardButton(text="الاشتراك المجاني (شهر)", callback_data="subscription"),
            types.InlineKeyboardButton(text="التعليمات", callback_data="instructions"),
        ],
        [
            types.InlineKeyboardButton(text="كتم الأشخاص", callback_data="mute"),
            types.InlineKeyboardButton(text="الكلمات المحظورة", callback_data="words"),
            types.InlineKeyboardButton(text="قفل الخاص", callback_data="lock"),
        ],
        [
            types.InlineKeyboardButton(text="الإشعارات", callback_data="notifications"),
            types.InlineKeyboardButton(text="حفظ الوسائط", callback_data="save_media"),
            types.InlineKeyboardButton(text="الساعة الحية", callback_data="clock"),
        ],
        [
            types.InlineKeyboardButton(text="الاختصارات", callback_data="shortcuts"),
            types.InlineKeyboardButton(text="إذاعة خاص", callback_data="broadcast"),
        ],
        [types.InlineKeyboardButton(text="الردود التلقائية", callback_data="autoreply")],
        [
            types.InlineKeyboardButton(text="تدمير الرسائل", callback_data="destroy"),
            types.InlineKeyboardButton(text="الاشتراك الإجباري", callback_data="forced"),
        ],
        [types.InlineKeyboardButton(text="الترحيب", callback_data="welcome")],
    ]

    if user_id == DEV_ID:
        rows.append([
            types.InlineKeyboardButton(
                text="لوحة المطور", callback_data="dev_panel"
            )
        ])

    return types.InlineKeyboardMarkup(inline_keyboard=rows)


def back_keyboard():
    return types.InlineKeyboardMarkup(
        inline_keyboard=[
            [types.InlineKeyboardButton(text="رجوع", callback_data="main")]
        ]
    )


# ============================================================
# FSM
# ============================================================

class Form(StatesGroup):
    waiting_phone = State()
    waiting_code = State()
    waiting_password = State()

    waiting_shortcut = State()
    waiting_shortcut_reply = State()

    waiting_word = State()

    waiting_autoreply_trigger = State()
    waiting_autoreply_reply = State()

    waiting_broadcast = State()

    waiting_destroy_seconds = State()
    waiting_forced_channel = State()


# ============================================================
# START
# ============================================================

@dp.message(Command("start"))
async def start(message: types.Message):
    await message.answer(
        "أهلاً بك في بوت إدارة الحساب.\n\n"
        "الاشتراك مجاني بالكامل لمدة شهر!\n"
        "اختر من الأزرار أدناه:",
        reply_markup=main_keyboard(message.from_user.id),
    )


@dp.callback_query(F.data == "main")
async def main_callback(callback: types.CallbackQuery):
    await callback.message.edit_text(
        "أهلاً بك في بوت إدارة الحساب.",
        reply_markup=main_keyboard(callback.from_user.id),
    )
    await callback.answer()


# ============================================================
# FREE SUBSCRIPTION & INSTALL OPTIONS
# ============================================================

@dp.callback_query(F.data == "subscription")
async def subscription(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    start_date = utcnow()
    expires = add_month(start_date)

    try:
        await db_upsert(
            "user_bots",
            {
                "user_id": user_id,
                "is_approved": True,
                "is_active": True,
                "subscription_status": "active",
                "subscription_started_at": start_date.isoformat(),
                "subscription_expires_at": expires.isoformat(),
            },
        )
    except Exception:
        pass

    kb = types.InlineKeyboardMarkup(
        inline_keyboard=[
            [types.InlineKeyboardButton(text="تسجيل الدخول برقم الهاتف 📱", callback_data="login_phone")],
            [types.InlineKeyboardButton(text="تسجيل الدخول برمز QR 🔲", callback_data="start_install")],
            [types.InlineKeyboardButton(text="رجوع", callback_data="main")],
        ]
    )
    await callback.message.edit_text(
        "تم تفعيل اشتراكك المجاني لمدة شهر بنجاح!\n\n"
        "اختر طريقة تسجيل الدخول لحسابك:",
        reply_markup=kb,
    )
    await callback.answer()


# ============================================================
# LOGIN METHOD 1: PHONE NUMBER & CODE
# ============================================================

@dp.callback_query(F.data == "login_phone")
async def login_phone(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(Form.waiting_phone)
    await callback.message.answer("أرسل رقم هاتفك مع رمز الدولة (مثال: +9647700000000):")
    await callback.answer()


@dp.message(Form.waiting_phone)
async def process_phone(message: types.Message, state: FSMContext):
    phone = message.text.strip()
    user_id = message.from_user.id

    client = TelegramClient(StringSession(), API_ID, API_HASH)
    await client.connect()

    try:
        sent = await client.send_code_request(phone)
        LOGIN_CLIENTS[user_id] = client
        await state.update_data(phone=phone, phone_code_hash=sent.phone_code_hash)
        await state.set_state(Form.waiting_code)
        await message.answer("تم إرسال رمز التحقق إلى تطبيق تيليجرام الخاص بك. أرسل الرمز الآن:")
    except Exception as e:
        await client.disconnect()
        await message.answer(f"حدث خطأ: {e}\nأرسل الرقم مجدداً بالشكل الصحيح.")


@dp.message(Form.waiting_code)
async def process_code(message: types.Message, state: FSMContext):
    code = normalize_code(message.text)
    user_id = message.from_user.id
    data = await state.get_data()
    client = LOGIN_CLIENTS.get(user_id)

    if not client:
        await message.answer("انتهت الجلسة، ابدأ من جديد عبر /start")
        await state.clear()
        return

    try:
        await client.sign_in(phone=data["phone"], code=code, phone_code_hash=data["phone_code_hash"])
        await finalize_login(client, user_id, message)
        await state.clear()
    except SessionPasswordNeededError:
        await state.set_state(Form.waiting_password)
        await message.answer("الحساب محمي بكلمة مرور (التحقق بخطوتين). أرسل كلمة المرور الآن:")
    except Exception as e:
        await message.answer(f"رمز التحقق خطأ أو انتهت صلاحيته: {e}\nأرسل الرمز الصحيح:")


@dp.message(Form.waiting_password)
async def process_password(message: types.Message, state: FSMContext):
    password = message.text.strip()
    user_id = message.from_user.id
    client = LOGIN_CLIENTS.get(user_id)

    if not client:
        await message.answer("انتهت الجلسة، ابدأ من جديد عبر /start")
        await state.clear()
        return

    try:
        await client.sign_in(password=password)
        await finalize_login(client, user_id, message)
        await state.clear()
    except Exception as e:
        await message.answer(f"كلمة المرور غير صحيحة: {e}\nأعد إرسال كلمة المرور:")


async def finalize_login(client: TelegramClient, user_id: int, message: types.Message):
    session = client.session.save()
    me = await client.get_me()

    try:
        await db_upsert(
            "user_bots",
            {
                "user_id": user_id,
                "telegram_user_id": me.id,
                "username": me.username,
                "first_name": me.first_name,
                "account_id": me.id,
                "session_string": session,
                "is_approved": True,
                "is_active": True,
            },
        )
    except Exception:
        pass

    LOGIN_CLIENTS.pop(user_id, None)
    await message.answer(
        f"تم تنصيب الحساب بنجاح برقم الهاتف!\n\nالاسم: {me.first_name or ''}",
        reply_markup=main_keyboard(user_id),
    )
    asyncio.create_task(start_userbot(session, me.id, user_id))


# ============================================================
# LOGIN METHOD 2: QR LOGIN
# ============================================================

@dp.callback_query(F.data == "start_install")
async def start_install(callback: types.CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id

    old = LOGIN_CLIENTS.get(user_id)
    if old:
        try:
            await old.disconnect()
        except Exception:
            pass

    client = TelegramClient(StringSession(), API_ID, API_HASH)
    await client.connect()

    try:
        qr = await client.qr_login()
    except Exception as e:
        await client.disconnect()
        await callback.message.answer(f"تعذر بدء تسجيل الدخول: {e}")
        return

    LOGIN_CLIENTS[user_id] = client

    await callback.message.answer(
        "تم إنشاء تسجيل الدخول عبر QR.\n\n"
        "افتح Telegram في جهازك الآخر > Settings > Devices > Link Desktop Device "
        "ثم امسح الرمز.\n\n"
        f"رابط QR:\n{qr.url}"
    )

    async def waiter():
        try:
            await qr.wait()
            session = client.session.save()
            me = await client.get_me()

            try:
                await db_upsert(
                    "user_bots",
                    {
                        "user_id": user_id,
                        "telegram_user_id": me.id,
                        "username": me.username,
                        "first_name": me.first_name,
                        "account_id": me.id,
                        "session_string": session,
                        "is_approved": True,
                        "is_active": True,
                    },
                )
            except Exception:
                pass

            await callback.message.answer(
                f"تم تنصيب الحساب بنجاح عبر QR.\nالاسم: {me.first_name or ''}",
                reply_markup=main_keyboard(user_id),
            )
            await start_userbot(session, me.id, user_id)

        except asyncio.CancelledError:
            raise
        except Exception as e:
            await callback.message.answer(f"فشل تسجيل الدخول: {e}")
        finally:
            LOGIN_CLIENTS.pop(user_id, None)
            try:
                await client.disconnect()
            except Exception:
                pass

    task = asyncio.create_task(waiter())
    LOGIN_TASKS[user_id] = task
    await callback.answer()


# ============================================================
# PANELS
# ============================================================

@dp.callback_query(F.data == "instructions")
async def instructions(callback: types.CallbackQuery):
    await callback.message.edit_text(
        "التعليمات:\n\n"
        "1. الاشتراك مجاني بالكامل لمدة شهر.\n"
        "2. اختر طريقة تسجيل الدخول (برقم الهاتف أو عبر QR).\n"
        "3. بعد تسجيل الدخول يعمل اليوزربوت تلقائياً.",
        reply_markup=back_keyboard(),
    )
    await callback.answer()


@dp.callback_query(F.data == "mute")
async def mute_panel(callback: types.CallbackQuery):
    await callback.message.edit_text(
        "كتم الأشخاص\n\n"
        "داخل محادثة الشخص من الحساب المرتبط، أرسل:\n"
        "كتم\n"
        "لفتح الكتم أرسل:\n"
        "فك كتم\n\n"
        "أو يمكنك كتمه بالأيدي هنا بإرسال:\n"
        "كتم الأيدي <الآيدي>\n"
        "فك كتم الأيدي <الآيدي>",
        reply_markup=back_keyboard(),
    )
    await callback.answer()


@dp.callback_query(F.data == "words")
async def words_panel(callback: types.CallbackQuery):
    kb = types.InlineKeyboardMarkup(
        inline_keyboard=[
            [
                types.InlineKeyboardButton(text="إضافة كلمة", callback_data="add_word"),
                types.InlineKeyboardButton(text="حذف كلمة", callback_data="delete_word"),
            ],
            [types.InlineKeyboardButton(text="عرض الكلمات", callback_data="list_words")],
            [types.InlineKeyboardButton(text="رجوع", callback_data="main")],
        ]
    )
    await callback.message.edit_text("إدارة الكلمات المحظورة.", reply_markup=kb)
    await callback.answer()


@dp.callback_query(F.data == "add_word")
async def add_word(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(Form.waiting_word)
    await callback.message.answer("أرسل الكلمة التي تريد حظرها.")
    await callback.answer()


@dp.message(Form.waiting_word)
async def save_word(message: types.Message, state: FSMContext):
    word = message.text.strip()
    if not word:
        await message.answer("الكلمة غير صالحة.")
        return

    try:
        await db_insert("blocked_words", {"owner_user_id": message.from_user.id, "word": word})
        await message.answer("تمت إضافة الكلمة.")
    except Exception:
        await message.answer("الكلمة موجودة مسبقًا أو حدث خطأ.")
    await state.clear()


@dp.callback_query(F.data == "delete_word")
async def delete_word(callback: types.CallbackQuery):
    await callback.message.answer("أرسل أمر حذف الكلمة بهذا الشكل:\nحذف كلمة الكلمة")
    await callback.answer()


@dp.callback_query(F.data == "list_words")
async def list_words(callback: types.CallbackQuery):
    res = await db_select("blocked_words", "*")
    rows = [x for x in (res.data or []) if x.get("owner_user_id") == callback.from_user.id]
    text = "الكلمات:\n\n" + "\n".join(f"- {x['word']}" for x in rows)
    await callback.message.answer(text if rows else "لا توجد كلمات.")
    await callback.answer()


@dp.callback_query(F.data == "lock")
async def lock_panel(callback: types.CallbackQuery):
    await callback.message.edit_text(
        "قفل الخاص\n\n"
        "هذه الواجهة جاهزة لحفظ إعدادات القفل في user_bots. "
        "التنفيذ الفعلي يتم داخل اليوزربوت حسب الأنواع التي يحددها المستخدم.",
        reply_markup=back_keyboard(),
    )
    await callback.answer()


@dp.callback_query(F.data == "notifications")
async def notifications(callback: types.CallbackQuery):
    row = await get_user_row(callback.from_user.id)
    enabled = bool(row.get("notifications_enabled", True)) if row else True
    await db_upsert(
        "user_bots",
        {"user_id": callback.from_user.id, "notifications_enabled": not enabled},
    )
    await callback.answer("تم التغيير.", show_alert=True)


@dp.callback_query(F.data == "save_media")
async def save_media(callback: types.CallbackQuery):
    row = await get_user_row(callback.from_user.id)
    enabled = bool(row.get("save_media_enabled", False)) if row else False
    await db_upsert(
        "user_bots",
        {"user_id": callback.from_user.id, "save_media_enabled": not enabled},
    )
    await callback.answer(
        "تم تشغيل حفظ الوسائط المؤقتة والعادية." if not enabled else "تم إيقاف حفظ الوسائط.",
        show_alert=True,
    )


@dp.callback_query(F.data == "clock")
async def clock_panel(callback: types.CallbackQuery):
    row = await get_user_row(callback.from_user.id)
    enabled = bool(row.get("clock_enabled", False)) if row else False

    kb = types.InlineKeyboardMarkup(
        inline_keyboard=[
            [
                types.InlineKeyboardButton(
                    text="إيقاف الساعة" if enabled else "تفعيل الساعة",
                    callback_data="toggle_clock",
                )
            ],
            [
                types.InlineKeyboardButton(text="Circle", callback_data="font:circle"),
                types.InlineKeyboardButton(text="Bold", callback_data="font:bold"),
                types.InlineKeyboardButton(text="Sans", callback_data="font:sans"),
            ],
            [types.InlineKeyboardButton(text="رجوع", callback_data="main")],
        ]
    )

    await callback.message.edit_text(
        f"الساعة الحية: {'مفعلة' if enabled else 'متوقفة'}",
        reply_markup=kb,
    )
    await callback.answer()


@dp.callback_query(F.data == "toggle_clock")
async def toggle_clock(callback: types.CallbackQuery):
    row = await get_user_row(callback.from_user.id)
    enabled = bool(row.get("clock_enabled", False)) if row else False
    await db_upsert(
        "user_bots",
        {"user_id": callback.from_user.id, "clock_enabled": not enabled},
    )
    await callback.answer("تم تغيير حالة الساعة.", show_alert=True)


@dp.callback_query(F.data.startswith("font:"))
async def set_font(callback: types.CallbackQuery):
    font = callback.data.split(":", 1)[1]
    if font not in CLOCK_FONTS:
        await callback.answer("خط غير صالح.", show_alert=True)
        return

    await db_upsert(
        "user_bots",
        {"user_id": callback.from_user.id, "clock_font": font},
    )
    await callback.answer("تم تغيير الخط.", show_alert=True)


@dp.callback_query(F.data == "shortcuts")
async def shortcuts_panel(callback: types.CallbackQuery):
    kb = types.InlineKeyboardMarkup(
        inline_keyboard=[
            [types.InlineKeyboardButton(text="إضافة اختصار", callback_data="add_shortcut")],
            [types.InlineKeyboardButton(text="عرض الاختصارات", callback_data="list_shortcuts")],
            [types.InlineKeyboardButton(text="رجوع", callback_data="main")],
        ]
    )
    await callback.message.edit_text("إدارة الاختصارات.", reply_markup=kb)
    await callback.answer()


@dp.callback_query(F.data == "add_shortcut")
async def add_shortcut(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(Form.waiting_shortcut)
    await callback.message.answer("أرسل الاختصار.")
    await callback.answer()


@dp.message(Form.waiting_shortcut)
async def shortcut_name(message: types.Message, state: FSMContext):
    await state.update_data(shortcut=message.text.strip())
    await state.set_state(Form.waiting_shortcut_reply)
    await message.answer("أرسل النص الذي يرسله الاختصار.")


@dp.message(Form.waiting_shortcut_reply)
async def shortcut_reply(message: types.Message, state: FSMContext):
    data = await state.get_data()
    try:
        await db_insert(
            "shortcuts",
            {
                "owner_user_id": message.from_user.id,
                "shortcut": data["shortcut"],
                "response": message.text,
            },
        )
        await message.answer("تمت إضافة الاختصار.")
    except Exception:
        await message.answer("الاختصار موجود مسبقًا أو حدث خطأ.")
    await state.clear()


@dp.callback_query(F.data == "list_shortcuts")
async def list_shortcuts(callback: types.CallbackQuery):
    res = await db_select("shortcuts", "*")
    rows = [x for x in (res.data or []) if x.get("owner_user_id") == callback.from_user.id]
    text = "الاختصارات:\n\n" + "\n".join(
        f"{x['shortcut']} -> {x['response']}" for x in rows
    )
    await callback.message.answer(text if rows else "لا توجد اختصارات.")
    await callback.answer()


@dp.callback_query(F.data == "broadcast")
async def broadcast(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(Form.waiting_broadcast)
    await callback.message.answer("أرسل الرسالة التي تريد بثها.")
    await callback.answer()


@dp.message(Form.waiting_broadcast)
async def do_broadcast(message: types.Message, state: FSMContext):
    row = await get_user_row(message.from_user.id)
    if not row or not row.get("account_id"):
        await message.answer("لا يوجد حساب مرتبط.")
        await state.clear()
        return

    res = await db_select("user_bots", "user_id")
    targets = [x["user_id"] for x in (res.data or []) if x.get("user_id") != message.from_user.id]

    client = ACTIVE_CLIENTS.get(row["account_id"])
    if not client:
        await message.answer("اليوزربوت غير متصل.")
        await state.clear()
        return

    sent = 0
    for target in targets:
        try:
            await client.send_message(target, message.text)
            sent += 1
            await asyncio.sleep(1.2)
        except FloodWaitError as e:
            await asyncio.sleep(e.seconds)
        except Exception:
            continue

    await message.answer(f"تم الإرسال إلى {sent} محادثة.")
    await state.clear()


@dp.callback_query(F.data == "autoreply")
async def autoreply_panel(callback: types.CallbackQuery):
    kb = types.InlineKeyboardMarkup(
        inline_keyboard=[
            [types.InlineKeyboardButton(text="إضافة رد", callback_data="add_autoreply")],
            [types.InlineKeyboardButton(text="عرض الردود", callback_data="list_autoreply")],
            [types.InlineKeyboardButton(text="رجوع", callback_data="main")],
        ]
    )
    await callback.message.edit_text("إدارة الردود التلقائية.", reply_markup=kb)
    await callback.answer()


@dp.callback_query(F.data == "add_autoreply")
async def add_autoreply(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(Form.waiting_autoreply_trigger)
    await callback.message.answer("أرسل النص الذي يشغّل الرد.")
    await callback.answer()


@dp.message(Form.waiting_autoreply_trigger)
async def autoreply_trigger(message: types.Message, state: FSMContext):
    await state.update_data(trigger=message.text.strip())
    await state.set_state(Form.waiting_autoreply_reply)
    await message.answer("أرسل نص الرد.")


@dp.message(Form.waiting_autoreply_reply)
async def autoreply_reply(message: types.Message, state: FSMContext):
    data = await state.get_data()
    try:
        await db_insert(
            "auto_replies",
            {
                "owner_user_id": message.from_user.id,
                "trigger_text": data["trigger"],
                "reply_text": message.text,
                "enabled": True,
            },
        )
        await message.answer("تمت إضافة الرد.")
    except Exception:
        await message.answer("حدث خطأ.")
    await state.clear()


@dp.callback_query(F.data == "list_autoreply")
async def list_autoreply(callback: types.CallbackQuery):
    res = await db_select("auto_replies", "*")
    rows = [x for x in (res.data or []) if x.get("owner_user_id") == callback.from_user.id]
    text = "الردود:\n\n" + "\n".join(
        f"{x['trigger_text']} -> {x['reply_text']}" for x in rows
    )
    await callback.message.answer(text if rows else "لا توجد ردود.")
    await callback.answer()


@dp.callback_query(F.data == "destroy")
async def destroy_panel(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(Form.waiting_destroy_seconds)
    await callback.message.answer(
        "أرسل مدة حذف رسائلك المرسلة بالثواني.\n"
        "أرسل 0 لتعطيل الميزة."
    )
    await callback.answer()


@dp.message(Form.waiting_destroy_seconds)
async def set_destroy(message: types.Message, state: FSMContext):
    try:
        seconds = int(message.text.strip())
        if seconds < 0 or seconds > 86400:
            raise ValueError
    except ValueError:
        await message.answer("أرسل رقمًا من 0 إلى 86400.")
        return

    await db_upsert(
        "user_bots",
        {
            "user_id": message.from_user.id,
            "destroy_messages_enabled": seconds > 0,
            "destroy_seconds": seconds,
        },
    )
    await message.answer("تم حفظ إعداد تدمير الرسائل.")
    await state.clear()


@dp.callback_query(F.data == "forced")
async def forced(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(Form.waiting_forced_channel)
    await callback.message.answer(
        "أرسل معرف القناة مثل @channel.\n"
        "تأكد أن الحساب يستطيع فحص العضوية."
    )
    await callback.answer()


@dp.message(Form.waiting_forced_channel)
async def set_forced(message: types.Message, state: FSMContext):
    channel = message.text.strip()
    await db_upsert(
        "user_bots",
        {
            "user_id": message.from_user.id,
            "forced_subscription_enabled": True,
            "forced_subscription_channel": channel,
        },
    )
    await message.answer("تم حفظ قناة الاشتراك الإجباري.")
    await state.clear()


@dp.callback_query(F.data == "welcome")
async def welcome(callback: types.CallbackQuery):
    await callback.message.edit_text(
        "إعداد الترحيب محفوظ في user_bots. "
        "يمكن تفعيل الخاص والمجموعات من خلال قاعدة البيانات أو إضافة أزرار إعداد مخصصة.",
        reply_markup=back_keyboard(),
    )
    await callback.answer()


# ============================================================
# USERBOT DATABASE HELPERS
# ============================================================

async def muted(owner_id: int, target_id: int) -> bool:
    res = await db_select("muted_users", "*")
    return any(
        x.get("owner_user_id") == owner_id and x.get("muted_user_id") == target_id
        for x in (res.data or [])
    )


async def get_words(owner_id: int):
    res = await db_select("blocked_words", "*")
    return [
        x.get("word", "").lower()
        for x in (res.data or [])
        if x.get("owner_user_id") == owner_id
    ]


async def get_shortcuts(owner_id: int):
    res = await db_select("shortcuts", "*")
    return [
        x for x in (res.data or [])
        if x.get("owner_user_id") == owner_id and x.get("enabled", True)
    ]


async def get_autoreplies(owner_id: int):
    res = await db_select("auto_replies", "*")
    return [
        x for x in (res.data or [])
        if x.get("owner_user_id") == owner_id and x.get("enabled", True)
    ]


# ============================================================
# USERBOT
# ============================================================

async def clock_loop(client: TelegramClient, user_id: int, account_id: int):
    while True:
        try:
            row = await get_user_row(user_id)
            if not row or not row.get("clock_enabled"):
                await asyncio.sleep(60)
                continue

            font = row.get("clock_font", "circle")
            translator = CLOCK_FONTS.get(font, CLOCK_FONTS["circle"])

            now = dt.datetime.now(dt.timezone.utc) + dt.timedelta(hours=3)
            time_text = now.strftime("%H:%M").translate(translator)

            me = await client.get_me()
            first = me.first_name or ""
            base = first.split(" | ")[0]
            new_first = f"{base} | {time_text}"

            if new_first != first:
                await client(functions.account.UpdateProfileRequest(first_name=new_first))

        except FloodWaitError as e:
            await asyncio.sleep(e.seconds)
        except Exception as e:
            print("[CLOCK]", account_id, e)

        await asyncio.sleep(60)


async def start_userbot(session_string: str, account_id: int, owner_id: int):
    if account_id in ACTIVE_CLIENTS:
        try:
            await ACTIVE_CLIENTS[account_id].disconnect()
        except Exception:
            pass

    client = TelegramClient(StringSession(session_string), API_ID, API_HASH)
    await client.connect()

    if not await client.is_user_authorized():
        await db_update(
            "user_bots",
            {"is_active": False, "subscription_status": "login_required"},
            user_id=owner_id,
        )
        await client.disconnect()
        return

    ACTIVE_CLIENTS[account_id] = client

    if account_id in USER_TASKS:
        for task in USER_TASKS[account_id]:
            task.cancel()

    USER_TASKS[account_id] = [
        asyncio.create_task(clock_loop(client, owner_id, account_id)),
    ]

    @client.on(events.NewMessage(incoming=True))
    async def incoming_handler(event):
        try:
            if not event.is_private:
                return

            sender_id = event.sender_id
            if not sender_id:
                return

            # Mute
            if await muted(owner_id, sender_id):
                try:
                    await event.delete()
                except Exception:
                    pass
                return

            text = (event.raw_text or "").strip()
            low = text.lower()

            # Commands for mute / unmute داخل المحادثة
            if low == "كتم":
                try:
                    await db_upsert(
                        "muted_users",
                        {
                            "owner_user_id": owner_id,
                            "muted_user_id": sender_id,
                        },
                        conflict="owner_user_id,muted_user_id",
                    )
                    await event.delete()
                except Exception:
                    pass
                return

            if low == "فك كتم":
                try:
                    await db_delete(
                        "muted_users",
                        owner_user_id=owner_id,
                        muted_user_id=sender_id,
                    )
                    await event.delete()
                except Exception:
                    pass
                return

            # كتم عبر الآيدي
            if low.startswith("كتم الأيدي "):
                try:
                    target_id = int(text.replace("كتم الأيدي", "").strip())
                    await db_upsert(
                        "muted_users",
                        {"owner_user_id": owner_id, "muted_user_id": target_id},
                        conflict="owner_user_id,muted_user_id",
                    )
                    await event.respond(f"تم كتم المستخدم ذو الأيدي: {target_id}")
                except Exception:
                    pass
                return

            if low.startswith("فك كتم الأيدي "):
                try:
                    target_id = int(text.replace("فك كتم الأيدي", "").strip())
                    await db_delete(
                        "muted_users",
                        owner_user_id=owner_id,
                        muted_user_id=target_id,
                    )
                    await event.respond(f"تم إلغاء كتم المستخدم ذو الأيدي: {target_id}")
                except Exception:
                    pass
                return

            # Blocked words
            words = await get_words(owner_id)
            if any(word and word in low for word in words):
                try:
                    await event.delete()
                except Exception:
                    pass
                return

            # Auto replies
            for item in await get_autoreplies(owner_id):
                trigger = (item.get("trigger_text") or "").lower()
                if trigger and trigger in low:
                    try:
                        await client.send_message(event.chat_id, item.get("reply_text", ""))
                    except Exception:
                        pass
                    break

            # ====================================================
            # حفظ الوسائط العادية وذاتية التدمير (TTL / View Once) فوراً
            # ====================================================
            row = await get_user_row(owner_id)
            if row and row.get("save_media_enabled") and event.message.media:
                try:
                    msg_media = event.message.media
                    is_ttl = (
                        getattr(msg_media, 'ttl_seconds', None) is not None or
                        getattr(event.message, 'ttl_period', None) is not None or
                        type(msg_media).__name__ in ['MessageMediaPhoto', 'MessageMediaDocument']
                    )

                    if is_ttl:
                        try:
                            await client.forward_messages('me', event.message)
                        except Exception:
                            path = await event.message.download_media()
                            if path:
                                await client.send_file('me', path, caption="[تم استعادة وسائط وقتية/ذاتية التدمير]")
                                try:
                                    os.remove(path)
                                except Exception:
                                    pass
                    else:
                        path = await event.message.download_media()
                        if path:
                            await client.send_file(
                                "me",
                                path,
                                caption="[حفظ وسائط]",
                            )
                            try:
                                os.remove(path)
                            except Exception:
                                pass
                except Exception as e:
                    print("[MEDIA]", e)

            # Forced subscription check
            if row and row.get("forced_subscription_enabled"):
                channel = row.get("forced_subscription_channel")
                if channel:
                    try:
                        participant = await client.get_permissions(channel, sender_id)
                        if not participant.is_member:
                            await client.send_message(
                                sender_id,
                                "يرجى الاشتراك في القناة أولًا قبل مراسلتي.",
                            )
                            await event.delete()
                            return
                    except Exception:
                        pass

        except Exception as e:
            print("[INCOMING]", e)

    @client.on(events.NewMessage(outgoing=True))
    async def outgoing_handler(event):
        try:
            text = (event.raw_text or "").strip()

            # Shortcut commands
            for item in await get_shortcuts(owner_id):
                shortcut = (item.get("shortcut") or "").strip()
                if shortcut and text == shortcut:
                    try:
                        await event.delete()
                    except Exception:
                        pass
                    await client.send_message(
                        event.chat_id,
                        item.get("response", ""),
                    )
                    return

            # Channel content commands (غنيلي، شعر، مزج، ميمز، قرآن)
            if text in CHANNELS_MAP:
                try:
                    await event.delete()
                except Exception:
                    pass
                return

            # Destroy outgoing messages
            row = await get_user_row(owner_id)
            if row and row.get("destroy_messages_enabled"):
                seconds = int(row.get("destroy_seconds") or 0)
                if seconds > 0:
                    asyncio.create_task(delete_later(client, event.chat_id, event.id, seconds))

        except Exception as e:
            print("[OUTGOING]", e)

    @client.on(events.NewMessage(incoming=True, outgoing=True))
    async def generic_commands(event):
        try:
            if not event.is_private:
                return

            text = (event.raw_text or "").strip()

            if event.out and text == "حذف" and event.is_reply:
                reply = await event.get_reply_message()
                if reply:
                    try:
                        await reply.delete()
                        await event.delete()
                    except Exception:
                        pass

        except Exception as e:
            print("[COMMAND]", e)

    try:
        await client.run_until_disconnected()
    except AuthKeyUnregisteredError:
        await db_update(
            "user_bots",
            {"is_active": False, "subscription_status": "login_required"},
            user_id=owner_id,
        )
    except Exception as e:
        print("[USERBOT STOPPED]", owner_id, e)
    finally:
        ACTIVE_CLIENTS.pop(account_id, None)
        for task in USER_TASKS.pop(account_id, []):
            task.cancel()


async def delete_later(client, chat_id: int, message_id: int, seconds: int):
    await asyncio.sleep(seconds)
    try:
        await client.delete_messages(chat_id, message_id)
    except Exception:
        pass


# ============================================================
# RESTORE
# ============================================================

async def restore_sessions():
    res = await db_select("user_bots", "*")

    for row in res.data or []:
        if not row.get("session_string"):
            continue
        if not row.get("is_approved"):
            continue

        user_id = row.get("user_id")
        if not user_id:
            continue

        try:
            asyncio.create_task(
                start_userbot(
                    row["session_string"],
                    row["account_id"],
                    user_id,
                )
            )
            await asyncio.sleep(0.3)
        except Exception as e:
            print("[RESTORE]", user_id, e)


# ============================================================
# DEVELOPER PANEL
# ============================================================

@dp.callback_query(F.data == "dev_panel")
async def dev_panel(callback: types.CallbackQuery):
    if callback.from_user.id != DEV_ID:
        await callback.answer("للمطور فقط.", show_alert=True)
        return

    res = await db_select("user_bots", "*")
    rows = res.data or []

    active = sum(1 for x in rows if x.get("is_active"))
    approved = sum(1 for x in rows if x.get("is_approved"))

    await callback.message.edit_text(
        "لوحة المطور\n\n"
        f"المستخدمون: {len(rows)}\n"
        f"الموافق عليهم: {approved}\n"
        f"اليوزربوتات النشطة: {active}",
        reply_markup=back_keyboard(),
    )
    await callback.answer()


# ============================================================
# GLOBAL ERROR-SAFE FALLBACK
# ============================================================

@dp.message()
async def generic_message(message: types.Message, state: FSMContext):
    text = (message.text or "").strip()
    if text.startswith("حذف كلمة "):
        word = text[len("حذف كلمة "):].strip()
        if word:
            await db_delete(
                "blocked_words",
                owner_user_id=message.from_user.id,
                word=word,
            )
            await message.answer("تم حذف الكلمة.")
            return

    await message.answer(
        "استخدم /start لفتح القائمة.",
        reply_markup=main_keyboard(message.from_user.id),
    )


# ============================================================
# STARTUP
# ============================================================

async def main():
    print("[INFO] Restoring active accounts...")
    await restore_sessions()

    print("[INFO] Bot is running...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
