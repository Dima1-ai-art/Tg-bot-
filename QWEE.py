import asyncio
import importlib.util
import subprocess

# === АВТОУСТАНОВКА ЗАВИСИМОСТЕЙ ===
def install_package(package):
    """Устанавливает пакет через pip."""
    print(f"📦 Устанавливаю {package}...")
    try:
        subprocess.check_call(["pip", "install", package])
        print(f"✅ {package} успешно установлен.")
    except FileNotFoundError:
        print("\n" + "="*50)
        print("❌ Ошибка: Команда 'pip' не найдена.")
        print("Это означает, что Python не смог найти программу 'pip'.")
        print("Возможно, Python установлен некорректно, или путь к 'pip' не добавлен в переменную окружения PATH.")
        print("Пожалуйста, установите пакеты вручную командой:")
        print(f"pip install {package}")
        print("="*50 + "\n")
        raise
    except subprocess.CalledProcessError as e:
        print(f"❌ Ошибка при установке {package}: {e}")
        raise e

# Проверяем telethon
if importlib.util.find_spec("telethon") is None:
    install_package("telethon==1.42.0")

# Проверяем aiogram
if importlib.util.find_spec("aiogram") is None:
    install_package("aiogram==3.24.0")

# Импорты после установки
from datetime import datetime, timedelta, timezone
from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError, FloodWaitError, UserDeactivatedError, PhoneNumberInvalidError, ApiIdInvalidError
from aiogram import Bot, Dispatcher, types
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.exceptions import TelegramMigrateToChat, TelegramBadRequest # Добавим импорты для ошибок aiogram

# === КОНФИГУРАЦИЯ ===
API_ID = 34568849
API_HASH = '264ef441fd914ba29bd3b39f5c0d8b6e'
BOT_TOKEN = '8324938233:AAG4ZnHTNE--ELRVnP-zMrR5h4w6CvFBNOI'

# Данные для авторегистрации (userbot setup)
PHONE_NUMBER = "+79952742016"
SESSION_NAME = "my_telegram_session"

# === ИНИЦИАЛИЗАЦИЯ ===
client = TelegramClient(SESSION_NAME, API_ID, API_HASH)
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# === СОСТОЯНИЯ FSM ===
class Analyze(StatesGroup):
    waiting_for_link = State()
    waiting_for_count = State()

# === ВСПОМОГАТЕЛЬНАЯ ФУНКЦИЯ ДЛЯ АВТОРИЗАЦИИ TELETHON ===
async def authorize_telethon_client():
    """
    Авторизует Telethon клиента.
    Если клиент уже авторизован, ничего не делает.
    Если не авторизован, запускает процесс входа.
    """
    if await client.is_user_authorized():
        print("Telethon клиент уже авторизован.")
        return True

    print("Telethon клиент не авторизован. Начинаем процесс авторизации...")
    try:
        await client.send_code_request(PHONE_NUMBER)
        print("Код запрошен. Пожалуйста, проверьте ваш Telegram.")
        # В реальном приложении лучше получать код через бота или другое безопасное взаимодействие
        phone_code = input('Введите код, полученный в Telegram: ')
        await client.sign_in(PHONE_NUMBER, phone_code)
        print("✅ Пользователь успешно авторизован.")
        return True
    except SessionPasswordNeededError:
        print("Требуется пароль для двухфакторной аутентификации.")
        app_password = input('Введите пароль для двухфакторной аутентификации: ')
        await client.sign_in(password=app_password)
        print("✅ Пользователь успешно авторизован (с паролем).")
        return True
    except PhoneNumberInvalidError:
        print(f"❌ Ошибка: Номер телефона '{PHONE_NUMBER}' введен некорректно.")
        return False
    except ApiIdInvalidError:
        print("❌ Ошибка: API ID или API Hash некорректны. Проверьте ваши данные.")
        return False
    except Exception as e:
        print(f"❌ Непредвиденная ошибка при авторизации Telethon: {e}")
        return False

# === ОБРАБОТЧИКИ СООБЩЕНИЙ ===
@dp.message(CommandStart())
async def cmd_start(message: types.Message, state: FSMContext):
    """Обработчик команды /start. Просит ссылку на канал."""
    await message.answer("🔗 Пришли ссылку на канал (например, @news или https://t.me/news):")
    await state.set_state(Analyze.waiting_for_link)

@dp.message(Analyze.waiting_for_link)
async def process_link(message: types.Message, state: FSMContext):
    """Обработчик получения ссылки. Просит количество постов."""
    await state.update_data(link=message.text)
    await message.answer("🔢 Сколько последних постов проанализировать?")
    await state.set_state(Analyze.waiting_for_count)

