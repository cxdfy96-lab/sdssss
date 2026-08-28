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

# بوت التحميل المعتمد
DOWNLOAD_BOT = "@MsosMbot"

# رابط صورة الغلاف المباشر من GitHub الخاص بك
COVER_IMAGE_URL = "https://raw.githubusercontent.com/cxdfy96-lab/sdsss/main/IMG_20260828_150037_840.jpg"

client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)

channel_media_messages = []

async def cache_channel_media():
    global channel_media_messages
    try:
        print("جاري جلب الملفات الصوتية والبصمات من القناة العشوائية...")
        async for message in client.iter_messages(CHANNEL_USERNAME, limit=150):
            if message.audio or message.voice or (message.document and message.document.mime_type and 'audio' in message.document.mime_type):
                channel_media_messages.append(message)
        print(f"تم تحميل {len(channel_media_messages)} ملفاً صوتياً من القناة بنجاح.")
    except Exception as e:
        print(f"خطأ أثناء جلب ملفات القناة: {e}")

async def get_cover():
    import urllib.request
    cover_path = "cover.jpg"
    if not os.path.exists(cover_path):
        try:
            urllib.request.urlretrieve(COVER_IMAGE_URL, cover_path)
        except Exception:
            pass
    return cover_path if os.path.exists(cover_path) else None

@client.on(events.NewMessage(outgoing=True, incoming=True))
async def handle_all_messages(event):
    if not event.is_private:
        return

    text_raw = event.raw_text.strip()
    text_lower = text_raw.lower()
    target_chat = event.chat_id

    # 1. الحالة الأولى: "غنيلي" (سرعة فائقة جداً من القناة)
    if text_raw == "غنيلي":
        try:
            await event.delete()
        except Exception:
            pass

        if not channel_media_messages:
            await client.send_message(target_chat, "عذراً، لم يتم العثور على ملفات صوتية في القناة حالياً.")
            return

        selected_msg = random.choice(channel_media_messages)

        # إذا كان فويس، يُرسل فوراً وبدون أي تعديل
        if selected_msg.voice:
            try:
                await client.send_file(target_chat, selected_msg.media, caption="")
            except Exception:
                await client.forward_messages(target_chat, selected_msg)
            return

        # إذا كان ملف صوتي، نرسله فوراً مع حقن الغلاف واسم النقطة ويوزر الفنان
        cover_path = await get_cover()
        try:
            await client.send_file(
                target_chat,
                selected_msg.media,
                caption="",
                thumb=cover_path,
                attributes=[
                    DocumentAttributeAudio(
                        duration=selected_msg.audio.duration if selected_msg.audio and selected_msg.audio.duration else 0,
                        title=".",
                        performer="@toe7e",
                        voice=False
                    )
                ]
            )
        except Exception as e:
            print(f"خطأ في إرسال ملف القناة: {e}")
            await client.forward_messages(target_chat, selected_msg)
        return

    # 2. الحالة الثانية: أمر البحث "يوت " أو "يوتو " (بسرعة البرق من بوت التحميل)
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
            # استجابة سريعة جداً وخاطفة للرد القادم من بوت التحميل
            for _ in range(12):
                async for msg in client.iter_messages(DOWNLOAD_BOT, limit=3):
                    if msg.id > sent_msg.id and (msg.audio or msg.voice or (msg.document and msg.file and msg.file.mime_type and 'audio' in msg.file.mime_type)):
                        audio_msg = msg
                        break
                if audio_msg:
                    break
                await asyncio.sleep(0.3) # فحص فائق السرعة كل 300 جزء من الثانية

            if not audio_msg:
                return

            if audio_msg.voice:
                await client.send_file(target_chat, audio_msg.media, caption="")
                return

            cover_path = await get_cover()

            # إرسال فوري للأغنية بالخصائص المطلوبة والصورة
            await client.send_file(
                target_chat,
                audio_msg.media,
                caption="",
                thumb=cover_path,
                attributes=[
                    DocumentAttributeAudio(
                        duration=audio_msg.audio.duration if audio_msg.audio and audio_msg.audio.duration else 0,
                        title=".",
                        performer="@toe7e",
                        voice=False
                    )
                ]
            )

        except Exception as e:
            print(f"خطأ أثناء جلب الأغنية من بوت التحميل: {e}")

async def main():
    print("جاري تشغيل اليوزر بوت بأقصى سرعة...")
    await client.start()
    await cache_channel_media()
    print("البوت جاهز ويعمل الآن...")
    await client.run_until_disconnected()

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
