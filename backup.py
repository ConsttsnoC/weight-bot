# backup.py
import os
import sqlite3
import shutil
from datetime import datetime, timedelta
import logging
import threading
import time
import schedule

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


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


def run_backup_schedule():
    """Запуск расписания для автоматических бекапов"""

    # Планируем бекап каждые 4 часа
    schedule.every(4).hours.do(lambda: backup_database())

    # Также делаем бекап при старте
    logger.info("🔄 Запуск первого бекапа при старте...")
    backup_database()

    logger.info("⏰ Планировщик бекапов запущен (каждые 4 часа)")

    while True:
        try:
            schedule.run_pending()
            time.sleep(60)  # Проверяем каждую минуту
        except Exception as e:
            logger.error(f"❌ Ошибка в планировщике бекапов: {e}")
            time.sleep(300)  # Ждем 5 минут при ошибке


def start_backup_scheduler():
    """Запуск планировщика бекапов в отдельном потоке"""

    try:
        # Создаем и запускаем поток с планировщиком
        scheduler_thread = threading.Thread(
            target=run_backup_schedule,
            daemon=True,  # Демон-поток, завершится с основным потоком
            name="BackupScheduler"
        )

        scheduler_thread.start()
        logger.info("🚀 Планировщик автоматических бекапов запущен")
        return True
    except Exception as e:
        logger.error(f"❌ Ошибка при запуске планировщика бекапов: {e}")
        return False


if __name__ == '__main__':
    # Если запускаем напрямую, создаем один бекап
    backup_database()
    logger.info("Для автоматических бекапов импортируйте start_backup_scheduler() в основном приложении")