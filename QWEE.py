import subprocess
import sys
import asyncio
import importlib.util

# === АВТОУСТАНОВКА ЗАВИСИМОСТЕЙ ===
def install_package(package):
    """Устанавливает пакет через pip"""
    subprocess.check_call([sys.executable, "-m", "pip", "install", package])

# Проверяем telethon
if importlib.util.find_spec("telethon") is None:
    print("📦 Устанавливаю telethon...")
    install_package("telethon==1.42.0")

# Проверяем aiogram
if importlib.util.find_spec("aiogram") is None:
    print("📦 Устанавливаю aiogram...")
    install_package("aiogram==3.24.0")

# Теперь можно импортировать
from datetime import datetime, timedelta, timezone
from telethon import TelegramClient
from aiogram import Bot, Dispatcher, types
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State

# ВСТАВЬ СВОИ ДАННЫЕ СЮДА:
API_ID = 34568849         # Твой ID с my.telegram.org
API_HASH = '264ef441fd914ba29bd3b39f5c0d8b6e'    # Твой Hash с my.telegram.org
BOT_TOKEN = '8324938233:AAG4ZnHTNE--ELRVnP-zMrR5h4w6CvFBNOI'  # Токен от @BotFather

# Инициализация
client = TelegramClient('session_name', API_ID, API_HASH)
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

class Analyze(StatesGroup):
    waiting_for_link = State()
    waiting_for_count = State()

@dp.message(CommandStart())
async def cmd_start(message: types.Message, state: FSMContext):
    await message.answer("🔗 Пришли ссылку на канал (например, @news или https://t.me):")
    await state.set_state(Analyze.waiting_for_link)

@dp.message(Analyze.waiting_for_link)
async def process_link(message: types.Message, state: FSMContext):
    await state.update_data(link=message.text)
    await message.answer("🔢 Сколько последних постов проанализировать?")
    await state.set_state(Analyze.waiting_for_count)

@dp.message(Analyze.waiting_for_count)
async def process_count(message: types.Message, state: FSMContext):
    if not message.text.isdigit():
        return await message.answer("Введи число!")

    count = int(message.text)
    data = await state.get_data()
    link = data['link']
    
    status = await message.answer("⏳ Читаю канал и считаю реакции... Это может занять время.")
    
    try:
        # Подключаем "клиента" (Userbot)
        await client.start()
        
        best_post = None
        max_reac = -1

        # Читаем указанное количество постов
        async for msg in client.iter_messages(link, limit=count):
            # Считаем сумму всех реакций на посте
            reac_count = 0
            if msg.reactions:
                reac_count = sum(r.count for r in msg.reactions.results)
            
            if reac_count >= max_reac:
                max_reac = reac_count
                best_post = msg

        if best_post:
            # Формируем ответ
            text = (
                f"🔥 **Самый популярный пост в {link}**\n"
                f"📊 Реакций: {max_reac}\n\n"
                f"{best_post.text[:800] if best_post.text else '[Медиа без текста]'}\n\n"
                f"🔗 [Ссылка на оригинал](https://t.me/{link.split('/')[-1]}/{best_post.id})"
            )
            await message.answer(text, parse_mode="Markdown")
        else:
            await message.answer("❌ Посты не найдены.")

    except Exception as e:
        await message.answer(f"⚠️ Ошибка доступа к каналу: {e}")
    finally:
        await status.delete()
        await state.clear()

async def main():
    await client.connect() # Подключаем "аккаунт"
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())