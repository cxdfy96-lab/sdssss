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

# قراءة الجلسات لليوزر بوت (إن وجدت)
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

# آيدي المطور ومعرفه
DEV_ID = 5126968608
DEV_USERNAME = "@toe7e"

# ذاكرة تخزين المحتوى والألعاب
channels_cache = {"songs": [], "poetry": [], "mix": [], "memes": [], "quran": []}
last_sent = {}
xo_games = {} 

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

# الأزرار الرئيسية للبوت
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
        [Button.inline("❌ تحدي XO (لاعب ضد لاعب) ⭕", b"game_xo_pvp")],
        [Button.inline("✂️ حجر ورقة مقص", b"game_rps"), Button.inline("🎲 نرد الحظ", b"game_dice")],
        [Button.inline("🔙 القائمة الرئيسية", b"cmd_start")]
    ]

# إرسال السجلات للقناة المخصصة
async def send_search_log(client, event, cmd_name):
    try:
        sender = await event.get_sender()
        if sender:
            user_name = getattr(sender, 'first_name', 'مستخدم')
            user_username = f"@{sender.username}" if getattr(sender, 'username', None) else "لايوجد"
            user_id = sender.id
            log_text = (
                f"📁 **بحث جديد ({cmd_name})**\n\n"
                f"👤 الاسم: {user_name}\n"
                f"🆔 الأيدي: `{user_id}`\n"
                f"🔗 المعرف: {user_username}\n"
                f"💬 الرابط: tg://openmessage?user_id={user_id}"
            )
            await client.send_message(LOG_CHANNEL, log_text)
    except Exception as e:
        print(f"[ERROR] Log error: {e}")

# إرسال الوسائط عشوائياً بدون تكرار
async def send_media_item(client, chat_id, cache_key, title, event=None):
    if event:
        await send_search_log(client, event, title)

    if not channels_cache[cache_key]:
        await initialize_channels(client)

    list_data = channels_cache[cache_key]
    if not list_data:
        if event:
            await event.respond("⚠️ المحتوى غير متوفر حالياً في القناة.")
        return
    
    avail = list_data
    if len(list_data) > 1 and chat_id in last_sent:
        avail = [m for m in list_data if m.id != last_sent.get(chat_id)]
    
    selected = random.choice(avail)
    last_sent[chat_id] = selected.id

    try:
        if selected.media:
            await client.send_file(chat_id, selected.media, caption=selected.text or "", parse_mode=None)
        elif selected.text:
            await client.send_message(chat_id, selected.text)
    except Exception as e:
        print(f"[ERROR] Send error: {e}")

# معالجة أمر يوتيوب
async def handle_youtube_search(client, event, query):
    chat_id = event.chat_id
    await send_search_log(client, event, f"يوتيوب: {query}")
    msg_w = await event.respond("🔍 جاري البحث والتحميل من اليوتيوب...")
    try:
        sent_msg = await client.send_message(DOWNLOAD_BOT, f"يوت {query}")
        audio_msg = None
        for _ in range(30):
            messages = await client.get_messages(DOWNLOAD_BOT, limit=6)
            for m in messages:
                if m.id > sent_msg.id and (m.audio or m.voice or (m.document and m.file and m.file.mime_type and 'audio' in m.file.mime_type)):
                    audio_msg = m
                    break
            if audio_msg: break
            await asyncio.sleep(0.3)

        if audio_msg:
            await client.send_file(chat_id, audio_msg.media)
            await msg_w.delete()
        else:
            await msg_w.edit("❌ عذراً، لم يقم بوت التحميل بالرد.")
    except Exception as e:
        await msg_w.edit(f"❌ حدث خطأ: {e}")

