import asyncio
import datetime
import json
import os
import random
import re
import socks
import requests
from aiohttp import web
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError
from telethon.tl.functions.account import UpdateProfileRequest, UpdateUsernameRequest
from telethon.tl.functions.photos import UploadProfilePhotoRequest
from telethon.tl.functions.auth import LogOutRequest

BOT_TOKEN = "8774106299:AAEADqQuAc3OKWnjbe0pla73IXNwlLomZqI"
ADMIN_ID = 8093069505

API_ID = 6
API_HASH = "eb06d4abfb49dc3eeb1aeb98ae0f581e"

# تنظیمات وب‌هوک برای Render (نام اپلیکیشن خود را در رندر جایگزین کنید)
# مثال: https://your-app-name.onrender.com
RENDER_EXTERNAL_URL = os.getenv("RENDER_EXTERNAL_URL", "https://my-telegram-bot.onrender.com")
WEBHOOK_PATH = f"/webhook/{BOT_TOKEN}"
WEBHOOK_URL = f"{RENDER_EXTERNAL_URL}{WEBHOOK_PATH}"

PORT = int(os.getenv("PORT", 10000))

FIRST_NAMES = ["Alex", "Daniel", "Michael", "David", "James", "Robert", "William", "John", "Chris", "Kevin"]
LAST_NAMES = ["Smith", "Johnson", "Williams", "Brown", "Jones", "Miller", "Davis", "Wilson", "Taylor", "Anderson"]

bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

class BotStates(StatesGroup):
    waiting_for_numbers = State()
    waiting_for_proxies = State()
    waiting_for_avatar = State()
    setting_country = State()
    setting_2fa_pass = State()
    setting_email_server = State()

user_config = {
    "country": "USA",
    "use_2fa": False,
    "password_2fa": "",
    "use_avatar": True,
    "use_username": True,
    "email_server": 1
}

bot_process_status = {
    "is_running": False,
    "task": None
}

STATS_FILE = "stats.json"

def load_stats():
    if os.path.exists(STATS_FILE):
        try:
            with open(STATS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            pass
    return {"total": 0, "daily": 0, "last_reset": str(datetime.date.today()), "by_country": {}}

def save_stats(data):
    with open(STATS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

def check_daily_reset():
    stats = load_stats()
    today_str = str(datetime.date.today())
    if stats.get("last_reset") != today_str:
        stats["daily"] = 0
        stats["last_reset"] = today_str
        save_stats(stats)

def get_main_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🚀 ساخت اکانت"), KeyboardButton(text="🛠 مدیریت اکانت ها")],
            [KeyboardButton(text="📊 آمار اکانت ها"), KeyboardButton(text="⚙️ تنظیمات")],
        ],
        resize_keyboard=True
    )

def get_creation_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="▶️ شروع"), KeyboardButton(text="⏹ توقف")],
            [KeyboardButton(text="🔙 بازگشت به منوی اصلی")]
        ],
        resize_keyboard=True
    )

def get_management_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📋 لیست سشن‌ها و عملیات"), KeyboardButton(text="🔙 بازگشت به منوی اصلی")]
        ],
        resize_keyboard=True
    )

def get_settings_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📁 ارسال فایل شماره‌ها"), KeyboardButton(text="🛡 ارسال فایل پراکسی")],
            [KeyboardButton(text="🖼 ارسال عکس‌های آواتار"), KeyboardButton(text="🌍 تغییر کشور")],
            [KeyboardButton(text="🎛 سرور ایمیل (۱ یا ۲)"), KeyboardButton(text="🔐 تنظیم رمز دوم")],
            [KeyboardButton(text="🔙 بازگشت به منوی اصلی")]
        ],
        resize_keyboard=True
    )

def is_admin(user_id: int):
    return user_id == ADMIN_ID

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    if not is_admin(message.from_user.id): return
    os.makedirs("sessions", exist_ok=True)
    os.makedirs("avatars", exist_ok=True)
    await message.answer("سلام ادمین عزیز! به پنل مدیریت سشن‌ها خوش آمدید:", reply_markup=get_main_keyboard())

