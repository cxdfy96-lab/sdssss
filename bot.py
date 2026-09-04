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

# القنوات الافتراضية لأوامر الترفيه العامة
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
last_sent_messages = {}

# قائمة الكلمات المسيئة الافتراضية (يمكن للمنصّب تعديلها أو إضافتها)
BAD_WORDS = ["وهابي", "عفن", "سخيف", "كلب", "انقلع"]

# ==================== بوت الإدارة والتنصيب الأساسي (Bot API) ====================
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

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    kb = [
        [types.InlineKeyboardButton(text="📥 تنصيب حساب جديد", callback_data="install_account")],
        [types.InlineKeyboardButton(text="⚙️ إعدادات قناتي والاشتراك", callback_data="my_settings")],
        [types.InlineKeyboardButton(text="👨‍💻 المطور", url=f"https://t.me/{DEV_USER.replace('@','')}")]
    ]
    markup = types.InlineKeyboardMarkup(inline_keyboard=kb)
    
    await message.answer(
        "👋 أهلاً بك في بوت إدارة الحسابات واليوزربوت المتطور.\n\n"
        "ميزات البوت: ساعة وقتية، ردود تلقائية، فلتر كلمات مسيئة، كتم، تحميل أغاني، وحفظ الوسائط.",
        reply_markup=markup
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
        await state.update_data(phone_code_hash=sent.phone_code_hash, client=client)
        await message.answer("✅ تم إرسال رمز التحقق إلى تلجرام. أرسل الرمز الآن:")
        await state.set_state(LoginState.waiting_for_code)
    except Exception as e:
        await message.answer(f"❌ خطأ: {e}")
        await client.disconnect()
        await state.clear()

@dp.message(LoginState.waiting_for_code)
async def process_code(message: types.Message, state: FSMContext):
    code = message.text.strip().replace(" ", "")
    data = await state.get_data()
    try:
        await data['client'].sign_in(phone=data['phone'], code=code, phone_code_hash=data['phone_code_hash'])
        session_str = data['client'].session.save()
        me = await data['client'].get_me()
        
        supabase.table("user_bots").upsert({
            "user_id": message.from_user.id,
            "session_string": session_str,
            "account_id": me.id,
            "is_active": True
        }).execute()
        
        await message.answer(f"✅ تم تفعيل اليوزربوت بنجاح!\n👤 الاسم: {me.first_name}")
        asyncio.create_task(start_userbot(session_str, me.id))
        await data['client'].disconnect()
        await state.clear()
    except Exception as e:
        if "Password" in str(e):
            await message.answer("🔐 الحساب محمي بكلمة مرور (تحقق بخطوتين). أرسل كلمة المرور:")
            await state.set_state(LoginState.waiting_for_password)
        else:
            await message.answer(f"❌ خطأ: {e}")
            await data['client'].disconnect()
            await state.clear()

@dp.message(LoginState.waiting_for_password)
async def process_password(message: types.Message, state: FSMContext):
    data = await state.get_data()
    try:
        await data['client'].sign_in(password=message.text.strip())
        session_str = data['client'].session.save()
        me = await data['client'].get_me()
        
        supabase.table("user_bots").upsert({
            "user_id": message.from_user.id,
            "session_string": session_str,
            "account_id": me.id,
            "is_active": True
        }).execute()
        
        await message.answer(f"✅ تم بنجاح!\n👤 الاسم: {me.first_name}")
        asyncio.create_task(start_userbot(session_str, me.id))
        await data['client'].disconnect()
        await state.clear()
    except Exception as e:
        await message.answer(f"❌ خطأ: {e}")
        await data['client'].disconnect()
        await state.clear()

# ==================== تشغيل اليوزربوت والميزات المتقدمة ====================
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

# ميزة الساعة التلقائية بجانب الاسم بخطوط متعددة
async def update_name_with_clock(client):
    fonts = ("0123456789", "⓪①②③④⑤⑥⑦⑧⑨") # خط الدوائر الأنيق
    while True:
        try:
            now = datetime.datetime.now().strftime("%H:%M")
            styled_time = now.translate(str.maketrans(*fonts))
            new_name = f"He the Iraq | {styled_time}"
            await client(functions.account.UpdateProfileRequest(first_name=new_name))
        except Exception as e:
            print(f"[ERROR] خطأ في تحديث الساعة: {e}")
        await asyncio.sleep(60)

async def start_userbot(session_str, client_id):
    client = TelegramClient(StringSession(session_str), API_ID, API_HASH)
    await client.start()
    ACTIVE_CLIENTS[client_id] = client
    
    for cat, chan in CHANNELS_MAP.items():
        await load_channel_messages(client, chan, cat, client_id)

    # تشغيل مهمة الساعة بالخلفية
    asyncio.create_task(update_name_with_clock(client))

    # معالج الأحداث والرسائل الواردة والصادرة
    @client.on(events.NewMessage(incoming=True))
    async def incoming_handler(event):
        sender_id = event.sender_id
        chat_id = event.chat_id
        text = event.raw_text or ""

        if sender_id == client_id:
            return

        # 1. فلتر الكلمات المسيئة
        if any(bad in text for bad in BAD_WORDS):
            try:
                await event.delete()
                # إرسال تحذير أو حظر صامت
                return
            except:
                pass

        # 2. الاشتراك الإجباري الخاص بالمنصّب
        res = supabase.table("user_bots").select("forced_channel").eq("account_id", client_id).execute()
        if res.data and res.data[0].get("forced_channel") and event.is_private:
            forced_chan = res.data[0]["forced_channel"]
            try:
                part = await client.get_permissions(forced_chan, sender_id)
                if not part or part.left:
                    await event.respond(f"⚠️ عذراً، يجب عليك الاشتراك بقناة المالك أولاً لمراسلته:\n👉 @{forced_chan}")
                    return
            except:
                pass

        # 3. حفظ الوسائط ذاتية التدمير
        if event.message.media and getattr(event.message, 'ttl_period', None):
            try:
                await client.forward_messages('me', event.message)
            except:
                pass

        # 4. الردود التلقائية (مثال: الرد على التحية أو الكلمات الشائعة)
        if "السلام عليكم" in text:
            await event.reply("وعليكم السلام ورحمة الله وبركاته، أهلاً بك.")

    @client.on(events.NewMessage(incoming=True, outgoing=True))
    async def commands_handler(event):
        text_raw = event.raw_text.strip()
        text_lower = text_raw.lower()
        chat_id = event.chat_id

        # أوامر الترفيه العامة (غنيلي، شعر، ميمز، إلخ)
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

        # أمر البحث والتحميل (يوت)
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

        # أوامر المالك الخاصة (كتم، حظر، مسح)
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

    print(f"[SUCCESS] يعمل اليوزربوت والميزات بنجاح للحساب: {client_id}")

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
    print("[INFO] جاري تشغيل بوت الإدارة الأساسي...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
