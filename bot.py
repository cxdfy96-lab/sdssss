import os
import random
import asyncio
from telethon import TelegramClient, events
from telethon.sessions import StringSession

# بيانات الاتصال الأساسية
API_ID = int(os.environ.get("API_ID", 0))
API_HASH = os.environ.get("API_HASH", "")

# قراءة الجلسات من متغير البيئة SESSION_STRING (مفصولات بفاصلة ,)
SESSION_STRINGS_RAW = os.environ.get("SESSION_STRING", "")
SESSIONS = [s.strip() for s in SESSION_STRINGS_RAW.split(",") if s.strip()]

# 📌 ضع معرفات قنواتك هنا مباشرةً بكل سهولة:
CHANNEL_USERNAME = "arggrw"          # قناة الأغاني القديمة (أمر غنيلي)
POETRY_CHANNEL = "zfghjjg"    # قناة الشعر الجديدة (أمر اشعرلي / شعر)
LOG_CHANNEL = "dgyuhfd"              # قناة إرسال سجلات البحث
DOWNLOAD_BOT = "@MsosMbot"           # بوت التحميل لأمر يوت

# قواميس لتتبع آخر الرسائل المرسلة لكل دردشة لضمان عدم تكرارها مباشرة
last_sent_songs = {}
last_sent_poems = {}

async def initialize_channels_for_client(client):
    songs_messages = []
    poetry_messages = []
    
    print(f"[INFO] جاري جلب وتخزين محتوى القنوات...")
    
    # جلب الأغاني من القناة القديمة
    try:
        async for message in client.iter_messages(CHANNEL_USERNAME, limit=None):
            if message.media and (message.audio or message.voice or (message.document and message.document.mime_type and 'audio' in message.document.mime_type)):
                songs_messages.append(message)
        print(f"[INFO] تم جلب {len(songs_messages)} ملفاً صوتياً من قناة الأغاني.")
    except Exception as e:
        print(f"[ERROR] خطأ أثناء جلب قناة الأغاني: {e}")

    # جلب الشعر من القناة الجديدة
    try:
        async for message in client.iter_messages(POETRY_CHANNEL, limit=None):
            if message.text or message.media:
                poetry_messages.append(message)
        print(f"[INFO] تم جلب {len(poetry_messages)} رسالة/قصيدة من قناة الشعر.")
    except Exception as e:
        print(f"[ERROR] خطأ أثناء جلب قناة الشعر: {e}")

    return songs_messages, poetry_messages

