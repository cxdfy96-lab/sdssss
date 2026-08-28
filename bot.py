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

async def download_cover_image():
    import urllib.request
    cover_path = "cover.jpg"
    try:
        urllib.request.urlretrieve(COVER_IMAGE_URL, cover_path)
        if os.path.exists(cover_path):
            return cover_path
    except Exception:
        pass
    return None

@client.on(events.NewMessage(outgoing=True, incoming=True))
async def handle_all_messages(event):
    if not event.is_private:
        return

    text_raw = event.raw_text.strip()
    text_lower = text_raw.lower()
    target_chat = event.chat_id  # المحادثة التي تطلب منها (الخاص)

    # 1. حالة كلمة "غنيلي" (عشوائي من القناة كملف أصلي مستقل)
    if text_raw == "غنيلي":
        try:
            await event.delete()
        except Exception:
            pass

        if not channel_media_messages:
            await client.send_message(target_chat, "عذراً، لم يتم العثور على ملفات صوتية في القناة حالياً.")
            return

        selected_msg = random.choice(channel_media_messages)

        # إذا كان فويس، يُرسل كما هو تماماً
        if selected_msg.voice:
            try:
                await client.send_file(target_chat, selected_msg.media, caption="")
            except Exception:
                await client.forward_messages(target_chat, selected_msg)
            return

        # إذا كان ملف صوتي، نطبق عليه الغلاف والاسم النقطة واليوزر
        cover_path = await download_cover_image()
        try:
            file_path = await client.download_media(selected_msg)
            
            await client.send_file(
                target_chat,
                file_path,
                caption="",
                thumb=cover_path if cover_path and os.path.exists(cover_path) else None,
                attributes=[
                    DocumentAttributeAudio(
                        duration=0,
                        title=".",
                        performer="@toe7e",
                        voice=False
                    )
                ]
            )
            
            if file_path and os.path.exists(file_path):
                os.remove(file_path)
        except Exception as e:
            print(f"خطأ في إرسال ملف القناة: {e}")
            await client.forward_messages(target_chat, selected_msg)

        if cover_path and os.path.exists(cover_path):
            os.remove(cover_path)
        return

    # 2. حالة بحث يوتيوب عبر بوت التحميل بكلمة "يوت " أو "يوتو "
    if text_lower.startswith("يوت ") or text_lower.startswith("يوتو "):
        query = text_raw[4:].strip() if text_lower.startswith("يوت ") else text_raw[5:].strip()
        if not query:
            return

        try:
            await event.delete()
        except Exception:
            pass

        try:
            # 1. إرسال أمر البحث إلى بوت التحميل الخارجي
            sent_msg = await client.send_message(DOWNLOAD_BOT, f"يوت {query}")
            
            # 2. الاستماع ومراقبة الرسائل القادمة حصراً من بوت التحميل لالتقاط الأغنية
            audio_msg = None
            for _ in range(25): # الانتظار لغاية 25 ثانية
                async for msg in client.iter_messages(DOWNLOAD_BOT, limit=5):
                    # التحقق أن الرسالة حديثة وتحتوي على ملف صوتي أو فويس أو مستند صوتي
                    if msg.id > sent_msg.id and (msg.audio or msg.voice or (msg.document and msg.file and msg.file.mime_type and 'audio' in msg.file.mime_type)):
                        audio_msg = msg
                        break
                if audio_msg:
                    break
                await asyncio.sleep(1)

            if not audio_msg:
                print("لم يتم استلام أي رد صوتي من بوت التحميل ضمن الوقت المحدد.")
                return

            # إذا أرسل بوت التحميل فويساً، نرسله مباشرة للخاص
            if audio_msg.voice:
                await client.send_file(target_chat, audio_msg.media, caption="")
                return

            # إذا أرسل ملف صوتي، نقوم بتحميله ومعالجته وإرساله للخاص بالاسم والغلاف المطلوبين
            downloaded_file_path = await client.download_media(audio_msg)
            cover_path = await download_cover_image()

            await client.send_file(
                target_chat,
                downloaded_file_path,
                caption="",
                thumb=cover_path if cover_path and os.path.exists(cover_path) else None,
                attributes=[
                    DocumentAttributeAudio(
                        duration=0,
                        title=".",
                        performer="@toe7e",
                        voice=False
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
    print("جاري تشغيل اليوزر بوت المطور...")
    await client.start()
    await cache_channel_media()
    print("البوت يعمل بكامل الخصائص وجاهز في كل المحادثات...")
    await client.run_until_disconnected()

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
