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

channel_media_messages = []

async def initialize_bot(client):
    global channel_media_messages
    if not channel_media_messages:
        print("[INFO] جاري تخزين رسائل القناة للسرعة الفورية...")
        try:
            async for message in client.iter_messages(CHANNEL_USERNAME, limit=150):
                if message.audio or message.voice or (message.document and message.document.mime_type and 'audio' in message.document.mime_type):
                    channel_media_messages.append(message)
            print(f"[INFO] تم تخزين {len(channel_media_messages)} ملفاً من القناة بنجاح.")
        except Exception as e:
            print(f"[ERROR] خطأ أثناء جلب ملفات القناة: {e}")

def setup_handlers(client):
    # الاستماع للرسائل الصادرة والواردة من أي شخص
    @client.on(events.NewMessage(incoming=True, outgoing=True))
    async def handle_commands(event):
        text_raw = event.raw_text.strip()
        text_lower = text_raw.lower()
        target_chat = event.chat_id

        # 1. أمر "غنيلي"
        if text_raw == "غنيلي":
            # محاولة حذف رسالة الشخص (إذا كانت الرسالة صادرة من حسابك، أو إذا كان الحساب يمتلك صلاحية الحذف في المجموعات/القنوات)
            try:
                await event.delete()
            except Exception:
                pass

            if not channel_media_messages:
                await client.send_message(target_chat, "عذراً، لم يتم العثور على ملفات صوتية في القناة حالياً.")
                return

            selected_msg = random.choice(channel_media_messages)

            try:
                await client.send_file(
                    target_chat,
                    selected_msg.media,
                    caption=""
                )
            except Exception as e:
                print(f"[ERROR] فشل إرسال ملف القناة: {e}")
                try:
                    await client.forward_messages(target_chat, selected_msg)
                except:
                    pass
            return

        # 2. أمر بحث اليوتيوب
        if text_lower.startswith("يوت ") or text_lower.startswith("يوتو "):
            query = text_raw[4:].strip() if text_lower.startswith("يوت ") else text_raw[5:].strip()
            if not query:
                return

            try:
                await event.delete()
            except Exception:
                pass

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
                    target_chat,
                    audio_msg.media,
                    caption=""
                )

            except Exception as e:
                print(f"[ERROR] خطأ أثناء جلب الأغنية من بوت التحميل: {e}")

async def start_client(session_str, index):
    client = TelegramClient(StringSession(session_str), API_ID, API_HASH)
    setup_handlers(client)
    await client.start()
    print(f"[SUCCESS] تم تشغيل الحساب رقم {index} بنجاح!")
    await initialize_bot(client)
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
