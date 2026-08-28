import os
import random
import asyncio
import time
from pathlib import Path

from telethon import TelegramClient, events
from telethon.sessions import StringSession
from telethon.tl.types import DocumentAttributeAudio


# ============================================================
# الإعدادات
# ============================================================

API_ID = int(os.environ.get("API_ID", "0"))
API_HASH = os.environ.get("API_HASH", "")
SESSION_STRING = os.environ.get("SESSION_STRING", "")

CHANNEL_USERNAME = "arggrw"
DOWNLOAD_BOT = "@MsosMbot"

# الميتاداتا المطلوبة
AUDIO_TITLE = "."
AUDIO_PERFORMER = "@toe7e"

# عدد رسائل القناة التي يبحث بينها أمر غنيلي
CHANNEL_LIMIT = 150

# مدة انتظار بوت التحميل
YOUTUBE_TIMEOUT = 30

# مجلد الملفات المؤقتة
TEMP_DIR = Path("./temp_audio")
TEMP_DIR.mkdir(parents=True, exist_ok=True)


# ============================================================
# فحص الإعدادات
# ============================================================

if not API_ID:
    raise RuntimeError("API_ID غير موجود في Railway Variables")

if not API_HASH:
    raise RuntimeError("API_HASH غير موجود في Railway Variables")

if not SESSION_STRING:
    raise RuntimeError("SESSION_STRING غير موجود في Railway Variables")


# ============================================================
# Telethon
# ============================================================

client = TelegramClient(
    StringSession(SESSION_STRING),
    API_ID,
    API_HASH,
    connection_retries=5,
    retry_delay=2
)


# ============================================================
# أدوات الصوت
# ============================================================

def is_audio_message(message):
    """
    التحقق من أن الرسالة تحتوي على Audio أو Voice.
    """

    if not message:
        return False

    if message.voice:
        return True

    if message.audio:
        return True

    try:
        if message.document:
            mime = message.document.mime_type or ""

            if mime.startswith("audio/"):
                return True

    except Exception:
        pass

    return False


def get_audio_duration(message):
    """
    استخراج مدة الصوت.
    """

    try:
        if message.audio:
            return message.audio.duration or 0
    except Exception:
        pass

    try:
        if message.document:
            for attribute in message.document.attributes:

                if isinstance(attribute, DocumentAttributeAudio):
                    return attribute.duration or 0

    except Exception:
        pass

    return 0


def audio_attributes(message):
    """
    Metadata المطلوبة:
    الاسم = .
    الفنان = @toe7e
    """

    return [
        DocumentAttributeAudio(
            duration=get_audio_duration(message),
            title=AUDIO_TITLE,
            performer=AUDIO_PERFORMER,
            voice=False
        )
    ]


# ============================================================
# إرسال Audio معدل
# ============================================================

async def send_audio_repacked(chat_id, message):
    """
    تنزيل الصوت مؤقتاً ثم إعادة رفعه كـ Audio
    بالاسم والفنان المطلوبين.
    """

    temp_file = None

    try:

        temp_file = await client.download_media(
            message,
            file=str(TEMP_DIR)
        )

        if not temp_file or not os.path.exists(temp_file):
            print("[ERROR] فشل تنزيل الملف الصوتي.")
            return False

        await client.send_file(
            chat_id,
            temp_file,
            caption="",
            force_document=False,
            attributes=audio_attributes(message)
        )

        return True

    except Exception as e:

        print(
            f"[ERROR] خطأ أثناء إعادة إرسال الصوت: {e}"
        )

        return False

    finally:

        if temp_file:

            try:

                if os.path.exists(temp_file):
                    os.remove(temp_file)

            except Exception:
                pass


# ============================================================
# غنيلي
# ============================================================

async def send_random_channel_audio(chat_id):
    """
    يأخذ أغنية عشوائية مباشرة من القناة.
    لا يوجد كاش إجباري عند بدء التشغيل.
    """

    try:

        print(
            f"[GHANNI] البحث عن أغنية من @{CHANNEL_USERNAME}..."
        )

        audio_messages = []

        async for message in client.iter_messages(
            CHANNEL_USERNAME,
            limit=CHANNEL_LIMIT
        ):

            if is_audio_message(message):
                audio_messages.append(message)

        if not audio_messages:

            print(
                "[GHANNI] لم يتم العثور على ملفات صوتية."
            )

            await client.send_message(
                chat_id,
                "ماكو ملفات صوتية متوفرة بالقناة حالياً."
            )

            return

        selected = random.choice(audio_messages)

        print(
            f"[GHANNI] تم اختيار الرسالة رقم {selected.id}"
        )

        # Voice يرسل مباشرة
        if selected.voice:

            try:

                await client.send_file(
                    chat_id,
                    selected.media,
                    caption=""
                )

                return

            except Exception as e:

                print(
                    f"[GHANNI] فشل إرسال الـVoice: {e}"
                )

        # Audio يعاد رفعه بالـMetadata المطلوبة
        success = await send_audio_repacked(
            chat_id,
            selected
        )

        if not success:

            print(
                "[GHANNI] فشل إعادة إرسال الأغنية."
            )

    except Exception as e:

        print(
            f"[GHANNI ERROR] {e}"
        )


# ============================================================
# انتظار أغنية من بوت التحميل
# ============================================================

