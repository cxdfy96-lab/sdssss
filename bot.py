import os
import random
import asyncio
import time

from telethon import TelegramClient, events
from telethon.sessions import StringSession


# ============================================================
# إعدادات Railway
# ============================================================

API_ID = int(os.environ.get("API_ID", "0"))
API_HASH = os.environ.get("API_HASH", "")
SESSION_STRING = os.environ.get("SESSION_STRING", "")


# ============================================================
# إعدادات السورس
# ============================================================

CHANNEL_USERNAME = "arggrw"
DOWNLOAD_BOT = "@MsosMbot"

CHANNEL_LIMIT = 150
YOUTUBE_TIMEOUT = 60


# ============================================================
# التحقق من المتغيرات
# ============================================================

if not API_ID:
    raise RuntimeError("API_ID غير موجود في Railway Variables")

if not API_HASH:
    raise RuntimeError("API_HASH غير موجود في Railway Variables")

if not SESSION_STRING:
    raise RuntimeError("SESSION_STRING غير موجود في Railway Variables")


# ============================================================
# إنشاء Telegram Client
# ============================================================

client = TelegramClient(
    StringSession(SESSION_STRING),
    API_ID,
    API_HASH,
    connection_retries=5,
    retry_delay=2
)


# ============================================================
# طلبات يوت الحالية
#
# كل طلب يحتوي:
# chat_id = الخاص الذي كتب الأمر
# request_id = رقم رسالة الطلب إلى البوت
# created = وقت إنشاء الطلب
# ============================================================

youtube_requests = {}

youtube_lock = asyncio.Lock()


# ============================================================
# التحقق من الرسالة الصوتية
# ============================================================

def is_audio_message(message):

    if not message:
        return False

    # Voice
    if message.voice:
        return True

    # Audio
    if message.audio:
        return True

    # Document بصيغة Audio
    try:

        if message.document:

            mime_type = message.document.mime_type or ""

            if mime_type.startswith("audio/"):
                return True

    except Exception:
        pass

    return False


# ============================================================
# الحصول على نوع الرسالة
# ============================================================

def get_media_type(message):

    if not message:
        return "UNKNOWN"

    if message.voice:
        return "VOICE"

    if message.audio:
        return "AUDIO"

    if message.document:
        return "DOCUMENT"

    if message.photo:
        return "PHOTO"

    if message.video:
        return "VIDEO"

    return "TEXT"


# ============================================================
# Listener دائم لبوت التحميل
#
# هذا أهم جزء في الكود
#
# لا ننتظر البوت بعد إرسال الطلب.
# الـListener موجود من بداية تشغيل السورس.
# ============================================================

@client.on(
    events.NewMessage(
        incoming=True,
        chats=DOWNLOAD_BOT
    )
)
async def download_bot_listener(event):

    try:

        message = event.message

        if not message:
            return

        print("=" * 55)

        print(
            f"[BOT] وصلت رسالة جديدة من {DOWNLOAD_BOT}"
        )

        print(
            f"[BOT] Message ID: {message.id}"
        )

        print(
            f"[BOT] Type: {get_media_type(message)}"
        )

        # ----------------------------------------------------
        # إذا ليست Audio نتجاهلها
        # ----------------------------------------------------

        if not is_audio_message(message):

            print(
                "[BOT] الرسالة ليست Audio - تم تجاهلها."
            )

            print("=" * 55)

            return

        print(
            "[BOT] هذه الرسالة Audio."
        )

        # ----------------------------------------------------
        # البحث عن طلب يوت المناسب
        # ----------------------------------------------------

        async with youtube_lock:

            if not youtube_requests:

                print(
                    "[BOT] لا توجد طلبات يوت منتظرة."
                )

                print("=" * 55)

                return

            # ------------------------------------------------
            # نأخذ أقدم طلب منتظر
            # ------------------------------------------------

            request_key = next(
                iter(youtube_requests)
            )

            request_data = youtube_requests[
                request_key
            ]

            target_chat = request_data["chat_id"]

            request_time = request_data["created"]

            print(
                f"[BOT] تم ربط Audio بطلب يوت."
            )

            print(
                f"[BOT] Target chat: {target_chat}"
            )

        # ----------------------------------------------------
        # إرسال الـMedia مباشرة للخاص
        # ----------------------------------------------------

        try:

            print(
                "[BOT] جاري إرسال Audio إلى الخاص..."
            )

            send_started = time.monotonic()

            await client.send_file(
                target_chat,
                message.media,
                caption=""
            )

            print(
                "[BOT] تم إرسال Audio بنجاح."
            )

            print(
                f"[BOT] زمن الإرسال: "
                f"{time.monotonic() - send_started:.2f}s"
            )

            print(
                f"[BOT] الزمن الكلي منذ الطلب: "
                f"{time.monotonic() - request_time:.2f}s"
            )

        except Exception as e:

            print(
                f"[BOT ERROR] فشل إرسال Audio: {e}"
            )

        # ----------------------------------------------------
        # حذف الطلب بعد المعالجة
        # ----------------------------------------------------

        async with youtube_lock:

            youtube_requests.pop(
                request_key,
                None
            )

        print("=" * 55)

    except Exception as e:

        print(
            f"[LISTENER ERROR] {e}"
        )


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

        # ----------------------------------------------------
        # قراءة آخر 150 رسالة
        # ----------------------------------------------------

        async for message in client.iter_messages(
            CHANNEL_USERNAME,
            limit=CHANNEL_LIMIT
        ):

            if is_audio_message(message):

                audio_messages.append(message)

        # ----------------------------------------------------
        # لا توجد ملفات
        # ----------------------------------------------------

        if not audio_messages:

            print(
                "[GHANNI] لم يتم العثور على Audio."
            )

            await client.send_message(
                chat_id,
                "ماكو ملفات صوتية بالقناة حالياً."
            )

            return

        # ----------------------------------------------------
        # اختيار عشوائي
        # ----------------------------------------------------

        selected = random.choice(
            audio_messages
        )

        print(
            f"[GHANNI] تم اختيار الرسالة: "
            f"{selected.id}"
        )

        # ----------------------------------------------------
        # إرسال Media مباشرة
        #
        # بدون Forward
        # بدون Download
        # بدون تعديل
        # بدون وصف
        # ----------------------------------------------------

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
# إرسال طلب يوت
# ============================================================