@dp.message(F.text == "🔙 بازگشت به منوی اصلی")
async def back_to_main(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    await state.clear()
    await message.answer("به منوی اصلی برگشتید:", reply_markup=get_main_keyboard())

@dp.message(F.text == "🚀 ساخت اکانت")
async def menu_creation(message: types.Message):
    if not is_admin(message.from_user.id): return
    status_text = "🟢 در حال اجرا..." if bot_process_status["is_running"] else "⚪️ متوقف"
    await message.answer(f"بخش ساخت اکانت (وضعیت: {status_text})\nیکی از گزینه‌های زیر را انتخاب کنید:", reply_markup=get_creation_keyboard())

@dp.message(F.text == "⏹ توقف")
async def stop_creation(message: types.Message):
    if not is_admin(message.from_user.id): return
    if bot_process_status["is_running"]:
        bot_process_status["is_running"] = False
        if bot_process_status["task"]:
            bot_process_status["task"].cancel()
        await message.answer("⏹ فرآیند ساخت اکانت متوقف شد.", reply_markup=get_creation_keyboard())
    else:
        await message.answer("⚠️ فرآیندی در حال اجرا نیست.", reply_markup=get_creation_keyboard())

@dp.message(F.text == "▶️ شروع")
async def start_creation_process(message: types.Message):
    if not is_admin(message.from_user.id): return
    if bot_process_status["is_running"]:
        await message.answer("⚠️ فرآیند ساخت از قبل در حال اجراست!")
        return

    if not os.path.exists("numbers.txt") or not os.path.exists("proxies.txt"):
        await message.answer("❌ ابتدا فایل numbers.txt و proxies.txt را در بخش تنظیمات ارسال کنید!")
        return

    bot_process_status["is_running"] = True
    bot_process_status["task"] = asyncio.create_task(run_account_creation_loop(message))

async def run_account_creation_loop(message: types.Message):
    try:
        with open("numbers.txt", "r", encoding="utf-8") as f:
            number_lines = [l.strip() for l in f if l.strip()]
        with open("proxies.txt", "r", encoding="utf-8") as f:
            proxy_lines = [l.strip() for l in f if l.strip()]

        proxy_index = 0
        total_proxies = len(proxy_lines)

        for line in number_lines:
            if not bot_process_status["is_running"]:
                break
            if "----" not in line: continue
            phone, api_url = line.split("----", 1)
            phone = phone.strip()
            if not phone.startswith("+"): phone = "+" + phone
            api_url = api_url.strip()

            proxy_config = parse_proxy_link(proxy_lines[proxy_index % total_proxies]) if total_proxies > 0 else None
            if total_proxies > 0: proxy_index += 1

            await bot.send_message(ADMIN_ID, f"⏳ در حال پردازش شماره: `{phone}`", parse_mode="Markdown")
            session_file = f"sessions/{phone.replace('+', '')}"
            client = TelegramClient(session_file, API_ID, API_HASH, proxy=proxy_config)

            try:
                await client.connect()
                if not await client.is_user_authorized():
                    await client.send_code_request(phone)
                    
                    code = None
                    if "venusads.ir" in api_url:
                        key_match = re.search(r"key=([^&]+)", api_url)
                        if key_match:
                            api_key = key_match.group(1)
                            server_id = user_config["email_server"]
                            get_email_url = f"https://venusads.ir/api/V1/email/getEmail/?key={api_key}&server={server_id}"
                            req_id = None
                            for _ in range(5):
                                if not bot_process_status["is_running"]: break
                                await asyncio.sleep(4)
                                try:
                                    r = requests.get(get_email_url, timeout=10).json()
                                    if "id" in r:
                                        req_id = r["id"]
                                        break
                                except: pass
                            
                            if req_id:
                                get_code_url = f"https://venusads.ir/api/V1/email/getCode/?key={api_key}&id={req_id}"
                                for _ in range(8):
                                    if not bot_process_status["is_running"]: break
                                    await asyncio.sleep(5)
                                    try:
                                        r = requests.get(get_code_url, timeout=10).json()
                                        match = re.search(r"\b\d{5,6}\b", str(r))
                                        if match:
                                            code = match.group(0)
                                            break
                                    except: pass
                    else:
                        for _ in range(6):
                            if not bot_process_status["is_running"]: break
                            await asyncio.sleep(5)
                            try:
                                res = requests.get(api_url, timeout=10)
                                if res.status_code == 200:
                                    match = re.search(r"\b\d{5,6}\b", res.text)
                                    if match:
                                        code = match.group(0)
                                        break
                            except: pass

                    if code:
                        try:
                            await client.sign_in(phone, code)
                        except SessionPasswordNeededError:
                            pass
                    else:
                        await bot.send_message(ADMIN_ID, f"❌ کد تایید برای `{phone}` دریافت نشد.", parse_mode="Markdown")
                        await client.disconnect()
                        continue

                try:
                    await client(UpdateProfileRequest(first_name=random.choice(FIRST_NAMES), last_name=random.choice(LAST_NAMES)))
                except: pass

                if user_config["use_2fa"] and user_config["password_2fa"]:
                    try: await client.edit_2fa(new_password=user_config["password_2fa"])
                    except: pass

                if user_config["use_avatar"] and os.path.exists("avatars"):
                    avatars = os.listdir("avatars")
                    if avatars:
                        try:
                            file = await client.upload_file(os.path.join("avatars", random.choice(avatars)))
                            await client(UploadProfilePhotoRequest(file=file))
                        except: pass

                if user_config["use_username"]:
                    try: await client(UpdateUsernameRequest(username=f"user_{random.randint(1000000, 9999999)}"))
                    except: pass

                check_daily_reset()
                stats = load_stats()
                stats["total"] += 1
                stats["daily"] += 1
                country = user_config["country"]
                stats["by_country"][country] = stats["by_country"].get(country, 0) + 1
                save_stats(stats)

                await bot.send_message(ADMIN_ID, f"✅ اکانت `{phone}` با موفقیت ساخته شد!", parse_mode="Markdown")

            except Exception as e:
                await bot.send_message(ADMIN_ID, f"❌ خطا در `{phone}`: {e}", parse_mode="Markdown")
            finally:
                try: await client.disconnect()
                except: pass

            await asyncio.sleep(3)

    except asyncio.CancelledError:
        pass
    finally:
        bot_process_status["is_running"] = False
        bot_process_status["task"] = None
        await bot.send_message(ADMIN_ID, "🏁 عملیات ساخت اکانت متوقف یا پایان یافت.", reply_markup=get_creation_keyboard())

@dp.message(F.text == "📊 آمار اکانت ها")
async def show_stats_menu(message: types.Message):
    if not is_admin(message.from_user.id): return
    check_daily_reset()
    stats = load_stats()
    
    country_details = ""
    for c, count in stats["by_country"].items():
        country_details += f"  - {c}: {count} اکانت\n"
    if not country_details:
        country_details = "  - موردی ثبت نشده است\n"

    text = (
        f"📊 **آمار جامع اکانت‌ها:**\n\n"
        f"🌐 کل اکانت‌های ساخته‌شده: **{stats['total']}**\n"
        f"📅 اکانت‌های ساخته‌شده در ۲۴ ساعت اخیر: **{stats['daily']}**\n\n"
        f"🌍 تفکیک کشوری:\n{country_details}"
    )
    await message.answer(text, parse_mode="Markdown", reply_markup=get_main_keyboard())

@dp.message(F.text == "🛠 مدیریت اکانت ها")
async def menu_management(message: types.Message):
    if not is_admin(message.from_user.id): return
    await message.answer("بخش مدیریت سشن‌های ذخیره‌شده:", reply_markup=get_management_keyboard())

@dp.message(F.text == "📋 لیست سشن‌ها و عملیات")
async def list_sessions(message: types.Message):
    if not is_admin(message.from_user.id): return
    sessions = [f.replace(".session", "") for f in os.listdir("sessions") if f.endswith(".session")]
    if not sessions:
        await message.answer("❌ هیچ فایل سشنی موجود نیست.")
        return
    
    text = "📁 **فایل‌های سشن موجود:**\n"
    for s in sessions[:20]:
        text += f"• `{s}`\n"
    text += "\nدستورات:\n- خروج: `logout شماره`\n- حذف: `delete شماره`\n- تغییر رمز: `set2fa شماره رمزجدید`"
    await message.answer(text, parse_mode="Markdown")

@dp.message(F.text.startswith(("logout ", "delete ", "set2fa ")))
async def execute_management_command(message: types.Message):
    if not is_admin(message.from_user.id): return
    parts = message.text.split(" ", 2)
    cmd = parts[0]
    target = parts[1].replace("+", "")
    session_path = f"sessions/{target}"
    
    if cmd == "delete":
        if os.path.exists(session_path + ".session"):
            os.remove(session_path + ".session")
            await message.answer(f"✅ سشن `{target}` حذف شد.")
        else:
            await message.answer("❌ پیدا نشد.")
        return

    client = TelegramClient(session_path, API_ID, API_HASH)
    try:
        await client.connect()
        if not await client.is_user_authorized():
            await message.answer("❌ سشن معتبر نیست.")
            await client.disconnect()
            return

        if cmd == "logout":
            await client(LogOutRequest())
            await client.disconnect()
            if os.path.exists(session_path + ".session"):
                os.remove(session_path + ".session")
            await message.answer(f"✅ اکانت `{target}` لاگ‌اوت شد.", parse_mode="Markdown")
        elif cmd == "set2fa":
            if len(parts) < 3:
                await message.answer("❌ رمز جدید را وارد کنید.")
            else:
                await client.edit_2fa(new_password=parts[2])
                await message.answer(f"✅ رمز دوم تغییر یافت.", parse_mode="Markdown")
            await client.disconnect()
    except Exception as e:
        await message.answer(f"❌ خطا: {e}")
        try: await client.disconnect()
        except: pass

@dp.message(F.text == "⚙️ تنظیمات")
async def menu_settings(message: types.Message):
    if not is_admin(message.from_user.id): return
    nums_exist = os.path.exists("numbers.txt")
    proxies_exist = os.path.exists("proxies.txt")
    avatars_count = len(os.listdir("avatars")) if os.path.exists("avatars") else 0

    text = (
        f"⚙️ **تنظیمات:**\n"
        f"🌍 کشور: `{user_config['country']}`\n"
        f"📧 سرور ایمیل: `سرور {user_config['email_server']}`\n"
        f"🔐 رمز دوم: {'فعال' if user_config['use_2fa'] else 'غیرفعال'}\n"
        f"🖼 آواتارها: {avatars_count} عکس\n"
        f"📁 شماره‌ها: {'موجود ✅' if nums_exist else 'خالی ❌'}\n"
        f"🛡 پراکسی: {'موجود ✅' if proxies_exist else 'خالی ❌'}"
    )
    await message.answer(text, parse_mode="Markdown", reply_markup=get_settings_keyboard())

@dp.message(F.text == "📁 ارسال فایل شماره‌ها")
async def ask_numbers(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    await state.set_state(BotStates.waiting_for_numbers)
    await message.answer("فایل `numbers.txt` را بفرستید:")

@dp.message(BotStates.waiting_for_numbers, F.document)
async def receive_numbers(message: types.Message, state: FSMContext):
    file = await bot.get_file(message.document.file_id)
    await bot.download_file(file.file_path, "numbers.txt")
    await state.clear()
    await message.answer("✅ ذخیره شد.", reply_markup=get_settings_keyboard())

@dp.message(F.text == "🛡 ارسال فایل پراکسی")
async def ask_proxies(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    await state.set_state(BotStates.waiting_for_proxies)
    await message.answer("فایل `proxies.txt` را بفرستید:")

@dp.message(BotStates.waiting_for_proxies, F.document)
async def receive_proxies(message: types.Message, state: FSMContext):
    file = await bot.get_file(message.document.file_id)
    await bot.download_file(file.file_path, "proxies.txt")
    await state.clear()
    await message.answer("✅ ذخیره شد.", reply_markup=get_settings_keyboard())

@dp.message(F.text == "🖼 ارسال عکس‌های آواتار")
async def ask_avatar(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    await state.set_state(BotStates.waiting_for_avatar)
    await message.answer("عکس‌های پروفایل را بفرستید:")

@dp.message(BotStates.waiting_for_avatar, F.photo)
async def receive_avatar_photo(message: types.Message):
    photo = message.photo[-1]
    file = await bot.get_file(photo.file_id)
    await bot.download_file(file.file_path, f"avatars/{photo.file_unique_id}.jpg")
    await message.answer("✅ عکس ذخیره شد.")

@dp.message(F.text == "🌍 تغییر کشور")
async def ask_country(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    await state.set_state(BotStates.setting_country)
    await message.answer("نام کشور جدید را وارد کنید:")

@dp.message(BotStates.setting_country)
async def save_country(message: types.Message, state: FSMContext):
    user_config["country"] = message.text.strip()
    await state.clear()
    await message.answer(f"✅ کشور ثبت شد.", reply_markup=get_settings_keyboard())

@dp.message(F.text == "🎛 سرور ایمیل (۱ یا ۲)")
async def ask_email_server(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    await state.set_state(BotStates.setting_email_server)
    await message.answer("شماره سرور ایمیل را وارد کنید (`1` یا `2`):")

@dp.message(BotStates.setting_email_server)
async def save_email_server(message: types.Message, state: FSMContext):
    txt = message.text.strip()
    if txt in ["1", "2"]:
        user_config["email_server"] = int(txt)
        await state.clear()
        await message.answer(f"✅ سرور ایمیل تنظیم شد.", reply_markup=get_settings_keyboard())
    else:
        await message.answer("❌ فقط عدد 1 یا 2:")

@dp.message(F.text == "🔐 تنظیم رمز دوم")
async def ask_2fa(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    await state.set_state(BotStates.setting_2fa_pass)
    await message.answer("رمز دوم یا کلمه `no`:")

@dp.message(BotStates.setting_2fa_pass)
async def save_2fa(message: types.Message, state: FSMContext):
    txt = message.text.strip()
    if txt.lower() == "no":
        user_config["use_2fa"] = False
        user_config["password_2fa"] = ""
    else:
        user_config["use_2fa"] = True
        user_config["password_2fa"] = txt
    await state.clear()
    await message.answer("✅ ذخیره شد.", reply_markup=get_settings_keyboard())

def parse_proxy_link(proxy_url):
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

async def on_startup(bot: Bot):
    await bot.set_webhook(WEBHOOK_URL)

async def main():
    app = web.Application()
    webhook_requests_handler = SimpleRequestHandler(
        dispatcher=dp,
        bot=bot,
    )
    webhook_requests_handler.register(app, path=WEBHOOK_PATH)
    setup_application(app, dp, bot=bot)
    
    dp.startup.register(on_startup)
    
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", PORT)
    print(f"Starting webserver on port {PORT}...")
    await site.start()
    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())
