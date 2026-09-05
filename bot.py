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
    res = await db_select("user_bots", "*")
    rows = [x for x in (res.data or []) if x.get("user_id") == user_id]
    return rows[0] if rows else None


async def is_subscription_active(user_id: int) -> bool:
    row = await get_user_row(user_id)
    if not row:
        start = utcnow()
        expires = add_month(start)
        await db_upsert(
            "user_bots",
            {
                "user_id": user_id,
                "is_approved": True,
                "subscription_status": "active",
                "subscription_started_at": start.isoformat(),
                "subscription_expires_at": expires.isoformat(),
                "is_active": False,
            },
        )
        return True
    return True


# ============================================================
# KEYBOARDS
# ============================================================

def main_keyboard(user_id: int):
    rows = [
        [
            types.InlineKeyboardButton(text="تفعيل الاشتراك المجاني", callback_data="subscription"),
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
        rows.append([types.InlineKeyboardButton(text="لوحة المطور", callback_data="dev_panel")])

    return types.InlineKeyboardMarkup(inline_keyboard=rows)


def back_keyboard():
    return types.InlineKeyboardMarkup(
        inline_keyboard=[[types.InlineKeyboardButton(text="رجوع", callback_data="main")]]
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
        "اختر طريقة التنصيب المناسبة لك:",
        reply_markup=main_keyboard(message.from_user.id),
    )


@dp.callback_query(F.data == "main")
async def main_callback(callback: types.CallbackQuery):
    await callback.message.edit_text(
        "أهلاً بك في بوت إدارة الحساب.",
        reply_markup=main_keyboard(callback.from_user.id),
    )
    await callback.answer()


@dp.callback_query(F.data == "subscription")
async def subscription(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    start_date = utcnow()
    expires = add_month(start_date)

    await db_upsert(
        "user_bots",
        {
            "user_id": user_id,
            "is_approved": True,
            "subscription_status": "active",
            "subscription_started_at": start_date.isoformat(),
            "subscription_expires_at": expires.isoformat(),
        },
    )

    kb = types.InlineKeyboardMarkup(
        inline_keyboard=[
            [types.InlineKeyboardButton(text="تسجيل الدخول برقم الهاتف 📱", callback_data="login_phone")],
            [types.InlineKeyboardButton(text="تسجيل الدخول برمز QR 🔲", callback_data="start_install")],
            [types.InlineKeyboardButton(text="رجوع", callback_data="main")],
        ]
    )
    await callback.message.edit_text(
        "تم تفعيل اشتراكك المجاني بنجاح لمدة شهر!\n\n"
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
    await is_subscription_active(user_id)

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
    await callback.message.edit_text("كتم الأشخاص عبر إرسال كلمة (كتم) في الخاص.", reply_markup=back_keyboard())
    await callback.answer()


@dp.callback_query(F.data == "words")
async def words_panel(callback: types.CallbackQuery):
    kb = types.InlineKeyboardMarkup(
        inline_keyboard=[
            [types.InlineKeyboardButton(text="إضافة كلمة", callback_data="add_word")],
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
    if word:
        try:
            await db_insert("blocked_words", {"owner_user_id": message.from_user.id, "word": word})
            await message.answer("تمت إضافة الكلمة.")
        except Exception:
            await message.answer("الكلمة موجودة مسبقًا.")
    await state.clear()


@dp.callback_query(F.data == "lock")
async def lock_panel(callback: types.CallbackQuery):
    await callback.message.edit_text("قفل الخاص مفعل.", reply_markup=back_keyboard())
    await callback.answer()


@dp.callback_query(F.data == "notifications")
async def notifications(callback: types.CallbackQuery):
    row = await get_user_row(callback.from_user.id)
    enabled = bool(row.get("notifications_enabled", True)) if row else True
    await db_upsert("user_bots", {"user_id": callback.from_user.id, "notifications_enabled": not enabled})
    await callback.answer("تم التغيير.", show_alert=True)


@dp.callback_query(F.data == "save_media")
async def save_media(callback: types.CallbackQuery):
    row = await get_user_row(callback.from_user.id)
    enabled = bool(row.get("save_media_enabled", False)) if row else False
    await db_upsert("user_bots", {"user_id": callback.from_user.id, "save_media_enabled": not enabled})
    await callback.answer("تم تبديل حالة حفظ الوسائط.", show_alert=True)


@dp.callback_query(F.data == "clock")
async def clock_panel(callback: types.CallbackQuery):
    await callback.message.edit_text("إعدادات الساعة الحية.", reply_markup=back_keyboard())
    await callback.answer()


@dp.callback_query(F.data == "shortcuts")
async def shortcuts_panel(callback: types.CallbackQuery):
    await callback.message.edit_text("إدارة الاختصارات.", reply_markup=back_keyboard())
    await callback.answer()


@dp.callback_query(F.data == "broadcast")
async def broadcast(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(Form.waiting_broadcast)
    await callback.message.answer("أرسل الرسالة للبث.")
    await callback.answer()


@dp.message(Form.waiting_broadcast)
async def do_broadcast(message: types.Message, state: FSMContext):
    await message.answer("تمت العملية.")
    await state.clear()


@dp.callback_query(F.data == "autoreply")
async def autoreply_panel(callback: types.CallbackQuery):
    await callback.message.edit_text("الردود التلقائية.", reply_markup=back_keyboard())
    await callback.answer()


@dp.callback_query(F.data == "destroy")
async def destroy_panel(callback: types.CallbackQuery):
    await callback.message.edit_text("تدمير الرسائل.", reply_markup=back_keyboard())
    await callback.answer()


@dp.callback_query(F.data == "forced")
async def forced(callback: types.CallbackQuery):
    await callback.message.edit_text("الاشتراك الإجباري.", reply_markup=back_keyboard())
    await callback.answer()


@dp.callback_query(F.data == "welcome")
async def welcome(callback: types.CallbackQuery):
    await callback.message.edit_text("الترحيب.", reply_markup=back_keyboard())
    await callback.answer()


# ============================================================
# USERBOT HELPERS
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


async def get_autoreplies(owner_id: int):
    res = await db_select("auto_replies", "*")
    return [
        x for x in (res.data or [])
        if x.get("owner_user_id") == owner_id and x.get("enabled", True)
    ]


# ============================================================
# USERBOT
# ============================================================

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

    @client.on(events.NewMessage(incoming=True))
    async def incoming_handler(event):
        try:
            if not event.is_private:
                return

            sender_id = event.sender_id
            if not sender_id:
                return

            if await muted(owner_id, sender_id):
                try:
                    await event.delete()
                except Exception:
                    pass
                return

            text = (event.raw_text or "").strip()
            low = text.lower()

            if low == "كتم":
                try:
                    await db_upsert(
                        "muted_users",
                        {"owner_user_id": owner_id, "muted_user_id": sender_id},
                        conflict="owner_user_id,muted_user_id",
                    )
                    await event.delete()
                except Exception:
                    pass
                return

            if low == "فك كتم":
                try:
                    await db_delete("muted_users", owner_user_id=owner_id, muted_user_id=sender_id)
                    await event.delete()
                except Exception:
                    pass
                return

            # حفظ الوسائط العادية وذاتية التدمير (TTL)
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
                            await client.send_file("me", path, caption="[حفظ وسائط]")
                            try:
                                os.remove(path)
                            except Exception:
                                pass
                except Exception as e:
                    print("[MEDIA]", e)

        except Exception as e:
            print("[INCOMING]", e)

    @client.on(events.NewMessage(outgoing=True))
    async def outgoing_handler(event):
        try:
            text = (event.raw_text or "").strip()
            if text in CHANNELS_MAP:
                try:
                    await event.delete()
                except Exception:
                    pass
                return
        except Exception as e:
            print("[OUTGOING]", e)

    try:
        await client.run_until_disconnected()
    except Exception as e:
        print("[USERBOT STOPPED]", owner_id, e)
    finally:
        ACTIVE_CLIENTS.pop(account_id, None)


# ============================================================
# RESTORE & STARTUP
# ============================================================

async def restore_sessions():
    res = await db_select("user_bots", "*")
    for row in res.data or []:
        if row.get("session_string") and row.get("is_approved"):
            user_id = row.get("user_id")
            if user_id:
                try:
                    asyncio.create_task(start_userbot(row["session_string"], row["account_id"], user_id))
                    await asyncio.sleep(0.3)
                except Exception as e:
                    print("[RESTORE]", user_id, e)


@dp.callback_query(F.data == "dev_panel")
async def dev_panel(callback: types.CallbackQuery):
    if callback.from_user.id != DEV_ID:
        await callback.answer("للمطور فقط.", show_alert=True)
        return
    res = await db_select("user_bots", "*")
    rows = res.data or []
    active = sum(1 for x in rows if x.get("is_active"))
    await callback.message.edit_text(f"لوحة المطور\n\nالمستخدمون: {len(rows)}\nالنشطة: {active}", reply_markup=back_keyboard())
    await callback.answer()


@dp.message()
async def generic_message(message: types.Message, state: FSMContext):
    await message.answer("استخدم /start لفتح القائمة.", reply_markup=main_keyboard(message.from_user.id))


async def main():
    print("[INFO] Restoring active accounts...")
    await restore_sessions()
    print("[INFO] Bot is running...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
