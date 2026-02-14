# backup.py
import os
import sqlite3
import shutil
from datetime import datetime
import logging
import threading
import time
import schedule
from telegram import Bot
from telegram.error import TelegramError

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ID администратора
ADMIN_ID = 203790724
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')


def backup_database():
    """Создание резервной копии базы данных"""
    source_db = 'data/weight_tracker.db'
    backup_dir = 'backups'

    if not os.path.exists(source_db):
        logger.warning(f"⚠️ Файл базы данных не найден: {source_db}")
        return None

    os.makedirs(backup_dir, exist_ok=True)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_file = f'{backup_dir}/weight_backup_{timestamp}.db'

    try:
        shutil.copy2(source_db, backup_file)

        # Удаляем старые бэкапы (оставляем последние 7)
        backups = sorted([f for f in os.listdir(backup_dir) if f.endswith('.db')])
        if len(backups) > 7:
            for old_backup in backups[:-7]:
                try:
                    os.remove(os.path.join(backup_dir, old_backup))
                except:
                    pass

        backup_size = os.path.getsize(backup_file) / 1024 / 1024
        logger.info(f"✅ Бэкап создан: {backup_file} ({backup_size:.2f} MB)")
        return backup_file

    except Exception as e:
        logger.error(f"❌ Ошибка при создании бэкапа: {e}")
        return None


def send_backup_to_admin_sync(backup_file):
    """СИНХРОННАЯ отправка бэкапа администратору"""
    if not backup_file or not os.path.exists(backup_file):
        logger.error("❌ Файл бэкапа не найден")
        return False

    try:
        bot = Bot(token=TELEGRAM_TOKEN)
        backup_size = os.path.getsize(backup_file) / 1024 / 1024
        timestamp = os.path.basename(backup_file).split('_')[2].replace('.db', '')
        backup_time = datetime.strptime(timestamp, '%Y%m%d_%H%M%S').strftime('%d.%m.%Y %H:%M')

        caption = (
            f"🤖 **АВТОМАТИЧЕСКИЙ БЭКАП БАЗЫ ДАННЫХ**\n\n"
            f"📅 Время создания: {backup_time}\n"
            f"📦 Размер: {backup_size:.2f} MB\n"
            f"💾 Всего записей: {get_total_records()}\n"
            f"👥 Всего пользователей: {get_total_users()}\n\n"
            f"✅ Бэкап успешно отправлен!"
        )

        with open(backup_file, 'rb') as file:
            bot.send_document(
                chat_id=ADMIN_ID,
                document=file,
                caption=caption,
                parse_mode='Markdown'
            )

        logger.info(f"✅ Бэкап отправлен администратору {ADMIN_ID}")
        return True

    except TelegramError as e:
        logger.error(f"❌ Telegram ошибка: {e}")
        return False
    except Exception as e:
        logger.error(f"❌ Ошибка отправки бэкапа: {e}")
        return False


def get_total_records():
    """Получить общее количество записей"""
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


def perform_auto_backup():
    """Выполнить автоматический бэкап (СИНХРОННО)"""
    logger.info("🚀 Выполняю автоматический бэкап...")
    backup_file = backup_database()

    if backup_file:
        success = send_backup_to_admin_sync(backup_file)
        if success:
            logger.info("✅ Автоматический бэкап успешно отправлен!")
        else:
            logger.error("❌ Не удалось отправить автоматический бэкап")
    else:
        logger.error("❌ Не удалось создать автоматический бэкап")


def run_backup_schedule():
    """Запуск расписания для автоматических бэкапов"""
    # Каждые 30 МИНУТ для теста (потом измените на 1 час)
    schedule.every(1).minutes.do(perform_auto_backup)

    # Первый бэкап сразу
    logger.info("🔄 Первый автоматический бэкап при старте...")
    perform_auto_backup()

    logger.info("⏰ Планировщик запущен (каждые 30 минут для теста)")

    while True:
        try:
            schedule.run_pending()
            time.sleep(1)
        except Exception as e:
            logger.error(f"❌ Ошибка планировщика: {e}")
            time.sleep(1)


def start_backup_scheduler():
    """Запуск планировщика в отдельном потоке"""
    try:
        scheduler_thread = threading.Thread(
            target=run_backup_schedule,
            daemon=True,
            name="AutoBackupScheduler"
        )
        scheduler_thread.start()
        logger.info("🚀 ✅ Планировщик бэкапов ЗАПУЩЕН (каждые 30 мин для теста)")
        return True
    except Exception as e:
        logger.error(f"❌ Ошибка запуска планировщика: {e}")
        return False


# Для ручного бэкапа (остается как было)
def backup_database():
    """Создание резервной копии для команды /backup"""
    # ... (тот же код что выше)
    pass  # Уже определена выше