async def wait_for_download_bot_audio(
    minimum_message_id,
    timeout=YOUTUBE_TIMEOUT
):
    """
    ينتظر رسالة صوتية جديدة من @MsosMbot.

    لا يعمل polling كل 0.4 ثانية.
    يستخدم Event من Telethon.
    """

    loop = asyncio.get_running_loop()

    future = loop.create_future()

    async def listener(event):

        try:

            message = event.message

            if not message:
                return

            if message.id <= minimum_message_id:
                return

            if not is_audio_message(message):
                return

            if not future.done():

                future.set_result(message)

        except Exception:
            pass

    # إضافة Listener مؤقت
    client.add_event_handler(
        listener,
        events.NewMessage(chats=DOWNLOAD_BOT)
    )

    try:

        return await asyncio.wait_for(
            future,
            timeout=timeout
        )

    except asyncio.TimeoutError:

        print(
            "[YT] انتهت مهلة الانتظار."
        )

        return None

    finally:

        try:

            client.remove_event_handler(
                listener,
                events.NewMessage(chats=DOWNLOAD_BOT)
            )

        except Exception:
            pass


# ============================================================
# يوت / يوتو
# ============================================================

async def process_youtube(chat_id, query):
    """
    إرسال البحث إلى بوت التحميل
    ثم انتظار ملف الصوت وإرساله للخاص.
    """

    started = time.monotonic()

    try:

        print(
            f"[YT] البحث عن: {query}"
        )

        # إرسال الطلب
        request_message = await client.send_message(
            DOWNLOAD_BOT,
            f"يوت {query}"
        )

        print(
            f"[YT] تم إرسال الطلب، رقم الرسالة: "
            f"{request_message.id}"
        )

        # انتظار الملف
        audio_message = await wait_for_download_bot_audio(
            request_message.id,
            YOUTUBE_TIMEOUT
        )

        if not audio_message:

            print(
                "[YT] لم يصل ملف صوتي من البوت."
            )

            return

        print(
            "[YT] وصل الملف من بوت التحميل."
        )

        # إذا Voice
        if audio_message.voice:

            try:

                await client.send_file(
                    chat_id,
                    audio_message.media,
                    caption=""
                )

                print(
                    f"[YT] تم إرسال الـVoice خلال "
                    f"{time.monotonic() - started:.2f}s"
                )

                return

            except Exception as e:

                print(
                    f"[YT] خطأ بإرسال الـVoice: {e}"
                )

        # إعادة رفع Audio بالـMetadata
        success = await send_audio_repacked(
            chat_id,
            audio_message
        )

        if success:

            print(
                f"[YT] تم إرسال الأغنية خلال "
                f"{time.monotonic() - started:.2f}s"
            )

        else:

            print(
                "[YT] فشل إرسال الأغنية."
            )

    except Exception as e:

        print(
            f"[YT ERROR] {e}"
        )


# ============================================================
# استقبال الرسائل
# ============================================================

@client.on(
    events.NewMessage(
        incoming=True,
        outgoing=True
    )
)
async def handle_commands(event):

    # فقط الخاص
    if not event.is_private:
        return

    text = event.raw_text.strip()

    if not text:
        return

    text_lower = text.lower()

    chat_id = event.chat_id

    # ========================================================
    # غنيلي
    # ========================================================

    if text == "غنيلي":

        try:
            await event.delete()
        except Exception:
            pass

        # تنفيذ مباشر بدون Cache
        await send_random_channel_audio(
            chat_id
        )

        return

    # ========================================================
    # يوت
    # ========================================================

    if text_lower.startswith("يوت "):

        query = text[4:].strip()

        if not query:
            return

        try:
            await event.delete()
        except Exception:
            pass

        # تشغيل المهمة
        asyncio.create_task(
            process_youtube(
                chat_id,
                query
            )
        )

        return

    # ========================================================
    # يوتو
    # ========================================================

    if text_lower.startswith("يوتو "):

        query = text[5:].strip()

        if not query:
            return

        try:
            await event.delete()
        except Exception:
            pass

        asyncio.create_task(
            process_youtube(
                chat_id,
                query
            )
        )

        return


# ============================================================
# تنظيف الملفات المؤقتة
# ============================================================

def cleanup_temp_files():

    try:

        if not TEMP_DIR.exists():
            return

        for file in TEMP_DIR.iterdir():

            try:

                if file.is_file():
                    file.unlink()

            except Exception:
                pass

    except Exception:
        pass


# ============================================================
# التشغيل
# ============================================================

async def main():

    print("=" * 55)
    print("[INFO] تشغيل اليوزربوت...")
    print("[INFO] نظام الصوت السريع مفعل")
    print("=" * 55)

    try:

        # الاتصال بالحساب
        await client.start()

        print(
            "[SUCCESS] تم الاتصال بحساب Telegram بنجاح."
        )

        print(
            f"[INFO] قناة الأغاني: @{CHANNEL_USERNAME}"
        )

        print(
            f"[INFO] بوت التحميل: {DOWNLOAD_BOT}"
        )

        print(
            "[INFO] الأوامر: غنيلي / يوت / يوتو"
        )

        print("=" * 55)
        print("[SUCCESS] اليوزربوت يعمل الآن.")
        print("=" * 55)

        await client.run_until_disconnected()

    except Exception as e:

        print(
            f"[FATAL ERROR] {e}"
        )

        raise

    finally:

        cleanup_temp_files()


# ============================================================
# START
# ============================================================

if __name__ == "__main__":

    asyncio.run(main())
