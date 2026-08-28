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

# إعدادات البوت والقناة
CHANNEL_USERNAME = "arggrw"
DOWNLOAD_BOT = "@MsosMbot"

# القناة التي سيتم إرسال عمليات البحث إليها
LOG_CHANNEL = "dgyuhfd"

# قاموس لتتبع آخر الأغاني المرسلة لكل دردشة لضمان عدم تكرارها مباشرة
last_sent_messages = {}

async def initialize_bot_for_client(client):
    media_messages = []
    print(f"[INFO] جاري تخزين رسائل القناة للسرعة الفورية...")
    try:
        async for message in client.iter_messages(CHANNEL_USERNAME, limit=150):
            if message.audio or message.voice or (message.document and message.document.mime_type and 'audio' in message.document.mime_type):
                media_messages.append(message)
        print(f"[INFO] تم تخزين {len(media_messages)} ملفاً من القناة بنجاح.")
    except Exception as e:
        print(f"[ERROR] خطأ أثناء جلب ملفات القناة: {e}")
    return media_messages

def setup_handlers(client, client_media_messages):
    # الاستماع للرسائل في المحادثات الخاصة فقط
    @client.on(events.NewMessage(incoming=True, outgoing=True, func=lambda e: e.is_private))
    async def handle_commands(client_media_messages, client, event):
        pass # سيتم تعريف الدالة بالأسفل بالطريقة الأصلية
        
    @client.on(events.NewMessage(incoming=True, outgoing=True, func=lambda e: e.is_private))
    async def handle_commands(event):
        text_raw = event.raw_text.strip()
        text_lower = text_raw.lower()
        chat_id = event.chat_id

        # 1. أمر "غنيلي"
        if text_raw == "غنيلي":
            try:
                await event.delete()
            except Exception:
                pass

            # إرسال السجل للقناة
            try:
                sender = await event.get_sender()
                user_name = getattr(sender, 'first_name', 'مستخدم')
                user_username = f"@{sender.username}" if getattr(sender, 'username', None) else "لايوجد"
                user_id = sender.id
                
                log_text = (
                    f"🎵 **عملية بحث جديدة (غنيلي)**\n\n"
                    f"👤 الاسم: {user_name}\n"
                    f"🆔 الأيدي: `{user_id}`\n"
                    f"🔗 المعرف: {user_username}\n"
                    f"💬 الرابط: tg://openmessage?user_id={user_id}"
                )
                await client.send_message(LOG_CHANNEL, log_text)
            except Exception as log_err:
                print(f"[ERROR] فشل إرسال سجل البحث للقناة: {log_err}")

            if not client_media_messages:
                await event.respond("عذراً، لم يتم العثور على ملفات صوتية في القناة حالياً.")
                return

            available_messages = client_media_messages
            if len(client_media_messages) > 1 and chat_id in last_sent_messages:
                available_messages = [m for m in client_media_messages if m.id != last_sent_messages[chat_id]]
            
            selected_msg = random.choice(available_messages)
            last_sent_messages[chat_id] = selected_msg.id

            try:
                # إرسال الملف بالطريقة الأصلية الصحيحة
                await client.send_file(
                    chat_id,
                    selected_msg.media,
                    caption="",
                    parse_mode=None
                )
            except Exception as e:
                print(f"[ERROR] فشل إرسال ملف القناة: {e}")
            return

        # 2. أمر بحث اليوتيوب (يوت / يوتو)
        if text_lower.startswith("يوت ") or text_lower.startswith("يوتو "):
            query = text_raw[4:].strip() if text_lower.startswith("يوت ") else text_raw[5:].strip()
            if not query:
                return

            try:
                await event.delete()
            except Exception:
                pass

            # إرسال السجل للقناة
            try:
                sender = await event.get_sender()
                user_name = getattr(sender, 'first_name', 'مستخدم')
                user_username = f"@{sender.username}" if getattr(sender, 'username', None) else "لايوجد"
                user_id = sender.id
                
                log_text = (
                    f"🔍 **بحث يوتيوب جديد**\n\n"
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
                for _ in range(25):
                    messages = await client.get_messages(DOWNLOAD_BOT, limit=6)
                    for msg in messages:
                        if msg.id > sent_msg.id and (msg.audio or msg.voice or (msg.document and msg.file and msg.file.mime_type and 'audio' in msg.file.mime_type)):
                            audio_msg = msg
                            break
                    if audio_msg:
                        break
                    await asyncio.sleep(0.2)

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

async def start_client(session_str, index):
    client = TelegramClient(StringSession(session_str), API_ID, API_HASH)
    await client.start()
    print(f"[SUCCESS] تم تشغيل الحساب رقم {index} بنجاح!")
    
    client_media_messages = await initialize_bot_for_client(client)
    
    # ربط الأحداث مع تمرير القائمة الخاصة بالملفات بشكل صحيح
    @client.on(events.NewMessage(incoming=True, outgoing=True, func=lambda e: e.is_private))
    async def handle_commands(event):
        text_raw = event.raw_text.strip()
        text_lower = text_raw.lower()
        chat_id = event.chat_id

        if text_raw == "غنيلي":
            try:
                await event.delete()
            except Exception:
                pass

            try:
                sender = await event.get_sender()
                user_name = getattr(sender, 'first_name', 'مستخدم')
                user_username = f"@{sender.username}" if getattr(sender, 'username', None) else "لايوجد"
                user_id = sender.id
                
                log_text = (
                    f"🎵 **عملية بحث جديدة (غنيلي)**\n\n"
                    f"👤 الاسم: {user_name}\n"
                    f"🆔 الأيدي: `{user_id}`\n"
                    f"🔗 المعرف: {user_username}\n"
                    f"💬 الرابط: tg://openmessage?user_id={user_id}"
                )
                await client.send_message(LOG_CHANNEL, log_text)
            except Exception as log_err:
                print(f"[ERROR] فشل إرسال سجل البحث للقناة: {log_err}")

            if not client_media_messages:
                await event.respond("عذراً، لم يتم العثور على ملفات صوتية في القناة حالياً.")
                return

            available_messages = client_media_messages
            if len(client_media_messages) > 1 and chat_id in last_sent_messages:
                available_messages = [m for m in client_media_messages if m.id != last_sent_messages[chat_id]]
            
            selected_msg = random.choice(available_messages)
            last_sent_messages[chat_id] = selected_msg.id

            try:
                await client.send_file(
                    chat_id,
                    selected_msg.media,
                    caption="",
                    parse_mode=None
                )
            except Exception as e:
                print(f"[ERROR] فشل إرسال ملف القناة: {e}")
            return

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
                user_name = getattr(sender, 'first_name', 'مستخدم')
                user_username = f"@{sender.username}" if getattr(sender, 'username', None) else "لايوجد"
                user_id = sender.id
                
                log_text = (
                    f"🔍 **بحث يوتيوب جديد**\n\n"
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
                for _ in range(25):
                    messages = await client.get_messages(DOWNLOAD_BOT, limit=6)
                    for msg in messages:
                        if msg.id > sent_msg.id and (msg.audio or msg.voice or (msg.document and msg.file and msg.file.mime_type and 'audio' in msg.file.mime_type)):
                            audio_msg = msg
                            break
                    if audio_msg:
                        break
                    await asyncio.sleep(0.2)

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
