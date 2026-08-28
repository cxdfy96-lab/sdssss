import os
import random
import asyncio
import time

from telethon import TelegramClient, events
from telethon.sessions import StringSession


# ============================================================
# الإعدادات
# ============================================================

API_ID = int(os.environ.get("API_ID", "0"))
API_HASH = os.environ.get("API_HASH", "")
SESSION_STRING = os.environ.get("SESSION_STRING", "")

CHANNEL_USERNAME = "arggrw"
DOWNLOAD_BOT = "@MsosMbot"

CHANNEL_LIMIT = 150
YOUTUBE_TIMEOUT = 60


# ============================================================
# التحقق من المتغيرات
# ============================================================

if not API_ID:
    raise RuntimeError("API_ID غير موجود")

if not API_HASH:
    raise RuntimeError("API_HASH غير موجود")

if not SESSION_STRING:
    raise RuntimeError("SESSION_STRING غير موجود")


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
# التحقق من الصوت
# ============================================================

def is_audio_message(message):

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


# ============================================================
# غنيلي
# ============================================================

async def ghannili(chat_id):

    started = time.monotonic()

    try:

        print(
            f"[GHANNI] البحث في @{CHANNEL_USERNAME}..."
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
                "[GHANNI] لا توجد ملفات صوتية."
            )

            return

        selected = random.choice(audio_messages)

        print(
            f"[GHANNI] تم اختيار الرسالة {selected.id}"
        )

        # ====================================================
        # إرسال نفس الـMedia بدون Forward
        # ====================================================

        await client.send_file(
            chat_id,
            selected.media,
            caption=""
        )

        print(
            f"[GHANNI] تم الإرسال خلال "
            f"{time.monotonic() - started:.2f}s"
        )

    except Exception as e:

        print(
            f"[GHANNI ERROR] {e}"
        )


# ============================================================
# انتظار نتيجة بوت التحميل
# ============================================================

async def wait_for_bot_result(
    after_message_id,
    timeout=YOUTUBE_TIMEOUT
):

    loop = asyncio.get_running_loop()

    future = loop.create_future()

    async def handler(event):

        try:

            message = event.message

            if not message:
                return

            # نريد رسالة أحدث من طلب البحث
            if message.id <= after_message_id:
                return

            # نريد Audio فقط
            if not is_audio_message(message):
                return

            if not future.done():

                future.set_result(message)

        except Exception:
            pass

    event_builder = events.NewMessage(
        chats=DOWNLOAD_BOT
    )

    client.add_event_handler(
        handler,
        event_builder
    )

    try:

        result = await asyncio.wait_for(
            future,
            timeout=timeout
        )

        return result

    except asyncio.TimeoutError:

        print(
            "[YT] لم يصل ملف صوتي خلال المهلة."
        )

        return None

    finally:

        try:
            client.remove_event_handler(
                handler,
                event_builder
            )
        except Exception:
            pass


# ============================================================
# يوت
# ============================================================

async def youtube_search(
    chat_id,
    query
):

    started = time.monotonic()

    try:

        print(
            f"[YT] البحث عن: {query}"
        )

        # ====================================================
        # إرسال الطلب للبوت
        # ====================================================

        request = await client.send_message(
            DOWNLOAD_BOT,
            f"يوت {query}"
        )

        print(
            f"[YT] تم إرسال الطلب إلى {DOWNLOAD_BOT}"
        )

        # ====================================================
        # انتظار الأغنية
        # ====================================================

        result = await wait_for_bot_result(
            request.id
        )

        if not result:

            print(
                "[YT] لم يتم العثور على نتيجة."
            )

            return

        print(
            f"[YT] وصلت النتيجة: {result.id}"
        )

        # ====================================================
        # إرسال نفس الـMedia
        #
        # بدون Forward
        # بدون Download
        # بدون Upload
        # بدون تغيير Metadata
        # بدون وصف
        # ====================================================

        await client.send_file(
            chat_id,
            result.media,
            caption=""
        )

        print(
            f"[YT] تم إرسال الأغنية خلال "
            f"{time.monotonic() - started:.2f}s"
        )

    except Exception as e:

        print(
            f"[YT ERROR] {e}"
        )


# ============================================================
# استقبال الأوامر
# ============================================================

@client.on(
    events.NewMessage(
        incoming=True,
        outgoing=True
    )
)
async def command_handler(event):

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

        await ghannili(chat_id)

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

        asyncio.create_task(
            youtube_search(
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
            youtube_search(
                chat_id,
                query
            )
        )

        return


# ============================================================
# التشغيل
# ============================================================

async def main():

    print("=" * 55)
    print("[INFO] تشغيل اليوزربوت...")
    print("[INFO] وضع السرعة القصوى مفعل")
    print("[INFO] بدون Cache")
    print("[INFO] بدون Download")
    print("[INFO] بدون إعادة رفع")
    print("=" * 55)

    await client.start()

    print(
        "[SUCCESS] تم الاتصال بحساب Telegram."
    )

    print(
        f"[INFO] قناة غنيلي: @{CHANNEL_USERNAME}"
    )

    print(
        f"[INFO] بوت البحث: {DOWNLOAD_BOT}"
    )

    print(
        "[INFO] الأوامر: غنيلي / يوت / يوتو"
    )

    print("=" * 55)
    print("[SUCCESS] اليوزربوت يعمل.")
    print("=" * 55)

    await client.run_until_disconnected()


# ============================================================
# START
# ============================================================

if __name__ == "__main__":
    asyncio.run(main())