async def youtube_search(chat_id, query):

    started = time.monotonic()

    try:

        print("=" * 55)

        print(
            f"[YT] بدء البحث: {query}"
        )

        # ----------------------------------------------------
        # إنشاء رقم داخلي للطلب
        # ----------------------------------------------------

        request_key = (
            f"{chat_id}:"
            f"{time.time_ns()}"
        )

        # ----------------------------------------------------
        # تسجيل الطلب قبل إرسال الرسالة
        #
        # مهم جدًا لأن البوت سريع.
        # ----------------------------------------------------

        async with youtube_lock:

            youtube_requests[
                request_key
            ] = {
                "chat_id": chat_id,
                "query": query,
                "created": time.monotonic()
            }

        print(
            "[YT] تم تسجيل الطلب في قائمة الانتظار."
        )

        # ----------------------------------------------------
        # إرسال الطلب إلى البوت
        # ----------------------------------------------------

        sent = await client.send_message(
            DOWNLOAD_BOT,
            f"يوت {query}"
        )

        print(
            f"[YT] تم إرسال الطلب إلى "
            f"{DOWNLOAD_BOT}"
        )

        print(
            f"[YT] Request Message ID: "
            f"{sent.id}"
        )

        print(
            "[YT] بانتظار Audio من البوت..."
        )

        # ----------------------------------------------------
        # انتظار وصول الـListener للنتيجة
        # ----------------------------------------------------

        deadline = time.monotonic() + YOUTUBE_TIMEOUT

        while time.monotonic() < deadline:

            async with youtube_lock:

                if request_key not in youtube_requests:

                    print(
                        "[YT] تم استلام ومعالجة النتيجة."
                    )

                    print("=" * 55)

                    return

            await asyncio.sleep(0.1)

        # ----------------------------------------------------
        # انتهت المهلة
        # ----------------------------------------------------

        async with youtube_lock:

            youtube_requests.pop(
                request_key,
                None
            )

        print(
            "[YT] انتهت مهلة الانتظار."
        )

        print(
            "[YT] لم يتم التقاط Audio من البوت."
        )

        print("=" * 55)

    except Exception as e:

        async with youtube_lock:

            youtube_requests.pop(
                request_key,
                None
            )

        print(
            f"[YT ERROR] {e}"
        )


# ============================================================
# استقبال أوامر المستخدم
# ============================================================

@client.on(
    events.NewMessage(
        incoming=True,
        outgoing=True
    )
)
async def command_handler(event):

    try:

        # ----------------------------------------------------
        # الخاص فقط
        # ----------------------------------------------------

        if not event.is_private:
            return

        text = event.raw_text.strip()

        if not text:
            return

        text_lower = text.lower()

        chat_id = event.chat_id

        # ====================================================
        # غنيلي
        # ====================================================

        if text == "غنيلي":

            print(
                "[COMMAND] غنيلي"
            )

            try:
                await event.delete()
            except Exception:
                pass

            await ghannili(
                chat_id
            )

            return

        # ====================================================
        # يوت
        # ====================================================

        if text_lower.startswith("يوت "):

            query = text[4:].strip()

            if not query:
                return

            print(
                f"[COMMAND] يوت: {query}"
            )

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

        # ====================================================
        # يوتو
        # ====================================================

        if text_lower.startswith("يوتو "):

            query = text[5:].strip()

            if not query:
                return

            print(
                f"[COMMAND] يوتو: {query}"
            )

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

    except Exception as e:

        print(
            f"[COMMAND ERROR] {e}"
        )


# ============================================================
# التشغيل
# ============================================================

async def main():

    print("=" * 60)

    print(
        "[INFO] تشغيل اليوزربوت..."
    )

    print(
        "[INFO] نظام Audio السريع مفعل"
    )

    print(
        "[INFO] Listener دائم لـ MsosMbot مفعل"
    )

    print(
        "[INFO] بدون Cache"
    )

    print(
        "[INFO] بدون Download"
    )

    print(
        "[INFO] بدون إعادة رفع"
    )

    print("=" * 60)

    # --------------------------------------------------------
    # الاتصال
    # --------------------------------------------------------

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
        "[INFO] Listener جاهز لاستقبال نتائج البوت."
    )

    print("=" * 60)

    print(
        "[SUCCESS] اليوزربوت يعمل الآن."
    )

    print("=" * 60)

    await client.run_until_disconnected()


# ============================================================
# START
# ============================================================

if __name__ == "__main__":

    asyncio.run(
        main()
    )
