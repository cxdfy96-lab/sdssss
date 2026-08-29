import os
import random
import asyncio
from telethon import TelegramClient, events, Button

# بيانات الاتصال الأساسية
API_ID = int(os.environ.get("API_ID", 0))
API_HASH = os.environ.get("API_HASH", "")
BOT_TOKEN = "8730782028:AAGaJlb44r7UE--4lmth7KnoGz1oDGbu_X8"

DEV_ID = 5126968608
DEV_USERNAME = "@toe7e"

# 📌 معرفات القنوات والبوتات مباشرة داخل الكود:
CHANNEL_USERNAME = "arggrw"        # قناة الأغاني
POETRY_CHANNEL = "zfghjjg"         # قناة الشعر
MIX_CHANNEL = "cvbhfdgds"          # قناة المزج
MEMES_CHANNEL = "cbklufswe"        # قناة الميمز
QURAN_CHANNEL = "chfdthhd"         # قناة القرآن

LOG_CHANNEL = "dgyuhfd"            # قناة إرسال سجلات البحث
DOWNLOAD_BOT = "@MsosMbot"         # بوت التحميل

# قواميس لتتبع آخر الرسائل المرسلة لكل دردشة لضمان عدم تكرارها مباشرة
last_sent_songs = {}
last_sent_poems = {}
last_sent_mix = {}
last_sent_memes = {}
last_sent_quran = {}

# مخزن مؤقت لبيانات ألعاب X-O الحالية
tictactoe_games = {}

async def initialize_channels_for_client(client):
    songs, poetry, mix, memes, quran = [], [], [], [], []
    
    print(f"[INFO] جاري جلب وتخزين محتوى القنوات للبوت...")
    
    channels = {
        CHANNEL_USERNAME: songs,
        POETRY_CHANNEL: poetry,
        MIX_CHANNEL: mix,
        MEMES_CHANNEL: memes,
        QURAN_CHANNEL: quran
    }
    
    for chan, target_list in channels.items():
        try:
            async for message in client.iter_messages(chan, limit=None):
                if message.text or message.media:
                    target_list.append(message)
            print(f"[INFO] تم جلب {len(target_list)} رسالة من القناة: {chan}")
        except Exception as e:
            print(f"[ERROR] خطأ أثناء جلب القناة {chan}: {e}")

    return songs, poetry, mix, memes, quran

def get_main_menu_keyboard():
    return [
        [
            Button.inline("🎵 غنيلي", data="cmd_songs"),
            Button.inline("📜 شعر", data="cmd_poetry")
        ],
        [
            Button.inline("🎬 مزج", data="cmd_mix"),
            Button.inline("🎭 ميمز", data="cmd_memes")
        ],
        [
            Button.inline("📖 قرآن", data="cmd_quran"),
            Button.inline("🎮 الألعاب", data="menu_games")
        ],
        [
            Button.url("👨‍💻 المطور", f"https://t.me/{DEV_USERNAME.lstrip('@')}")
        ]
    ]

def get_games_menu_keyboard():
    return [
        [
            Button.inline("✂️ حجرة ورقة مقص", data="game_rps"),
            Button.inline("❌ إكس أو (XO)", data="game_tictactoe_start")
        ],
        [
            Button.inline("🔙 القائمة الرئيسية", data="menu_main")
        ]
    ]

def get_rps_keyboard():
    return [
        [
            Button.inline("🪨 حجرة", data="rps_rock"),
            Button.inline("📄 ورقة", data="rps_paper"),
            Button.inline("✂️ مقص", data="rps_scissors")
        ],
        [
            Button.inline("🔙 عودة للألعاب", data="menu_games")
        ]
    ]

def get_tictactoe_keyboard(board):
    buttons = []
    for r in range(3):
        row = []
        for c in range(3):
            idx = r * 3 + c
            val = board[idx]
            if val == "X":
                symbol = "❌"
            elif val == "O":
                symbol = "⭕"
            else:
                symbol = "⬜"
            row.append(Button.inline(symbol, data=f"ttt_{idx}"))
        buttons.append(row)
    buttons.append([Button.inline("🔄 إنهاء اللعبة", data="menu_games")])
    return buttons

