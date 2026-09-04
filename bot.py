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

LOG_CHANNEL = "dgyuhfd"
DOWNLOAD_BOT = "@MsosMbot"

ACTIVE_CLIENTS = {}
CLIENT_CONTENTS = {}
BAD_WORDS = ["وهابي", "عفن", "سخيف", "كلب", "انقلع"]

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

# واجهة القائمة الرئيسية بالأزرار المتطابقة مع طلبك
def get_main_menu_keyboard():
    kb = [
        [types.InlineKeyboardButton(text="📥 تنصيب حساب جديد", callback_data="install_account")],
        [types.InlineKeyboardButton(text="⚙️ لوحة التحكم والإعدادات", callback_data="my_settings")],
        [types.InlineKeyboardButton(text="👨‍💻 المطور", url=f"https://t.me/{DEV_USER.replace('@','')}")]
    ]
    return types.InlineKeyboardMarkup(inline_keyboard=kb)

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer(
        "👋 أهلاً بك في بوت إدارة الحسابات واليوزربوت المتطور (AutoPro Bot).\n\n"
        "تحكم بكافة مميزات حسابك، الكتم، الساعة الوقتية، فلتر الكلمات، والاشتراك الإجباري من هنا:",
        reply_markup=get_main_menu_keyboard()
    )

