# backup.py
import os
import sqlite3
import shutil
from datetime import datetime, timedelta
import logging
import threading
import time
import schedule
from telegram import Bot
import asyncio

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ID администратора (тот же, что в основном боте)
ADMIN_ID = 203790724  # Ваш Telegram ID
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')


def backup_database():
    """Создание резервной копии базы данных"""

    source_db = 'data/weight_tracker.db'
    backup_dir = 'backups'

    # Проверяем существует ли файл базы данных
    if not os.path.exists(source_db):
        logger.warning(f"⚠️ Файл базы данных не найден: {source_db}")
        return None

    # Создаем папку для бэкапов
    os.makedirs(backup_dir, exist_ok=True)

    # Генерируем имя файла с датой
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_file = f'{backup_dir}/weight_backup_{timestamp}.db'

    try:
        # Проверяем размер базы данных
        db_size = os.path.getsize(source_db) / 1024 / 1024  # Размер в MB

        # Копируем файл базы данных
        shutil.copy2(source_db, backup_file)

        # Проверяем размер бекапа
        backup_size = os.path.getsize(backup_file) / 1024 / 1024  # Размер в MB

        # Удаляем старые бэкапы (оставляем последние 7)
        backups = sorted([f for f in os.listdir(backup_dir)
                          if f.endswith('.db')])

        if len(backups) > 7:
            for old_backup in backups[:-7]:
                old_path = os.path.join(backup_dir, old_backup)
                try:
                    os.remove(old_path)
                    logger.info(f"🗑️ Удален старый бэкап: {old_backup}")
                except Exception as e:
                    logger.error(f"❌ Ошибка при удалении {old_backup}: {e}")

        logger.info(f"✅ Бэкап создан: {backup_file} ({backup_size:.2f} MB)")
        return backup_file

    except Exception as e:
        logger.error(f"❌ Ошибка при создании бэкапа: {e}")
        return None


async def send_backup_to_admin(backup_file):
    """Отправка бэкапа администратору в Telegram"""
    if not backup_file or not os.path.exists(backup_file):
        logger.error("❌ Файл бэкапа не найден для отправки")
        return False

    try:
        bot = Bot(token=TELEGRAM_TOKEN)

        # Информация о бэкапе
        backup_size = os.path.getsize(backup_file) / 1024 / 1024  # MB
        timestamp = os.path.basename(backup_file).split('_')[2].replace('.db', '')
        backup_time = datetime.strptime(timestamp, '%Y%m%d_%H%M%S').strftime('%d.%m.%Y %H:%M')

        caption = (
            f"🤖 **АВТОМАТИЧЕСКИЙ БЭКАП БАЗЫ ДАННЫХ**\n\n"
            f"📅 Время создания: {backup_time}\n"
            f"📦 Размер: {backup_size:.2f} MB\n"
            f"💾 Всего записей в БД: {get_total_records()}\n"
            f"👥 Всего пользователей: {get_total_users()}\n\n"
            f"✅ Бэкап успешно создан и отправлен!"
        )

        # Отправляем файл
        with open(backup_file, 'rb') as file:
            await bot.send_document(
                chat_id=ADMIN_ID,
                document=file,
                caption=caption,
                parse_mode='Markdown'
            )

        logger.info(f"✅ Бэкап отправлен администратору {ADMIN_ID}")
        return True

    except Exception as e:
        logger.error(f"❌ Ошибка при отправке бэкапа админу: {e}")
        return False


def get_total_records():
    """Получить общее количество записей о весе"""
    try:
        conn = sqlite3.connect('data/weight_tracker.db')
        cursor = conn.cursor()
        cursor.execute('SELECT COUNT(*) FROM weight_records')
        count = cursor.fetchone()[0]
        conn.close()
        return count
    except:
        return 0


def get_total_users():
    """Получить общее количество пользователей"""
    try:
        conn = sqlite3.connect('data/weight_tracker.db')
        cursor = conn.cursor()
        cursor.execute('SELECT COUNT(*) FROM users')
        count = cursor.fetchone()[0]
        conn.close()
        return count
    except:
        return 0


def run_backup_schedule():
    """Запуск расписания для автоматических бэкапов"""

    # Планируем бэкап каждые 4 часа
    schedule.every(4).hours.do(lambda: perform_auto_backup())

    # Также делаем бэкап при старте
    logger.info("🔄 Запуск первого автоматического бэкапа при старте...")
    perform_auto_backup()

    logger.info("⏰ Автоматический планировщик бэкапов запущен (каждые 4 часа)")

    while True:
        try:
            schedule.run_pending()
            time.sleep(60)  # Проверяем каждую минуту
        except Exception as e:
            logger.error(f"❌ Ошибка в планировщике бэкапов: {e}")
            time.sleep(300)  # Ждем 5 минут при ошибке


async def perform_auto_backup():
    """Выполнить автоматический бэкап и отправить админу"""
    logger.info("🚀 Выполняю автоматический бэкап...")
    backup_file = backup_database()

    if backup_file:
        # Создаем новый event loop для отправки в потоке
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            success = loop.run_until_complete(send_backup_to_admin(backup_file))
            if success:
                logger.info("✅ Автоматический бэкап успешно отправлен админу")
            else:
                logger.error("❌ Не удалось отправить автоматический бэкап админу")
        finally:
            loop.close()
    else:
        logger.error("❌ Не удалось создать автоматический бэкап")


def start_backup_scheduler():
    """Запуск планировщика бэкапов в отдельном потоке"""
    try:
        # Создаем и запускаем поток с планировщиком
        scheduler_thread = threading.Thread(
            target=run_backup_schedule,
            daemon=True,  # Демон-поток, завершится с основным потоком
            name="AutoBackupScheduler"
        )

        scheduler_thread.start()
        logger.info("🚀 Автоматический планировщик бэкапов запущен (отправка админу каждые 4 часа)")
        return True
    except Exception as e:
        logger.error(f"❌ Ошибка при запуске планировщика бэкапов: {e}")
        return False


if __name__ == '__main__':
    # Если запускаем напрямую, создаем один бэкап
    backup_database()
    logger.info("Для автоматических бэкапов импортируйте start_backup_scheduler() в основном приложении")
