import os
import random
import asyncio
from telethon import TelegramClient, events
from telethon.sessions import StringSession

# بيانات الاتصال بمتغيرات البيئة في Railway
API_ID = int(os.environ.get("API_ID", 0))
API_HASH = os.environ.get("API_HASH", "")
SESSION_STRING = os.environ.get("SESSION_STRING", "")

# إعدادات البوت والقناة
CHANNEL_USERNAME = "arggrw"
DOWNLOAD_BOT = "@MsosMbot"

client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)
channel_media_messages = []

async def initialize_bot():
    global channel_media_messages
    print("[INFO] جاري تخزين رسائل القناة للسرعة الفورية...")
    try:
        async for message in client.iter_messages(CHANNEL_USERNAME, limit=150):
            if message.audio or message.voice or (message.document and message.document.mime_type and 'audio' in message.document.mime_type):
                channel_media_messages.append(message)
        print(f"[INFO] تم تخزين {len(channel_media_messages)} ملفاً من القناة بنجاح.")
    except Exception as e:
        print(f"[ERROR] خطأ أثناء جلب ملفات القناة: {e}")

@client.on(events.NewMessage(outgoing=True, incoming=True))
async def handle_commands(event):
    if not event.is_private:
        return

    text_raw = event.raw_text.strip()
    text_lower = text_raw.lower()
    target_chat = event.chat_id

    # 1. أمر "غنيلي" (سرعة صاروخية وبدون تحميل)
    if text_raw == "غنيلي":
        try:
            await event.delete()
        except Exception:
            pass

        if not channel_media_messages:
            await client.send_message(target_chat, "عذراً، لم يتم العثور على ملفات صوتية في القناة حالياً.")
            return

        selected_msg = random.choice(channel_media_messages)

        try:
            # إرسال الميديا مباشرة بدون تنزيل لضمان السرعة القصوى وثبات الاسم والفنان الأصلي وبدون وصف
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

    # 2. أمر بحث اليوتيوب (يوت / يوتو) بسرعة البرق
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

            # إرسال ميديا الأغنية مباشرة للخاص بدون تنزيل للحفاظ على الاسم والفنان الأصلي وبدون وصف
            await client.send_file(
                target_chat,
                audio_msg.media,
                caption=""
            )

        except Exception as e:
            print(f"[ERROR] خطأ أثناء جلب الأغنية من بوت التحميل: {e}")

async def main():
    print("[INFO] تشغيل اليوزر بوت بأقصى سرعة ممكنة...")
    await client.start()
    await initialize_bot()
    print("[SUCCESS] البوت يعمل بكامل السرعة وبأسمائه الأصلية...")
    await client.run_until_disconnected()

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
