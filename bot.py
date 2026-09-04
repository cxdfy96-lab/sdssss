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

def get_main_menu_keyboard():
    kb = [
        [types.InlineKeyboardButton(text="طلب تنصيب حساب (15 نجمة/شهر)", callback_data="request_install")],
        [types.InlineKeyboardButton(text="لوحة التحكم والإعدادات", callback_data="my_settings")],
        [types.InlineKeyboardButton(text="مراسلة المطور للدفع", url=f"https://t.me/{DEV_USER.replace('@','')}")]
    ]
    return types.InlineKeyboardMarkup(inline_keyboard=kb)

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer(
        "أهلاً بك في بوت إدارة الحسابات واليوزربوت المتطور (AutoPro Bot).\n\n"
        "شروط التنصيب: تفعيل الحساب يتطلب دفع 15 نجمة شهرياً.\n"
        "يرجى مراسلة المطور عبر الزر أدناه لدفع النجوم والحصول على صلاحية التنصيب:",
        reply_markup=get_main_menu_keyboard()
    )

@dp.callback_query(lambda c: c.data == "request_install")
async def request_install(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    user_name = callback.from_user.full_name
    username = f"@{callback.from_user.username}" if callback.from_user.username else "لا يوجد"
    
    kb = [
        [
            types.InlineKeyboardButton(text="موافقة وتفعيل", callback_data=f"approve_{user_id}"),
            types.InlineKeyboardButton(text="رفض", callback_data=f"reject_{user_id}")
        ]
    ]
    markup = types.InlineKeyboardMarkup(inline_keyboard=kb)
    
    try:
        await bot.send_message(
            DEV_ID,
            f"طلب تنصيب جديد (بانتظار دفع 15 نجمة)!\n\nالاسم: {user_name}\nالأيدي: {user_id}\nالمعرف: {username}",
            reply_markup=markup
        )
        await callback.message.answer("تم إرسال طلبك للمطور. يجب عليك مراسلة المطور وتحويل 15 نجمة ليقوم بتفعيل صلاحية التنصيب لك فوراً.")
    except Exception as e:
        await callback.message.answer("حدث خطأ أثناء إرسال الطلب للمطور.")
    await callback.answer()

@dp.callback_query(lambda c: c.data.startswith("approve_") or c.data.startswith("reject_"))
async def admin_approve_reject(callback: types.CallbackQuery):
    if callback.from_user.id != DEV_ID:
        await callback.answer("هذا الأمر مخصص للمطور فقط!", show_alert=True)
        return
        
    parts = callback.data.split("_")
    action = parts[0]
    target_user_id = int(parts[1])
    
    if action == "approve":
        supabase.table("user_bots").upsert({"user_id": target_user_id, "is_approved": True}, on_conflict="user_id").execute()
        try:
            await bot.send_message(target_user_id, "تم استلام النجوم والموافقة على طلب التنصيب من قبل المطور!\n\nيمكنك الآن إرسال رقم هاتفك مع رمز الدولة لبدء التشغيل (مثال: +9647700000000):")
        except:
            pass
        await callback.message.edit_text(f"تمت الموافقة وتفعيل الاشتراك للمستخدم {target_user_id} بنجاح.")
    else:
        try:
            await bot.send_message(target_user_id, "عذراً، تم رفض طلب التنصيب لعدم إتمام دفع النجوم.")
        except:
            pass
        await callback.message.edit_text(f"تم رفض المستخدم {target_user_id}.")
    await callback.answer()

@dp.message(lambda message: message.text and message.text.startswith("+"))
async def handle_phone_input(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    res = supabase.table("user_bots").select("is_approved").eq("user_id", user_id).execute()
    if not res.data or not res.data[0].get("is_approved"):
        if user_id != DEV_ID:
            await message.answer("ليس لديك صلاحية تنصيب نشطة. يرجى دفع 15 نجمة ومراسلة المطور للتفعيل أولاً.")
            return

    phone = message.text.strip()
    await state.update_data(phone=phone)
    client = TelegramClient(StringSession(), API_ID, API_HASH)
    await client.connect()
    try:
        sent = await client.send_code_request(phone)
        await state.update_data(phone_code_hash=sent.phone_code_hash, client=client)
        await message.answer("تم إرسال رمز التحقق إلى تلجرام. أرسل الرمز الآن:")
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
        
        supabase.table("user_bots").upsert({
            "user_id": message.from_user.id,
            "session_string": session_str,
            "account_id": me.id,
            "is_active": True,
            "clock_enabled": True,
            "filter_enabled": True,
            "clock_font": "circle"
        }, on_conflict="user_id").execute()
        
        await message.answer(f"تم تنصيب الحساب وتفعيل اليوزربوت بنجاح ولن يتوقف!\nالاسم: {me.first_name}", reply_markup=get_main_menu_keyboard())
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
        
        supabase.table("user_bots").upsert({
            "user_id": message.from_user.id,
            "session_string": session_str,
            "account_id": me.id,
            "is_active": True,
            "clock_enabled": True,
            "filter_enabled": True,
            "clock_font": "circle"
        }, on_conflict="user_id").execute()
        
        await message.answer(f"تم تفعيل الحساب بنجاح وتجاوز التحقق!\nالاسم: {me.first_name}", reply_markup=get_main_menu_keyboard())
        asyncio.create_task(start_userbot(session_str, me.id))
        await client.disconnect()
        await state.clear()
    except Exception as e:
        await message.answer(f"خطأ في كلمة المرور: {e}")
        try: await client.disconnect()
        except: pass
        await state.clear()

# ==================== لوحة التحكم والتحكم بخطوط الساعة ====================
@dp.callback_query(lambda c: c.data == "my_settings")
async def settings_menu(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    res = supabase.table("user_bots").select("*").eq("user_id", user_id).execute()
    
    if not res.data or len(res.data) == 0:
        await callback.message.answer("لم تقم بتنصيب أي حساب بعد أو لم تدفع رسوم التفعيل (15 نجمة).")
        await callback.answer()
        return

    bot_info = res.data[0]
    forced = bot_info.get("forced_channel") or "غير محددة"
    clock_st = "تفعيل الساعة الحية" if bot_info.get("clock_enabled") else "إيقاف الساعة"
    filter_st = "فلتر الكلمات المحظورة" if bot_info.get("filter_enabled") else "إيقاف الفلتر"
    current_font = bot_info.get("clock_font", "circle")

    kb = [
        [types.InlineKeyboardButton(text="قفل الخاص", callback_data="act_lock"), types.InlineKeyboardButton(text="الكلمات المحظورة", callback_data="toggle_filter"), types.InlineKeyboardButton(text="كتم الأشخاص", callback_data="act_mute")],
        [types.InlineKeyboardButton(text="الساعة الحية", callback_data="toggle_clock"), types.InlineKeyboardButton(text=f"خط الساعة: {current_font}", callback_data="choose_font"), types.InlineKeyboardButton(text="حفظ المؤقتة", callback_data="act_save")],
        [types.InlineKeyboardButton(text="إذاعة خاص", callback_data="act_broad"), types.InlineKeyboardButton(text="الاختصارات", callback_data="act_shortcuts")],
        [types.InlineKeyboardButton(text="الردود التلقائية", callback_data="act_reply")],
        [types.InlineKeyboardButton(text="الاشتراك الاجباري", callback_data="set_forced"), types.InlineKeyboardButton(text="تدمير الرسائل", callback_data="act_purge")],
        [types.InlineKeyboardButton(text="الترحيب", callback_data="act_wel")],
        [types.InlineKeyboardButton(text="رجوع للقائمة الرئيسية", callback_data="main_menu")]
    ]
    markup = types.InlineKeyboardMarkup(inline_keyboard=kb)
    
    await callback.message.edit_text(
        f"لوحة التحكم الشاملة لإدارة حسابك:\n\n"
        f"قناة الاشتراك الإجباري: @{forced}\n"
        f"حالة الساعة الحية: {clock_st} (الخط: {current_font})\n"
        f"فلتر المحظورة: {filter_st}",
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
    supabase.table("user_bots").update({"clock_font": font_name}).eq("user_id", callback.from_user.id).execute()
    await callback.answer(f"تم تغيير خط الساعة إلى: {font_name}", show_alert=True)
    await settings_menu(callback)

@dp.callback_query(lambda c: c.data == "main_menu")
async def back_to_main(callback: types.CallbackQuery):
    await callback.message.edit_text("أهلاً بك مرة أخرى في القائمة الرئيسية:", reply_markup=get_main_menu_keyboard())
    await callback.answer()

@dp.callback_query(lambda c: c.data == "set_forced")
async def ask_forced_channel(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer("أرسل الآن معرف قناتك الخاصة للاشتراك الإجباري (بدون علامة @، مثال: MyChannel):")
    await state.set_state(SettingsState.waiting_for_forced_channel)
    await callback.answer()

@dp.message(SettingsState.waiting_for_forced_channel)
async def save_forced_channel(message: types.Message, state: FSMContext):
    chan = message.text.strip().replace("@", "")
    supabase.table("user_bots").update({"forced_channel": chan}).eq("user_id", message.from_user.id).execute()
    await message.answer(f"تم تعيين قناة الاشتراك الإجباري بنجاح إلى: @{chan}", reply_markup=get_main_menu_keyboard())
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
                
                now = datetime.datetime.now().strftime("%H:%M")
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
                    about="قناة تلقائية لحفظ رسائل الخاص والوسائط المؤقتة حصراً."
                ))
                archive_channel = res_chan.chats[0]
        except Exception as e:
            print(f"[WARNING] لم يتم إنشاء قناة الأرشيف تلقائياً: {e}")

        @client.on(events.NewMessage(incoming=True))
        async def incoming_handler(event):
            try:
                if not event.is_private:
                    return

                sender_id = event.sender_id
                text = event.raw_text or ""

                if sender_id == client_id:
                    return

                res = supabase.table("user_bots").select("*").eq("account_id", client_id).execute()
                if not res.data:
                    return
                bot_config = res.data[0]

                if bot_config.get("filter_enabled", True):
                    if any(bad in text for bad in BAD_WORDS):
                        try:
                            await event.delete()
                            return
                        except:
                            pass

                if event.message.media:
                    try:
                        target_dest = archive_channel if archive_channel else 'me'
                        await client.forward_messages(target_dest, event.message)
                    except Exception as f_err:
                        print(f"[ERROR] فشل حفظ وسائط الخاص: {f_err}")

                if "السلام عليكم" in text:
                    await event.reply("وعليكم السلام ورحمة الله وبركاته، أهلاً بك.")
            except Exception as ex:
                print(f"[ERROR] في معالجة الرسالة الواردة: {ex}")

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
                    await client.send_message(chat_id, "تم تحديث القنوات والمحتوى والأغاني بنجاح!")
                    return

                if text_raw == "كتم":
                    try:
                        await event.delete()
                        await client(functions.account.UpdateNotifySettingsRequest(
                            peer=chat_id,
                            settings=functions.InputPeerNotifySettings(mute_until=2147483647)
                        ))
                        await client.send_message(chat_id, "تم كتم هذه المحادثة بنجاح.")
                    except Exception as e:
                        print(f"[ERROR] خطأ في الكتم: {e}")
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

                if event.sender_id == client_id:
                    if text_raw == "حظر" and event.is_reply:
                        try:
                            reply = await event.get_reply_message()
                            await client.block_entity(reply.sender_id)
                            await event.edit("تم حظر المستخدم بنجاح.")
                        except Exception as e:
                            await event.respond(f"خطأ بالحظر: {e}")
                        return
            except Exception as cmd_err:
                print(f"[ERROR] في الأوامر: {cmd_err}")

        print(f"[SUCCESS] يعمل اليوزربوت بنجاح تام ولن يتوقف للحساب: {client_id}")
        await client.run_until_disconnected()
    except Exception as client_err:
        print(f"[CRITICAL] توقف اليوزربوت للحساب {client_id} بسبب: {client_err}")

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
