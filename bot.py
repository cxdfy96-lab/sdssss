import os
import random
import asyncio
from telethon import TelegramClient, events
from telethon.sessions import StringSession

# بيانات الاتصال الأساسية
API_ID = int(os.environ.get("API_ID", 0))
API_HASH = os.environ.get("API_HASH", "")

# قراءة الجلسات الأساسية من متغير البيئة SESSION_STRING
SESSION_STRINGS_RAW = os.environ.get("SESSION_STRING", "")
SESSIONS = [s.strip() for s in SESSION_STRINGS_RAW.split(",") if s.strip()]

# 📌 القنوات والأوامر الافتراضية
CHANNELS_MAP = {
    "غنيلي": "arggrw",
    "شعر": "zfghjjg",
    "مزج": "cvbhfdgds",
    "ميمز": "cbklufswe",
    "قرآن": "chfdthhd"
}

LOG_CHANNEL = "dgyuhfd"            # قناة إرسال سجلات البحث
DOWNLOAD_BOT = "@MsosMbot"         # بوت التحميل لأمر يوت

# قواميس التخزين لضمان جلب المحتوى وعدم التكرار لكل جلسة
CLIENT_CONTENTS = {}
last_sent_messages = {}

async def load_channel_messages(client, chan_username, category_key, client_id):
    messages_list = []
    print(f"[INFO] جاري جلب محتوى القناة {chan_username} لأمر ({category_key})...")
    try:
        async for message in client.iter_messages(chan_username, limit=200):
            if message.text or message.media:
                messages_list.append(message)
        print(f"[INFO] تم جلب {len(messages_list)} رسالة بنجاح من {chan_username}")
    except Exception as e:
        print(f"[ERROR] خطأ أثناء جلب القناة {chan_username}: {e}")
    
    if client_id not in CLIENT_CONTENTS:
        CLIENT_CONTENTS[client_id] = {}
    CLIENT_CONTENTS[client_id][category_key] = messages_list

async def initialize_all_channels(client, client_id):
    for cat, chan in CHANNELS_MAP.items():
        await load_channel_messages(client, chan, cat, client_id)

async def check_admin_permission(client, event):
    if event.is_private:
        return True
    try:
        chat = await event.get_chat()
        if chat.megagroup or chat.broadcast or getattr(chat, 'forum', False):
            me = await client.get_me()
            participant = await client.get_permissions(chat, me.id)
            if participant and (participant.is_admin or participant.is_creator):
                return True
    except Exception as e:
        print(f"[ERROR] التحقق من الصلاحيات: {e}")
    return False

async def start_client(session_str, index):
    client = TelegramClient(StringSession(session_str), API_ID, API_HASH)
    await client.start()
    
    me = await client.get_me()
    client_id = me.id
    print(f"[SUCCESS] تم تشغيل الحساب رقم {index} ({me.first_name}) بنجاح!")
    
    await initialize_all_channels(client, client_id)
    
    @client.on(events.NewMessage(incoming=True, outgoing=True))
    async def handle_commands(event):
        text_raw = event.raw_text.strip()
        text_lower = text_raw.lower()
        chat_id = event.chat_id

        # 1. أمر التنصيب عبر الرد (Reply) في المحفوظات أو الخاص
        if event.is_private and event.sender_id == client_id and text_raw in ["تنصيب", "إضافة"]:
            if event.is_reply:
                try:
                    reply_msg = await event.get_reply_message()
                    if reply_msg and reply_msg.text:
                        new_session_str = reply_msg.text.strip()
                        await event.delete()
                        
                        status_msg = await client.send_message(chat_id, "⏳ جاري اختبار وتشغيل الحساب الجديد...")
                        try:
                            temp_client = TelegramClient(StringSession(new_session_str), API_ID, API_HASH)
                            await temp_client.connect()
                            if await temp_client.is_user_authorized():
                                asyncio.create_task(start_client(new_session_str, "المضاف"))
                                await status_msg.edit("✅ تم تنصيب وتشغيل الحساب الجديد بنجاح!")
                            else:
                                await status_msg.edit("❌ الجلسة غير صالحة.")
                            await temp_client.disconnect()
                        except Exception as ex:
                            await status_msg.edit(f"❌ فشل تنصيب الجلسة: {ex}")
                except Exception as err:
                    print(f"[ERROR] مشكلة في التنصيب: {err}")
                return

        # 2. أمر إضافة قناة جديدة: (إضافة قناة @username اسم_الأمر)
        if event.is_private and event.sender_id == client_id and text_raw.startswith("إضافة قناة "):
            parts = text_raw.split(" ")
            if len(parts) >= 4:
                new_chan = parts[2].strip()
                # دمج باقي الأجزاء لتصبح الأمر (حتى لو كان عدة كلمات مثل: صافي اشعر لي)
                custom_cmd = " ".join(parts[3:]).strip()
                
                CHANNELS_MAP[custom_cmd] = new_chan
                await load_channel_messages(client, new_chan, custom_cmd, client_id)
                await event.respond(f"✅ تمت إضافة القناة `{new_chan}` وربطها بالأمر (`{custom_cmd}`) بنجاح!")
            else:
                await event.respond("⚠️ الصيغة غير صحيحة. استخدم:\n`إضافة قناة @معرف_القناة اسم_الأمر`")
            return

        if not event.is_private:
            is_allowed = await check_admin_permission(client, event)
            if not is_allowed:
                return

        # 3. أمر التحديث
        if text_raw == "تحديث":
            try:
                await event.delete()
            except Exception:
                pass
            
            try:
                await initialize_all_channels(client, client_id)
                await client.send_message(chat_id, f"✅ تم تحديث القنوات والمحتوى بنجاح!")
            except Exception as e:
                await client.send_message(chat_id, f"❌ حدث خطأ أثناء التحديث: {e}")
            return

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

        async def send_random_media(category_name):
            await send_log(category_name)
            messages_list = CLIENT_CONTENTS.get(client_id, {}).get(category_name, [])
            if not messages_list:
                await event.respond(f"عذراً، لا يوجد محتوى في هذا القسم حالياً. أرسل 'تحديث'.")
                return

            if client_id not in last_sent_messages:
                last_sent_messages[client_id] = {}
            if category_name not in last_sent_messages[client_id]:
                last_sent_messages[client_id][category_name] = {}

            available = messages_list
            if len(messages_list) > 1 and chat_id in last_sent_messages[client_id][category_name]:
                available = [m for m in messages_list if m.id != last_sent_messages[client_id][category_name][chat_id]]
            
            selected = random.choice(available)
            last_sent_messages[client_id][category_name][chat_id] = selected.id

            try:
                if selected.media:
                    await client.send_file(chat_id, selected.media, caption=selected.text or "", parse_mode=None)
                elif selected.text:
                    await client.send_message(chat_id, selected.text)
            except Exception as e:
                print(f"[ERROR] فشل الإرسال: {e}")

        # التحقق من الأوامر المسجلة (حتى لو كانت عبارات مركبة مطابقة تماماً للنص المدخل)
        matched_cmd = None
        for cmd in CHANNELS_MAP.keys():
            if text_raw == cmd:
                matched_cmd = cmd
                break

        if matched_cmd:
            try: await event.delete()
            except: pass
            await send_random_media(matched_cmd)
            return

        # أمر بحث اليوتيوب
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