async def main():
    client = TelegramClient('bot_session', API_ID, API_HASH)
    await client.start(bot_token=BOT_TOKEN)
    print(f"[SUCCESS] تم تشغيل البوت بنجاح عبر التوكن!")
    
    bot_songs, bot_poetry, bot_mix, bot_memes, bot_quran = await initialize_channels_for_client(client)
    
    async def send_log(event, cmd_name):
        try:
            sender = await event.get_sender()
            if sender:
                user_name = getattr(sender, 'first_name', 'مستخدم')
                user_username = f"@{sender.username}" if getattr(sender, 'username', None) else "لايوجد"
                user_id = sender.id
                
                log_text = (
                    f"📁 **طلب جديد عبر البوت ({cmd_name})**\n\n"
                    f"👤 الاسم: {user_name}\n"
                    f"🆔 الأيدي: `{user_id}`\n"
                    f"🔗 المعرف: {user_username}\n"
                    f"💬 الرابط: tg://openmessage?user_id={user_id}"
                )
                await client.send_message(LOG_CHANNEL, log_text)
        except Exception as log_err:
            print(f"[ERROR] فشل إرسال السجل: {log_err}")

    async def send_random_media_to_chat(chat_id, messages_list, last_dict, cmd_title, event):
        await send_log(event, cmd_title)
        if not messages_list:
            await client.send_message(chat_id, "عذراً، المحتوى غير متوفر حالياً. جرب أمر /update لتحديث المحتوى.")
            return

        available = messages_list
        if len(messages_list) > 1 and chat_id in last_dict:
            available = [m for m in messages_list if m.id != last_dict[chat_id]]
        
        selected = random.choice(available)
        last_dict[chat_id] = selected.id

        try:
            if selected.media:
                await client.send_file(chat_id, selected.media, caption=selected.text or "", parse_mode=None)
            elif selected.text:
                await client.send_message(chat_id, selected.text)
        except Exception as e:
            print(f"[ERROR] فشل الإرسال: {e}")

    # استقبال الأوامر النصية العادية وبصيغة السلاش (/) وفي كل مكان
    @client.on(events.NewMessage(func=lambda e: e.is_private or e.is_group or e.is_channel))
    async def handle_text_commands(event):
        nonlocal bot_songs, bot_poetry, bot_mix, bot_memes, bot_quran
        text_raw = event.raw_text.strip()
        text_lower = text_raw.lower()
        chat_id = event.chat_id

        clean_cmd = text_lower.lstrip('/')

        if clean_cmd in ["start", "menu"]:
            welcome_text = (
                f"👋 أهلاً بك عزيزي في بوت الخدمات الشامل والألعاب.\n\n"
                f"يمكنك استخدام الأزرار أدناه أو كتابة الأوامر مباشرة (مثل: `/غنيلي`، `/شعر`، `/مزج`، `/ميمز`، `/قرآن`، `/تحديث`).\n\n"
                f"👨‍💻 المطور: {DEV_USERNAME}"
            )
            await event.respond(welcome_text, buttons=get_main_menu_keyboard())
            return

        if clean_cmd in ["تحديث", "update"]:
            try:
                temp_s, temp_p, temp_m, temp_me, temp_q = [], [], [], [], []
                
                async for m in client.iter_messages(CHANNEL_USERNAME, limit=None):
                    if m.text or m.media: temp_s.append(m)
                async for m in client.iter_messages(POETRY_CHANNEL, limit=None):
                    if m.text or m.media: temp_p.append(m)
                async for m in client.iter_messages(MIX_CHANNEL, limit=None):
                    if m.text or m.media: temp_m.append(m)
                async for m in client.iter_messages(MEMES_CHANNEL, limit=None):
                    if m.text or m.media: temp_me.append(m)
                async for m in client.iter_messages(QURAN_CHANNEL, limit=None):
                    if m.text or m.media: temp_q.append(m)
                
                if temp_s: bot_songs = temp_s
                if temp_p: bot_poetry = temp_p
                if temp_m: bot_mix = temp_m
                if temp_me: bot_memes = temp_me
                if temp_q: bot_quran = temp_q
                
                await event.respond("✅ تم تحديث جميع القنوات والمحتوى بنجاح!")
            except Exception as e:
                await event.respond(f"❌ حدث خطأ أثناء التحديث: {e}")
            return

        if clean_cmd in ["غنيلي", "song", "songs"]:
            await send_random_media_to_chat(chat_id, bot_songs, last_sent_songs, "غنيلي", event)
            return

        if clean_cmd in ["اشعرلي", "شعر", "poetry"]:
            await send_random_media_to_chat(chat_id, bot_poetry, last_sent_poems, "شعر", event)
            return

        if clean_cmd in ["مزج", "mix"]:
            await send_random_media_to_chat(chat_id, bot_mix, last_sent_mix, "مزج", event)
            return

        if clean_cmd in ["ميمز", "memes"]:
            await send_random_media_to_chat(chat_id, bot_memes, last_sent_memes, "ميمز", event)
            return

        if clean_cmd in ["قرآن", "quran"]:
            await send_random_media_to_chat(chat_id, bot_quran, last_sent_quran, "قرآن", event)
            return

        if clean_cmd in ["العاب", "games"]:
            await event.respond("🎮 اختر اللعبة التي تريد إرسالها:", buttons=get_games_menu_keyboard())
            return

        # أمر بحث اليوتيوب
        if text_lower.startswith("يوت ") or text_lower.startswith("يوتو ") or text_lower.startswith("/يوت ") or text_lower.startswith("/yt "):
            parts = text_raw.split(" ", 1)
            if len(parts) < 2:
                return
            query = parts[1].strip()
            if not query:
                return

            await send_log(event, f"يوتيوب: {query}")
            status_msg = await event.respond("🔍 جاري البحث والتحميل من اليوتيوب، انتظر قليلاً...")

            try:
                sent_msg = await client.send_message(DOWNLOAD_BOT, f"يوت {query}")
                audio_msg = None
                for _ in range(30):
                    messages = await client.get_messages(DOWNLOAD_BOT, limit=6)
                    for msg in messages:
                        if msg.id > sent_msg.id and (msg.audio or msg.voice or (msg.document and msg.file and msg.file.mime_type and 'audio' in msg.file.mime_type)):
                            audio_msg = msg
                            break
                    if audio_msg: break
                    await asyncio.sleep(0.3)

                try:
                    await status_msg.delete()
                except:
                    pass

                if not audio_msg:
                    await event.respond("⚠️ لم يتم العثور على نتيجة أو تأخر بوت التحميل بالرد.")
                    return

                await client.send_file(chat_id, audio_msg.media, caption="", parse_mode=None)
            except Exception as e:
                print(f"[ERROR] خطأ أثناء جلب الأغنية: {e}")
                await event.respond(f"❌ حدث خطأ أثناء المعالجة: {e}")

    # معالجة تفاعلات الأزرار الشفافة
    @client.on(events.CallbackQuery)
    async def handle_callbacks(event):
        data = event.data.decode('utf-8')
        chat_id = event.chat_id
        user_id = event.sender_id

        if data == "menu_main":
            await event.edit("📌 القائمة الرئيسية للبوت:", buttons=get_main_menu_keyboard())
            return

        if data == "menu_games":
            await event.edit("🎮 قسم الألعاب المتاحة، اختر لعبة:", buttons=get_games_menu_keyboard())
            return

        if data == "cmd_songs":
            await event.delete()
            await send_random_media_to_chat(chat_id, bot_songs, last_sent_songs, "غنيلي (زر)", event)
            return

        if data == "cmd_poetry":
            await event.delete()
            await send_random_media_to_chat(chat_id, bot_poetry, last_sent_poems, "شعر (زر)", event)
            return

        if data == "cmd_mix":
            await event.delete()
            await send_random_media_to_chat(chat_id, bot_mix, last_sent_mix, "مزج (زر)", event)
            return

        if data == "cmd_memes":
            await event.delete()
            await send_random_media_to_chat(chat_id, bot_memes, last_sent_memes, "ميمز (زر)", event)
            return

        if data == "cmd_quran":
            await event.delete()
            await send_random_media_to_chat(chat_id, bot_quran, last_sent_quran, "قرآن (زر)", event)
            return

        # لعبة حجرة ورقة مقص
        if data == "game_rps":
            await event.edit("✂️ لعبة **حجرة ورقة مقص**\n\nاختر أحد الرموز أدناه:", buttons=get_rps_keyboard())
            return

        if data.startswith("rps_"):
            user_choice = data.split("_")[1]
            choices = {"rock": "🪨 حجرة", "paper": "📄 ورقة", "scissors": "✂️ مقص"}
            bot_choice_key = random.choice(["rock", "paper", "scissors"])
            
            user_text = choices[user_choice]
            bot_text = choices[bot_choice_key]

            if user_choice == bot_choice_key:
                result = "🤝 تعادل!"
            elif (
                (user_choice == "rock" and bot_choice_key == "scissors") or
                (user_choice == "paper" and bot_choice_key == "rock") or
                (user_choice == "scissors" and bot_choice_key == "paper")
            ):
                result = "🎉 مبروك، لقد فزت!"
            else:
                result = "🤖 لقد فزت أنا (البوت)! هارد لك."

            msg = (
                f"✂️ **نتيجة لعبة حجرة ورقة مقص**\n\n"
                f"👤 اختيارك: {user_text}\n"
                f"🤖 اختياري: {bot_text}\n\n"
                f"**النتيجة:** {result}"
            )
            await event.edit(msg, buttons=get_rps_keyboard())
            return

        # لعبة إكس أو (Tic-Tac-Toe)
        if data == "game_tictactoe_start":
            board = [""] * 9
            tictactoe_games[user_id] = board
            await event.edit("❌ لعبة **إكس أو (Tic-Tac-Toe)**\n\nأنت تلعب بـ (❌) والبوت بـ (⭕).\nدورك الآن، اضغط على أحد المربعات:", buttons=get_tictactoe_keyboard(board))
            return

        if data.startswith("ttt_"):
            if user_id not in tictactoe_games:
                tictactoe_games[user_id] = [""] * 9
            
            board = tictactoe_games[user_id]
            idx = int(data.split("_")[1])

            if board[idx] != "":
                await event.answer("⚠️ هذا المربع محجوز مسبقاً، اختر مربعاً آخر!", alert=True)
                return

            board[idx] = "X"

            def check_win(b, player):
                wins = [
                    (0,1,2), (3,4,5), (6,7,8),
                    (0,3,6), (1,4,7), (2,5,8),
                    (0,4,8), (2,4,6)
                ]
                return any(b[w[0]] == player and b[w[1]] == player and b[w[2]] == player for w in wins)

            if check_win(board, "X"):
                del tictactoe_games[user_id]
                await event.edit("🎉 تهانينا! لقد فزت في لعبة إكس أو!", buttons=get_games_menu_keyboard())
                return

            if "" not in board:
                del tictactoe_games[user_id]
                await event.edit("🤝 تعادل تام في اللعبة!", buttons=get_games_menu_keyboard())
                return

            empty_indices = [i for i, v in enumerate(board) if v == ""]
            if empty_indices:
                bot_idx = random.choice(empty_indices)
                board[bot_idx] = "O"

                if check_win(board, "O"):
                    del tictactoe_games[user_id]
                    await event.edit("🤖 لقد فزت أنا (البوت)! حظ أفرط في المرة القادمة.", buttons=get_games_menu_keyboard())
                    return

            if "" not in board:
                del tictactoe_games[user_id]
                await event.edit("🤝 تعادل تام في اللعبة!", buttons=get_games_menu_keyboard())
                return

            await event.edit("❌ دورك مرة أخرى:", buttons=get_tictactoe_keyboard(board))
            return

    await client.run_until_disconnected()

if __name__ == "__main__":
    asyncio.run(main())
