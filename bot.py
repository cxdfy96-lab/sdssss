import os
import random
import asyncio
import time

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

PERFORMER = "@toe7e"
AUDIO_TITLE = "."

# عدد الملفات التي نأخذها من القناة
CHANNEL_LIMIT = 150

# عدد عمليات التحميل المتوازية أثناء تجهيز الكاش
DOWNLOAD_WORKERS = 6

# مهلة انتظار بوت التحميل
YOUTUBE_TIMEOUT = 15


# ============================================================
# العميل
# ============================================================

client = TelegramClient(
    StringSession(SESSION_STRING),
    API_ID,
    API_HASH,
    connection_retries=None,
    retry_delay=1
)


# ============================================================
# الكاش
# ============================================================

channel_media_messages = []

# الملفات التي تم تحميلها مسبقاً
audio_cache = []

# قفل حتى لا يحصل تعارض أثناء تحديث الكاش
cache_lock = asyncio.Lock()


# ============================================================
# تجهيز ملف الصوت للإرسال
# ============================================================

def get_audio_duration(message):
    try:
        if message.audio and message.audio.duration:
            return message.audio.duration
    except Exception:
        pass

    try:
        if message.document:
            for attr in message.document.attributes:
                if isinstance(attr, DocumentAttributeAudio):
                    return attr.duration or 0
    except Exception:
        pass

    return 0


def build_audio_attributes(message):
    return [
        DocumentAttributeAudio(
            duration=get_audio_duration(message),
            title=AUDIO_TITLE,
            performer=PERFORMER,
            voice=False
        )
    ]


# ============================================================
# التحقق من الملف الصوتي
# ============================================================

def is_audio_message(message):
    if not message:
        return False

    if message.voice:
        return True

    if message.audio:
        return True

    try:
        if message.document and message.document.mime_type:
            return message.document.mime_type.startswith("audio/")
    except Exception:
        pass

    return False


# ============================================================
# تحميل ملف واحد للكاش
# ============================================================

async def cache_single_audio(message, semaphore):
    async with semaphore:
        try:
            path = await client.download_media(
                message,
                file="./audio_cache/"
            )

            if not path or not os.path.exists(path):
                return None

            return {
                "message": message,
                "path": path
            }

        except Exception as e:
            print(f"[CACHE ERROR] {e}")
            return None


# ============================================================
# تجهيز كاش القناة
# ============================================================

async def initialize_bot():
    global channel_media_messages
    global audio_cache

    os.makedirs("./audio_cache", exist_ok=True)

    print("[INFO] بدء قراءة ملفات القناة...")

    try:
        messages = []

        async for message in client.iter_messages(
            CHANNEL_USERNAME,
            limit=CHANNEL_LIMIT
        ):
            if is_audio_message(message):
                messages.append(message)

        channel_media_messages = messages

        print(
            f"[INFO] تم العثور على "
            f"{len(channel_media_messages)} ملف صوتي."
        )

        # ----------------------------------------------------
        # تحميل الملفات بشكل متوازٍ
        # ----------------------------------------------------

        semaphore = asyncio.Semaphore(DOWNLOAD_WORKERS)

        tasks = [
            cache_single_audio(message, semaphore)
            for message in channel_media_messages
        ]

        results = await asyncio.gather(
            *tasks,
            return_exceptions=True
        )

        audio_cache = [
            result
            for result in results
            if isinstance(result, dict)
            and result.get("path")
            and os.path.exists(result["path"])
        ]

        print(
            f"[SUCCESS] تم تجهيز {len(audio_cache)} ملف "
            f"في الكاش."
        )

    except Exception as e:
        print(f"[ERROR] فشل تجهيز الكاش: {e}")


# ============================================================
# اختيار ملف عشوائي من الكاش
# ============================================================

def get_random_cached_audio():
    if not audio_cache:
        return None

    # نحاول اختيار ملف موجود فعلياً
    for _ in range(min(10, len(audio_cache))):
        item = random.choice(audio_cache)

        if os.path.exists(item["path"]):
            return item

    return None


# ============================================================
# إرسال الأغنية من الكاش
# ============================================================

async def send_cached_audio(chat_id, item):
    path = item["path"]
    message = item["message"]

    try:
        await client.send_file(
            chat_id,
            path,
            caption="",
            force_document=False,
            attributes=build_audio_attributes(message)
        )

        return True

    except Exception as e:
        print(f"[SEND CACHE ERROR] {e}")
        return False


# ============================================================
# انتظار رد بوت التحميل
# ============================================================

