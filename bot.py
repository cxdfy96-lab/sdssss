import os
import random
import asyncio
from telethon import TelegramClient, events
from telethon.sessions import StringSession

# بيانات الاتصال الأساسية
API_ID = int(os.environ.get("API_ID", 0))
API_HASH = os.environ.get("API_HASH", "")

# قراءة الجلسات من متغير البيئة SESSION_STRING (مفصولات بفاصلة ,)
SESSION_STRINGS_RAW = os.environ.get("SESSION_STRING", "")
SESSIONS = [s.strip() for s in SESSION_STRINGS_RAW.split(",") if s.strip()]

# 📌 معرفات القنوات والبوتات مباشرة داخل الكود:
CHANNEL_USERNAME = "arggrw"        # قناة الأغاني (أمر غنيلي)
POETRY_CHANNEL = "zfghjjg"         # قناة الشعر (أمر اشعرلي / شعر)
MIX_CHANNEL = "cvbhfdgds"          # قناة المزج (أمر مزج)
MEMES_CHANNEL = "cbklufswe"        # قناة الميمز (أمر ميمز)
QURAN_CHANNEL = "chfdthhd"         # قناة القرآن (أمر قرآن)

LOG_CHANNEL = "dgyuhfd"            # قناة إرسال سجلات البحث
DOWNLOAD_BOT = "@MsosMbot"         # بوت التحميل لأمر يوت

# قواميس لتتبع آخر الرسائل المرسلة لكل دردشة لضمان عدم تكرارها مباشرة
last_sent_songs = {}
last_sent_poems = {}
last_sent_mix = {}
last_sent_memes = {}
last_sent_quran = {}

async def initialize_channels_for_client(client):
    songs, poetry, mix, memes, quran = [], [], [], [], []
    
    print(f"[INFO] جاري جلب وتخزين محتوى القنوات...")
    
    channels = {
        CHANNEL_USERNAME: songs,
        POETRY_CHANNEL: poetry,
        MIX_CHANNEL: mix,
        MEMES_CHANNEL: memes,
        QURAN_CHANNEL: quran
    }
    
    for chan, target_list in channels.items():
        try:
            # وضع حد أقصى (مثلاً 200 رسالة) لضمان عدم تعليق البوت أثناء التشغيل
            async for message in client.iter_messages(chan, limit=200):
                if message.text or message.media:
                    target_list.append(message)
            print(f"[INFO] تم جلب {len(target_list)} رسالة من القناة: {chan}")
        except Exception as e:
            print(f"[ERROR] خطأ أثناء جلب القناة {chan}: {e}")

    return songs, poetry, mix, memes, quran

