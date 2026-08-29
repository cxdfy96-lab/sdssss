import os
import random
import asyncio
from telethon import TelegramClient, events, Button
from telethon.sessions import StringSession

# بيانات الاتصال الأساسية
API_ID = int(os.environ.get("API_ID", 0))
API_HASH = os.environ.get("API_HASH", "")

# توكن البوت المباشر
BOT_TOKEN = "8730782028:AAGaJlb44r7UE--4lmth7KnoGz1oDGbu_X8"

# قراءة الجلسات (إن وجدت) لليوزر بوت
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

# آيدي المطور
DEV_ID = 5126968608

# قواميس محتوى القنوات والألعاب
channels_cache = {"songs": [], "poetry": [], "mix": [], "memes": [], "quran": []}
last_sent = {}
xo_boards = {} # تتبع ألعاب XO

async def initialize_channels(client):
    global channels_cache
    print(f"[INFO] جاري جلب وتخزين محتوى القنوات...")
    mapping = {
        CHANNEL_USERNAME: "songs",
        POETRY_CHANNEL: "poetry",
        MIX_CHANNEL: "mix",
        MEMES_CHANNEL: "memes",
        QURAN_CHANNEL: "quran"
    }
    for chan, key in mapping.items():
        temp = []
        try:
            async for message in client.iter_messages(chan, limit=None):
                if message.text or message.media:
                    temp.append(message)
            channels_cache[key] = temp
            print(f"[INFO] تم جلب {len(temp)} رسالة من: {chan}")
        except Exception as e:
            print(f"[ERROR] خطأ في جلب {chan}: {e}")

# تصميم لوحة الأزرار الرئيسية للبوت (مع زر المطور الشفاف ضمن الأزرار)
def get_main_keyboard():
    return [
        [Button.inline("🎵 أغاني", b"cmd_songs"), Button.inline("📜 شعر", b"cmd_poetry")],
        [Button.inline("🎧 مزج", b"cmd_mix"), Button.inline("🔥 ميمز", b"cmd_memes")],
        [Button.inline("📖 قرآن", b"cmd_quran"), Button.inline("🎮 قسم الألعاب", b"cmd_games")],
        [Button.inline("💡 طريقة الاستخدام", b"cmd_help"), Button.inline("🔄 تحديث المحتوى", b"cmd_update")],
        [Button.inline("👨‍💻 المطور", b"cmd_dev"), Button.url("📢 قناة المطور", "https://t.me/toe7e")]
    ]

def get_games_keyboard():
    return [
        [Button.inline("❌ لعبة XO ⭕", b"game_xo"), Button.inline("✂️ حجر ورقة مقص", b"game_rps")],
        [Button.inline("🎲 نرد الحظ", b"game_dice"), Button.inline("🎯 رمي السهم", b"game_dart")],
        [Button.inline("🔙 القائمة الرئيسية", b"cmd_start")]
    ]

