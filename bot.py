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

# عدد رسائل القناة التي يبحث بينها أمر غنيلي
CHANNEL_LIMIT = 150

# أقصى مدة انتظار لنتيجة يوت
YOUTUBE_TIMEOUT = 60


# ============================================================
# التحقق من المتغيرات
# ============================================================

if not API_ID:
    raise RuntimeError(
        "API_ID غير موجود في Railway Variables"
    )

if not API_HASH:
    raise RuntimeError(
        "API_HASH غير موجود في Railway Variables"
    )

if not SESSION_STRING:
    raise RuntimeError(
        "SESSION_STRING غير موجود في Railway Variables"
    )


# ============================================================
# إنشاء العميل
# ============================================================

client = TelegramClient(
    StringSession(SESSION_STRING),
    API_ID,
    API_HASH,
    connection_retries=5,
    retry_delay=2
)


# ============================================================
# فحص هل الرسالة Audio
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
        # قراءة آخر 150 رسالة من القناة
        # ----------------------------------------------------

        async for message in client.iter_messages(
            CHANNEL_USERNAME,
            limit=CHANNEL_LIMIT
        ):

            if is_audio_message(message):

                audio_messages.append(message)

        # ----------------------------------------------------
        # لا توجد أغاني
        # ----------------------------------------------------

        if not audio_messages:

            print(
                "[GHANNI] لم يتم العثور على Audio."
            )

            await client.send_message(
                chat_id,
                "ماكو ملفات صوتية متوفرة بالقناة حالياً."
            )

            return

        # ----------------------------------------------------
        # اختيار عشوائي
        # ----------------------------------------------------

        selected = random.choice(
            audio_messages
        )

        print(
            f"[GHANNI] تم اختيار الأغنية "
            f"(ID: {selected.id})"
        )

        # ----------------------------------------------------
        # إرسال الـMedia مباشرة
        #
        # لا Forward
        # لا Download
        # لا Upload
        # لا Metadata جديدة
        # لا وصف
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
# يوت
# ============================================================

async def youtube_search(
    chat_id,
    query
):

    started = time.monotonic()

    loop = asyncio.get_running_loop()

    # --------------------------------------------------------
    # Future لاستقبال ملف الصوت
    # --------------------------------------------------------

    future = loop.create_future()

    # --------------------------------------------------------
    # Listener
    #
    # مهم جداً:
    # يتم تشغيله قبل إرسال طلب البحث
    # --------------------------------------------------------

    async def bot_listener(event):

        try:

            message = event.message

            if not message:
                return

            # نريد Audio فقط
            if not is_audio_message(message):
                return

            # إذا وصل ملف صوتي
            if not future.done():

                future.set_result(
                    message
                )

                print(
                    f"[YT] تم التقاط Audio من "
                    f"{DOWNLOAD_BOT} "
                    f"(ID: {message.id})"
                )

        except Exception as e:

            print(
                f"[YT LISTENER ERROR] {e}"
            )

    event_builder = events.NewMessage(
        chats=DOWNLOAD_BOT
    )

    # ========================================================
    # تسجيل Listener قبل إرسال الطلب
    # ========================================================

    client.add_event_handler(
        bot_listener,
        event_builder
    )

    try:

        print(
            f"[YT] بدء البحث عن: {query}"
        )

        # ====================================================
        # إرسال الطلب
        # ====================================================

        request = await client.send_message(
            DOWNLOAD_BOT,
            f"يوت {query}"
        )

        print(
            f"[YT] تم إرسال الطلب إلى "
            f"{DOWNLOAD_BOT} "
            f"(ID: {request.id})"
        )

        # ====================================================
        # انتظار الأغنية
        # ====================================================

        try:

            result = await asyncio.wait_for(
                future,
                timeout=YOUTUBE_TIMEOUT
            )

        except asyncio.TimeoutError:

            print(
                "[YT] انتهت مهلة الانتظار "
                "ولم يصل Audio."
            )

            return

        # ====================================================
        # التأكد من النتيجة
        # ====================================================

        if not result:

            print(
                "[YT] لا توجد نتيجة."
            )

            return

        print(
            f"[YT] تم العثور على الأغنية "
            f"(ID: {result.id})"
        )

        # ====================================================
        # إرسال نفس الـMedia للخاص
        #
        # بدون Forward
        # بدون Download
        # بدون إعادة Upload
        # بدون تعديل الاسم
        # بدون تعديل الفنان
        # بدون وصف
        # ====================================================

        await client.send_file(
            chat_id,
            result.media,
            caption=""
        )

        print(
            f"[YT] تم إرسال الأغنية للخاص خلال "
            f"{time.monotonic() - started:.2f}s"
        )

    except Exception as e:

        print(
            f"[YT ERROR] {e}"
        )

    finally:

        # ----------------------------------------------------
        # إزالة Listener
        # ----------------------------------------------------

        try:

            client.remove_event_handler(
                bot_listener,
                event_builder
            )

        except Exception:
            pass


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

    # --------------------------------------------------------
    # الخاص فقط
    # --------------------------------------------------------

    if not event.is_private:
        return

    text = event.raw_text.strip()

    if not text:
        return

    text_lower = text.lower()

    chat_id = event.chat_id

    # ========================================================
    # أمر غنيلي
    # ========================================================

    if text == "غنيلي":

        try:

            await event.delete()

        except Exception:
            pass

        await ghannili(
            chat_id
        )

        return

    # ========================================================
    # أمر يوت
    # ========================================================

    if text_lower.startswith("يوت "):

        query = text[4:].strip()

        if not query:
            return

        try:

            await event.delete()

        except Exception:
            pass

        # تشغيل البحث بدون تعطيل استقبال الأوامر
        asyncio.create_task(
            youtube_search(
                chat_id,
                query
            )
        )

        return

    # ========================================================
    # أمر يوتو
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

    print("=" * 60)

    print(
        "[INFO] تشغيل اليوزربوت..."
    )

    print(
        "[INFO] نظام السرعة القصوى مفعل"
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
        f"[INFO] بوت التحميل: {DOWNLOAD_BOT}"
    )

    print(
        "[INFO] الأوامر:"
    )

    print(
        "       غنيلي"
    )

    print(
        "       يوت <اسم الأغنية>"
    )

    print(
        "       يوتو <اسم الأغنية>"
    )

    print("=" * 60)

    print(
        "[SUCCESS] اليوزربوت يعمل الآن."
    )

    print("=" * 60)

    # --------------------------------------------------------
    # تشغيل دائم
    # --------------------------------------------------------

    await client.run_until_disconnected()


# ============================================================
# START
# ============================================================

if __name__ == "__main__":

    asyncio.run(
        main()
    )
