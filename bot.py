import os
import random
from telethon import TelegramClient, events
from telethon.sessions import StringSession

# جلب بيانات الاتصال من متغيرات البيئة في Railway
API_ID = int(os.environ.get("API_ID", 0))
API_HASH = os.environ.get("API_HASH", "")
SESSION_STRING = os.environ.get("SESSION_STRING", "")

# معرف قناتك التي توجد بها الأغاني والفويسات
CHANNEL_USERNAME = "arggrw"

# قائمة الكلمات المفتاحية التي يستجيب لها البوت
TRIGGER_WORDS = ["حزين", "حزن", "غنيلي", "اغنيه", "أغنية", "صوت", "صوتية", "موسيقى", "طرب", "رومانسية", "هادئ"]

# بدء جلسة اليوزر بوت باستخدام StringSession
client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)

# تخزين مؤقت لرسائل القناة
channel_media_messages = []

async def cache_channel_media():
    global channel_media_messages
    try:
        print("جاري جلب الملفات الصوتية والبصمات من القناة...")
        async for message in client.iter_messages(CHANNEL_USERNAME, limit=100):
            if message.audio or message.voice:
                channel_media_messages.append(message)
        print(f"تم تحميل {len(channel_media_messages)} ملفاً صوتياً بنجاح.")
    except Exception as e:
        print(f"خطأ أثناء جلب ملفات القناة: {e}")

@client.on(events.NewMessage(outgoing=False, incoming=True))
async def handle_incoming_message(event):
    # نتأكد أن المحادثة خاصة (محادثة شخصية مع المستخدم)
    if not event.is_private:
        return

    text_raw = event.raw_text.strip()
    text_lower = text_raw.lower()
    
    # التحقق مما إذا كانت الرسالة تحتوي على إحدى الكلمات المفتاحية
    matched_word = next((word for word in TRIGGER_WORDS if word in text_lower), None)
    
    if matched_word:
        if not channel_media_messages:
            await event.reply("عذراً، لم أتمكن من العثور على ملفات صوتية في القناة حالياً.")
            return

        # اختيار ملف عشوائي من القناة (أغنية أو فويس)
        selected_msg = random.choice(channel_media_messages)
        
        # جعل اسم الأغنية مرتبطاً بما كتبه المستخدم مع تنسيق مرتب
        song_title = f"{text_raw} 🎶"
        caption = f"🎵 **{song_title}**\n👤 **Artist:** @toe7e"

        try:
            # إرسال الملف الصوتي مع التنسيق والكابتشن مباشرة
            await client.send_file(
                event.chat_id,
                selected_msg.media,
                caption=caption,
                parse_mode="md"
            )
        except Exception as e:
            # طريقة احتياطية في حال حدث خطأ بالإرسال المباشر
            await event.respond(caption)
            await client.forward_messages(event.chat_id, selected_msg)

async def main():
    print("جاري تشغيل اليوزر بوت...")
    await client.start()
    await cache_channel_media()
    print("البوت يعمل الآن وجاهز للاستماع...")
    await client.run_until_disconnected()

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
