import os
import sqlite3
import logging
from datetime import datetime
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')

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
logger.info("🤖 Запускаем Telegram Weight Bot...")
logger.info("📋 Доступные команды в боте:")
logger.info("  /start - Начать работу")
logger.info("  /help - Помощь и инструкции")
logger.info("  /last - Последний вес")
logger.info("  /history - История измерений")
logger.info("  Просто отправьте вес числом (например: 75.5)")


# ==========================================

# Инициализация базы данных
def init_db():
    # Создаем папку data если её нет
    os.makedirs('data', exist_ok=True)

    # Подключаемся к базе в папке data
    conn = sqlite3.connect('weight_tracker.db')
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
    conn = sqlite3.connect('weight_tracker.db')
    cursor = conn.cursor()

    cursor.execute('''
        INSERT OR IGNORE INTO users (user_id, username, first_name, last_name)
        VALUES (?, ?, ?, ?)
    ''', (user_id, username, first_name, last_name))

    conn.commit()
    conn.close()


# Функция для сохранения веса
def save_weight(user_id, weight):
    conn = sqlite3.connect('weight_tracker.db')
    cursor = conn.cursor()

    # Сохраняем вес
    cursor.execute('''
        INSERT INTO weight_records (user_id, weight)
        VALUES (?, ?)
    ''', (user_id, weight))

    conn.commit()
    conn.close()


# Функция для получения последнего веса
def get_last_weight(user_id):
    conn = sqlite3.connect('weight_tracker.db')
    cursor = conn.cursor()

    cursor.execute('''
        SELECT weight, date 
        FROM weight_records 
        WHERE user_id = ? 
        ORDER BY date DESC 
        LIMIT 1
    ''', (user_id,))

    result = cursor.fetchone()
    conn.close()

    return result


# Функция для получения истории веса
def get_weight_history(user_id, limit=10):
    conn = sqlite3.connect('weight_tracker.db')
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


# Команда /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    register_user(user.id, user.username, user.first_name, user.last_name)

    welcome_text = f"""
👋 Привет, {user.first_name}!

Я бот для отслеживания веса.

📊 Просто отправь мне свой вес в килограммах (например: 75.5 или 80).

📈 Я буду сохранять его и показывать изменения.

📋 Доступные команды:
/start - Начать работу
/last - Посмотреть последний вес
/history - История измерений (последние 10)
/help - Помощь
"""

    await update.message.reply_text(welcome_text)


# Команда /help
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = """
📋 Как пользоваться ботом:

Просто отправьте свой вес в килограммах.
Примеры: 75.5, 80, 68.3

📊 Команды:
/start - Начать работу
/last - Посмотреть последний вес
/history - История измерений (последние 10)
/help - Помощь

💡 Совет: Отправляйте вес каждый день в одно и то же время для более точного отслеживания!
"""

    await update.message.reply_text(help_text)


# Команда /last
async def last_weight(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    last_record = get_last_weight(user_id)

    if last_record:
        weight, date = last_record
        # Преобразуем строку даты в объект datetime
        try:
            date_obj = datetime.strptime(date, '%Y-%m-%d %H:%M:%S')
            formatted_date = date_obj.strftime('%d.%m.%Y %H:%M')
        except:
            formatted_date = date

        await update.message.reply_text(f"📅 Последнее измерение: {formatted_date}\n⚖️ Вес: {weight} кг")
    else:
        await update.message.reply_text("📭 У вас еще нет записей о весе. Отправьте свой вес!")


# Команда /history
async def weight_history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    history = get_weight_history(user_id)

    if history:
        response = "📊 История ваших измерений:\n\n"
        for i, (weight, date) in enumerate(history, 1):
            try:
                # Преобразуем строку даты в объект datetime
                date_obj = datetime.strptime(date, '%Y-%m-%d %H:%M:%S')
                formatted_date = date_obj.strftime('%d.%m.%Y')
            except:
                formatted_date = date
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

    await update.message.reply_text(response)


# Обработка сообщений с весом
async def handle_weight_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user_id = update.effective_user.id
        text = update.message.text.strip()

        # Пробуем преобразовать в число
        weight = float(text.replace(',', '.'))

        # Проверяем, что вес в разумных пределах
        if weight < 30 or weight > 300:
            await update.message.reply_text("⚠️ Пожалуйста, введите реальный вес (30-300 кг)")
            return

        # Регистрируем пользователя если он новый
        user = update.effective_user
        register_user(user.id, user.username, user.first_name, user.last_name)

        # Получаем последний вес
        last_record = get_last_weight(user_id)

        # Сохраняем новый вес
        save_weight(user_id, weight)

        # Формируем ответ
        current_time = datetime.now().strftime('%d.%m.%Y %H:%M')
        response = f"✅ Вес сохранен!\n\n"
        response += f"📅 Дата: {current_time}\n"
        response += f"⚖️ Вес: {weight} кг\n"

        if last_record:
            last_weight_value, last_date = last_record
            difference = weight - last_weight_value

            # Форматируем дату последней записи
            try:
                last_date_obj = datetime.strptime(last_date, '%Y-%m-%d %H:%M:%S')
                formatted_last_date = last_date_obj.strftime('%d.%m.%Y')
            except:
                formatted_last_date = last_date

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

        await update.message.reply_text(response)

    except ValueError:
        # Если не удалось преобразовать в число
        await update.message.reply_text("⚠️ Пожалуйста, отправьте вес в виде числа (например: 75.5 или 80)")


# Команда для очистки истории (скрытая команда для админа)
async def clear_history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    conn = sqlite3.connect('weight_tracker.db')
    cursor = conn.cursor()

    cursor.execute('DELETE FROM weight_records WHERE user_id = ?', (user_id,))
    conn.commit()
    conn.close()

    await update.message.reply_text("🗑️ Ваша история веса очищена!")


from backup import backup_database


# Команда /backup (для админа)
async def backup_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    # Проверка на администратора (укажите свой ID)
    ADMIN_ID = 123456789  # Замените на ваш Telegram ID

    if user_id != ADMIN_ID:
        await update.message.reply_text("⛔ Эта команда только для администратора")
        return

    await update.message.reply_text("🔄 Создаю резервную копию...")

    backup_file = backup_database()

    if backup_file:
        await update.message.reply_text(f"✅ Резервная копия создана: {backup_file}")
    else:
        await update.message.reply_text("❌ Ошибка при создании резервной копии")


# Главная функция
def main():
    # Инициализируем базу данных
    init_db()

    # Создаем приложение
    application = Application.builder().token(TELEGRAM_TOKEN).build()

    # Регистрируем обработчики команд
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("last", last_weight))
    application.add_handler(CommandHandler("history", weight_history))
    application.add_handler(CommandHandler("clear", clear_history))  # Скрытая команда
    application.add_handler(CommandHandler("backup", backup_command))

    # Регистрируем обработчик текстовых сообщений
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_weight_message))

    # Запускаем бота
    logger.info("🤖 Бот успешно запущен на Railway!")
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