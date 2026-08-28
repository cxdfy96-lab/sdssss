import os
import asyncio
import time

from telethon import TelegramClient, events
from telethon.sessions import StringSession


# ============================================================
# CONFIG
# ============================================================

API_ID = int(os.environ.get("API_ID", "0"))
API_HASH = os.environ.get("API_HASH", "")
SESSION_STRING = os.environ.get("SESSION_STRING", "")

CHANNEL_USERNAME = "arggrw"
DOWNLOAD_BOT = "MsosMbot"

YOUTUBE_TIMEOUT = 90


# ============================================================
# CHECK CONFIG
# ============================================================

if not API_ID:
    raise RuntimeError("API_ID غير موجود")

if not API_HASH:
    raise RuntimeError("API_HASH غير موجود")

if not SESSION_STRING:
    raise RuntimeError("SESSION_STRING غير موجود")


# ============================================================
# CLIENT
# ============================================================

client = TelegramClient(
    StringSession(SESSION_STRING),
    API_ID,
    API_HASH,
    connection_retries=10,
    retry_delay=2
)


# ============================================================
# GLOBALS
# ============================================================

DOWNLOAD_BOT_ID = None
DOWNLOAD_BOT_ENTITY = None

# الطلبات المنتظرة
pending_youtube = {}

# قفل بسيط
youtube_lock = asyncio.Lock()


# ============================================================
# AUDIO CHECK
# ============================================================

def is_audio(message):

    if not message:
        return False

    if message.audio:
        return True

    if message.voice:
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
# MEDIA TYPE
# ============================================================

def media_type(message):

    if message.audio:
        return "AUDIO"

    if message.voice:
        return "VOICE"

    if message.document:
        return "DOCUMENT"

    if message.video:
        return "VIDEO"

    if message.photo:
        return "PHOTO"

    return "TEXT"


# ============================================================
# DOWNLOAD BOT LISTENER
#
# هذا Listener عام وليس chats=...
# حتى نضمن التقاط رسالة البوت.
# ============================================================

@client.on(
    events.NewMessage(
        incoming=True
    )
)
async def download_bot_listener(event):

    global DOWNLOAD_BOT_ID

    try:

        message = event.message

        if not message:
            return

        sender_id = event.sender_id

        # ----------------------------------------------------
        # تجاهل أي رسالة ليست من بوت التحميل
        # ----------------------------------------------------

        if DOWNLOAD_BOT_ID is None:
            return

        if sender_id != DOWNLOAD_BOT_ID:
            return

        print("")
        print("==================================================")
        print("[BOT] وصلت رسالة من MsosMbot")
        print(f"[BOT] Message ID : {message.id}")
        print(f"[BOT] Type       : {media_type(message)}")
        print(f"[BOT] Sender ID  : {sender_id}")

        # ----------------------------------------------------
        # إذا ليست Audio
        # ----------------------------------------------------

        if not is_audio(message):

            print("[BOT] ليست رسالة صوتية.")
            print("==================================================")

            return

        print("[BOT] تم العثور على ملف صوتي.")

        # ----------------------------------------------------
        # البحث عن طلب يوت منتظر
        # ----------------------------------------------------

        async with youtube_lock:

            if not pending_youtube:

                print(
                    "[BOT] لا يوجد طلب يوت منتظر حاليًا."
                )

                print("==================================================")

                return

            # أخذ أقدم طلب
            request_id = next(
                iter(pending_youtube)
            )

            request = pending_youtube[
                request_id
            ]

            target_chat = request["chat_id"]

            started_at = request["started_at"]

            # نحذفه فورًا حتى لا تتم معالجة نفس الطلب مرتين
            del pending_youtube[
                request_id
            ]

        # ----------------------------------------------------
        # إرسال الصوت للخاص
        #
        # نستخدم message.media مباشرة:
        # بدون Forward
        # بدون Caption
        # بدون تعديل الاسم
        # بدون تعديل الفنان
        # ----------------------------------------------------

        print(
            f"[BOT] الهدف: {target_chat}"
        )

        print(
            "[BOT] جاري إرسال الملف إلى الخاص..."
        )

        send_start = time.monotonic()

        try:

            await client.send_file(
                target_chat,
                message.media,
                caption=None,
                force_document=False
            )

            send_time = (
                time.monotonic()
                - send_start
            )

            total_time = (
                time.monotonic()
                - started_at
            )

            print(
                f"[BOT] تم الإرسال بنجاح."
            )

            print(
                f"[BOT] زمن الإرسال: {send_time:.2f}s"
            )

            print(
                f"[BOT] الزمن الكلي: {total_time:.2f}s"
            )

        except Exception as send_error:

            print(
                f"[BOT ERROR] فشل إرسال Media: "
                f"{send_error}"
            )

        print("==================================================")
        print("")

    except Exception as e:

        print(
            f"[LISTENER ERROR] {e}"
        )


# ============================================================
# GHANNILI
# ============================================================

async def ghannili(chat_id):

    try:

        print("[GHANNI] البحث عن أغنية...")

        selected = None

        # ----------------------------------------------------
        # نبحث عن أول مجموعة ملفات صوتية
        # ----------------------------------------------------

        audio_messages = []

        async for message in client.iter_messages(
            CHANNEL_USERNAME,
            limit=150
        ):

            if is_audio(message):

                audio_messages.append(
                    message
                )

        # ----------------------------------------------------
        # لا توجد أغاني
        # ----------------------------------------------------

        if not audio_messages:

            await client.send_message(
                chat_id,
                "ماكو ملفات صوتية بالقناة حاليًا."
            )

            print(
                "[GHANNI] لا توجد ملفات صوتية."
            )

            return

        # ----------------------------------------------------
        # اختيار عشوائي
        # ----------------------------------------------------

        import random

        selected = random.choice(
            audio_messages
        )

        print(
            f"[GHANNI] الرسالة المختارة: "
            f"{selected.id}"
        )

        # ----------------------------------------------------
        # إرسال مباشر
        #
        # بدون Forward
        # بدون Caption
        # بدون تعديل Metadata
        # ----------------------------------------------------

        await client.send_file(
            chat_id,
            selected.media,
            caption=None
        )

        print(
            "[GHANNI] تم الإرسال."
        )

    except Exception as e:

        print(
            f"[GHANNI ERROR] {e}"
        )