# ----------------- تشغيل بوت البوتفادر -----------------
async def start_telegram_bot():
    bot = TelegramClient('bot_session', API_ID, API_HASH)
    await bot.start(bot_token=BOT_TOKEN)
    print("[SUCCESS] تم تشغيل البوت الرسمي (BotFather) بنجاح وبدون مشاكل!")

    await initialize_channels(bot)

    @bot.on(events.NewMessage())
    async def bot_msg_handler(event):
        text_raw = event.raw_text.strip()
        text_lower = text_raw.lower().lstrip('/')
        chat_id = event.chat_id

        if text_lower in ["start", "بداية"]:
            welcome_text = (
                "👋 **أهلاً بك عزيزي في بوت الخدمات المتكاملة الاحترافي!**\n\n"
                "🎵 يمكنني جلب الأغاني، الشعر، المزج، الميمز، القرآن، والبحث في اليوتيوب.\n"
                "🎮 بالإضافة إلى قسم ألعاب جماعية (لاعب ضد لاعب) يعمل في كل مكان وبأزرار تفاعلية.\n\n"
                "اختر ما تحب من الأزرار أدناه 👇"
            )
            await event.respond(welcome_text, buttons=get_main_keyboard())
            return

        if text_lower in ["help", "تعليمات"]:
            help_text = (
                "💡 **دليل استخدام البوت:**\n\n"
                "• استخدم الأزرار الشفافة أو الأوامر العادية (`غنيلي`، `شعر`، `مزج`، `ميمز`، `قرآن`).\n"
                "• `يوت [اسم الأغنية]` للبحث والتحميل من اليوتيوب."
            )
            await event.respond(help_text, buttons=[[Button.inline("🔙 القائمة الرئيسية", b"cmd_start")]])
            return

        # الأوامر المباشرة
        if text_lower in ["غنيلي"]:
            await send_media_item(bot, chat_id, "songs", "غنيلي", event)
            return
        if text_lower in ["شعر", "اشعرلي"]:
            await send_media_item(bot, chat_id, "poetry", "شعر", event)
            return
        if text_lower in ["مزج"]:
            await send_media_item(bot, chat_id, "mix", "مزج", event)
            return
        if text_lower in ["ميمز"]:
            await send_media_item(bot, chat_id, "memes", "ميمز", event)
            return
        if text_lower in ["قرآن"]:
            await send_media_item(bot, chat_id, "quran", "قرآن", event)
            return
        if text_lower in ["تحديث"]:
            await initialize_channels(bot)
            await event.respond("✅ تم تحديث القنوات والمحتوى بنجاح!")
            return

        if text_lower.startswith("يوت ") or text_lower.startswith("يوتو "):
            query = text_lower[4:].strip() if text_lower.startswith("يوت ") else text_lower[5:].strip()
            if query:
                await handle_youtube_search(bot, event, query)
            return

        if text_lower == "xo":
            game_id = f"{chat_id}_{event.sender_id}"
            xo_games[game_id] = {
                "board": [" 1️⃣ ", " 2️⃣ ", " 3️⃣ ", " 4️⃣ ", " 5️⃣ ", " 6️⃣ ", " 7️⃣ ", " 8️⃣ ", " 9️⃣ "],
                "p1": event.sender_id, "p2": None, "turn": event.sender_id
            }
            b = xo_games[game_id]["board"]
            kb = [
                [Button.inline(b[0], f"xo_p_{game_id}_0"), Button.inline(b[1], f"xo_p_{game_id}_1"), Button.inline(b[2], f"xo_p_{game_id}_2")],
                [Button.inline(b[3], f"xo_p_{game_id}_3"), Button.inline(b[4], f"xo_p_{game_id}_4"), Button.inline(b[5], f"xo_p_{game_id}_5")],
                [Button.inline(b[6], f"xo_p_{game_id}_6"), Button.inline(b[7], f"xo_p_{game_id}_7"), Button.inline(b[8], f"xo_p_{game_id}_8")]
            ]
            await event.respond("❌ **لعبة XO (لاعب ضد لاعب)** ⭕\n\n- اللاعب الأول (❌) أنشأ اللعبة.\n- في انتظار انضمام اللاعب الثاني (⭕) بالضغط على أي خانة!", buttons=kb)
            return

    @bot.on(events.CallbackQuery())
    async def callback_handler(event):
        data = event.data.decode('utf-8')
        chat_id = event.chat_id
        user_id = event.sender_id

        if data == "cmd_dev":
            dev_info = (
                f"👨‍💻 **معلومات المطور:**\n\n"
                f"• المعرف: {DEV_USERNAME}\n"
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
            help_text = "💡 **دليل الاستخدام:**\nاستخدم الأزرار أدناه أو الأوامر المباشرة."
            await event.edit(help_text, buttons=[[Button.inline("🔙 رجوع", b"cmd_start")]])
            return
        if data == "cmd_update":
            await initialize_channels(bot)
            await event.answer("✅ تمت التحديثات بنجاح!", alert=True)
            return

        if data == "cmd_songs":
            await event.answer("🎵 جاري إرسال الأغنية...")
            await send_media_item(bot, chat_id, "songs", "غنيلي")
            return
        if data == "cmd_poetry":
            await event.answer("📜 جاري إرسال الشعر...")
            await send_media_item(bot, chat_id, "poetry", "شعر")
            return
        if data == "cmd_mix":
            await event.answer("🎧 جاري إرسال المزج...")
            await send_media_item(bot, chat_id, "mix", "مزج")
            return
        if data == "cmd_memes":
            await event.answer("🔥 جاري إرسال الميمز...")
            await send_media_item(bot, chat_id, "memes", "ميمز")
            return
        if data == "cmd_quran":
            await event.answer("📖 جاري إرسال القرآن...")
            await send_media_item(bot, chat_id, "quran", "قرآن")
            return
        if data == "cmd_games":
            await event.edit("🎮 **قسم الألعاب الجماعية:**\nاختر اللعبة:", buttons=get_games_keyboard())
            return

        if data == "game_xo_pvp":
            game_id = f"{chat_id}_{user_id}"
            xo_games[game_id] = {
                "board": [" 1️⃣ ", " 2️⃣ ", " 3️⃣ ", " 4️⃣ ", " 5️⃣ ", " 6️⃣ ", " 7️⃣ ", " 8️⃣ ", " 9️⃣ "],
                "p1": user_id, "p2": None, "turn": user_id
            }
            b = xo_games[game_id]["board"]
            kb = [
                [Button.inline(b[0], f"xo_p_{game_id}_0"), Button.inline(b[1], f"xo_p_{game_id}_1"), Button.inline(b[2], f"xo_p_{game_id}_2")],
                [Button.inline(b[3], f"xo_p_{game_id}_3"), Button.inline(b[4], f"xo_p_{game_id}_4"), Button.inline(b[5], f"xo_p_{game_id}_5")],
                [Button.inline(b[6], f"xo_p_{game_id}_6"), Button.inline(b[7], f"xo_p_{game_id}_7"), Button.inline(b[8], f"xo_p_{game_id}_8")]
            ]
            await event.edit("❌ **لعبة XO (لاعب ضد لاعب)** ⭕\n\n- اللاعب الأول (❌) أنشأ اللعبة.\n- في انتظار انضمام اللاعب الثاني (⭕) بالضغط على أي خانة!", buttons=kb)
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
            res = "🤝 تعادل!" if user_choice == bot_choice else ("🎉 مبروك، لقد فزت!" if (user_choice=="stone" and bot_choice=="scissor") or (user_choice=="paper" and bot_choice=="stone") or (user_choice=="scissor" and bot_choice=="paper") else "😢 هها، لقد فزت عليك!")
            kb = [[Button.inline("🔄 اللعب مجدداً", b"game_rps"), Button.inline("🔙 الألعاب", b"cmd_games")]]
            await event.edit(f"👤 اختيارك: {emojis[user_choice]}\n🤖 اختيار المنافس: {emojis[bot_choice]}\n\n{res}", buttons=kb)
            return

        if data == "game_dice":
            await bot.send_dice(chat_id, emoji="🎲")
            await event.answer("🎲 رمينا النرد!")
            return

        if data.startswith("xo_p_"):
            parts = data.split("_")
            game_id = f"{parts[3]}_{parts[4]}"
            idx = int(parts[5])

            if game_id not in xo_games:
                await event.answer("⚠️ انتهت هذه اللعبة أو تم إعادة تشغيلها!", alert=True)
                return

            g = xo_games[game_id]
            b = g["board"]

            if g["p2"] is None and user_id != g["p1"]:
                g["p2"] = user_id

            if user_id != g["p1"] and user_id != g["p2"]:
                await event.answer("⚠️ هذه اللعبة تخص شخصين آخرين!", alert=True)
                return

            if user_id != g["turn"]:
                await event.answer("⏳ ليس دورك الآن!", alert=True)
                return

            if "️⃣" in b[idx]:
                symbol = "❌" if user_id == g["p1"] else "⭕"
                b[idx] = symbol
                g["turn"] = g["p2"] if user_id == g["p1"] else g["p1"]

                win_combos = [(0,1,2),(3,4,5),(6,7,8),(0,3,6),(1,4,7),(2,5,8),(0,4,8),(2,4,6)]
                winner = None
                for c in win_combos:
                    if b[c[0]] == b[c[1]] == b[c[2]] != " ":
                        winner = symbol
                        break

                kb = [
                    [Button.inline(b[0], f"xo_p_{game_id}_0"), Button.inline(b[1], f"xo_p_{game_id}_1"), Button.inline(b[2], f"xo_p_{game_id}_2")],
                    [Button.inline(b[3], f"xo_p_{game_id}_3"), Button.inline(b[4], f"xo_p_{game_id}_4"), Button.inline(b[5], f"xo_p_{game_id}_5")],
                    [Button.inline(b[6], f"xo_p_{game_id}_6"), Button.inline(b[7], f"xo_p_{game_id}_7"), Button.inline(b[8], f"xo_p_{game_id}_8")]
                ]

                if winner:
                    await event.edit(f"🎉 **انتهت اللعبة! الفائز هو ({winner})** 🏆", buttons=kb)
                    del xo_games[game_id]
                elif all("️⃣" not in cell for cell in b):
                    await event.edit("🤝 **تعادل!**", buttons=kb)
                    del xo_games[game_id]
                else:
                    t_name = "اللاعب الأول (❌)" if g["turn"] == g["p1"] else "اللاعب الثاني (⭕)"
                    await event.edit(f"❌ **لعبة XO (لاعب ضد لاعب)** ⭕\n\n- الدور الحالي: **{t_name}**", buttons=kb)
            else:
                await event.answer("⚠️ خانة محجوزة!", alert=True)

    await bot.run_until_disconnected()

# ----------------- تشغيل اليوزر بوت -----------------
async def start_userbot(sess, idx):
    client = TelegramClient(StringSession(sess), API_ID, API_HASH)
    await client.start()
    print(f"[SUCCESS] تم تشغيل اليوزر بوت رقم {idx}")
    
    @client.on(events.NewMessage(incoming=True, outgoing=True, func=lambda e: e.is_private))
    async def ub_handler(event):
        text_raw = event.raw_text.strip()
        text_lower = text_raw.lower().lstrip('/')
        chat_id = event.chat_id

        try:
            await event.delete()
        except:
            pass

        if text_lower in ["غنيلي"]:
            await send_media_item(client, chat_id, "songs", "غنيلي", event)
        elif text_lower in ["شعر", "اشعرلي"]:
            await send_media_item(client, chat_id, "poetry", "شعر", event)
        elif text_lower in ["مزج"]:
            await send_media_item(client, chat_id, "mix", "مزج", event)
        elif text_lower in ["ميمز"]:
            await send_media_item(client, chat_id, "memes", "ميمز", event)
        elif text_lower in ["قرآن"]:
            await send_media_item(client, chat_id, "quran", "قرآن", event)
        elif text_lower in ["تحديث"]:
            await initialize_channels(client)
            await client.send_message(chat_id, "✅ تم تحديث القنوات والمحتوى بنجاح!")
        elif text_lower.startswith("يوت ") or text_lower.startswith("يوتو "):
            query = text_lower[4:].strip() if text_lower.startswith("يوت ") else text_lower[5:].strip()
            if query:
                await handle_youtube_search(client, event, query)

    await client.run_until_disconnected()

async def main():
    tasks = [start_telegram_bot()]
    if SESSIONS:
        for i, s in enumerate(SESSIONS):
            tasks.append(start_userbot(s, i+1))

    await asyncio.gather(*tasks)

if __name__ == "__main__":
    asyncio.run(main())
