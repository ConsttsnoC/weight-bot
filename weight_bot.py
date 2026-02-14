import os
import sqlite3
import logging
from datetime import datetime, timezone, timedelta
from telegram import Update, InputFile, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
from admin_stats import (
    stats_command,
    users_command,
    user_details_command,
    admin_callback_handler
)

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')

# ========== ПРОВЕРКА ТОКЕНА ==========
if not TELEGRAM_TOKEN:
    logger.error("❌ ОШИБКА: TELEGRAM_TOKEN не установлен!")
    logger.error("Добавьте TELEGRAM_TOKEN в переменные окружения Railway")
    logger.error("Settings → Variables → New Variable")
    exit(1)

if ':' not in TELEGRAM_TOKEN:
    logger.error(f"❌ НЕВЕРНЫЙ ФОРМАТ ТОКЕНА: {TELEGRAM_TOKEN}")
    logger.error("Токен должен быть: 1234567890:ABCdefGHIjklMNOpqrsTUVwxyz")
    exit(1)

logger.info(f"✅ Токен получен: {TELEGRAM_TOKEN[:10]}...")
logger.info("🤖 Запускаем Telegram Weight Bot...")
logger.info("🌍 Временная зона: Самара (UTC+4)")
logger.info("📋 Доступные команды в боте:")
logger.info("  /start - Начать работу")
logger.info("  /help - Помощь и инструкции")
logger.info("  /last - Последний вес")
logger.info("  /history - История измерений")
logger.info("  /delete_last - Удалить последнюю запись о весе")
logger.info("  Просто отправьте вес числом (например: 75.5)")

# Настройка временной зоны Самары (UTC+4)
SAMARA_TZ = timezone(timedelta(hours=4))


def get_samara_time():
    """Получить текущее время в Самаре"""
    return datetime.now(SAMARA_TZ)


def format_samara_time(dt=None, date_only=False):
    """Форматировать время в Самаре"""
    if dt is None:
        dt = get_samara_time()

    if isinstance(dt, str):
        try:
            dt = datetime.strptime(dt, '%Y-%m-%d %H:%M:%S')
        except:
            return dt

    if date_only:
        return dt.strftime('%d.%m.%Y')
    else:
        return dt.strftime('%d.%m.%Y %H:%M')


# Инициализация базы данных
def init_db():
    os.makedirs('data', exist_ok=True)
    conn = sqlite3.connect('data/weight_tracker.db')
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            last_name TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS weight_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            weight REAL NOT NULL,
            date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (user_id)
        )
    ''')

    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_weight_records 
        ON weight_records (user_id, date DESC)
    ''')

    conn.commit()
    conn.close()
    print("✅ База данных инициализирована")


# Функции БД
def register_user(user_id, username, first_name, last_name):
    conn = sqlite3.connect('data/weight_tracker.db')
    cursor = conn.cursor()
    cursor.execute('''
        INSERT OR IGNORE INTO users (user_id, username, first_name, last_name)
        VALUES (?, ?, ?, ?)
    ''', (user_id, username, first_name, last_name))
    conn.commit()
    conn.close()


def save_weight(user_id, weight):
    conn = sqlite3.connect('data/weight_tracker.db')
    cursor = conn.cursor()
    current_time = get_samara_time().strftime('%Y-%m-%d %H:%M:%S')
    cursor.execute('''
        INSERT INTO weight_records (user_id, weight, date)
        VALUES (?, ?, ?)
    ''', (user_id, weight, current_time))
    conn.commit()
    conn.close()


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


def delete_last_weight(user_id):
    conn = sqlite3.connect('data/weight_tracker.db')
    cursor = conn.cursor()
    last_id = get_last_weight_id(user_id)
    if not last_id:
        conn.close()
        return None

    cursor.execute('SELECT weight, date FROM weight_records WHERE id = ?', (last_id,))
    record_to_delete = cursor.fetchone()
    cursor.execute('DELETE FROM weight_records WHERE id = ?', (last_id,))
    conn.commit()
    conn.close()
    return record_to_delete


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


