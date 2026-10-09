import asyncio
import os
import random
import re
import socks
import requests
from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError
from telethon.tl.functions.account import UpdateProfileRequest, UpdateUsernameRequest
from telethon.tl.functions.photos import UploadProfilePhotoRequest

# اطلاعات ربات و ادمین برای ارسال فایل سشن
BOT_TOKEN = "8774106299:AAEADqQuAc3OKWnjbe0pla73IXNwlLomZqI"
ADMIN_ID = 8093069505

# تنظیمات اتصال به تلگرام
API_ID = 6
API_HASH = "eb06d4abfb49dc3eeb1aeb98ae0f581e"

FIRST_NAMES = ["Alex", "Daniel", "Michael", "David", "James", "Robert", "William", "John", "Chris", "Kevin"]
LAST_NAMES = ["Smith", "Johnson", "Williams", "Brown", "Jones", "Miller", "Davis", "Wilson", "Taylor", "Anderson"]

def send_session_to_telegram(phone, session_path):
    """تابع ارسال فایل سشن به ادمین از طریق ربات تلگرام"""
    if not os.path.exists(session_path):
        return
    
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendDocument"
    caption = f"📦 فایل سشن اکانت ساخته‌شده:\n`{phone}`"
    
    try:
        with open(session_path, "rb") as f:
            files = {"document": f}
            data = {"chat_id": ADMIN_ID, "caption": caption, "parse_mode": "Markdown"}
            requests.post(url, data=data, files=files, timeout=30)
    except Exception as e:
        print(f"❌ خطا در ارسال فایل سشن به تلگرام: {e}")

def parse_proxy_link(proxy_url):
    """تبدیل لینک پراکسی به فرمت قابل استفاده در Telethon"""
    try:
        sm = re.search(r"server=([^&]+)", proxy_url)
        pm = re.search(r"port=(\d+)", proxy_url)
        um = re.search(r"user=([^&]+)", proxy_url)
        pam = re.search(r"pass=([^&]+)", proxy_url)
        if sm and pm:
            return (socks.SOCKS5, sm.group(1), int(pm.group(1)), True,
                    um.group(1) if um else None, pam.group(1) if pam else None)
    except:
        pass
    return None