async def start_client(session_str, index):
    client = TelegramClient(StringSession(session_str), API_ID, API_HASH)
    await client.start()
    print(f"[SUCCESS] تم تشغيل الحساب رقم {index} بنجاح!")
    
    client_songs, client_poetry, client_mix, client_memes, client_quran = await initialize_channels_for_client(client)
    
    # الاستماع للرسائل في المحادثات الخاصة
    @client.on(events.NewMessage(incoming=True, func=lambda e: e.is_private))
    async def handle_commands(event):
        nonlocal client_songs, client_poetry, client_mix, client_memes, client_quran
        text_raw = event.raw_text.strip()
        text_lower = text_raw.lower()
        chat_id = event.chat_id

        # أمر "تحديث" لإعادة تحميل القنوات يدوياً
        if text_raw == "تحديث":
            try:
                await event.delete()
            except Exception:
                pass
            
            try:
                temp_s, temp_p, temp_m, temp_me, temp_q = [], [], [], [], []
                
                async for m in client.iter_messages(CHANNEL_USERNAME, limit=200):
                    if m.text or m.media: temp_s.append(m)
                async for m in client.iter_messages(POETRY_CHANNEL, limit=200):
                    if m.text or m.media: temp_p.append(m)
                async for m in client.iter_messages(MIX_CHANNEL, limit=200):
                    if m.text or m.media: temp_m.append(m)
                async for m in client.iter_messages(MEMES_CHANNEL, limit=200):
                    if m.text or m.media: temp_me.append(m)
                async for m in client.iter_messages(QURAN_CHANNEL, limit=200):
                    if m.text or m.media: temp_q.append(m)
                
                if temp_s: client_songs = temp_s
                if temp_p: client_poetry = temp_p
                if temp_m: client_mix = temp_m
                if temp_me: client_memes = temp_me
                if temp_q: client_quran = temp_q
                
                await client.send_message(chat_id, f"✅ تم تحديث جميع القنوات بنجاح!")
            except Exception as e:
                await client.send_message(chat_id, f"❌ حدث خطأ أثناء التحديث: {e}")
            return

        # دالة مساعدة لإرسال السجلات
        async def send_log(cmd_name):
            try:
                sender = await event.get_sender()
                if sender:
                    user_name = getattr(sender, 'first_name', 'مستخدم')
                    user_username = f"@{sender.username}" if getattr(sender, 'username', None) else "لايوجد"
                    user_id = sender.id
                    
                    log_text = (
                        f"📁 **بحث جديد ({cmd_name})** [حساب {index}]\n\n"
                        f"👤 الاسم: {user_name}\n"
                        f"🆔 الأيدي: `{user_id}`\n"
                        f"🔗 المعرف: {user_username}\n"
                        f"💬 الرابط: tg://openmessage?user_id={user_id}"
                    )
                    await client.send_message(LOG_CHANNEL, log_text)
            except Exception as log_err:
                print(f"[ERROR] فشل إرسال السجل: {log_err}")

        # دالة مساعدة للإرسال العشوائي بدون تكرار
        async def send_random_media(messages_list, last_dict, cmd_title):
            await send_log(cmd_title)
            if not messages_list:
                await event.respond("عذراً، المحتوى غير متوفر حالياً. أرسل 'تحديث' لإعادة التحميل.")
                return

            available = messages_list
            if len(messages_list) > 1 and chat_id in last_dict:
                available = [m for m in messages_list if m.id != last_dict[chat_id]]
            
            selected = random.choice(available)
            last_dict[chat_id] = selected.id

            try:
                if selected.media:
                    await client.send_file(chat_id, selected.media, caption=selected.text or "", parse_mode=None)
                elif selected.text:
                    await client.send_message(chat_id, selected.text)
            except Exception as e:
                print(f"[ERROR] فشل الإرسال: {e}")

        # 1. أمر "غنيلي"
        if text_raw == "غنيلي":
            try: await event.delete()
            except: pass
            await send_random_media(client_songs, last_sent_songs, "غنيلي")
            return

        # 2. أمر "اشعرلي" أو "شعر"
        if text_raw in ["اشعرلي", "شعر"]:
            try: await event.delete()
            except: pass
            await send_random_media(client_poetry, last_sent_poems, "شعر")
            return

        # 3. أمر "مزج"
        if text_raw == "مزج":
            try: await event.delete()
            except: pass
            await send_random_media(client_mix, last_sent_mix, "مزج")
            return

        # 4. أمر "ميمز"
        if text_raw == "ميمز":
            try: await event.delete()
            except: pass
            await send_random_media(client_memes, last_sent_memes, "ميمز")
            return

        # 5. أمر "قرآن"
        if text_raw == "قرآن":
            try: await event.delete()
            except: pass
            await send_random_media(client_quran, last_sent_quran, "قرآن")
            return

        # 6. أمر بحث اليوتيوب (يوت / يوتو)
        if text_lower.startswith("يوت ") or text_lower.startswith("يوتو "):
            query = text_raw[4:].strip() if text_lower.startswith("يوت ") else text_raw[5:].strip()
            if not query: return

            try: await event.delete()
            except: pass

            await send_log(f"يوتيوب: {query}")

            try:
                sent_msg = await client.send_message(DOWNLOAD_BOT, f"يوت {query}")
                audio_msg = None
                for _ in range(30):
                    messages = await client.get_messages(DOWNLOAD_BOT, limit=6)
                    for msg in messages:
                        if msg.id > sent_msg.id and (msg.audio or msg.voice or (msg.document and msg.file and msg.file.mime_type and 'audio' in msg.file.mime_type)):
                            audio_msg = msg
                            break
                    if audio_msg: break
                    await asyncio.sleep(0.3)

                if not audio_msg:
                    print("[WARNING] لم يرد بوت التحميل بملف صوتي.")
                    return

                await client.send_file(chat_id, audio_msg.media, caption="", parse_mode=None)
            except Exception as e:
                print(f"[ERROR] خطأ أثناء جلب الأغنية: {e}")

    return client

async def main():
    if not SESSIONS:
        print("[ERROR] لم يتم العثور على أي جلسات في متغير SESSION_STRING")
        return

    print(f"[INFO] جاري تشغيل {len(SESSIONS)} حسابات من متغيرات البيئة...")
    tasks = [start_client(sess, i+1) for i, sess in enumerate(SESSIONS)]
    clients = await asyncio.gather(*tasks)
    
    await asyncio.gather(*(client.run_until_disconnected() for client in clients))

if __name__ == "__main__":
    asyncio.run(main())
