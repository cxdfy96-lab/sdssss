import os
import random
import asyncio
from telethon import TelegramClient, events
from telethon.sessions import StringSession
from telethon.tl.types import DocumentAttributeAudio

# جلب بيانات الاتصال من متغيرات البيئة في Railway
API_ID = int(os.environ.get("API_ID", 0))
API_HASH = os.environ.get("API_HASH", "")
SESSION_STRING = os.environ.get("SESSION_STRING", "")

# معرف قناتك الخاصة بالأغاني والفويسات العشوائية
CHANNEL_USERNAME = "arggrw"

# بوت التحميل المعتمد للبحث المخصص
DOWNLOAD_BOT = "@MsosMbot"

# رابط صورة الغلاف المباشر من GitHub الخاص بك
COVER_IMAGE_URL = "https://raw.githubusercontent.com/cxdfy96-lab/sdsss/main/IMG_20260828_150037_840.jpg"

client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)

# تخزين مؤقت لملفات القناة للسرعة
channel_media_messages = []

async def cache_channel_media():
    global channel_media_messages
    try:
        print("جاري جلب الملفات الصوتية والبصمات من القناة العشوائية...")
        async for message in client.iter_messages(CHANNEL_USERNAME, limit=100):
            if message.audio or message.voice:
                channel_media_messages.append(message)
        print(f"تم تحميل {len(channel_media_messages)} ملفاً صوتياً من القناة بنجاح.")
    except Exception as e:
        print(f"خطأ أثناء جلب ملفات القناة: {e}")

async def download_cover_image():
    import urllib.request
    cover_path = "cover.jpg"
    try:
        urllib.request.urlretrieve(COVER_IMAGE_URL, cover_path)
        return cover_path
    except Exception:
        return None

@client.on(events.NewMessage(outgoing=True, incoming=True))
async def handle_all_messages(event):
    if not event.is_private:
        return

    text_raw = event.raw_text.strip()
    text_lower = text_raw.lower()

    # 1. حالة كلمة "غنيلي" (عشوائي من القناة المحددة وبدون وصف واسم نقطة)
    if text_raw == "غنيلي":
        try:
            await event.delete()
        except Exception:
            pass

        if not channel_media_messages:
            await event.respond("عذراً، لم يتم العثور على ملفات صوتية في القناة حالياً.")
            return

        selected_msg = random.choice(channel_media_messages)
        cover_path = await download_cover_image()

        try:
            await client.send_file(
                event.chat_id,
                selected_msg.media,
                caption="",
                thumb=cover_path if cover_path and os.path.exists(cover_path) else None,
                attributes=[
                    DocumentAttributeAudio(
                        duration=0,
                        title=".",
                        performer="@toe7e"
                    )
                ]
            )
        except Exception:
            await client.forward_messages(event.chat_id, selected_msg)

        if cover_path and os.path.exists(cover_path):
            os.remove(cover_path)
        return

    # 2. حالة بحث يوتيوب عبر بوت التحميل @MsosMbot بكلمة "يوت "
    if text_lower.startswith("يوت "):
        query = text_raw[4:].strip()
        if not query:
            return

        try:
            await event.delete()
        except Exception:
            pass

        try:
            async with client.conversation(DOWNLOAD_BOT) as conv:
                await conv.send_message(f"يوت {query}")
                
                audio_msg = None
                for _ in range(20):
                    response = await conv.get_response()
                    if response and (response.audio or response.voice or response.document):
                        audio_msg = response
                        break
                    await asyncio.sleep(1)

                if not audio_msg:
                    return

                downloaded_file_path = await client.download_media(audio_msg)
                cover_path = await download_cover_image()

                await client.send_file(
                    event.chat_id,
                    downloaded_file_path,
                    caption="",
                    thumb=cover_path if cover_path and os.path.exists(cover_path) else None,
                    attributes=[
                        DocumentAttributeAudio(
                            duration=0,
                            title=".",
                            performer="@toe7e"
                        )
                    ]
                )

                if downloaded_file_path and os.path.exists(downloaded_file_path):
                    os.remove(downloaded_file_path)
                if cover_path and os.path.exists(cover_path):
                    os.remove(cover_path)

        except Exception as e:
            print(f"خطأ أثناء جلب الأغنية من بوت التحميل: {e}")

async def main():
    print("جاري تشغيل اليوزر بوت...")
    await client.start()
    await cache_channel_media()
    print("البوت يعمل بكامل الخصائص الآن...")
    await client.run_until_disconnected()

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
