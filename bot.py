import os
import random
import asyncio
from telethon import TelegramClient, events
from telethon.sessions import StringSession
from telethon.tl.types import DocumentAttributeAudio

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

    # 1. أمر "غنيلي" (جلب عشوائي فائق السرعة من القناة كملف أصلي مستقل)
    if text_raw == "غنيلي":
        try:
            await event.delete()
        except Exception:
            pass

        if not channel_media_messages:
            await client.send_message(target_chat, "عذراً، لم يتم العثور على ملفات صوتية في القناة حالياً.")
            return

        selected_msg = random.choice(channel_media_messages)

        if selected_msg.voice:
            try:
                await client.send_file(target_chat, selected_msg.media, caption="")
            except Exception:
                await client.forward_messages(target_chat, selected_msg)
            return

        try:
            # تحميل الملف مؤقتاً وإعادة إرساله كملف أصلي مستقل تماماً مع تعديل الميتا داتا وثبات الغلاف الأصلي
            downloaded_path = await client.download_media(selected_msg)
            
            await client.send_file(
                target_chat,
                downloaded_path,
                caption="",
                attributes=[
                    DocumentAttributeAudio(
                        duration=selected_msg.audio.duration if selected_msg.audio and selected_msg.audio.duration else 0,
                        title=".",          # العنوان نقطة
                        performer="@toe7e", # الفنان اليوزر المتفق عليه
                        voice=False
                    )
                ]
            )
            
            if downloaded_path and os.path.exists(downloaded_path):
                os.remove(downloaded_path)

        except Exception as e:
            print(f"[ERROR] فشل إرسال ملف القناة: {e}")
            try:
                await client.forward_messages(target_chat, selected_msg)
            except:
                pass
        return

    # 2. أمر بحث اليوتيوب (يوت / يوتو) عبر بوت التحميل وسحبه للخاص فوراً
    if text_lower.startswith("يوت ") or text_lower.startswith("يوتو "):
        query = text_raw[4:].strip() if text_lower.startswith("يوت ") else text_raw[5:].strip()
        if not query:
            return

        try:
            await event.delete()
        except Exception:
            pass

        try:
            # إرسال الأمر لبوت التحميل ومراقبة الرد الفوري
            sent_msg = await client.send_message(DOWNLOAD_BOT, f"يوت {query}")
            
            audio_msg = None
            for _ in range(25): # وقت انتظار كافٍ لاستجابة بوت التحميل
                messages = await client.get_messages(DOWNLOAD_BOT, limit=5)
                for msg in messages:
                    if msg.id > sent_msg.id and (msg.audio or msg.voice or (msg.document and msg.file and msg.file.mime_type and 'audio' in msg.file.mime_type)):
                        audio_msg = msg
                        break
                if audio_msg:
                    break
                await asyncio.sleep(0.4)

            if not audio_msg:
                print("[WARNING] لم يتم العثور على ملف صوتي من بوت التحميل.")
                return

            if audio_msg.voice:
                await client.send_file(target_chat, audio_msg.media, caption="")
                return

            # تحميل الملف الوارد من بوت التحميل ومعالجته وإرساله كملف أصلي مستقل للخاص
            downloaded_file_path = await client.download_media(audio_msg)

            await client.send_file(
                target_chat,
                downloaded_file_path,
                caption="",
                attributes=[
                    DocumentAttributeAudio(
                        duration=audio_msg.audio.duration if audio_msg.audio and audio_msg.audio.duration else 0,
                        title=".",          # العنوان نقطة
                        performer="@toe7e", # الفنان اليوزر المتفق عليه
                        voice=False
                    )
                ]
            )

            if downloaded_file_path and os.path.exists(downloaded_file_path):
                os.remove(downloaded_file_path)

        except Exception as e:
            print(f"[ERROR] أثناء جلب الأغنية من بوت التحميل: {e}")

async def main():
    print("[INFO] تشغيل اليوزر بوت النهائي بأعلى كفاءة...")
    await client.start()
    await initialize_bot()
    print("[SUCCESS] البوت يعمل الآن بكامل الميزات وبدون أي أخطاء...")
    await client.run_until_disconnected()

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