async def start_telegram_bot():
    bot = TelegramClient('bot_session', API_ID, API_HASH)
    await bot.start(bot_token=BOT_TOKEN)
    print("[SUCCESS] تم تشغيل البوت الاحترافي بنجاح مع الألعاب والأزرار الشفافة!")

    await initialize_channels(bot)

    # معالجة الأوامر والرسائل
    @bot.on(events.NewMessage())
    async def handler(event):
        text = event.raw_text.strip()
        text_lower = text.lower().lstrip('/')
        chat_id = event.chat_id

        # أمر البداية /start
        if text_lower in ["start", "بداية"]:
            welcome_text = (
                "👋 **أهلاً بك عزيزي في بوت الخدمات المتكاملة الاحترافي!**\n\n"
                "🎵 يمكنني جلب الأغاني، الشعر، المزج، الميمز، القرآن، والبحث في اليوتيوب.\n"
                "🎮 بالإضافة إلى قسم ألعاب ممتع يعمل في كل مكان وبأزرار تفاعلية.\n\n"
                "اختر ما تحب من الأزرار أدناه 👇"
            )
            await event.respond(welcome_text, buttons=get_main_keyboard())
            return

        # تعليمات الاستخدام
        if text_lower in ["help", "تعليمات", "التعليمات"]:
            help_text = (
                "💡 **دليل استخدام البوت:**\n\n"
                "1️⃣ **الأوامر العادية وبالسلاش (/):**\n"
                "• `غنيلي` أو `/غنيلي` : لجلب أغنية عشوائية.\n"
                "• `شعر` أو `/شعر` : لجلب قصيدة أو بصمة شعرية.\n"
                "• `مزج` أو `/مزج` : لجلب مقطع مزج.\n"
                "• `ميمز` أو `/ميمز` : لجلب ميمز مضحك.\n"
                "• `قرآن` أو `/قرآن` : لجلب آيات وتلاوات قرآنية.\n"
                "• `يوت [اسم الأغنية]` : للبحث والتحميل من اليوتيوب.\n"
                "• `تحديث` : لتحديث محتوى القنوات فوراً.\n\n"
                "2️⃣ **الألعاب:**\n"
                "• اكتب `xo` أو اذهب لقسم الألعاب للعب مع البوت.\n"
                "• ألعاب حجر ورقة مقص والنرد السريع."
            )
            await event.respond(help_text, buttons=[[Button.inline("🔙 القائمة الرئيسية", b"cmd_start")]])
            return

        # دالة الإرسال للمحتوى
        async def send_media_from_cache(cache_key, title):
            list_data = channels_cache[cache_key]
            if not list_data:
                await event.respond("⚠️ المحتوى غير متوفر حالياً، جاري محاولة التحديث...")
                return
            
            avail = list_data
            if len(list_data) > 1 and chat_id in last_sent:
                avail = [m for m in list_data if m.id != last_sent.get(chat_id)]
            
            selected = random.choice(avail)
            last_sent[chat_id] = selected.id

            try:
                if selected.media:
                    await bot.send_file(chat_id, selected.media, caption=selected.text or "", parse_mode=None)
                elif selected.text:
                    await bot.send_message(chat_id, selected.text)
            except Exception as e:
                print(f"[ERROR] خطأ بالإرسال: {e}")

        if text_lower in ["غنيلي"]:
            await send_media_from_cache("songs", "غنيلي")
            return
        if text_lower in ["شعر", "اشعرلي"]:
            await send_media_from_cache("poetry", "شعر")
            return
        if text_lower in ["مزج"]:
            await send_media_from_cache("mix", "مزج")
            return
        if text_lower in ["ميمز"]:
            await send_media_from_cache("memes", "ميمز")
            return
        if text_lower in ["قرآن"]:
            await send_media_from_cache("quran", "قرآن")
            return
        if text_lower in ["تحديث"]:
            await initialize_channels(bot)
            await event.respond("✅ تم تحديث القنوات والمحتوى بنجاح!")
            return

        # أمر يوتيوب
        if text_lower.startswith("يوت ") or text_lower.startswith("يوتو "):
            query = text_lower[4:].strip() if text_lower.startswith("يوت ") else text_lower[5:].strip()
            if not query: return
            
            msg_w = await event.respond("🔍 جاري البحث والتحميل من اليوتيوب...")
            try:
                sent_msg = await bot.send_message(DOWNLOAD_BOT, f"يوت {query}")
                audio_msg = None
                for _ in range(30):
                    messages = await bot.get_messages(DOWNLOAD_BOT, limit=6)
                    for m in messages:
                        if m.id > sent_msg.id and (m.audio or m.voice or (m.document and m.file and m.file.mime_type and 'audio' in m.file.mime_type)):
                            audio_msg = m
                            break
                    if audio_msg: break
                    await asyncio.sleep(0.3)

                if audio_msg:
                    await bot.send_file(chat_id, audio_msg.media)
                    await msg_w.delete()
                else:
                    await msg_w.edit("❌ عذراً، لم يقم بوت التحميل بالرد.")
            except Exception as e:
                await msg_w.edit(f"❌ حدث خطأ: {e}")
            return

        # لعبة XO السريعة بالكتابة
        if text_lower == "xo":
            xo_boards[chat_id] = [" 1️⃣ ", " 2️⃣ ", " 3️⃣ ", " 4️⃣ ", " 5️⃣ ", " 6️⃣ ", " 7️⃣ ", " 8️⃣ ", " 9️⃣ "]
            b = xo_boards[chat_id]
            kb = [
                [Button.inline(b[0], b"xo_0"), Button.inline(b[1], b"xo_1"), Button.inline(b[2], b"xo_2")],
                [Button.inline(b[3], b"xo_3"), Button.inline(b[4], b"xo_4"), Button.inline(b[5], b"xo_5")],
                [Button.inline(b[6], b"xo_6"), Button.inline(b[7], b"xo_7"), Button.inline(b[8], b"xo_8")]
            ]
            await event.respond("❌ **لعبة XO** ⭕\nدور اللاعب (❌): اختر خانة:", buttons=kb)
            return

    # معالجة الأزرار التفاعلية
    @bot.on(events.CallbackQuery())
    async def callback_handler(event):
        data = event.data.decode('utf-8')
        chat_id = event.chat_id

        if data == "cmd_dev":
            dev_info = (
                f"👨‍💻 **معلومات المطور:**\n\n"
                f"• المعرف: @toe7e\n"
                f"• الآيدي: `{DEV_ID}`\n\n"
                f"أهلاً بك، يمكنك التواصل مع المطور لأي استفسار أو طلب برمجي."
            )
            await event.answer("👨‍💻 معلومات المطور", alert=False)
            await event.edit(dev_info, buttons=[[Button.inline("🔙 القائمة الرئيسية", b"cmd_start")]])
            return

        if data == "cmd_start":
            await event.edit("📌 القائمة الرئيسية للبوت:", buttons=get_main_keyboard())
            return
        if data == "cmd_help":
            help_text = "💡 **دليل الاستخدام:**\nاستخدم الأزرار أدناه أو اكتب الأوامر (غنيلي، شعر، مزج، ميمز، قرآن، يوت)."
            await event.edit(help_text, buttons=[[Button.inline("🔙 رجوع", b"cmd_start")]])
            return
        if data == "cmd_update":
            await initialize_channels(bot)
            await event.answer("✅ تمت التحديثات بنجاح!", alert=True)
            return
        if data == "cmd_songs":
            await event.answer("🎵 جاري إرسال الأغنية...")
            list_data = channels_cache["songs"]
            if list_data:
                sel = random.choice(list_data)
                await bot.send_file(chat_id, sel.media, caption=sel.text or "", parse_mode=None)
            return
        if data == "cmd_poetry":
            await event.answer("📜 جاري إرسال الشعر...")
            list_data = channels_cache["poetry"]
            if list_data:
                sel = random.choice(list_data)
                if sel.media: await bot.send_file(chat_id, sel.media, caption=sel.text or "", parse_mode=None)
                else: await bot.send_message(chat_id, sel.text)
            return
        if data == "cmd_mix":
            await event.answer("🎧 جاري إرسال المزج...")
            list_data = channels_cache["mix"]
            if list_data:
                sel = random.choice(list_data)
                if sel.media: await bot.send_file(chat_id, sel.media, caption=sel.text or "", parse_mode=None)
                else: await bot.send_message(chat_id, sel.text)
            return
        if data == "cmd_memes":
            await event.answer("🔥 جاري إرسال الميمز...")
            list_data = channels_cache["memes"]
            if list_data:
                sel = random.choice(list_data)
                if sel.media: await bot.send_file(chat_id, sel.media, caption=sel.text or "", parse_mode=None)
                else: await bot.send_message(chat_id, sel.text)
            return
        if data == "cmd_quran":
            await event.answer("📖 جاري إرسال القرآن...")
            list_data = channels_cache["quran"]
            if list_data:
                sel = random.choice(list_data)
                if sel.media: await bot.send_file(chat_id, sel.media, caption=sel.text or "", parse_mode=None)
                else: await bot.send_message(chat_id, sel.text)
            return
        if data == "cmd_games":
            await event.edit("🎮 **قسم الألعاب الترفيهية:**\nاختر اللعبة التي تريدها:", buttons=get_games_keyboard())
            return

        # لوحة الألعاب
        if data == "game_xo":
            xo_boards[chat_id] = [" 1️⃣ ", " 2️⃣ ", " 3️⃣ ", " 4️⃣ ", " 5️⃣ ", " 6️⃣ ", " 7️⃣ ", " 8️⃣ ", " 9️⃣ "]
            b = xo_boards[chat_id]
            kb = [
                [Button.inline(b[0], b"xo_0"), Button.inline(b[1], b"xo_1"), Button.inline(b[2], b"xo_2")],
                [Button.inline(b[3], b"xo_3"), Button.inline(b[4], b"xo_4"), Button.inline(b[5], b"xo_5")],
                [Button.inline(b[6], b"xo_6"), Button.inline(b[7], b"xo_7"), Button.inline(b[8], b"xo_8")]
            ]
            await event.edit("❌ **لعبة XO** ⭕\nدور اللاعب (❌): اختر خانة:", buttons=kb)
            return

        if data == "game_rps":
            kb = [
                [Button.inline("🪨 حجر", b"rps_stone"), Button.inline("📄 ورقة", b"rps_paper"), Button.inline("✂️ مقص", b"rps_scissor")],
                [Button.inline("🔙 رجوع للألعاب", b"cmd_games")]
            ]
            await event.edit("✂️ **حجر ورقة مقص**\nاختر سلاحك:", buttons=kb)
            return

        if data.startswith("rps_"):
            user_choice = data.split("_")[1]
            bot_choice = random.choice(["stone", "paper", "scissor"])
            emojis = {"stone": "🪨 حجر", "paper": "📄 ورقة", "scissor": "✂️ مقص"}
            
            if user_choice == bot_choice:
                res = "🤝 تعادل!"
            elif (user_choice == "stone" and bot_choice == "scissor") or \
                 (user_choice == "paper" and bot_choice == "stone") or \
                 (user_choice == "scissor" and bot_choice == "paper"):
                res = "🎉 مبروك، لقد فزت!"
            else:
                res = "😢 هها، لقد فزت عليك!"
            
            text_res = f"👤 اختيارك: {emojis[user_choice]}\n🤖 اختيار البوت: {emojis[bot_choice]}\n\n{res}"
            kb = [[Button.inline("🔄 اللعب مجدداً", b"game_rps"), Button.inline("🔙 الألعاب", b"cmd_games")]]
            await event.edit(text_res, buttons=kb)
            return

        if data == "game_dice":
            await bot.send_dice(chat_id, emoji="🎲")
            await event.answer("🎲 رمينا النرد لك!")
            return
        if data == "game_dart":
            await bot.send_dice(chat_id, emoji="🎯")
            await event.answer("🎯 رمينا السهم لك!")
            return

        # تفاعل أزرار XO
        if data.startswith("xo_"):
            idx = int(data.split("_")[1])
            if chat_id not in xo_boards:
                xo_boards[chat_id] = [" 1️⃣ ", " 2️⃣ ", " 3️⃣ ", " 4️⃣ ", " 5️⃣ ", " 6️⃣ ", " 7️⃣ ", " 8️⃣ ", " 9️⃣ "]
            
            b = xo_boards[chat_id]
            if "️⃣" in b[idx]:
                b[idx] = "❌"
                empty_spots = [i for i, x in enumerate(b) if "️⃣" in x]
                if empty_spots:
                    bot_spot = random.choice(empty_spots)
                    b[bot_spot] = "⭕"
                
                kb = [
                    [Button.inline(b[0], b"xo_0"), Button.inline(b[1], b"xo_1"), Button.inline(b[2], b"xo_2")],
                    [Button.inline(b[3], b"xo_3"), Button.inline(b[4], b"xo_4"), Button.inline(b[5], b"xo_5")],
                    [Button.inline(b[6], b"xo_6"), Button.inline(b[7], b"xo_7"), Button.inline(b[8], b"xo_8")]
                ]
                await event.edit("❌ **لعبة XO** ⭕", buttons=kb)
            else:
                await event.answer("⚠️ هذه الخانة محجوزة مسبقاً!", alert=True)

    await bot.run_until_disconnected()

async def main():
    tasks = [start_telegram_bot()]
    if SESSIONS:
        async def start_userbot(sess, idx):
            client = TelegramClient(StringSession(sess), API_ID, API_HASH)
            await client.start()
            print(f"[SUCCESS] تم تشغيل اليوزر بوت رقم {idx}")
            @client.on(events.NewMessage(incoming=True, outgoing=True, func=lambda e: e.is_private))
            async def ub_handler(event):
                pass
            await client.run_until_disconnected()

        for i, s in enumerate(SESSIONS):
            tasks.append(start_userbot(s, i+1))

    await asyncio.gather(*tasks)

if __name__ == "__main__":
    asyncio.run(main())