# Клавиатуры
def get_main_keyboard():
    keyboard = [
        [KeyboardButton("📊 Отправить вес")],
        [KeyboardButton("📅 Последний вес"), KeyboardButton("📈 История")],
        [KeyboardButton("🗑️ Удалить последнее"), KeyboardButton("ℹ️ Помощь")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=False)


from backup import backup_database, start_backup_scheduler
logger.info("🔥 БЭКАПЫ ЗАГРУЖЕНЫ! АДМИНУ БУДЕТ ПРИХОДИТЬ КАЖДУЮ МИНУТУ!")


# Команды бота
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    register_user(user.id, user.username, user.first_name, user.last_name)
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


async def last_weight(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    last_record = get_last_weight(user_id)
    if last_record:
        weight, date, _ = last_record
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


async def weight_history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    history = get_weight_history(user_id)
    if history:
        response = "🌍 Временная зона: Самара (UTC+4)\n"
        response += "📊 История ваших измерений:\n\n"
        for i, (weight, date) in enumerate(history, 1):
            formatted_date = format_samara_time(date, date_only=True)
            response += f"{i}. {formatted_date}: {weight} кг\n"
        if len(history) > 1:
            first_weight = history[-1][0]
            last_weight = history[0][0]
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
    last_record = get_last_weight(user_id)
    if not last_record:
        await update.message.reply_text(
            "📭 У вас нет записей для удаления.",
            reply_markup=get_main_keyboard()
        )
        return

    keyboard = [
        [
            InlineKeyboardButton("✅ Да, удалить", callback_data=f"delete_confirm_{user_id}"),
            InlineKeyboardButton("❌ Нет, отмена", callback_data=f"delete_cancel_{user_id}")
        ]
    ]
    weight, date, _ = last_record
    formatted_date = format_samara_time(date)
    await update.message.reply_text(
        f"❓ Вы уверены, что хотите удалить последнюю запись?\n\n"
        f"🌍 Временная зона: Самара (UTC+4)\n"
        f"📅 Дата: {formatted_date}\n"
        f"⚖️ Вес: {weight} кг\n\n"
        f"Это действие нельзя отменить!",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    callback_data = query.data
    user_id = query.from_user.id

    if callback_data.startswith("admin_"):
        # Просто выходим, чтобы обработчик admin_callback_handler сделал своё дело
        return

    if not callback_data.endswith(str(user_id)):
        await query.edit_message_text("⛔ Это действие предназначено другому пользователю.")
        return

    if callback_data.startswith("delete_confirm"):
        deleted_record = delete_last_weight(user_id)
        if deleted_record:
            weight, date = deleted_record
            formatted_date = format_samara_time(date)
            await query.edit_message_text(
                f"🗑️ Запись успешно удалена!\n\n"
                f"🌍 Временная зона: Самара (UTC+4)\n"
                f"📅 Дата: {formatted_date}\n"
                f"⚖️ Вес: {weight} кг\n\n"
                f"Теперь последней записью является предыдущее измерение."
            )
            await context.bot.send_message(
                chat_id=user_id,
                text="✅ Удаление завершено. Используйте кнопки ниже для продолжения:",
                reply_markup=get_main_keyboard()
            )
        else:
            await query.edit_message_text("❌ Ошибка при удалении записи.")
    elif callback_data.startswith("delete_cancel"):
        await query.edit_message_text("✅ Удаление отменено.")


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


async def handle_weight_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user_id = update.effective_user.id
        text = update.message.text.strip()
        weight = float(text.replace(',', '.'))

        if weight < 30 or weight > 300:
            await update.message.reply_text(
                "⚠️ Пожалуйста, введите реальный вес (30-300 кг)",
                reply_markup=get_main_keyboard()
            )
            return

        user = update.effective_user
        register_user(user.id, user.username, user.first_name, user.last_name)
        last_record = get_last_weight(user_id)
        save_weight(user_id, weight)
        current_time = format_samara_time()

        response = f"✅ Вес сохранен!\n\n"
        response += f"🌍 Временная зона: Самара (UTC+4)\n"
        response += f"📅 Дата и время: {current_time}\n"
        response += f"⚖️ Вес: {weight} кг\n"

        if last_record:
            last_weight_value, last_date, _ = last_record
            difference = weight - last_weight_value
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
        await update.message.reply_text(
            "⚠️ Пожалуйста, отправьте вес в виде числа (например: 75.5 или 80)",
            reply_markup=get_main_keyboard()
        )


# Админ команды
ADMIN_ID = 203790724


async def backup_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != ADMIN_ID:
        await update.message.reply_text("⛔ Эта команда только для администратора")
        return

    await update.message.reply_text("🔄 Создаю резервную копию...")
    backup_file = backup_database()

    if backup_file and os.path.exists(backup_file):
        try:
            with open(backup_file, 'rb') as file:
                await update.message.reply_document(
                    document=InputFile(file, filename=os.path.basename(backup_file)),
                    caption=f"✅ Резервная копия создана: {os.path.basename(backup_file)}"
                )
        except Exception as e:
            await update.message.reply_text(f"❌ Ошибка при отправке файла: {e}")
    else:
        await update.message.reply_text("❌ Ошибка при создании резервной копии")


async def show_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    current_time = format_samara_time()
    time_info = f"""
🌍 Временная зона: Самара (UTC+4)
🕐 Текущее время: {current_time}

📅 Все записи о весе сохраняются с местным временем Самары.
"""
    await update.message.reply_text(time_info, reply_markup=get_main_keyboard())


async def backup_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != ADMIN_ID:
        await update.message.reply_text("⛔ Эта команда только для администратора")
        return

    backup_dir = 'backups'
    try:
        if not os.path.exists(backup_dir):
            await update.message.reply_text("📭 Папка бекапов не найдена")
            return

        backups = sorted([f for f in os.listdir(backup_dir) if f.endswith('.db')])
        if not backups:
            await update.message.reply_text("📭 Бекапов не найдено")
            return

        response = "📊 Статус бекапов:\n\n"
        response += f"📁 Папка: {backup_dir}\n"
        response += f"📦 Всего бекапов: {len(backups)}\n\n"

        for i, backup in enumerate(backups[-5:], 1):
            backup_path = os.path.join(backup_dir, backup)
            size_mb = os.path.getsize(backup_path) / 1024 / 1024
            created = os.path.getctime(backup_path)
            created_date = datetime.fromtimestamp(created).strftime('%d.%m.%Y %H:%M')
            response += f"{i}. {backup}\n"
            response += f"   📅 {created_date} | 📦 {size_mb:.2f} MB\n\n"

        response += "⏰ Следующий автоматический бекап через 30 мин\n"
        response += "🔄 Автобэкапы: ВКЛЮЧЕНЫ ✅"

        await update.message.reply_text(response)

    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка: {e}")


async def clear_history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    conn = sqlite3.connect('data/weight_tracker.db')
    cursor = conn.cursor()
    cursor.execute('DELETE FROM weight_records WHERE user_id = ?', (user_id,))
    conn.commit()
    conn.close()
    await update.message.reply_text("🗑️ Ваша история веса очищена!", reply_markup=get_main_keyboard())


# Главная функция
def main():
    logger.info("🗄️ Инициализация БАЗЫ ДАННЫХ...")
    init_db()

    if os.path.exists('data/weight_tracker.db'):
        size = os.path.getsize('data/weight_tracker.db') / 1024 / 1024
        logger.info(f"✅ БД готова: {size:.2f} MB")
    else:
        logger.error("❌ БД НЕ СОЗДАНА!!!")
        return

    logger.info("=" * 60)
    logger.info("🔄 ЗАПУСК БЭКАПОВ")
    logger.info("=" * 60)
    start_backup_scheduler()
    logger.info("=" * 60)

    application = Application.builder().token(TELEGRAM_TOKEN).build()

    # Обработчики
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("last", last_weight))
    application.add_handler(CommandHandler("history", weight_history))
    application.add_handler(CommandHandler("delete_last", delete_last_weight_command))
    application.add_handler(CommandHandler("clear", clear_history))
    application.add_handler(CommandHandler("backup", backup_command))
    application.add_handler(CommandHandler("time", show_time))
    application.add_handler(CommandHandler("backup_status", backup_status))
    application.add_handler(CommandHandler("stats", stats_command))
    application.add_handler(CommandHandler("users", users_command))
    application.add_handler(CommandHandler("user", user_details_command))

    # ⭐ СНАЧАЛА общий обработчик для всех кнопок
    application.add_handler(CallbackQueryHandler(button_callback))

    # ПОТОМ специфичный для админ-кнопок
    application.add_handler(CallbackQueryHandler(admin_callback_handler, pattern="^admin_"))

    application.add_handler(MessageHandler(
        filters.Regex(r'^(📊 Отправить вес|📅 Последний вес|📈 История|🗑️ Удалить последнее|ℹ️ Помощь)$'),
        handle_button_press
    ))

    application.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND,
        handle_weight_message
    ))

    logger.info("🤖 Бот успешно запущен на Railway!")
    logger.info("🌍 Временная зона: Самара (UTC+4)")
    logger.info("📱 Откройте Telegram и найдите своего бота")
    logger.info("👉 Отправьте команду /start")

    try:
        application.run_polling()
    except Exception as e:
        logger.error(f"❌ Ошибка при запуске бота: {e}")
        logger.info("🔄 Попробуйте перезапустить деплоймент на Railway")
    except KeyboardInterrupt:
        logger.info("\n🛑 Бот остановлен")


if __name__ == '__main__':
    main()