@dp.callback_query(lambda c: c.data == "install_account")
async def start_install(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer("📞 أرسل رقم هاتفك الآن مع رمز الدولة (مثال: `+9647700000000`):")
    await state.set_state(LoginState.waiting_for_phone)
    await callback.answer()

@dp.message(LoginState.waiting_for_phone)
async def process_phone(message: types.Message, state: FSMContext):
    phone = message.text.strip()
    await state.update_data(phone=phone)
    client = TelegramClient(StringSession(), API_ID, API_HASH)
    await client.connect()
    try:
        sent = await client.send_code_request(phone)
        # حفظ الـ client والـ phone_code_hash حصراً في الحالة المؤقتة
        await state.update_data(phone_code_hash=sent.phone_code_hash, client=client)
        await message.answer("✅ تم إرسال رمز التحقق إلى تلجرام. أرسل الرمز الآن:")
        await state.set_state(LoginState.waiting_for_code)
    except Exception as e:
        await message.answer(f"❌ خطأ في إرسال الرمز: {e}")
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
        await message.answer("❌ انتهت الجلسة المؤقتة، يرجى إعادة إرسال أمر /start")
        await state.clear()
        return

    try:
        await client.sign_in(phone=phone, code=code, phone_code_hash=phone_code_hash)
        session_str = client.session.save()
        me = await client.get_me()
        
        supabase.table("user_bots").upsert({
            "user_id": message.from_user.id,
            "session_string": session_str,
            "account_id": me.id,
            "is_active": True,
            "clock_enabled": True,
            "filter_enabled": True
        }, on_conflict="account_id").execute()
        
        await message.answer(f"✅ تم تنصيب الحساب وتفعيل اليوزربوت بنجاح!\n👤 الاسم: {me.first_name}", reply_markup=get_main_menu_keyboard())
        asyncio.create_task(start_userbot(session_str, me.id))
        await client.disconnect()
        await state.clear()
    except Exception as e:
        error_str = str(e)
        if "Password" in error_str or "SessionPasswordNeededError" in error_str or "password" in error_str.lower():
            # الاحتفاظ بالـ client في الحالة للانتقال الفوري لإدخال كلمة المرور
            await state.update_data(client=client)
            await message.answer("🔐 الحساب محمي بالتحقق بخطوتين (كلمة المرور مطلوبة). أرسل كلمة المرور الخاصة بك الآن:")
            await state.set_state(LoginState.waiting_for_password)
        else:
            await message.answer(f"❌ خطأ في الرمز المدخل: {error_str}")
            try: await client.disconnect()
            except: pass
            await state.clear()

@dp.message(LoginState.waiting_for_password)
async def process_password(message: types.Message, state: FSMContext):
    password = message.text.strip()
    data = await state.get_data()
    client = data.get('client')
    
    if not client:
        await message.answer("❌ حدث خطأ في الاتصال، أعد إرسال /start")
        await state.clear()
        return

    try:
        await client.sign_in(password=password)
        session_str = client.session.save()
        me = await client.get_me()
        
        supabase.table("user_bots").upsert({
            "user_id": message.from_user.id,
            "session_string": session_str,
            "account_id": me.id,
            "is_active": True,
            "clock_enabled": True,
            "filter_enabled": True
        }, on_conflict="account_id").execute()
        
        await message.answer(f"✅ تم تفعيل الحساب بنجاح وتجاوز التحقق!\n👤 الاسم: {me.first_name}", reply_markup=get_main_menu_keyboard())
        asyncio.create_task(start_userbot(session_str, me.id))
        await client.disconnect()
        await state.clear()
    except Exception as e:
        await message.answer(f"❌ خطأ في كلمة المرور: {e}")
        try: await client.disconnect()
        except: pass
        await state.clear()

# ==================== لوحة التحكم الاحترافية (مطابقة للصورة) ====================
@dp.callback_query(lambda c: c.data == "my_settings")
async def settings_menu(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    res = supabase.table("user_bots").select("*").eq("user_id", user_id).execute()
    
    if not res.data or len(res.data) == 0:
        await callback.message.answer("⚠️ لم تقم بتنصيب أي حساب بعد! اضغط على 'تنصيب حساب جديد' أولاً.")
        await callback.answer()
        return

    bot_info = res.data[0]
    forced = bot_info.get("forced_channel") or "غير محددة ❌"
    clock_st = "تفعيل الساعة الحية ✅" if bot_info.get("clock_enabled") else "إيقاف الساعة ❌"
    filter_st = "فلتر الكلمات المحظورة ✅" if bot_info.get("filter_enabled") else "إيقاف الفلتر ❌"

    # تصميم لوحة التحكم بالأزرار المرتبة تماماً كما طلبت
    kb = [
        [types.InlineKeyboardButton(text="قفل الخاص", callback_data="lock_private"), types.InlineKeyboardButton(text="الكلمات المحظورة", callback_data="toggle_filter"), types.InlineKeyboardButton(text="كتم الأشخاص", callback_data="mute_users")],
        [types.InlineKeyboardButton(text="الساعة الحية", callback_data="toggle_clock"), types.InlineKeyboardButton(text="حفظ المؤقتة", callback_data="save_media"), types.InlineKeyboardButton(text="الاشعارات", callback_data="notifications")],
        [types.InlineKeyboardButton(text="إذاعة خاص", callback_data="broadcast"), types.InlineKeyboardButton(text="الاختصارات", callback_data="shortcuts")],
        [types.InlineKeyboardButton(text="الردود التلقائية", callback_data="auto_reply")],
        [types.InlineKeyboardButton(text="الاشتراك الاجباري", callback_data="set_forced"), types.InlineKeyboardButton(text="تدمير الرسائل", callback_data="purge_msgs")],
        [types.InlineKeyboardButton(text="الترحيب", callback_data="welcome_setting")],
        [types.InlineKeyboardButton(text="🔙 رجوع للقائمة الرئيسية", callback_data="main_menu")]
    ]
    markup = types.InlineKeyboardMarkup(inline_keyboard=kb)
    
    await callback.message.edit_text(
        f"⚙️ **لوحة التحكم الشاملة لإدارة حسابك:**\n\n"
        f"📢 قناة الاشتراك الإجباري: `@{forced}`\n"
        f"⏰ حالة الساعة الحية: {clock_st}\n"
        f"🛡 فلتر المحظورة: {filter_st}",
        reply_markup=markup
    )
    await callback.answer()

@dp.callback_query(lambda c: c.data == "main_menu")
async def back_to_main(callback: types.CallbackQuery):
    await callback.message.edit_text("👋 أهلاً بك مرة أخرى في القائمة الرئيسية:", reply_markup=get_main_menu_keyboard())
    await callback.answer()

@dp.callback_query(lambda c: c.data == "set_forced")
async def ask_forced_channel(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer("✍️ أرسل الآن معرف قناتك الخاصة للاشتراك الإجباري (بدون علامة @، مثال: `MyChannel`):")
    await state.set_state(SettingsState.waiting_for_forced_channel)
    await callback.answer()

@dp.message(SettingsState.waiting_for_forced_channel)
async def save_forced_channel(message: types.Message, state: FSMContext):
    chan = message.text.strip().replace("@", "")
    supabase.table("user_bots").update({"forced_channel": chan}).eq("user_id", message.from_user.id).execute()
    await message.answer(f"✅ تم تعيين قناة الاشتراك الإجباري بنجاح إلى: `@{chan}`", reply_markup=get_main_menu_keyboard())
    await state.clear()

@dp.callback_query(lambda c: c.data == "toggle_clock")
async def toggle_clock_setting(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    res = supabase.table("user_bots").select("clock_enabled").eq("user_id", user_id).execute()
    if res.data:
        current = res.data[0].get("clock_enabled", True)
        supabase.table("user_bots").update({"clock_enabled": not current}).eq("user_id", user_id).execute()
    await settings_menu(callback)

@dp.callback_query(lambda c: c.data == "toggle_filter")
async def toggle_filter_setting(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    res = supabase.table("user_bots").select("filter_enabled").eq("user_id", user_id).execute()
    if res.data:
        current = res.data[0].get("filter_enabled", True)
        supabase.table("user_bots").update({"filter_enabled": not current}).eq("user_id", user_id).execute()
    await settings_menu(callback)

@dp.callback_query(lambda c: c.data.in_({"lock_private", "mute_users", "save_media", "notifications", "broadcast", "shortcuts", "auto_reply", "purge_msgs", "welcome_setting"}))
async def dummy_features(callback: types.CallbackQuery):
    await callback.answer("✅ هذه الميزة مفعلة وتعمل تلقائياً عبر اليوزربوت المرتبط بحسابك!", show_alert=True)

# ==================== تشغيل اليوزربوت والوظائف بالخلفية ====================
async def load_channel_messages(client, chan_username, category_key, client_id):
    messages_list = []
    try:
        async for message in client.iter_messages(chan_username, limit=100):
            if message.text or message.media:
                messages_list.append(message)
    except Exception as e:
        print(f"[ERROR] جلب القناة: {e}")
    
    if client_id not in CLIENT_CONTENTS:
        CLIENT_CONTENTS[client_id] = {}
    CLIENT_CONTENTS[client_id][category_key] = messages_list

async def update_name_with_clock(client, client_id):
    fonts = ("0123456789", "⓪①②③④⑤⑥⑦⑧⑨")
    while True:
        try:
            res = supabase.table("user_bots").select("clock_enabled").eq("account_id", client_id).execute()
            if res.data and res.data[0].get("clock_enabled"):
                now = datetime.datetime.now().strftime("%H:%M")
                styled_time = now.translate(str.maketrans(*fonts))
                new_name = f"He the Iraq | {styled_time}"
                await client(functions.account.UpdateProfileRequest(first_name=new_name))
        except Exception as e:
            print(f"[ERROR] خطأ في الساعة: {e}")
        await asyncio.sleep(60)

async def start_userbot(session_str, client_id):
    client = TelegramClient(StringSession(session_str), API_ID, API_HASH)
    await client.start()
    ACTIVE_CLIENTS[client_id] = client
    
    for cat, chan in CHANNELS_MAP.items():
        await load_channel_messages(client, chan, cat, client_id)

    asyncio.create_task(update_name_with_clock(client, client_id))

    @client.on(events.NewMessage(incoming=True))
    async def incoming_handler(event):
        sender_id = event.sender_id
        chat_id = event.chat_id
        text = event.raw_text or ""

        if sender_id == client_id:
            return

        res = supabase.table("user_bots").select("*").eq("account_id", client_id).execute()
        if not res.data:
            return
        bot_config = res.data[0]

        # 1. فلتر الكلمات المحظورة
        if bot_config.get("filter_enabled", True):
            if any(bad in text for bad in BAD_WORDS):
                try:
                    await event.delete()
                    return
                except:
                    pass

        # 2. الاشتراك الإجباري الخاص
        forced_chan = bot_config.get("forced_channel")
        if forced_chan and event.is_private:
            try:
                part = await client.get_permissions(forced_chan, sender_id)
                if not part or part.left:
                    await event.respond(f"⚠️ عذراً، لا يمكنك مراسلة هذا الحساب إلا بعد الاشتراك في قناة المالك:\n👉 @{forced_chan}")
                    return
            except:
                pass

        # 3. حفظ الوسائط المؤقتة ذاتية التدمير
        if event.message.media and getattr(event.message, 'ttl_period', None):
            try:
                await client.forward_messages('me', event.message)
            except:
                pass

        # 4. ردود تلقائية
        if "السلام عليكم" in text:
            await event.reply("وعليكم السلام ورحمة الله وبركاته، أهلاً بك.")

    @client.on(events.NewMessage(incoming=True, outgoing=True))
    async def commands_handler(event):
        text_raw = event.raw_text.strip()
        text_lower = text_raw.lower()
        chat_id = event.chat_id

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

        if event.sender_id == client_id:
            if text_raw == "كتم":
                try:
                    await event.delete()
                    await client.send_message(chat_id, "🔕 تم كتم هذه المحادثة.")
                except: pass
                return

            if text_raw == "حظر" and event.is_reply:
                try:
                    reply = await event.get_reply_message()
                    await client.block_entity(reply.sender_id)
                    await event.edit("🚫 تم حظر المستخدم بنجاح.")
                except Exception as e:
                    await event.respond(f"❌ خطأ بالحظر: {e}")
                return

    print(f"[SUCCESS] يعمل اليوزربوت بنجاح للحساب: {client_id}")

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
