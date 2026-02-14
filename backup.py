#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🤖 Telegram Weight Tracker - Автобэкапы
✅ АСИНХРОННАЯ отправка админу 203790724
✅ Railway совместимый
"""

import os
import shutil
import sqlite3
import asyncio
import logging
from datetime import datetime
from telegram import Bot
from telegram.error import TelegramError

# ==================== КОНФИГУРАЦИЯ ====================
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')  # Railway переменная
ADMIN_ID = 203790724
DB_PATH = "data/weight_tracker.db"
BACKUP_DIR = "backups"
BACKUP_INTERVAL = 1

# Логирование
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('backup.log', encoding='utf-8')
    ]
)
logger = logging.getLogger('backup')


# ==================== БАЗА ДАННЫХ ====================
def get_total_records():
    """Количество записей в БД"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM measurements")
        count = cursor.fetchone()[0]
        conn.close()
        return count
    except:
        return 0


def get_total_users():
    """Количество пользователей"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(DISTINCT user_id) FROM measurements")
        count = cursor.fetchone()[0]
        conn.close()
        return count
    except:
        return 0


# ==================== АСИНХРОННАЯ ОТПРАВКА ====================
async def send_backup_to_admin(backup_file):
    """
    ✅ АСИНХРОННАЯ отправка бэкапа админу
    ADMIN_ID = 203790724
    """
    try:
        bot = Bot(token=TELEGRAM_TOKEN)

        # Размер файла
        backup_size = os.path.getsize(backup_file) / (1024 * 1024)

        # Парсим время из имени файла
        filename = os.path.basename(backup_file)
        timestamp_part = filename.replace('weight_backup_', '').replace('.db', '')
        backup_time = datetime.strptime(timestamp_part, '%Y%m%d_%H%M%S').strftime('%d.%m.%Y %H:%M')

        # Красивая подпись
        caption = (
            f"🤖 **АВТОБЭКАП #{backup_time}**\n\n"
            f"📦 Размер: **{backup_size:.2f} MB**\n"
            f"📊 Записей: **{get_total_records():,d}**\n"
            f"👥 Пользователей: **{get_total_users()}**\n"
            f"⏰ {datetime.now().strftime('%H:%M:%S')}"
        )

        # ✅ АСИНХРОННАЯ отправка!
        with open(backup_file, 'rb') as file:
            await bot.send_document(
                chat_id=ADMIN_ID,
                document=file,
                caption=caption,
                parse_mode='Markdown'
            )

        logger.info(f"✅ ✅ ОТПРАВЛЕНО АДМИНУ {ADMIN_ID}: {backup_file}")
        return True

    except TelegramError as e:
        logger.error(f"❌ TELEGRAM ОШИБКА: {e}")
        return False
    except Exception as e:
        logger.error(f"❌ ОШИБКА ОТПРАВКИ: {e}")
        return False


# ==================== СОЗДАНИЕ БЭКАПА ====================
def create_backup():
    """Создает копию БД"""
    try:
        # Создаем папку backups
        os.makedirs(BACKUP_DIR, exist_ok=True)

        # Проверяем БД
        if not os.path.exists(DB_PATH):
            logger.warning("⚠️ БД не найдена!")
            return None

        db_size = os.path.getsize(DB_PATH) / (1024 * 1024)
        logger.info(f"✅ БД найдена: {DB_PATH} ({db_size:.2f} MB)")

        # Имя бэкапа
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_file = os.path.join(BACKUP_DIR, f'weight_backup_{timestamp}.db')

        # Копируем БД
        shutil.copy2(DB_PATH, backup_file)
        logger.info(f"✅ КОПИРОВАНИЕ УСПЕШНО: {backup_file}")

        return backup_file

    except Exception as e:
        logger.error(f"❌ ОШИБКА КОПИРОВАНИЯ: {e}")
        return None


# ==================== ОСНОВНОЙ БЭКАП ====================
async def do_backup():
    """Полный цикл бэкапа"""
    logger.info("🚀 === АВТОБЭКАП СТАРТ ===")

    # 1. Создаем копию
    backup_file = create_backup()
    if not backup_file:
        logger.error("❌ НЕ УДАЛОСЬ СОЗДАТЬ БЭКАП!")
        return False

    # 2. Отправляем админу АСИНХРОННО
    success = await send_backup_to_admin(backup_file)

    if success:
        logger.info("🚀 === АВТОБЭКАП КОНЕЦ ✅ ===")
    else:
        logger.error("🚀 === АВТОБЭКАП ОШИБКА ❌ ===")

    return success


# ==================== ПЛАНИРОВЩИК ====================
def backup_scheduler():
    """Бесконечный цикл бэкапов"""
    logger.info(f"✅ ✅ ПЛАНИРОВЩИК ЗАПУЩЕН! Интервал: {BACKUP_INTERVAL // 60} мин")

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    next_backup = datetime.now().timestamp() + BACKUP_INTERVAL
    while True:
        try:
            now = datetime.now().timestamp()
            if now >= next_backup:
                loop.run_until_complete(do_backup())
                next_backup = now + BACKUP_INTERVAL
                wait_time = BACKUP_INTERVAL
            else:
                wait_time = int(next_backup - now)

            logger.info(f"⏰ Планировщик: Ждем {wait_time // 60} мин до следующего бэкапа...")
            asyncio.sleep(wait_time)

        except KeyboardInterrupt:
            logger.info("🛑 Планировщик остановлен")
            break
        except Exception as e:
            logger.error(f"❌ ОШИБКА ПЛАНИРОВЩИКА: {e}")
            asyncio.sleep(60)


# ==================== ТЕСТ ФУНКЦИЯ ====================
async def test_backup():
    """Тестовая отправка прямо сейчас"""
    logger.info("🧪 === ТЕСТ БЭКАПА ===")
    await do_backup()


# ==================== ЗАПУСК ====================
if __name__ == "__main__":
    print("🤖 Telegram Weight Backup Bot")
    print(f"👤 Админ: {ADMIN_ID}")
    print(f"📁 БД: {DB_PATH}")
    print(f"⏱️ Интервал: {BACKUP_INTERVAL // 60} мин")

    if not TELEGRAM_TOKEN:
        print("❌ TELEGRAM_TOKEN не найден!")
        exit(1)

    # Тест (раскомментируйте для проверки)
    # asyncio.run(test_backup())

    # Запуск планировщика
    backup_scheduler()