@dp.message(Analyze.waiting_for_count)
async def process_count(message: types.Message, state: FSMContext):
    """Обработчик получения количества постов. Анализирует канал."""
    if not message.text.isdigit():
        return await message.answer("❌ Введи число! Попробуй снова.")

    count = int(message.text)
    data = await state.get_data()
    link = data['link']

    status_message = await message.answer("⏳ Читаю канал и считаю реакции... Это может занять некоторое время.")

    try:
        # 1. Подключаемся к Telethon, если это не сделано
        if not client.is_connected():
            print("Подключаемся к серверам Telegram...")
            await client.connect()
            print("Подключение установлено.")

        # 2. Авторизуем пользователя, если это необходимо
        if not await client.is_user_authorized():
            auth_success = await authorize_telethon_client()
            if not auth_success:
                await message.answer("❌ Не удалось авторизоваться в Telegram. Пожалуйста, проверьте введенные данные и настройки.")
                await state.clear()
                await status_message.delete()
                return

        # --- Анализ постов ---
        best_post = None
        max_reac_count = -1

        print(f"Анализирую последние {count} постов из канала: {link}")

        # Получаем объект чата (entity) для корректной работы
        try:
            # client.get_entity() работает только после client.connect()
            entity = await client.get_entity(link)
        except ValueError:
            await message.answer(f"❌ Не удалось найти канал или пользователя по ссылке: {link}. Проверьте правильность ссылки.")
            await state.clear()
            await status_message.delete()
            return
        except Exception as e:
            await message.answer(f"❌ Ошибка при получении информации о канале '{link}': {e}")
            print(f"Ошибка get_entity: {e}")
            await state.clear()
            await status_message.delete()
            return

        # Итерируемся по сообщениям ПОСЛЕ установления соединения и получения entity
        post_counter = 0 # Считаем, сколько постов уже обработали
        total_posts_processed = 0 # Общее количество постов в канале (приблизительно)
        last_message_id = None

        # Получаем ID первого сообщения (самого старого) для более точного отображения прогресса
        # Это может занять время, поэтому вынесем отдельно
        try:
            first_message = await client.get_messages(entity, limit=1)
            if first_message:
                last_message_id = first_message[0].id # ID самого старого поста
        except Exception as e:
            print(f"Не удалось получить ID первого сообщения: {e}. Прогресс может отображаться некорректно.")


        async for msg in client.iter_messages(entity, limit=count):
            post_counter += 1
            current_reac_count = 0
            if msg.reactions:
                current_reac_count = sum(r.count for r in msg.reactions.results)

            if current_reac_count >= max_reac_count:
                max_reac_count = current_reac_count
                best_post = msg

            # Обновляем статус сообщения бота
            if last_message_id is not None:
                progress_text = f"⏳ Обработано {post_counter}/{count} постов..."
                try:
                    await status_message.edit_text(progress_text)
                except: # Игнорируем, если сообщение уже удалено или не может быть изменено
                    pass
            else: # Если last_message_id не удалось получить
                try:
                    await status_message.edit_text(f"⏳ Обработано {post_counter}/{count} постов...")
                except:
                    pass


        # --- Результат анализа ---
        if best_post:
            post_text_preview = best_post.text[:800] if best_post.text else "[Медиа без текстового описания]"
            target_chat_id = link.split('/')[-1].replace('@', '') if '/' in link else link.replace('@', '')
            result_text = (
                f"🔥 **Самый популярный пост в канале '{link}'**\n"
                f"📊 Общее количество реакций: **{max_reac_count}**\n\n"
                f"{post_text_preview}\n\n"
                f"🔗 [Перейти к посту](https://t.me/{target_chat_id}/{best_post.id})"
            )
            await message.answer(result_text, parse_mode="Markdown")
        else:
            await message.answer("❌ К сожалению, посты в указанном канале не найдены или не удалось получить данные.")

    except FloodWaitError as e:
        await message.answer(f"⚠️ Слишком частые запросы к Telegram. Попробуйте через {e.seconds} секунд.")
        print(f"FloodWaitError: {e.seconds} секунд.")
    except UserDeactivatedError:
        await message.answer("❌ Аккаунт Telegram, используемый для подключения, деактивирован.")
        print("Ошибка: Аккаунт Telegram деактивирован.")
    except ConnectionError as e: # Ловим нашу собственную ошибку, если клиент все же не подключен
        await message.answer(f"❌ Произошла ошибка соединения с Telegram: {e}. Пожалуйста, проверьте ваше интернет-соединение и попробуйте позже.")
        print(f"Ошибка: {e}")
    except Exception as e: # Общий обработчик ошибок
        await message.answer(f"⚠️ Произошла неизвестная ошибка при доступе к каналу или обработке: {e}")
        print(f"Серьезная ошибка: {e}")
    finally:
        # Очищаем состояние FSM после завершения обработки
        await state.clear()
        # Удаляем сообщение-статус
        try:
            await status_message.delete()
        except:
            pass # Игнорируем, если сообщение уже удалено или не было отправлено

# === ЗАПУСК БОТА ===
async def main():
    """Запускает polling для бота и управляет подключением Telethon."""
    print("Bot started. Press Ctrl+C to stop.")

    # Подключаем Telethon при запуске бота
    try:
        print("Подключаем Telethon клиента...")
        await client.connect()
        print("Telethon клиент подключен.")
        if not await client.is_user_authorized():
            print("Клиент не авторизован. Запускаем процесс авторизации...")
            await authorize_telethon_client()
    except Exception as e:
        print(f"❌ Ошибка при инициализации Telethon: {e}. Бот может работать с ограничениями.")

    # Запускаем polling бота
    await dp.start_polling(bot)

    # Этот блок будет выполнен при остановке бота (например, Ctrl+C)
    print("Stopping bot...")
    await client.disconnect() # Отключаем Telethon клиент
    print("Telethon client disconnected.")
    print("Bot stopped.")

if __name__ == "__main__":
    # Запускаем асинхронную функцию main
    asyncio.run(main())
