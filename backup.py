# backup.py
import os
import sqlite3
import shutil
from datetime import datetime
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def backup_database():
    """Создание резервной копии базы данных"""

    source_db = 'data/weight_tracker.db'
    backup_dir = 'backups'

    # Создаем папку для бэкапов
    os.makedirs(backup_dir, exist_ok=True)

    # Генерируем имя файла с датой
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_file = f'{backup_dir}/weight_backup_{timestamp}.db'

    try:
        # Копируем файл базы данных
        shutil.copy2(source_db, backup_file)

        # Удаляем старые бэкапы (оставляем последние 7)
        backups = sorted([f for f in os.listdir(backup_dir)
                          if f.endswith('.db')])

        if len(backups) > 7:
            for old_backup in backups[:-7]:
                os.remove(os.path.join(backup_dir, old_backup))
                logger.info(f"Удален старый бэкап: {old_backup}")

        logger.info(f"✅ Бэкап создан: {backup_file}")
        return backup_file

    except Exception as e:
        logger.error(f"❌ Ошибка при создании бэкапа: {e}")
        return None


if __name__ == '__main__':
    backup_database()