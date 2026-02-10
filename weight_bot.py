import os
import sqlite3
import logging
from datetime import datetime, timezone, timedelta
import asyncio
import threading
from telegram import Update, InputFile, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
ADMIN_ID = 203790724  # Замените на ваш ID Telegram

# ========== ДОБАВЬТЕ ЭТУ ПРОВЕРКУ ==========
if not TELEGRAM_TOKEN:
    logger.error("❌ ОШИБКА: TELEGRAM_TOKEN не установлен!")
    logger.error("Добавьте TELEGRAM_TOKEN в переменные окружения Railway")
    logger.error("Settings → Variables → New Variable")
    exit(1)

# Проверяем формат токена
if ':' not in TELEGRAM_TOKEN:
    logger.error(f"❌ НЕВЕРНЫЙ ФОРМАТ ТОКЕНА: {TELEGRAM_TOKEN}")
    logger.error("Токен должен быть: 1234567890:ABCdefGHIjklMNOpqrsTUVwxyz")
    exit(1)

# Выводим информацию о токене (первые 10 символов для безопасности)
logger.info(f"✅ Токен получен: {TELEGRAM_TOKEN[:10]}...")
logger.info(f"👑 Администратор: {ADMIN_ID}")
logger.info("🤖 Запускаем Telegram Weight Bot...")
logger.info("🌍 Временная зона: Самара (UTC+4)")
logger.info("🔄 Автоматический бэкап: каждые 4 часа")
logger.info("📋 Доступные команды в боте:")
logger.info("  /start - Начать работу")
logger.info("  /help - Помощь и инструкции")
logger.info("  /last - Последний вес")
logger.info("  /history - История измерений")
logger.info("  /delete_last - Удалить последнюю запись о весе")
logger.info("  /backup - Создать резервную копию (админ)")
logger.info("  /backup_status - Статус автоматического бэкапа")
logger.info("  Просто отправьте вес числом (например: 75.5)")

# ==========================================

# Настройка временной зоны Самары (UTC+4)
SAMARA_TZ = timezone(timedelta(hours=4))

# Глобальные переменные для управления бэкапом
backup_job = None
backup_enabled = True
last_backup_time = None
backup_interval_hours = 4


def get_samara_time():
    """Получить текущее время в Самаре"""
    return datetime.now(SAMARA_TZ)


def format_samara_time(dt=None, date_only=False):
    """Форматировать время в Самаре"""
    if dt is None:
        dt = get_samara_time()

    if isinstance(dt, str):
        try:
            # Если dt - строка из базы данных, преобразуем её
            # Время в базе хранится как строка в формате Самары
            dt = datetime.strptime(dt, '%Y-%m-%d %H:%M:%S')
        except:
            return dt

    if date_only:
        return dt.strftime('%d.%m.%Y')
    else:
        return dt.strftime('%d.%m.%Y %H:%M')


# Инициализация базы данных
def init_db():
    # Создаем папку data если её нет
    os.makedirs('data', exist_ok=True)

    # Подключаемся к базе в папке data
    conn = sqlite3.connect('data/weight_tracker.db')
    cursor = conn.cursor()

    # Создаем таблицу пользователей
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            last_name TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Создаем таблицу записей веса
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS weight_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            weight REAL NOT NULL,
            date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (user_id)
        )
    ''')

    # Создаем индекс для быстрого поиска последней записи
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_weight_records 
        ON weight_records (user_id, date DESC)
    ''')

    conn.commit()
    conn.close()
    print("✅ База данных инициализирована")


# Функция для регистрации пользователя
def register_user(user_id, username, first_name, last_name):
    conn = sqlite3.connect('data/weight_tracker.db')
    cursor = conn.cursor()

    cursor.execute('''
        INSERT OR IGNORE INTO users (user_id, username, first_name, last_name)
        VALUES (?, ?, ?, ?)
    ''', (user_id, username, first_name, last_name))

    conn.commit()
    conn.close()


# Функция для сохранения веса с текущим временем Самары
def save_weight(user_id, weight):
    conn = sqlite3.connect('data/weight_tracker.db')
    cursor = conn.cursor()

    # Получаем текущее время в Самаре и форматируем для SQLite
    current_time = get_samara_time().strftime('%Y-%m-%d %H:%M:%S')

    # Сохраняем вес с текущим временем Самары
    cursor.execute('''
        INSERT INTO weight_records (user_id, weight, date)
        VALUES (?, ?, ?)
    ''', (user_id, weight, current_time))

    conn.commit()
    conn.close()


