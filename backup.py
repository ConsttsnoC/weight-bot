# backup.py - ПОЛНАЯ ВЕРСИЯ С ПРОВЕРКАМИ
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

ADMIN_ID = 203790724
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')


def backup_database():
    """Создание резервной копии базы данных"""
    source_db = 'data/weight_tracker.db'
    backup_dir = 'backups'

    # ✅ КРИТИЧЕСКАЯ ПРОВЕРКА БАЗЫ
    if not os.path.exists(source_db):
        logger.error(f"❌ БАЗА НЕ НАЙДЕНА: {source_db}")
        logger.error(f"📂 Содержимое папки data: {os.listdir('data') if os.path.exists('data') else 'ПАПКИ data НЕТ!'}")
        return None

    # ✅ Проверяем размер БД
    try:
        db_size = os.path.getsize(source_db)
        logger.info(f"✅ БД найдена: {source_db} ({db_size / 1024 / 1024:.2f} MB)")
    except:
        logger.error("❌ Не удалось прочитать размер БД")
        return None

    os.makedirs(backup_dir, exist_ok=True)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_file = f'{backup_dir}/weight_backup_{timestamp}.db'

    try:
        shutil.copy2(source_db, backup_file)
        logger.info(f"✅ КОПИРОВАНИЕ УСПЕШНО: {backup_file}")

        # Удаляем старые (оставляем 7)
        backups = sorted([f for f in os.listdir(backup_dir) if f.endswith('.db')])
        if len(backups) > 7:
            for old_backup in backups[:-7]:
                os.remove(os.path.join(backup_dir, old_backup))

        return backup_file
    except Exception as e:
        logger.error(f"❌ ОШИБКА КОПИРОВАНИЯ: {e}")
        return None


def send_backup_to_admin_sync(backup_file):
    """Синхронная отправка бэкапа"""
    try:
        bot = Bot(token=TELEGRAM_TOKEN)
        backup_size = os.path.getsize(backup_file) / 1024 / 1024
        timestamp = os.path.basename(backup_file).split('_')[2].replace('.db', '')
        backup_time = datetime.strptime(timestamp, '%Y%m%d_%H%M%S').strftime('%d.%m.%Y %H:%M')

        caption = (
            f"🤖 **АВТОБЭКАП #{backup_time}**\n\n"
            f"📦 Размер: {backup_size:.2f} MB\n"
            f"💾 Записей: {get_total_records()}\n"
            f"👥 Пользователей: {get_total_users()}"
        )

        with open(backup_file, 'rb') as file:
            bot.send_document(chat_id=ADMIN_ID, document=file, caption=caption)

        logger.info(f"✅ ✅ ОТПРАВЛЕНО АДМИНУ: {backup_file}")
        return True
    except Exception as e:
        logger.error(f"❌ ОШИБКА ОТПРАВКИ: {e}")
        return False


def get_total_records():
    try:
        conn = sqlite3.connect('data/weight_tracker.db')
        cursor = conn.cursor()
        cursor.execute('SELECT COUNT(*) FROM weight_records')
        return cursor.fetchone()[0]
    except:
        return 0


def get_total_users():
    try:
        conn = sqlite3.connect('data/weight_tracker.db')
        cursor = conn.cursor()
        cursor.execute('SELECT COUNT(*) FROM users')
        return cursor.fetchone()[0]
    except:
        return 0


def perform_auto_backup():
    logger.info("🚀 === АВТОБЭКАП СТАРТ ===")
    backup_file = backup_database()
    if backup_file:
        send_backup_to_admin_sync(backup_file)
    logger.info("🚀 === АВТОБЭКАП КОНЕЦ ===")


def run_backup_schedule():
    schedule.every(1).minutes.do(perform_auto_backup)

    logger.info("⏰ Планировщик: Ждем 30 минут до следующего бэкапа...")

    while True:
        schedule.run_pending()
        time.sleep(60)


def start_backup_scheduler():
    scheduler_thread = threading.Thread(
        target=run_backup_schedule,
        daemon=True,
        name="AutoBackup"
    )
    scheduler_thread.start()
    logger.info("✅ ✅ ПЛАНИРОВЩИК ЗАПУЩЕН!")
    return True
