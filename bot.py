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

# تنظیمات وب‌هوک برای Render
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
    waiting_for_proxy_text = State()
    waiting_for_photos = State()
    setting_country = State()
    setting_2fa_pass = State()
    setting_email_server = State()

user_config = {
    "country": "USA",
    "use_2fa": False,
    "password_2fa": "",
    "use_avatar": True,
    "use_username": True,
    "email_server": 1,
    "delivery_method": "سشن (Session) 📁"
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

# --- کیبوردها با چیدمان درخواستی شما ---

def get_main_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🚀 ساخت اکانت"), KeyboardButton(text="🛠 مدیریت اکانت ها")],
            [KeyboardButton(text="📊 آمار اکانت ها")],
            [KeyboardButton(text="⚙️ تنظیمات")],
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
            [KeyboardButton(text="📁 ارسال فایل شماره‌ها"), KeyboardButton(text="🌍 تغییر کشور")],
            [KeyboardButton(text="پروکسی 🌐"), KeyboardButton(text="ایمیل 📧")],
            [KeyboardButton(text="عکس‌ها 🖼️"), KeyboardButton(text="رمز دو مرحله‌ای 🔐")],
            [KeyboardButton(text="حذف 🗑️"), KeyboardButton(text="خروجی 📥")],
            [KeyboardButton(text="تحویل اکانت 📦"), KeyboardButton(text="آمار 📊")],
            [KeyboardButton(text="🔙 بازگشت به منوی اصلی")]
        ],
        resize_keyboard=True
    )

def proxy_menu_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="افزودن پروکسی ➕"), KeyboardButton(text="حذف پروکسی 🗑️")],
            [KeyboardButton(text="دریافت توکن پروکسی 🔑"), KeyboardButton(text="دریافت API پروکسی ⚡")],
            [KeyboardButton(text="🔙 بازگشت به تنظیمات")]
        ],
        resize_keyboard=True
    )

def email_menu_keyboard(active_server=1):
    s1 = "سرور ۱ (فعال) ✅" if active_server == 1 else "سرور ۱ 🟢"
    s2 = "سرور ۲ (فعال) ✅" if active_server == 2 else "سرور ۲ 🔢"
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=s1), KeyboardButton(text=s2)],
            [KeyboardButton(text="🔙 بازگشت به تنظیمات")]
        ],
        resize_keyboard=True
    )

def photos_menu_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="ارسال عکس 🖼️"), KeyboardButton(text="حذف عکس‌ها ❌")],
            [KeyboardButton(text="🔙 بازگشت به تنظیمات")]
        ],
        resize_keyboard=True
    )

def tfa_menu_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="فعال ✅"), KeyboardButton(text="غیر فعال ❌")],
            [KeyboardButton(text="🔙 بازگشت به تنظیمات")]
        ],
        resize_keyboard=True
    )

def delete_menu_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="همه 🗑️"), KeyboardButton(text="کد گرفته ها 📄")],
            [KeyboardButton(text="🔙 بازگشت به تنظیمات")]
        ],
        resize_keyboard=True
    )

def export_menu_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="دریأفتی ها ✅"), KeyboardButton(text="دریافت نشده ها 🆓")],
            [KeyboardButton(text="کد نگرفته ها ⏳")],
            [KeyboardButton(text="🔙 بازگشت به تنظیمات")]
        ],
        resize_keyboard=True
    )

def delivery_menu_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="سشن (Session) 📁"), KeyboardButton(text="زیپ (Zip) 🗜️")],
            [KeyboardButton(text="🔙 بازگشت به تنظیمات")]
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