# Функция для получения последнего веса
def get_last_weight(user_id):
    conn = sqlite3.connect('data/weight_tracker.db')
    cursor = conn.cursor()

    cursor.execute('''
        SELECT weight, date, id
        FROM weight_records 
        WHERE user_id = ? 
        ORDER BY date DESC 
        LIMIT 1
    ''', (user_id,))

    result = cursor.fetchone()
    conn.close()

    return result


# Функция для получения ID последней записи
def get_last_weight_id(user_id):
    conn = sqlite3.connect('data/weight_tracker.db')
    cursor = conn.cursor()

    cursor.execute('''
        SELECT id
        FROM weight_records 
        WHERE user_id = ? 
        ORDER BY date DESC 
        LIMIT 1
    ''', (user_id,))

    result = cursor.fetchone()
    conn.close()

    return result[0] if result else None


# Функция для удаления последней записи о весе
def delete_last_weight(user_id):
    conn = sqlite3.connect('data/weight_tracker.db')
    cursor = conn.cursor()

    # Получаем ID последней записи
    last_id = get_last_weight_id(user_id)

    if not last_id:
        conn.close()
        return None

    # Получаем информацию об удаляемой записи перед удалением
    cursor.execute('''
        SELECT weight, date 
        FROM weight_records 
        WHERE id = ?
    ''', (last_id,))

    record_to_delete = cursor.fetchone()

    # Удаляем запись
    cursor.execute('''
        DELETE FROM weight_records 
        WHERE id = ?
    ''', (last_id,))

    conn.commit()
    conn.close()

    return record_to_delete


# Функция для получения истории веса
def get_weight_history(user_id, limit=10):
    conn = sqlite3.connect('data/weight_tracker.db')
    cursor = conn.cursor()

    cursor.execute('''
        SELECT weight, date 
        FROM weight_records 
        WHERE user_id = ? 
        ORDER BY date DESC 
        LIMIT ?
    ''', (user_id, limit))

    results = cursor.fetchall()
    conn.close()

    return results


