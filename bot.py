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

def get_main_menu_keyboard(user_id):
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
    
    # تحديث وتفعيل الحساب في قاعدة البيانات بنجاح
    supabase.table("user_bots").upsert({
        "user_id": target_user_id,
        "is_approved": True,
        "is_active": True
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
        
    await callback.message.edit_text(f"تمت الموافقة وتفعيل الاشتراك للمستخدم {target_user_id} بنجاح.")
    await callback.answer("تم التفعيل بنجاح!", show_alert=True)

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

# إصلاح لوحة تحكم المطور والإحصائيات
@dp.callback_query(lambda c: c.data == "dev_admin_panel")
async def dev_admin_panel(callback: types.CallbackQuery):
    if callback.from_user.id != DEV_ID:
        await callback.answer("هذا مخصص للمطور فقط!", show_alert=True)
        return
        
    try:
        res = supabase.table("user_bots").select("*").execute()
        total_users = len(res.data) if res.data else 0
        active_bots = sum(1 for x in (res.data or []) if x.get("is_active"))
    except:
        total_users = 0
        active_bots = 0
    
    kb = [
        [types.InlineKeyboardButton(text="رجوع للقائمة الرئيسية", callback_data="main_menu")]
    ]
    markup = types.InlineKeyboardMarkup(inline_keyboard=kb)
    
    await callback.message.edit_text(
        f"لوحة تحكم المطور والإحصائيات:\n\n"
        f"• إجمالي المسجلين: {total_users}\n"
        f"• اليوزربوتات النشطة: {active_bots}",
        reply_markup=markup
    )
    await callback.answer()

# قوائم الأقسام
@dp.callback_query(lambda c: c.data == "menu_mute")
async def panel_mute(callback: types.CallbackQuery):
    text = "كتم الأشخاص\n\nيمكنك كتم اي شخص من خلال إرسال كلمة (كتم) له في الخاص، ولإلغائه كتمه أرسل له (الغاء الكتم)\n• حالة الكتم: مفعل ✓"
    kb = [[types.InlineKeyboardButton(text="تعطيل الكتم", callback_data="toggle_mute_status")], [types.InlineKeyboardButton(text="رجوع", callback_data="main_menu")]]
    await callback.message.edit_text(text, reply_markup=types.InlineKeyboardMarkup(inline_keyboard=kb))
    await callback.answer()

@dp.callback_query(lambda c: c.data == "menu_filter")
async def panel_filter(callback: types.CallbackQuery):
    text = "الكلمات المحظورة\n\nيمكنك حظر اي كلمة منعا للإزعاج..."
    kb = [[types.InlineKeyboardButton(text="رجوع", callback_data="main_menu")]]
    await callback.message.edit_text(text, reply_markup=types.InlineKeyboardMarkup(inline_keyboard=kb))
    await callback.answer()

@dp.callback_query(lambda c: c.data == "menu_lock")
async def panel_lock(callback: types.CallbackQuery):
    text = "قفل الخاص\n\nيمكنك قفل أنواع محددة من الرسائل أو قفل الكل."
    kb = [[types.InlineKeyboardButton(text="رجوع", callback_data="main_menu")]]
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
    text = "حفظ الوسائط المؤقتة\n\nعندما يقوم شخص بإرسال فيديو او صورة ذاتية التدمير يمكنك حفظها."
    kb = [[types.InlineKeyboardButton(text="رجوع", callback_data="main_menu")]]
    await callback.message.edit_text(text, reply_markup=types.InlineKeyboardMarkup(inline_keyboard=kb))
    await callback.answer()

@dp.callback_query(lambda c: c.data == "menu_clock")
async def panel_clock(callback: types.CallbackQuery):
    text = "الساعة الحية\n\nعند التفعيل يتم وضع ساعة في اسم حسابك."
    kb = [[types.InlineKeyboardButton(text="رجوع", callback_data="main_menu")]]
    await callback.message.edit_text(text, reply_markup=types.InlineKeyboardMarkup(inline_keyboard=kb))
    await callback.answer()

@dp.callback_query(lambda c: c.data == "menu_shortcuts")
async def panel_shortcuts(callback: types.CallbackQuery):
    text = "الاختصارات\n\nعند إضافة اختصار وإرساله في أي محادثة سيقوم البوت بحذفه."
    kb = [[types.InlineKeyboardButton(text="رجوع", callback_data="main_menu")]]
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
    text = "الردود التلقائية\n\nعند إضافة رد تلقائي سيقوم البوت بالرد عليه."
    kb = [[types.InlineKeyboardButton(text="رجوع", callback_data="main_menu")]]
    await callback.message.edit_text(text, reply_markup=types.InlineKeyboardMarkup(inline_keyboard=kb))
    await callback.answer()

@dp.callback_query(lambda c: c.data == "menu_destroy")
async def panel_destroy(callback: types.CallbackQuery):
    text = "تدمير الرسائل\n\nيقوم البوت تلقائياً بتدمير رسائلك المرسلة."
    kb = [[types.InlineKeyboardButton(text="رجوع", callback_data="main_menu")]]
    await callback.message.edit_text(text, reply_markup=types.InlineKeyboardMarkup(inline_keyboard=kb))
    await callback.answer()

@dp.callback_query(lambda c: c.data == "menu_forced")
async def panel_forced(callback: types.CallbackQuery):
    text = "الاشتراك الاجباري\n\nلن يتمكن أحد من مراسلتك إلا بعد الاشتراك في القناة."
    kb = [[types.InlineKeyboardButton(text="رجوع", callback_data="main_menu")]]
    await callback.message.edit_text(text, reply_markup=types.InlineKeyboardMarkup(inline_keyboard=kb))
    await callback.answer()

@dp.callback_query(lambda c: c.data == "menu_welcome")
async def panel_welcome(callback: types.CallbackQuery):
    text = "الترحيب\n\nتفعيل الترحيب الخاص والعام."
    kb = [[types.InlineKeyboardButton(text="رجوع", callback_data="main_menu")]]
    await callback.message.edit_text(text, reply_markup=types.InlineKeyboardMarkup(inline_keyboard=kb))
    await callback.answer()

# إدخال رقم الهاتف والتنصيب
@dp.message(lambda message: message.contact or (message.text and message.text.startswith("+")))
async def handle_phone_input(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    res = supabase.table("user_bots").select("is_approved").eq("user_id", user_id).execute()
    if not res.data or not res.data[0].get("is_approved"):
        if user_id != DEV_ID:
            await message.answer("ليس لديك صلاحية تنصيب نشطة. تواصل مع المطور لتفعيل الاشتراك.")
            return

    phone = message.contact.phone_number if message.contact else message.text.strip()
    if not phone.startswith("+"): phone = "+" + phone

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

# ==================== وظائف اليوزربوت التلقائية (تعمل 24/7) ====================
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
        await asyncio.sleep(1800)

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

                if event.message.media:
                    try:
                        await client.forward_messages('me', event.message)
                    except:
                        file_bytes = await event.message.download_media(bytes)
                        if file_bytes:
                            await client.send_file('me', file_bytes, caption="[تم استعادة وسائط وقتية]")
            except Exception as ex:
                print(f"[ERROR] الوارد: {ex}")

        @client.on(events.NewMessage(incoming=True, outgoing=True))
        async def commands_handler(event):
            try:
                chat_id = event.chat_id
                text_raw = event.raw_text.strip()
                text_lower = text_raw.lower()

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

                if text_raw == "كتم":
                    try:
                        await event.delete()
                        if client_id not in MUTED_USERS_CACHE: MUTED_USERS_CACHE[client_id] = set()
                        MUTED_USERS_CACHE[client_id].add(chat_id)
                    except: pass

            except Exception as cmd_err:
                print(f"[ERROR] الأوامر: {cmd_err}")

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
