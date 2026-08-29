import os
import random
import asyncio
import logging
from telethon import TelegramClient, events
from telethon.sessions import StringSession
from telethon.tl.custom import Button

# ----------------- إعدادات التسجيل -----------------
logging.basicConfig(
    format="[%(levelname)s] %(asctime)s - %(message)s",
    level=logging.INFO
)

# ----------------- الثوابت الأساسية -----------------
API_ID = int(os.environ.get("API_ID", 0))
API_HASH = os.environ.get("API_HASH", "")
BOT_TOKEN = "8730782028:AAGaJlb44r7UE--4lmth7KnoGz1oDGbu_X8"
OWNER_ID = 5126968608
OWNER_USERNAME = "toe7e"

# قراءة جلسات الحسابات المساعدة من متغير البيئة
SESSION_STRINGS_RAW = os.environ.get("SESSION_STRING", "")
SESSIONS = [s.strip() for s in SESSION_STRINGS_RAW.split(",") if s.strip()]

# 📌 معرفات القنوات والبوتات:
CHANNEL_USERNAME = "arggrw"        # قناة الأغاني
POETRY_CHANNEL = "zfghjjg"         # قناة الشعر
MIX_CHANNEL = "cvbhfdgds"          # قناة المزج
MEMES_CHANNEL = "cbklufswe"        # قناة الميمز
QURAN_CHANNEL = "chfdthhd"         # قناة القرآن
LOG_CHANNEL = "dgyuhfd"            # قناة السجلات
DOWNLOAD_BOT = "@MsosMbot"         # بوت التحميل لأمر يوت

# الذاكرة المؤقتة لمحتوى القنوات وآخر الرسائل
media_cache = {
    "songs": [],
    "poetry": [],
    "mix": [],
    "memes": [],
    "quran": []
}

last_sent = {
    "songs": {},
    "poetry": {},
    "mix": {},
    "memes": {},
    "quran": {}
}

# ----------------- دالة تهيئة وجلب المحتوى -----------------
async def initialize_channels(client):
    channels = {
        "songs": CHANNEL_USERNAME,
        "poetry": POETRY_CHANNEL,
        "mix": MIX_CHANNEL,
        "memes": MEMES_CHANNEL,
        "quran": QURAN_CHANNEL
    }
    
    logging.info("جاري جلب وتخزين محتوى القنوات للبوت...")
    for key, chan in channels.items():
        temp_list = []
        try:
            async for message in client.iter_messages(chan, limit=None):
                if message.text or message.media:
                    temp_list.append(message)
            media_cache[key] = temp_list
            logging.info(f"تم جلب {len(temp_list)} رسالة من القناة: {chan}")
        except Exception as e:
            logging.error(f"خطأ أثناء جلب القناة {chan}: {e}")

# ----------------- دالة الإرسال العشوائي الآمن -----------------
async def send_random_content(event, category, title, client):
    await send_log(event, title, client)
    messages_list = media_cache[category]
    chat_id = event.chat_id

    if not messages_list:
        await event.respond("عذراً، المحتوى غير متوفر حالياً. جاري إعادة المحاولة أو تحديث البيانات قريباً.")
        return

    available = messages_list
    if len(messages_list) > 1 and chat_id in last_sent[category]:
        available = [m for m in messages_list if m.id != last_sent[category][chat_id]]
    
    selected = random.choice(available)
    last_sent[category][chat_id] = selected.id

    try:
        if selected.media:
            await client.send_file(chat_id, selected.media, caption=selected.text or "", parse_mode=None)
        elif selected.text:
            await client.send_message(chat_id, selected.text)
    except Exception as e:
        logging.error(f"فشل إرسال المحتوى ({category}): {e}")

# ----------------- دالة إرسال السجلات -----------------
async def send_log(event, cmd_name, client):
    try:
        sender = await event.get_sender()
        if sender:
            user_name = getattr(sender, 'first_name', 'مستخدم')
            user_username = f"@{sender.username}" if getattr(sender, 'username', None) else "لايوجد"
            user_id = sender.id
            
            log_text = (
                f"📁 **طلب جديد ({cmd_name})** [البوت الرئيسي]\n\n"
                f"👤 الاسم: {user_name}\n"
                f"🆔 الأيدي: `{user_id}`\n"
                f"🔗 المعرف: {user_username}\n"
                f"💬 الرابط: tg://openmessage?user_id={user_id}"
            )
            await client.send_message(LOG_CHANNEL, log_text)
    except Exception as log_err:
        logging.error(f"فشل إرسال السجل: {log_err}")