# ============================================================
# YOUTUBE REQUEST
# ============================================================

async def youtube_request(
    chat_id,
    query
):

    request_id = (
        f"{chat_id}_"
        f"{time.time_ns()}"
    )

    started_at = time.monotonic()

    try:

        print("")
        print("==================================================")
        print(
            f"[YT] البحث عن: {query}"
        )

        # ----------------------------------------------------
        # مهم:
        # نسجل الطلب قبل إرسال الرسالة للبوت.
        # ----------------------------------------------------

        async with youtube_lock:

            pending_youtube[
                request_id
            ] = {
                "chat_id": chat_id,
                "query": query,
                "started_at": started_at
            }

        print(
            "[YT] تم تسجيل الطلب."
        )

        # ----------------------------------------------------
        # إرسال الأمر إلى البوت
        # ----------------------------------------------------

        sent = await client.send_message(
            DOWNLOAD_BOT_ENTITY,
            f"يوت {query}"
        )

        print(
            "[YT] تم إرسال الطلب للبوت."
        )

        print(
            f"[YT] Message ID: {sent.id}"
        )

        print(
            "[YT] أنتظر نتيجة البوت..."
        )

        # ----------------------------------------------------
        # انتظار Listener
        # ----------------------------------------------------

        deadline = (
            time.monotonic()
            + YOUTUBE_TIMEOUT
        )

        while time.monotonic() < deadline:

            async with youtube_lock:

                if request_id not in pending_youtube:

                    print(
                        "[YT] تمت معالجة الأغنية."
                    )

                    print(
                        "=================================================="
                    )

                    return

            await asyncio.sleep(
                0.05
            )

        # ----------------------------------------------------
        # Timeout
        # ----------------------------------------------------

        async with youtube_lock:

            pending_youtube.pop(
                request_id,
                None
            )

        print(
            "[YT] انتهت المهلة."
        )

        print(
            "[YT] البوت لم يرسل Audio يمكن التقاطه."
        )

        print(
            "=================================================="
        )

    except Exception as e:

        async with youtube_lock:

            pending_youtube.pop(
                request_id,
                None
            )

        print(
            f"[YT ERROR] {e}"
        )

        print(
            "=================================================="
        )


# ============================================================
# USER COMMANDS
# ============================================================

@client.on(
    events.NewMessage(
        incoming=True,
        outgoing=True
    )
)
async def command_handler(event):

    try:

        if not event.is_private:
            return

        text = (
            event.raw_text
            or ""
        ).strip()

        if not text:
            return

        chat_id = event.chat_id

        text_lower = text.lower()

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

            # تشغيل بدون تعطيل Listener
            asyncio.create_task(
                ghannili(
                    chat_id
                )
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
                f"[COMMAND] يوت {query}"
            )

            try:
                await event.delete()
            except Exception:
                pass

            asyncio.create_task(
                youtube_request(
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
                f"[COMMAND] يوتو {query}"
            )

            try:
                await event.delete()
            except Exception:
                pass

            asyncio.create_task(
                youtube_request(
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
# MAIN
# ============================================================

async def main():

    global DOWNLOAD_BOT_ID
    global DOWNLOAD_BOT_ENTITY

    print("")
    print("==================================================")
    print("[INFO] تشغيل اليوزربوت")
    print("==================================================")

    # --------------------------------------------------------
    # الاتصال
    # --------------------------------------------------------

    await client.start()

    print(
        "[SUCCESS] تم الاتصال بتليجرام."
    )

    # --------------------------------------------------------
    # الحصول على Entity للبوت
    # --------------------------------------------------------

    print(
        "[INFO] جاري التعرف على MsosMbot..."
    )

    DOWNLOAD_BOT_ENTITY = await client.get_entity(
        DOWNLOAD_BOT
    )

    DOWNLOAD_BOT_ID = (
        DOWNLOAD_BOT_ENTITY.id
    )

    print(
        "[SUCCESS] تم التعرف على البوت."
    )

    print(
        f"[INFO] MsosMbot ID = "
        f"{DOWNLOAD_BOT_ID}"
    )

    print(
        f"[INFO] Channel = "
        f"@{CHANNEL_USERNAME}"
    )

    print("")
    print("==================================================")
    print("[SUCCESS] اليوزربوت جاهز.")
    print("[SUCCESS] Listener الخاص بـ MsosMbot يعمل.")
    print("[SUCCESS] غنيلي يعمل.")
    print("[SUCCESS] يوت يعمل.")
    print("==================================================")
    print("")

    # --------------------------------------------------------
    # التشغيل المستمر
    # --------------------------------------------------------

    await client.run_until_disconnected()


# ============================================================
# START
# ============================================================

if __name__ == "__main__":

    try:

        asyncio.run(
            main()
        )

    except KeyboardInterrupt:

        print(
            "[INFO] تم إيقاف البرنامج."
        )

    except Exception as e:

        print(
            f"[FATAL ERROR] {e}"
        )