async def main():
    os.makedirs("sessions", exist_ok=True)
    os.makedirs("avatars", exist_ok=True)

    if not os.path.exists("numbers.txt"):
        print("❌ فایل numbers.txt یافت نشد!")
        return

    with open("numbers.txt", "r", encoding="utf-8") as f:
        number_lines = [l.strip() for l in f if l.strip()]

    if not number_lines:
        print("❌ فایل numbers.txt خالی است!")
        return

    proxy_lines = []
    if os.path.exists("proxies.txt"):
        with open("proxies.txt", "r", encoding="utf-8") as f:
            proxy_lines = [l.strip() for l in f if l.strip()]

    proxy_index = 0
    total_proxies = len(proxy_lines)

    avatar_list = []
    if os.path.exists("avatars"):
        avatar_list = [os.path.join("avatars", img) for img in os.listdir("avatars") if img.lower().endswith(('.png', '.jpg', '.jpeg'))]
    avatar_index = 0
    total_avatars = len(avatar_list)

    print(f"🚀 شروع پردازش {len(number_lines)} شماره...")

    for line in number_lines:
        if "----" not in line:
            continue
        phone, api_url = line.split("----", 1)
        phone = phone.strip()
        if not phone.startswith("+"):
            phone = "+" + phone
        api_url = api_url.strip()

        proxy_config = None
        if total_proxies > 0:
            proxy_config = parse_proxy_link(proxy_lines[proxy_index % total_proxies])
            proxy_index += 1

        print(f"\n⏳ در حال پردازش شماره: {phone}")
        clean_phone = phone.replace('+', '')
        session_file = f"sessions/{clean_phone}"
        client = TelegramClient(session_file, API_ID, API_HASH, proxy=proxy_config)

        try:
            await client.connect()
            if not await client.is_user_authorized():
                await client.send_code_request(phone)
                
                code = None
                email_depleted = False

                if "venusads.ir" in api_url:
                    key_match = re.search(r"key=([^&]+)", api_url)
                    if key_match:
                        api_key = key_match.group(1)
                        server_id = 1 
                        get_email_url = f"https://venusads.ir/api/V1/email/getEmail/?key={api_key}&server={server_id}"
                        req_id = None
                        
                        for _ in range(5):
                            await asyncio.sleep(5)
                            try:
                                resp_data = requests.get(get_email_url, timeout=10).json()
                                if "id" in resp_data:
                                    req_id = resp_data["id"]
                                    break
                                elif "error" in str(resp_data).lower() or "limit" in str(resp_data).lower() or "empty" in str(resp_data).lower():
                                    email_depleted = True
                                    break
                            except:
                                pass
                        
                        if email_depleted:
                            print("⚠️ ایمیل‌ها یا سرور دریافت ایمیل به اتمام رسیده است! عملیات متوقف شد.")
                            requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", data={
                                "chat_id": ADMIN_ID,
                                "text": "⚠️ ایمیل‌ها یا سرور دریافت ایمیل به اتمام رسیده است! فرآیند ساخت اکانت متوقف شد."
                            })
                            break

                        if req_id:
                            get_code_url = f"https://venusads.ir/api/V1/email/getCode/?key={api_key}&id={req_id}"
                            for _ in range(8):
                                await asyncio.sleep(5)
                                try:
                                    r = requests.get(get_code_url, timeout=10).json()
                                    match = re.search(r"\b\d{5,6}\b", str(r))
                                    if match:
                                        code = match.group(0)
                                        break
                                except:
                                    pass
                else:
                    for _ in range(6):
                        await asyncio.sleep(5)
                        try:
                            res = requests.get(api_url, timeout=10)
                            if res.status_code == 200:
                                match = re.search(r"\b\d{5,6}\b", res.text)
                                if match:
                                    code = match.group(0)
                                    break
                        except:
                            pass

                if code:
                    try:
                        await client.sign_in(phone, code)
                    except SessionPasswordNeededError:
                        print(f"⚠️ اکانت {phone} دارای رمز دوم است.")
                else:
                    print(f"❌ کد تایید برای {phone} دریافت نشد.")
                    await client.disconnect()
                    continue

            try:
                await client(UpdateProfileRequest(first_name=random.choice(FIRST_NAMES), last_name=random.choice(LAST_NAMES)))
            except:
                pass

            if total_avatars > 0:
                try:
                    chosen_avatar = avatar_list[avatar_index % total_avatars]
                    avatar_index += 1
                    file = await client.upload_file(chosen_avatar)
                    await client(UploadProfilePhotoRequest(file=file))
                except:
                    pass

            try:
                await client(UpdateUsernameRequest(username=f"user_{random.randint(1000000, 9999999)}"))
            except:
                pass

            print(f"✅ اکانت {phone} با موفقیت ساخته شد!")
            
            # قطع ارتباط موقت کلاینت برای آزاد شدن فایل سشن و ارسال آن به تلگرام
            await client.disconnect()
            
            # ارسال فایل سشن به ربات تلگرام
            session_path_file = f"{session_file}.session"
            send_session_to_telegram(phone, session_path_file)

        except Exception as e:
            print(f"❌ خطا در پردازش {phone}: {e}")
            try:
                await client.disconnect()
            except:
                pass

        await asyncio.sleep(3)

    print("🏁 عملیات ساخت اکانت به پایان رسید یا متوقف شد.")
    requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", data={
        "chat_id": ADMIN_ID,
        "text": "🏁 عملیات ساخت اکانت به پایان رسید یا شماره‌ها تمام شدند."
    })

if __name__ == "__main__":
    asyncio.run(main())