async def wait_for_audio_message(after_id, timeout=YOUTUBE_TIMEOUT):
    loop = asyncio.get_running_loop()

    future = loop.create_future()

    async def check_message(message):
        try:
            if not message:
                return

            if message.id <= after_id:
                return

            if not is_audio_message(message):
                return

            if not future.done():
                future.set_result(message)

        except Exception:
            pass

    # Handler مؤقت
    client.add_event_handler(
        check_message,
        events.NewMessage(chats=DOWNLOAD_BOT)
    )

    try:
        return await asyncio.wait_for(
            future,
            timeout=timeout
        )

    except asyncio.TimeoutError:
        return None

    finally:
        try:
            client.remove_event_handler(
                check_message,
                events.NewMessage(chats=DOWNLOAD_BOT)
            )
        except Exception:
            pass


# ============================================================
# أمر اليوتيوب
# ============================================================

async def process_youtube(chat_id, query):
    try:
        started = time.monotonic()

        sent_msg = await client.send_message(
            DOWNLOAD_BOT,
            f"يوت {query}"
        )

        print(
            f"[YT] تم إرسال الطلب: {query}"
        )

        audio_msg = await wait_for_audio_message(
            sent_msg.id,
            YOUTUBE_TIMEOUT
        )

        if not audio_msg:
            print(
                "[YT] انتهت المهلة بدون ملف صوتي."
            )
            return

        print(
            f"[YT] وصل الملف خلال "
            f"{time.monotonic() - started:.2f}s"
        )

        # ----------------------------------------------------
        # إذا كان Voice نرسله مباشرة
        # ----------------------------------------------------

        if audio_msg.voice:
            await client.send_file(
                chat_id,
                audio_msg.media,
                caption=""
            )
            return

        # ----------------------------------------------------
        # تحميل الملف ثم إعادة رفعه ببياناتنا
        # ----------------------------------------------------

        temp_path = None

        try:
            temp_path = await client.download_media(
                audio_msg,
                file="./audio_cache/"
            )

            if not temp_path or not os.path.exists(temp_path):
                print("[YT] فشل تحميل الملف.")
                return

            await client.send_file(
                chat_id,
                temp_path,
                caption="",
                force_document=False,
                attributes=build_audio_attributes(audio_msg)
            )

            print(
                f"[YT] تم الإرسال خلال "
                f"{time.monotonic() - started:.2f}s"
            )

        finally:
            if temp_path and os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except Exception:
                    pass

    except Exception as e:
        print(f"[YT ERROR] {e}")


# ============================================================
# استقبال الأوامر
# ============================================================

@client.on(events.NewMessage(incoming=True, outgoing=True))
async def handle_commands(event):

    if not event.is_private:
        return

    text_raw = event.raw_text.strip()

    if not text_raw:
        return

    text_lower = text_raw.lower()
    target_chat = event.chat_id

    # ========================================================
    # غنيلي
    # ========================================================

    if text_raw == "غنيلي":

        try:
            await event.delete()
        except Exception:
            pass

        if not audio_cache:
            await client.send_message(
                target_chat,
                "عذراً، الكاش الصوتي غير جاهز حالياً."
            )
            return

        item = get_random_cached_audio()

        if not item:
            await client.send_message(
                target_chat,
                "تعذر العثور على ملف صوتي جاهز."
            )
            return

        success = await send_cached_audio(
            target_chat,
            item
        )

        if not success:
            # محاولة ثانية بملف عشوائي آخر
            for _ in range(2):
                item = get_random_cached_audio()

                if not item:
                    break

                if await send_cached_audio(
                    target_chat,
                    item
                ):
                    break

        return

    # ========================================================
    # يوت / يوتو
    # ========================================================

    if (
        text_lower.startswith("يوت ")
        or text_lower.startswith("يوتو ")
    ):

        if text_lower.startswith("يوت "):
            query = text_raw[4:].strip()
        else:
            query = text_raw[5:].strip()

        if not query:
            return

        try:
            await event.delete()
        except Exception:
            pass

        await process_youtube(
            target_chat,
            query
        )


# ============================================================
# تنظيف الكاش عند الإغلاق
# ============================================================

async def cleanup_cache():
    try:
        if not os.path.exists("./audio_cache/"):
            return

        for filename in os.listdir("./audio_cache/"):
            path = os.path.join(
                "./audio_cache/",
                filename
            )

            try:
                if os.path.isfile(path):
                    os.remove(path)
            except Exception:
                pass

    except Exception:
        pass


# ============================================================
# التشغيل
# ============================================================

async def main():

    print("=" * 50)
    print("[INFO] تشغيل اليوزربوت...")
    print("[INFO] وضع السرعة العالية مفعّل")
    print("=" * 50)

    await client.start()

    # تجهيز الملفات قبل استقبال الأوامر
    await initialize_bot()

    print("=" * 50)
    print("[SUCCESS] اليوزربوت يعمل الآن")
    print(
        f"[CACHE] {len(audio_cache)} ملف جاهز للإرسال"
    )
    print("=" * 50)

    try:
        await client.run_until_disconnected()

    finally:
        await cleanup_cache()


# ============================================================
# START
# ============================================================

if __name__ == "__main__":
    asyncio.run(main())