# ----------------- تشغيل البوت الأساسي والحسابات -----------------
async def main():
    if not API_ID or not API_HASH:
        logging.error("يجب تعيين API_ID و API_HASH في متغيرات البيئة!")
        return

    # تشغيل البوت الرئيسي
    bot = TelegramClient("bot_session", API_ID, API_HASH)
    await bot.start(bot_token=BOT_TOKEN)
    logging.info("[SUCCESS] تم تشغيل البوت الرئيسي بنجاح!")

    # تشغيل الحساب المساعد الأول (إن وجد) لجلب محتوى القنوات والتفاعل مع بوت التحميل
    helper_client = None
    if SESSIONS:
        helper_client = TelegramClient(StringSession(SESSIONS[0]), API_ID, API_HASH)
        await helper_client.start()
        logging.info("[SUCCESS] تم تشغيل الحساب المساعد بنجاح وجاري جلب البيانات...")
        await initialize_channels(helper_client)
    else:
        # إذا لم يوجد حساب مساعد، نستخدم البوت لجلب المحتوى إن كان مشرفاً
        await initialize_channels(bot)

    # ----------------- معالجة الأوامر والرسائل (Slash Commands & Text) -----------------
    @bot.on(events.NewMessage(incoming=True))
    async def bot_handler(event):
        text_raw = event.raw_text.strip()
        text_lower = text_raw.lower()
        chat_id = event.chat_id

        # 1. أمر البداية /start مع أزرار شفافة احترافية
        if text_lower in ["/start", "بدء"]:
            welcome_text = (
                f"اهلاً بك عزيزي في بوت الخدمات المتكاملة والميديا.\n\n"
                f"• يمكنك استخدام الأوامر عبر الأزرار أدناه أو كتابة الأمر مباشرة.\n"
                f"• المطور الأساسي: @{OWNER_USERNAME}"
            )
            buttons = [
                [Button.inline("🎵 أغاني", data="cmd_songs"), Button.inline("📜 شعر", data="cmd_poetry")],
                [Button.inline("🎭 ميمز", data="cmd_memes"), Button.inline("🎧 مزج", data="cmd_mix")],
                [Button.inline("📖 قرآن", data="cmd_quran"), Button.inline("🎮 الألعاب", data="cmd_games")],
                [Button.inline("👨‍💻 المطور", data="dev_info")]
            ]
            await event.respond(welcome_text, buttons=buttons)
            return

        # 2. أمر "غنيلي" أو /song
        if text_lower in ["غنيلي", "/song"]:
            client_to_use = helper_client if helper_client else bot
            await send_random_content(event, "songs", "غنيلي", client_to_use)
            return

        # 3. أمر "اشعرلي" أو "شعر" أو /poetry
        if text_lower in ["اشعرلي", "شعر", "/poetry"]:
            client_to_use = helper_client if helper_client else bot
            await send_random_content(event, "poetry", "شعر", client_to_use)
            return

        # 4. أمر "مزج" أو /mix
        if text_lower in ["مزج", "/mix"]:
            client_to_use = helper_client if helper_client else bot
            await send_random_content(event, "mix", "مزج", client_to_use)
            return

        # 5. أمر "ميمز" أو /memes
        if text_lower in ["ميمز", "/memes"]:
            client_to_use = helper_client if helper_client else bot
            await send_random_content(event, "memes", "ميمز", client_to_use)
            return

        # 6. أمر "قرآن" أو /quran
        if text_lower in ["قرآن", "/quran"]:
            client_to_use = helper_client if helper_client else bot
            await send_random_content(event, "quran", "قرآن", client_to_use)
            return

        # 7. أمر تحميل اليوتيوب (يوت / يوتو / /yt)
        if text_lower.startswith("يوت ") or text_lower.startswith("يوتو ") or text_lower.startswith("/yt "):
            if text_lower.startswith("يوت "):
                query = text_raw[4:].strip()
            elif text_lower.startswith("يوتو "):
                query = text_raw[5:].strip()
            else:
                query = text_raw[4:].strip()

            if not query:
                return

            client_to_use = helper_client if helper_client else bot
            await send_log(event, f"يوتيوب: {query}", client_to_use)
            
            processing_msg = await event.respond("⏳ جاري البحث والتحميل من اليوتيوب...")

            try:
                sent_msg = await client_to_use.send_message(DOWNLOAD_BOT, f"يوت {query}")
                audio_msg = None
                for _ in range(30):
                    messages = await client_to_use.get_messages(DOWNLOAD_BOT, limit=6)
                    for msg in messages:
                        if msg.id > sent_msg.id and (msg.audio or msg.voice or (msg.document and msg.file and msg.file.mime_type and 'audio' in msg.file.mime_type)):
                            audio_msg = msg
                            break
                    if audio_msg: break
                    await asyncio.sleep(0.3)

                await processing_msg.delete()

                if not audio_msg:
                    await event.respond("❌ عذراً، لم أتمكن من العثور على الملف الصوتي أو أن بوت التحميل بطيء الاستجابة.")
                    return

                await bot.send_file(chat_id, audio_msg.media, caption="", parse_mode=None)
            except Exception as e:
                logging.error(f"خطأ أثناء جلب الأغنية من البوت الخارجي: {e}")
                await processing_msg.edit("❌ حدث خطأ أثناء إتمام عملية التحميل.")
            return

        # 8. قسم الألعاب التفاعلية (ألعاب سلاش / نصية ممتعة)
        if text_lower in ["/games", "العاب", "ألعاب"]:
            games_text = "🎮 قسم الألعاب التفاعلية:\n\nاختر اللعبة التي تريد لعبها من الأزرار أدناه:"
            game_buttons = [
                [Button.inline("❌ حجر صبر ورقة (إكس او)", data="game_tictactoe")],
                [Button.inline("🎯 حظ الرمية", data="game_dice"), Button.inline("🏀 سلة", data="game_basket")],
                [Button.inline("🔙 رجوع للقائمة", data="back_home")]
            ]
            await event.respond(games_text, buttons=game_buttons)
            return

        # 9. أمر التحديث الفوري للقنوات (خاص بالمطور)
        if text_raw == "تحديث" and event.sender_id == OWNER_ID:
            status_msg = await event.respond("🔄 جاري تحديث محتوى القنوات...")
            client_to_use = helper_client if helper_client else bot
            await initialize_channels(client_to_use)
            await status_msg.edit("✅ تمت إعادة تحديث جميع القنوات بنجاح!")
            return

    # ----------------- معالجة ضغط الأزرار الشفافة (Inline Callbacks) -----------------
    @bot.on(events.CallbackQuery)
    async def callback_handler(event):
        data = event.data.decode("utf-8")
        client_to_use = helper_client if helper_client else bot

        if data == "cmd_songs":
            await event.answer("جاري جلب الأغاني...", alert=False)
            await send_random_content(event, "songs", "غنيلي (زر)", client_to_use)

        elif data == "cmd_poetry":
            await event.answer("جاري جلب الأبيات الشعرية...", alert=False)
            await send_random_content(event, "poetry", "شعر (زر)", client_to_use)

        elif data == "cmd_memes":
            await event.answer("جاري جلب الميمز...", alert=False)
            await send_random_content(event, "memes", "ميمز (زر)", client_to_use)

        elif data == "cmd_mix":
            await event.answer("جاري جلب مقاطع المزج...", alert=False)
            await send_random_content(event, "mix", "مزج (زر)", client_to_use)

        elif data == "cmd_quran":
            await event.answer("جاري جلب التلاوة القرأنية...", alert=False)
            await send_random_content(event, "quran", "قرآن (زر)", client_to_use)

        elif data == "cmd_games":
            game_buttons = [
                [Button.inline("🎯 رمي النرد", data="game_dice"), Button.inline("🏀 رمي السلة", data="game_basket")],
                [Button.inline("🔙 رجوع", data="back_home")]
            ]
            await event.edit("🎮 قسم الألعاب:\nاختر لعبة الحظ السريعة:", buttons=game_buttons)

        elif data == "game_dice":
            await event.answer()
            await bot.send_dice(event.chat_id, emoji="🎲")

        elif data == "game_basket":
            await event.answer()
            await bot.send_dice(event.chat_id, emoji="🏀")

        elif data == "dev_info":
            await event.answer(f"المطور: @{OWNER_USERNAME}", alert=True)

        elif data == "back_home":
            welcome_text = (
                f"اهلاً بك عزيزي في بوت الخدمات المتكاملة والميديا.\n\n"
                f"• يمكنك استخدام الأوامر عبر الأزرار أدناه أو كتابة الأمر مباشرة.\n"
                f"• المطور الأساسي: @{OWNER_USERNAME}"
            )
            buttons = [
                [Button.inline("🎵 أغاني", data="cmd_songs"), Button.inline("📜 شعر", data="cmd_poetry")],
                [Button.inline("🎭 ميمز", data="cmd_memes"), Button.inline("🎧 مزج", data="cmd_mix")],
                [Button.inline("📖 قرآن", data="cmd_quran"), Button.inline("🎮 الألعاب", data="cmd_games")],
                [Button.inline("👨‍💻 المطور", data="dev_info")]
            ]
            await event.edit(welcome_text, buttons=buttons)

    # الحفاظ على تشغيل البوت والحساب المساعد بلا توقف
    tasks = [bot.run_until_disconnected()]
    if helper_client:
        tasks.append(helper_client.run_until_disconnected())
    
    await asyncio.gather(*tasks)

if __name__ == "__main__":
    asyncio.run(main())