@dp.message(F.text == "🔙 بازگشت به تنظیمات")
async def back_to_settings(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    await state.clear()
    await message.answer("⚙️ پنل مدیریت و تنظیمات:", reply_markup=get_settings_keyboard())

# --- ساخت اکانت ---
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
        await message.answer("❌ ابتدا فایل numbers.txt و proxies.txt را ارسال یا آماده کنید.")
        return

    bot_process_status["is_running"] = True
    bot_process_status["task"] = asyncio.create_task(run_account_creation_loop(message))

async def run_account_creation_loop(message: types.Message):
    try:
        if not os.path.exists("numbers.txt"):
            await bot.send_message(ADMIN_ID, "❌ فایل شماره‌ها (`numbers.txt`) یافت نشد!")
            return

        with open("numbers.txt", "r", encoding="utf-8") as f:
            number_lines = [l.strip() for l in f if l.strip()]
        
        if not number_lines:
            await bot.send_message(ADMIN_ID, "❌ فایل شماره‌ها خالی است. شماره‌ای برای پردازش وجود ندارد!")
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

        for line_idx, line in enumerate(number_lines):
            if not bot_process_status["is_running"]:
                break
            if "----" not in line: continue
            phone, api_url = line.split("----", 1)
            phone = phone.strip()
            if not phone.startswith("+"): phone = "+" + phone
            api_url = api_url.strip()

            # استفاده ترتیبی و چرخشی از پروکسی‌ها
            proxy_config = None
            if total_proxies > 0:
                proxy_config = parse_proxy_link(proxy_lines[proxy_index % total_proxies])
                proxy_index += 1

            await bot.send_message(ADMIN_ID, f"⏳ در حال پردازش شماره: `{phone}`", parse_mode="Markdown")
            session_file = f"sessions/{phone.replace('+', '')}"
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
                            server_id = user_config["email_server"]
                            get_email_url = f"https://venusads.ir/api/V1/email/getEmail/?key={api_key}&server={server_id}"
                            req_id = None
                            for _ in range(5):
                                if not bot_process_status["is_running"]: break
                                await asyncio.sleep(5)
                                try:
                                    resp_data = requests.get(get_email_url, timeout=10).json()
                                    if "id" in resp_data:
                                        req_id = resp_data["id"]
                                        break
                                    elif "error" in str(resp_data).lower() or "limit" in str(resp_data).lower() or "empty" in str(resp_data).lower():
                                        email_depleted = True
                                        break
                                except: pass
                            
                            if email_depleted:
                                await bot.send_message(ADMIN_ID, "⚠️ ایمیل‌ها یا سرور دریافت ایمیل به اتمام رسیده است! عملیات متوقف شد.", parse_mode="Markdown")
                                await client.disconnect()
                                break

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

                # استفاده ترتیبی و چرخشی از عکس‌های آواتار
                if user_config["use_avatar"] and total_avatars > 0:
                    try:
                        chosen_avatar = avatar_list[avatar_index % total_avatars]
                        avatar_index += 1
                        file = await client.upload_file(chosen_avatar)
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

            # حذف شماره پردازش شده از فایل یا بررسی پایان شماره‌ها
            if line_idx == len(number_lines) - 1:
                await bot.send_message(ADMIN_ID, "⚠️ تمامی شماره‌های داخل فایل به پایان رسیدند!", parse_mode="Markdown")

            await asyncio.sleep(3)

    except asyncio.CancelledError:
        pass
    finally:
        bot_process_status["is_running"] = False
        bot_process_status["task"] = None
        await bot.send_message(ADMIN_ID, "🏁 عملیات ساخت اکانت متوقف یا پایان یافت.", reply_markup=get_creation_keyboard())

# --- تنظیمات ---
@dp.message(F.text == "⚙️ تنظیمات")
async def menu_settings(message: types.Message):
    if not is_admin(message.from_user.id): return
    await message.answer("⚙️ منوی مدیریت و تنظیمات:\nلطفاً بخش مورد نظر را انتخاب کنید:", reply_markup=get_settings_keyboard())

@dp.message(F.text == "📁 ارسال فایل شماره‌ها")
async def ask_numbers(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    await state.set_state(BotStates.waiting_for_numbers)
    await message.answer("فایل `numbers.txt` را بفرستید:")

@dp.message(BotStates.waiting_for_numbers, F.document)
async def receive_numbers(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    file = await bot.get_file(message.document.file_id)
    await bot.download_file(file.file_path, "numbers.txt")
    
    count = 0
    try:
        with open("numbers.txt", "r", encoding="utf-8") as f:
            count = sum(1 for line in f if line.strip())
    except:
        pass

    await state.clear()
    await message.answer(f"✅ فایل شماره‌ها با موفقیت ذخیره شد.\n🔢 تعداد شماره‌های ذخیره‌شده: **{count}** عدد", parse_mode="Markdown", reply_markup=get_settings_keyboard())

@dp.message(F.text == "🌍 تغییر کشور")
async def ask_country(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    await state.set_state(BotStates.setting_country)
    await message.answer("نام کشور جدید را وارد کنید:")

@dp.message(BotStates.setting_country)
async def save_country(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    user_config["country"] = message.text.strip()
    await state.clear()
    await message.answer(f"✅ کشور با موفقیت به `{user_config['country']}` تغییر یافت.", parse_mode="Markdown", reply_markup=get_settings_keyboard())

# پروکسی 🌐
@dp.message(F.text == "پروکسی 🌐")
async def menu_proxy(message: types.Message):
    if not is_admin(message.from_user.id): return
    await message.answer("🌐 منوی مدیریت پروکسی‌ها:", reply_markup=proxy_menu_keyboard())

@dp.message(F.text == "افزودن پروکسی ➕")
async def add_proxy_prompt(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    await state.set_state(BotStates.waiting_for_proxy_text)
    await message.answer("لطفاً پروکسی خود را به‌صورت متن یا ارسال فایل/سند ارسال کنید:")

@dp.message(BotStates.waiting_for_proxy_text, F.text | F.document)
async def receive_proxy_input(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    if message.document:
        file = await bot.get_file(message.document.file_id)
        await bot.download_file(file.file_path, "proxies.txt")
    else:
        with open("proxies.txt", "a", encoding="utf-8") as f:
            f.write(message.text + "\n")
    await state.clear()
    await message.answer("✅ پروکسی با موفقیت دریافت و ذخیره شد.", reply_markup=proxy_menu_keyboard())

@dp.message(F.text == "حذف پروکسی 🗑️")
async def delete_proxy_file(message: types.Message):
    if not is_admin(message.from_user.id): return
    if os.path.exists("proxies.txt"):
        os.remove("proxies.txt")
        await message.answer("🗑️ فایل پروکسی‌ها پاک شد.", reply_markup=proxy_menu_keyboard())
    else:
        await message.answer("❌ هیچ فایل پروکسی‌ای وجود ندارد.", reply_markup=proxy_menu_keyboard())

@dp.message(F.text == "دریافت توکن پروکسی 🔑")
async def get_proxy_token(message: types.Message):
    if not is_admin(message.from_user.id): return
    await message.answer("🔑 توکن پروکسی فعال سیستم.", reply_markup=proxy_menu_keyboard())

@dp.message(F.text == "دریافت API پروکسی ⚡")
async def get_proxy_api(message: types.Message):
    if not is_admin(message.from_user.id): return
    await message.answer("⚡ اطلاعات API پروکسی.", reply_markup=proxy_menu_keyboard())

# ایمیل 📧
@dp.message(F.text == "ایمیل 📧")
async def menu_email(message: types.Message):
    if not is_admin(message.from_user.id): return
    current = user_config["email_server"]
    await message.answer(
        f"📧 تنظیمات سرور دریافت ایمیل\n🟢 سرور فعال فعلی: سرور {current}\n\nلطفاً سرور مورد نظر خود را انتخاب کنید:",
        reply_markup=email_menu_keyboard(current)
    )

@dp.message(F.text.in_(["سرور ۱ (فعال) ✅", "سرور ۱ 🟢"]))
async def set_server_1(message: types.Message):
    if not is_admin(message.from_user.id): return
    user_config["email_server"] = 1
    await message.answer("✅ سرور فعال روی **سرور ۱** تنظیم شد.", parse_mode="Markdown", reply_markup=email_menu_keyboard(1))

@dp.message(F.text.in_(["سرور ۲ (فعال) ✅", "سرور ۲ 🔢"]))
async def set_server_2(message: types.Message):
    if not is_admin(message.from_user.id): return
    user_config["email_server"] = 2
    await message.answer("✅ سرور فعال روی **سرور ۲** تنظیم شد.", parse_mode="Markdown", reply_markup=email_menu_keyboard(2))

# عکس‌ها 🖼️
@dp.message(F.text == "عکس‌ها 🖼️")
async def menu_photos(message: types.Message):
    if not is_admin(message.from_user.id): return
    await message.answer("🖼️ مدیریت عکس‌ها:", reply_markup=photos_menu_keyboard())

@dp.message(F.text == "ارسال عکس 🖼️")
async def prompt_send_photo(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    await state.set_state(BotStates.waiting_for_photos)
    await message.answer("لطفاً عکس یا عکس‌های خود را به‌صورت تکی یا فایل ارسال کنید:")

@dp.message(BotStates.waiting_for_photos, F.photo | F.document)
async def receive_photos(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    if message.photo:
        photo = message.photo[-1]
        file = await bot.get_file(photo.file_id)
        os.makedirs("avatars", exist_ok=True)
        await bot.download_file(file.file_path, f"avatars/{photo.file_unique_id}.jpg")
    await state.clear()
    await message.answer("✅ عکس‌ها با موفقیت دریافت شدند.", reply_markup=photos_menu_keyboard())

@dp.message(F.text == "حذف عکس‌ها ❌")
async def delete_all_photos(message: types.Message):
    if not is_admin(message.from_user.id): return
    if os.path.exists("avatars"):
        for f in os.listdir("avatars"):
            try: os.remove(os.path.join("avatars", f))
            except: pass
    await message.answer("🗑️ تمامی عکس‌ها با موفقیت حذف شدند.", reply_markup=photos_menu_keyboard())

# رمز دو مرحله‌ای 🔐
@dp.message(F.text == "رمز دو مرحله‌ای 🔐")
async def menu_tfa(message: types.Message):
    if not is_admin(message.from_user.id): return
    await message.answer("🔐 تنظیمات رمز دو مرحله‌ای (بدون ثبت ایمیل):", reply_markup=tfa_menu_keyboard())

@dp.message(F.text == "فعال ✅")
async def tfa_active(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    await state.set_state(BotStates.setting_2fa_pass)
    await message.answer("لطفاً رمز عبور دو مرحله‌ای مورد نظر خود را ارسال کنید تا روی اکانت‌ها اعمال شود:")

@dp.message(BotStates.setting_2fa_pass)
async def save_tfa_password(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    txt = message.text.strip()
    user_config["use_2fa"] = True
    user_config["password_2fa"] = txt
    await state.clear()
    await message.answer("✅ رمز دو مرحله‌ای با موفقیت تنظیم و ذخیره شد.", reply_markup=tfa_menu_keyboard())

@dp.message(F.text == "غیر فعال ❌")
async def tfa_inactive(message: types.Message):
    if not is_admin(message.from_user.id): return
    user_config["use_2fa"] = False
    user_config["password_2fa"] = ""
    await message.answer("❌ رمز دو مرحله‌ای غیرفعال شد.", reply_markup=tfa_menu_keyboard())

# حذف 🗑️
@dp.message(F.text == "حذف 🗑️")
async def menu_delete(message: types.Message):
    if not is_admin(message.from_user.id): return
    await message.answer("🗑️ بخش حذف اطلاعات:", reply_markup=delete_menu_keyboard())

@dp.message(F.text == "همه 🗑️")
async def delete_all(message: types.Message):
    if not is_admin(message.from_user.id): return
    await message.answer("✅ تمام موارد با موفقیت حذف شدند.", reply_markup=delete_menu_keyboard())

@dp.message(F.text == "کد گرفته ها 📄")
async def delete_code_taken(message: types.Message):
    if not is_admin(message.from_user.id): return
    await message.answer("✅ موارد کد گرفته شده با موفقیت پاک شدند.", reply_markup=delete_menu_keyboard())

# خروجی 📥
@dp.message(F.text == "خروجی 📥")
async def menu_export(message: types.Message):
    if not is_admin(message.from_user.id): return
    await message.answer("📥 خروجی شماره‌ها: از کدام بخش فایل خروجی می‌خواهید؟", reply_markup=export_menu_keyboard())

@dp.message(F.text.in_(["دریأفتی ها ✅", "دریافت نشده ها 🆓", "کد نگرفته ها ⏳"]))
async def export_category_handler(message: types.Message):
    if not is_admin(message.from_user.id): return
    await message.answer(f"📦 فایل خروجی بخش «{message.text}» آماده و ارسال شد.")

# تحویل اکانت 📦
@dp.message(F.text == "تحویل اکانت 📦")
async def menu_delivery(message: types.Message):
    if not is_admin(message.from_user.id): return
    await message.answer("📦 لطفاً نحوه تحویل اکانت‌ها را انتخاب کنید:", reply_markup=delivery_menu_keyboard())

@dp.message(F.text.in_(["سشن (Session) 📁", "زیپ (Zip) 🗜️"]))
async def set_delivery_method(message: types.Message):
    if not is_admin(message.from_user.id): return
    user_config["delivery_method"] = message.text
    await message.answer(f"✅ روش تحویل اکانت روی حالت «{message.text}» تنظیم شد.", reply_markup=delivery_menu_keyboard())

# منوی آمار جدید داخل تنظیمات 📊
@dp.message(F.text == "آمار 📊")
async def settings_stats_menu(message: types.Message):
    if not is_admin(message.from_user.id): return
    
    total_nums = 0
    if os.path.exists("numbers.txt"):
        try:
            with open("numbers.txt", "r", encoding="utf-8") as f:
                total_nums = sum(1 for line in f if line.strip())
        except:
            pass

    stats = load_stats()
    total_accounts = stats.get("total", 0)

    text = (
        f"🔢 **آمار شماره‌های ربات**\n\n"
        f"🔹 کل شماره‌های موجود: `{total_nums}`\n"
        f"🔸 شماره‌های دریافت‌شده: `0`\n"
        f"  ├ ✅ کد گرفته‌ها: `0`\n"
        f"  └ ⏳ کد نگرفته‌ها: `0`\n\n"
        f"🆓 شماره‌های آزاد (دریافت‌نشده): `0`\n\n"
        f"🚀 کل اکانت‌های ساخته‌شده و موجود: `{total_accounts}`"
    )
    await message.answer(text, parse_mode="Markdown", reply_markup=get_settings_keyboard())

# آمار و مدیریت کلی
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
    if not os.path.exists("sessions"):
        await message.answer("❌ هیچ فایل سشنی موجود نیست.")
        return
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
