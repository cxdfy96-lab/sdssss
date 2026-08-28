import os
import random
import asyncio
import urllib.request
from telethon import TelegramClient, events
from telethon.sessions import StringSession
from telethon.tl.types import DocumentAttributeAudio
from mutagen.mp3 import MP3
from mutagen.id3 import ID3, APIC, TIT2, TPE1, error

# جلب بيانات الاتصال من متغيرات البيئة في Railway
API_ID = int(os.environ.get("API_ID", 0))
API_HASH = os.environ.get("API_HASH", "")
SESSION_STRING = os.environ.get("SESSION_STRING", "")

# إعدادات البوت والقناة
CHANNEL_USERNAME = "arggrw"
DOWNLOAD_BOT = "@MsosMbot"
COVER_IMAGE_URL = "https://raw.githubusercontent.com/cxdfy96-lab/sdsss/main/IMG_20260828_150037_840.jpg"

client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)
channel_media_messages = []
cover_cache_path = "cover_cached.jpg"

async def initialize_bot():
    global channel_media_messages
    print("[INFO] جاري تحميل الغلاف وتخزين رسائل القناة مؤقتاً...")
    
    # تحميل الغلاف وتخزينه محلياً للسرعة القصوى
    try:
        urllib.request.urlretrieve(COVER_IMAGE_URL, cover_cache_path)
    except Exception as e:
        print(f"[WARNING] لم يتم تحميل الغلاف: {e}")

    # جلب الرسائل من القناة
    try:
        async for message in client.iter_messages(CHANNEL_USERNAME, limit=150):
            if message.audio or message.voice or (message.document and message.document.mime_type and 'audio' in message.document.mime_type):
                channel_media_messages.append(message)
        print(f"[INFO] تم تخزين {len(channel_media_messages)} ملفاً من القناة بنجاح.")
    except Exception as e:
        print(f"[ERROR] خطأ أثناء جلب ملفات القناة: {e}")

def process_audio_metadata(file_path):
    """دالة احترافية لحقن الغلاف، النقطة (.)، واسم الفنان بداخل الملف الصوتي"""
    try:
        audio = MP3(file_path, ID3=ID3)
        
        # إضافة العلامات إذا لم تكن موجودة
        try:
            audio.add_tags()
        except error:
            pass

        # تعديل العنوان إلى نقطة (.) والفنان إلى @toe7e
        audio.tags.add(TIT2(encoding=3, text='.'))
        audio.tags.add(TPE1(encoding=3, text='@toe7e'))

        # حقن صورة الغلاف بداخل الملف الصوتي إذا كانت متوفرة
        if os.path.exists(cover_cache_path):
            with open(cover_cache_path, 'rb') as album_art:
                audio.tags.add(
                    APIC(
                        encoding=3,
                        mime='image/jpeg',
                        type=3, # الغلاف الأمامي
                        desc='Cover',
                        data=album_art.read()
                    )
                )
        audio.save()
    except Exception as e:
        print(f"[WARNING] تعذر تعديل الميتا داتا للصوت: {e}")

@client.on(events.NewMessage(outgoing=True, incoming=True))
async def handle_commands(event):
    if not event.is_private:
        return

    text_raw = event.raw_text.strip()
    text_lower = text_raw.lower()
    target_chat = event.chat_id

    # 1. أمر "غنيلي" (جلب عشوائي من القناة)
    if text_raw == "غنيلي":
        try:
            await event.delete()
        except Exception:
            pass

        if not channel_media_messages:
            await client.send_message(target_chat, "عذراً، لم يتم العثور على ملفات صوتية في القناة حالياً.")
            return

        selected_msg = random.choice(channel_media_messages)

        # إذا كان بصمة صوتية (Voice)، يُرسل كما هو
        if selected_msg.voice:
            try:
                await client.send_file(target_chat, selected_msg.media, caption="")
            except Exception:
                await client.forward_messages(target_chat, selected_msg)
            return

        # إذا كان ملف صوتي، يتم تحميله ومعالجته وإرساله كملف أصلي
        file_path = None
        try:
            file_path = await client.download_media(selected_msg)
            process_audio_metadata(file_path)

            await client.send_file(
                target_chat,
                file_path,
                caption="",
                thumb=cover_cache_path if os.path.exists(cover_cache_path) else None,
                attributes=[
                    DocumentAttributeAudio(
                        duration=0,
                        title=".",
                        performer="@toe7e",
                        voice=False
                    )
                ]
            )
        except Exception as e:
            print(f"[ERROR] فشل إرسال ملف القناة: {e}")
        finally:
            if file_path and os.path.exists(file_path):
                os.remove(file_path)
        return

    # 2. أمر بحث اليوتيوب (يوت / يوتو) عبر بوت التحميل
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
            # استماع فائق السرعة لرد بوت التحميل
            for _ in range(20):
                async for msg in client.iter_messages(DOWNLOAD_BOT, limit=3):
                    if msg.id > sent_msg.id and (msg.audio or msg.voice or (msg.document and msg.file and msg.file.mime_type and 'audio' in msg.file.mime_type)):
                        audio_msg = msg
                        break
                if audio_msg:
                    break
                await asyncio.sleep(0.4)

            if not audio_msg:
                return

            if audio_msg.voice:
                await client.send_file(target_chat, audio_msg.media, caption="")
                return

            downloaded_file_path = await client.download_media(audio_msg)
            process_audio_metadata(downloaded_file_path)

            await client.send_file(
                target_chat,
                downloaded_file_path,
                caption="",
                thumb=cover_cache_path if os.path.exists(cover_cache_path) else None,
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

        except Exception as e:
            print(f"[ERROR] خطأ أثناء جلب الأغنية من بوت التحميل: {e}")

async def main():
    print("[INFO] جاري تشغيل اليوزر بوت الاحترافي...")
    await client.start()
    await initialize_bot()
    print("[SUCCESS] البوت يعمل بكامل الخصائص والسرعة القصوى الآن...")
    await client.run_until_disconnected()

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