# Функция для создания клавиатуры с кнопками
def get_main_keyboard():
    keyboard = [
        [KeyboardButton("📊 Отправить вес")],
        [KeyboardButton("📅 Последний вес"), KeyboardButton("📈 История")],
        [KeyboardButton("🗑️ Удалить последнее"), KeyboardButton("ℹ️ Помощь")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=False)


# Команда /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    register_user(user.id, user.username, user.first_name, user.last_name)

    # Получаем текущее время в Самаре
    current_time = format_samara_time()

    welcome_text = f"""
👋 Привет, {user.first_name}!

Я бот для отслеживания веса.

🌍 Временная зона: Самара (UTC+4)
🕐 Текущее время: {current_time}

📊 Просто отправь мне свой вес в килограммах (например: 75.5 или 80).

📈 Я буду сохранять его и показывать изменения.

👇 Используй кнопки ниже для управления:
"""

    await update.message.reply_text(welcome_text, reply_markup=get_main_keyboard())


# Команда /help
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    current_time = format_samara_time()

    help_text = f"""
📋 Как пользоваться ботом:

🌍 Временная зона: Самара (UTC+4)
🕐 Текущее время: {current_time}

Просто отправьте свой вес в килограммах.
Примеры: 75.5, 80, 68.3

📊 Команды:
📊 Отправить вес - Ввести текущий вес
📅 Последний вес - Посмотреть последнее измерение
📈 История - История измерений (последние 10)
🗑️ Удалить последнее - Удалить последнюю запись
ℹ️ Помощь - Эта справка

💡 Совет: Отправляйте вес каждый день в одно и то же время для более точного отслеживания!
"""

    await update.message.reply_text(help_text, reply_markup=get_main_keyboard())


# Команда /last
async def last_weight(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    last_record = get_last_weight(user_id)

    if last_record:
        weight, date, _ = last_record
        # Преобразуем время в Самару
        formatted_date = format_samara_time(date)

        await update.message.reply_text(
            f"🌍 Временная зона: Самара (UTC+4)\n"
            f"📅 Последнее измерение: {formatted_date}\n"
            f"⚖️ Вес: {weight} кг",
            reply_markup=get_main_keyboard()
        )
    else:
        await update.message.reply_text(
            "📭 У вас еще нет записей о весе. Отправьте свой вес!",
            reply_markup=get_main_keyboard()
        )


# Команда /history
async def weight_history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    history = get_weight_history(user_id)

    if history:
        response = "🌍 Временная зона: Самара (UTC+4)\n"
        response += "📊 История ваших измерений:\n\n"
        for i, (weight, date) in enumerate(history, 1):
            # Форматируем дату для Самары
            formatted_date = format_samara_time(date, date_only=True)
            response += f"{i}. {formatted_date}: {weight} кг\n"

        # Добавляем изменение с первого до последнего измерения
        if len(history) > 1:
            first_weight = history[-1][0]  # Самый старый
            last_weight = history[0][0]  # Самый новый
            difference = last_weight - first_weight

            if difference > 0:
                response += f"\n📈 Общее изменение: +{difference:.1f} кг"
            elif difference < 0:
                response += f"\n📉 Общее изменение: {difference:.1f} кг"
            else:
                response += f"\n📊 Вес не изменился"
    else:
        response = "📭 У вас еще нет записей о весе."

    await update.message.reply_text(response, reply_markup=get_main_keyboard())


async def delete_last_weight_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    # Проверяем, есть ли записи у пользователя
    last_record = get_last_weight(user_id)

    if not last_record:
        await update.message.reply_text(
            "📭 У вас нет записей для удаления.",
            reply_markup=get_main_keyboard()
        )
        return

    # Создаем inline-кнопки подтверждения
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup

    keyboard = [
        [
            InlineKeyboardButton("✅ Да, удалить", callback_data=f"delete_confirm_{user_id}"),
            InlineKeyboardButton("❌ Нет, отмена", callback_data=f"delete_cancel_{user_id}")
        ]
    ]

    weight, date, _ = last_record

    # Форматируем дату для Самары
    formatted_date = format_samara_time(date)

    await update.message.reply_text(
        f"❓ Вы уверены, что хотите удалить последнюю запись?\n\n"
        f"🌍 Временная зона: Самара (UTC+4)\n"
        f"📅 Дата: {formatted_date}\n"
        f"⚖️ Вес: {weight} кг\n\n"
        f"Это действие нельзя отменить!",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


# Обработка callback-запросов (inline-кнопок)
async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    callback_data = query.data
    user_id = query.from_user.id

    # Проверяем, что callback_data принадлежит текущему пользователю
    if not callback_data.endswith(str(user_id)):
        await query.edit_message_text("⛔ Это действие предназначено другому пользователю.")
        return

    if callback_data.startswith("delete_confirm"):
        # Удаляем последнюю запись
        deleted_record = delete_last_weight(user_id)

        if deleted_record:
            weight, date = deleted_record
            # Форматируем дату для Самары
            formatted_date = format_samara_time(date)

            await query.edit_message_text(
                f"🗑️ Запись успешно удалена!\n\n"
                f"🌍 Временная зона: Самара (UTC+4)\n"
                f"📅 Дата: {formatted_date}\n"
                f"⚖️ Вес: {weight} кг\n\n"
                f"Теперь последней записью является предыдущее измерение."
            )
        else:
            await query.edit_message_text("❌ Ошибка при удалении записи.")

    elif callback_data.startswith("delete_cancel"):
        await query.edit_message_text("✅ Удаление отменено.")


# Обработка нажатий на кнопки клавиатуры
async def handle_button_press(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    user_id = update.effective_user.id

    if text == "📊 Отправить вес":
        current_time = format_samara_time()
        await update.message.reply_text(
            f"🌍 Временная зона: Самара (UTC+4)\n"
            f"🕐 Текущее время: {current_time}\n\n"
            f"Введите ваш вес в килограммах (например: 75.5 или 80):",
            reply_markup=get_main_keyboard()
        )

    elif text == "📅 Последний вес":
        await last_weight(update, context)

    elif text == "📈 История":
        await weight_history(update, context)

    elif text == "🗑️ Удалить последнее":
        await delete_last_weight_command(update, context)

    elif text == "ℹ️ Помощь":
        await help_command(update, context)


# Обработка сообщений с весом
async def handle_weight_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user_id = update.effective_user.id
        text = update.message.text.strip()

        # Пробуем преобразовать в число
        weight = float(text.replace(',', '.'))

        # Проверяем, что вес в разумных пределах
        if weight < 30 or weight > 300:
            await update.message.reply_text(
                "⚠️ Пожалуйста, введите реальный вес (30-300 кг)",
                reply_markup=get_main_keyboard()
            )
            return

        # Регистрируем пользователя если он новый
        user = update.effective_user
        register_user(user.id, user.username, user.first_name, user.last_name)

        # Получаем последний вес
        last_record = get_last_weight(user_id)

        # Сохраняем новый вес С ТЕКУЩИМ ВРЕМЕНЕМ САМАРЫ
        save_weight(user_id, weight)

        # Получаем текущее время в Самаре
        current_time = format_samara_time()

        # Формируем ответ
        response = f"✅ Вес сохранен!\n\n"
        response += f"🌍 Временная зона: Самара (UTC+4)\n"
        response += f"📅 Дата и время: {current_time}\n"
        response += f"⚖️ Вес: {weight} кг\n"

        if last_record:
            last_weight_value, last_date, _ = last_record
            difference = weight - last_weight_value

            # Форматируем дату последней записи для Самары
            formatted_last_date = format_samara_time(last_date, date_only=True)

            response += f"\n📊 Сравнение с последним измерением ({formatted_last_date}):\n"
            response += f"Предыдущий вес: {last_weight_value} кг\n"

            if difference > 0:
                response += f"📈 Изменение: +{difference:.1f} кг"
            elif difference < 0:
                response += f"📉 Изменение: {difference:.1f} кг"
            else:
                response += f"📊 Вес не изменился"
        else:
            response += "\n🎉 Это ваша первая запись! Продолжайте в том же духе!"

        await update.message.reply_text(response, reply_markup=get_main_keyboard())

    except ValueError:
        # Если не удалось преобразовать в число
        await update.message.reply_text(
            "⚠️ Пожалуйста, отправьте вес в виде числа (например: 75.5 или 80)",
            reply_markup=get_main_keyboard()
        )


# Команда для очистки истории (скрытая команда для админа)
async def clear_history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    conn = sqlite3.connect('data/weight_tracker.db')
    cursor = conn.cursor()

    cursor.execute('DELETE FROM weight_records WHERE user_id = ?', (user_id,))
    conn.commit()
    conn.close()

    await update.message.reply_text("🗑️ Ваша история веса очищена!", reply_markup=get_main_keyboard())


from backup import backup_database


# Команда /backup (для админа)
async def backup_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    # Проверка на администратора
    if user_id != ADMIN_ID:
        await update.message.reply_text("⛔ Эта команда только для администратора")
        return

    await update.message.reply_text("🔄 Создаю резервную копию...")

    # Создаем бэкап
    backup_file = backup_database()

    if backup_file and os.path.exists(backup_file):
        try:
            # Отправляем файл в Telegram
            with open(backup_file, 'rb') as file:
                await update.message.reply_document(
                    document=InputFile(file, filename=os.path.basename(backup_file)),
                    caption=f"✅ Резервная копия создана вручную: {os.path.basename(backup_file)}"
                )

        except Exception as e:
            await update.message.reply_text(f"❌ Ошибка при отправке файла: {e}")
    else:
        await update.message.reply_text("❌ Ошибка при создании резервной копии")


# Команда для управления автоматическим бэкапом
async def backup_status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    # Проверка на администратора
    if user_id != ADMIN_ID:
        await update.message.reply_text("⛔ Эта команда только для администратора")
        return

    global backup_enabled, last_backup_time, backup_interval_hours

    status_text = f"""
🔄 **Статус автоматического бэкапа**

{'✅ **ВКЛЮЧЕН**' if backup_enabled else '❌ **ВЫКЛЮЧЕН**'}
⏰ **Интервал:** каждые {backup_interval_hours} часа
📅 **Последний бэкап:** {last_backup_time if last_backup_time else 'Еще не создан'}

**Команды:**
/backup_enable - Включить автобэкап
/backup_disable - Выключить автобэкап
/backup_now - Создать бэкап сейчас
/backup_set_interval X - Установить интервал (в часах)
"""

    await update.message.reply_text(status_text)


async def backup_enable_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != ADMIN_ID:
        await update.message.reply_text("⛔ Эта команда только для администратора")
        return

    global backup_enabled
    backup_enabled = True
    await update.message.reply_text("✅ Автоматический бэкап включен")


async def backup_disable_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != ADMIN_ID:
        await update.message.reply_text("⛔ Эта команда только для администратора")
        return

    global backup_enabled
    backup_enabled = False
    await update.message.reply_text("⛔ Автоматический бэкап выключен")


async def backup_set_interval_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != ADMIN_ID:
        await update.message.reply_text("⛔ Эта команда только для администратора")
        return

    try:
        interval = int(context.args[0])
        if interval < 1 or interval > 24:
            await update.message.reply_text("❌ Интервал должен быть от 1 до 24 часов")
            return

        global backup_interval_hours
        backup_interval_hours = interval
        await update.message.reply_text(f"✅ Интервал бэкапа установлен: каждые {interval} часов")

    except (IndexError, ValueError):
        await update.message.reply_text("❌ Использование: /backup_set_interval <часы>")


async def backup_now_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != ADMIN_ID:
        await update.message.reply_text("⛔ Эта команда только для администратора")
        return

    await create_and_send_backup(context.bot)


# Команда /time - показать текущее время в Самаре
async def show_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    current_time = format_samara_time()

    time_info = f"""
🌍 Временная зона: Самара (UTC+4)
🕐 Текущее время: {current_time}

📅 Все записи о весе сохраняются с местным временем Самары.
"""

    await update.message.reply_text(time_info, reply_markup=get_main_keyboard())


# Функция для создания и отправки бэкапа
async def create_and_send_backup(bot):
    global last_backup_time

    try:
        logger.info("🔄 Запускаю автоматический бэкап...")

        # Создаем бэкап
        backup_file = backup_database()

        if backup_file and os.path.exists(backup_file):
            # Отправляем файл админу
            with open(backup_file, 'rb') as file:
                await bot.send_document(
                    chat_id=ADMIN_ID,
                    document=InputFile(file, filename=os.path.basename(backup_file)),
                    caption=f"✅ Автоматический бэкап создан: {os.path.basename(backup_file)}\n"
                            f"🕐 Время: {format_samara_time()}"
                )

            last_backup_time = format_samara_time()
            logger.info(f"✅ Автоматический бэкап отправлен админу: {backup_file}")

            # Удаляем файл после отправки (опционально)
            # os.remove(backup_file)

        else:
            logger.error("❌ Не удалось создать файл бэкапа")

    except Exception as e:
        logger.error(f"❌ Ошибка при создании/отправке бэкапа: {e}")


# Функция для периодического создания бэкапов
async def auto_backup_task(bot):
    global backup_enabled, backup_interval_hours

    while True:
        try:
            await asyncio.sleep(backup_interval_hours * 3600)  # Ждем заданное количество часов

            if backup_enabled:
                await create_and_send_backup(bot)

        except Exception as e:
            logger.error(f"❌ Ошибка в задаче автобэкапа: {e}")
            await asyncio.sleep(300)  # Ждем 5 минут при ошибке


# Главная функция
async def main():
    # Инициализируем базу данных
    init_db()

    # Создаем приложение
    application = Application.builder().token(TELEGRAM_TOKEN).build()

    # Регистрируем обработчики команд
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("last", last_weight))
    application.add_handler(CommandHandler("history", weight_history))
    application.add_handler(CommandHandler("delete_last", delete_last_weight_command))
    application.add_handler(CommandHandler("clear", clear_history))
    application.add_handler(CommandHandler("backup", backup_command))
    application.add_handler(CommandHandler("time", show_time))
    application.add_handler(CommandHandler("backup_status", backup_status_command))
    application.add_handler(CommandHandler("backup_enable", backup_enable_command))
    application.add_handler(CommandHandler("backup_disable", backup_disable_command))
    application.add_handler(CommandHandler("backup_set_interval", backup_set_interval_command))
    application.add_handler(CommandHandler("backup_now", backup_now_command))

    # Добавляем обработчик callback-запросов
    application.add_handler(CallbackQueryHandler(button_callback))

    # Регистрируем обработчик нажатий на кнопки клавиатуры
    application.add_handler(MessageHandler(
        filters.Regex(r'^(📊 Отправить вес|📅 Последний вес|📈 История|🗑️ Удалить последнее|ℹ️ Помощь)$'),
        handle_button_press
    ))

    # Регистрируем обработчик текстовых сообщений (для ввода веса)
    application.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND,
        handle_weight_message
    ))

    # Запускаем бота
    logger.info("🤖 Бот успешно запущен на Railway!")
    logger.info("🌍 Временная зона: Самара (UTC+4)")
    logger.info("🔄 Автоматический бэкап: каждые 4 часа")
    logger.info("👑 Админ ID:", ADMIN_ID)
    logger.info("📱 Откройте Telegram и найдите своего бота")
    logger.info("👉 Отправьте команду /start")

    # Получаем бота для задачи автобэкапа
    bot = application.bot

    # Запускаем задачу автобэкапа в фоне
    backup_task = asyncio.create_task(auto_backup_task(bot))

    try:
        # Запускаем polling
        await application.run_polling()
    except Exception as e:
        logger.error(f"❌ Ошибка при запуске бота: {e}")
        logger.info("🔄 Попробуйте перезапустить деплоймент на Railway")
    except KeyboardInterrupt:
        logger.info("\n🛑 Бот остановлен")
    finally:
        # Отменяем задачу автобэкапа при выходе
        backup_task.cancel()


if __name__ == '__main__':
    asyncio.run(main())