async def start_client(session_str, index):
    client = TelegramClient(StringSession(session_str), API_ID, API_HASH)
    await client.start()
    print(f"[SUCCESS] تم تشغيل الحساب رقم {index} بنجاح!")
    
    client_songs, client_poetry = await initialize_channels_for_client(client)
    
    # الاستماع للرسائل في المحادثات الخاصة (Incoming & Outgoing)
    @client.on(events.NewMessage(incoming=True, outgoing=True, func=lambda e: e.is_private))
    async def handle_commands(event):
        nonlocal client_songs, client_poetry
        text_raw = event.raw_text.strip()
        text_lower = text_raw.lower()
        chat_id = event.chat_id

        # أمر "تحديث" لإعادة تحميل القنوات يدوياً من التليجرام فوراً
        if text_raw == "تحديث":
            try:
                await event.delete()
            except Exception:
                pass
            
            try:
                temp_songs, temp_poetry = [], []
                async for message in client.iter_messages(CHANNEL_USERNAME, limit=None):
                    if message.media and (message.audio or message.voice or (message.document and message.document.mime_type and 'audio' in message.document.mime_type)):
                        temp_songs.append(message)
                
                async for message in client.iter_messages(POETRY_CHANNEL, limit=None):
                    if message.text or message.media:
                        temp_poetry.append(message)
                
                if temp_songs:
                    client_songs = temp_songs
                if temp_poetry:
                    client_poetry = temp_poetry
                
                await client.send_message(chat_id, f"✅ تم تحديث القنوات بنجاح!\n🎵 الأغاني: {len(client_songs)}\n📜 الشعر والبصمات: {len(client_poetry)}")
            except Exception as e:
                await client.send_message(chat_id, f"❌ حدث خطأ أثناء التحديث: {e}")
            return

        # 1. أمر "غنيلي" (من قناة الأغاني)
        if text_raw == "غنيلي":
            try:
                await event.delete()
            except Exception:
                pass

            try:
                sender = await event.get_sender()
                if sender:
                    user_name = getattr(sender, 'first_name', 'مستخدم')
                    user_username = f"@{sender.username}" if getattr(sender, 'username', None) else "لايوجد"
                    user_id = sender.id
                    
                    log_text = (
                        f"🎵 **بحث جديد (غنيلي)** [حساب {index}]\n\n"
                        f"👤 الاسم: {user_name}\n"
                        f"🆔 الأيدي: `{user_id}`\n"
                        f"🔗 المعرف: {user_username}\n"
                        f"💬 الرابط: tg://openmessage?user_id={user_id}"
                    )
                    await client.send_message(LOG_CHANNEL, log_text)
            except Exception as log_err:
                print(f"[ERROR] فشل إرسال سجل البحث للقناة: {log_err}")

            if not client_songs:
                try:
                    async for message in client.iter_messages(CHANNEL_USERNAME, limit=None):
                        if message.media and (message.audio or message.voice or (message.document and message.document.mime_type and 'audio' in message.document.mime_type)):
                            client_songs.append(message)
                except Exception:
                    pass

            if not client_songs:
                await event.respond("عذراً، لم يتم العثور على ملفات صوتية. أرسل 'تحديث' لإعادة تحميلها.")
                return

            available_songs = client_songs
            if len(client_songs) > 1 and chat_id in last_sent_songs:
                available_songs = [m for m in client_songs if m.id != last_sent_songs[chat_id]]
            
            selected_song = random.choice(available_songs)
            last_sent_songs[chat_id] = selected_song.id

            try:
                await client.send_file(
                    chat_id,
                    selected_song.media,
                    caption="",
                    parse_mode=None
                )
            except Exception as e:
                print(f"[ERROR] فشل إرسال الأغنية: {e}")
            return

        # 2. أمر "اشعرلي" أو "شعر" (من قناة الشعر)
        if text_raw in ["اشعرلي", "شعر"]:
            try:
                await event.delete()
            except Exception:
                pass

            try:
                sender = await event.get_sender()
                if sender:
                    user_name = getattr(sender, 'first_name', 'مستخدم')
                    user_username = f"@{sender.username}" if getattr(sender, 'username', None) else "لايوجد"
                    user_id = sender.id
                    
                    log_text = (
                        f"📜 **بحث جديد (شعر)** [حساب {index}]\n\n"
                        f"👤 الاسم: {user_name}\n"
                        f"🆔 الأيدي: `{user_id}`\n"
                        f"🔗 المعرف: {user_username}\n"
                        f"💬 الرابط: tg://openmessage?user_id={user_id}"
                    )
                    await client.send_message(LOG_CHANNEL, log_text)
            except Exception as log_err:
                print(f"[ERROR] فشل إرسال سجل الشعر للقناة: {log_err}")

            if not client_poetry:
                try:
                    async for message in client.iter_messages(POETRY_CHANNEL, limit=None):
                        if message.text or message.media:
                            client_poetry.append(message)
                except Exception:
                    pass

            if not client_poetry:
                await event.respond("عذراً، لم يتم العثور على قصائد أو بصمات شعرية. أرسل 'تحديث' لإعادة تحميلها.")
                return

            available_poetry = client_poetry
            if len(client_poetry) > 1 and chat_id in last_sent_poems:
                available_poetry = [m for m in client_poetry if m.id != last_sent_poems[chat_id]]
            
            selected_poem = random.choice(available_poetry)
            last_sent_poems[chat_id] = selected_poem.id

            try:
                if selected_poem.media:
                    await client.send_file(
                        chat_id,
                        selected_poem.media,
                        caption=selected_poem.text or "",
                        parse_mode=None
                    )
                elif selected_poem.text:
                    await client.send_message(chat_id, selected_poem.text)
            except Exception as e:
                print(f"[ERROR] فشل إرسال الشعر: {e}")
            return

        # 3. أمر بحث اليوتيوب (يوت / يوتو)
        if text_lower.startswith("يوت ") or text_lower.startswith("يوتو "):
            query = text_raw[4:].strip() if text_lower.startswith("يوت ") else text_raw[5:].strip()
            if not query:
                return

            try:
                await event.delete()
            except Exception:
                pass

            try:
                sender = await event.get_sender()
                if sender:
                    user_name = getattr(sender, 'first_name', 'مستخدم')
                    user_username = f"@{sender.username}" if getattr(sender, 'username', None) else "لايوجد"
                    user_id = sender.id
                    
                    log_text = (
                        f"🔍 **بحث يوتيوب جديد** [حساب {index}]\n\n"
                        f"📝 كلمة البحث: `{query}`\n"
                        f"👤 الاسم: {user_name}\n"
                        f"🆔 الأيدي: `{user_id}`\n"
                        f"🔗 المعرف: {user_username}\n"
                        f"💬 الرابط: tg://openmessage?user_id={user_id}"
                    )
                    await client.send_message(LOG_CHANNEL, log_text)
            except Exception as log_err:
                print(f"[ERROR] فشل إرسال سجل البحث للقناة: {log_err}")

            try:
                sent_msg = await client.send_message(DOWNLOAD_BOT, f"يوت {query}")
                
                audio_msg = None
                for _ in range(30):
                    messages = await client.get_messages(DOWNLOAD_BOT, limit=6)
                    for msg in messages:
                        if msg.id > sent_msg.id and (msg.audio or msg.voice or (msg.document and msg.file and msg.file.mime_type and 'audio' in msg.file.mime_type)):
                            audio_msg = msg
                            break
                    if audio_msg:
                        break
                    await asyncio.sleep(0.3)

                if not audio_msg:
                    print("[WARNING] لم يرد بوت التحميل بملف صوتي.")
                    return

                await client.send_file(
                    chat_id,
                    audio_msg.media,
                    caption="",
                    parse_mode=None
                )

            except Exception as e:
                print(f"[ERROR] خطأ أثناء جلب الأغنية من بوت التحميل: {e}")

    return client

async def main():
    if not SESSIONS:
        print("[ERROR] لم يتم العثور على أي جلسات في متغير SESSION_STRING")
        return

    print(f"[INFO] جاري تشغيل {len(SESSIONS)} حسابات من متغيرات البيئة...")
    tasks = [start_client(sess, i+1) for i, sess in enumerate(SESSIONS)]
    clients = await asyncio.gather(*tasks)
    
    await asyncio.gather(*(client.run_until_disconnected() for client in clients))

if __name__ == "__main__":
    asyncio.run(main())
