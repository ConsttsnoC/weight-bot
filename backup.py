#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🤖 Telegram Weight Tracker - Автобэкапы
✅ БЕКАП КАЖДУЮ МИНУТУ В ЛИЧКУ АДМИНУ
"""

import os
import shutil
import sqlite3
import asyncio
import logging
from datetime import datetime
from telegram import Bot

# ==================== КОНФИГУРАЦИЯ ====================
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
ADMIN_ID = 203790724
DB_PATH = "data/weight_tracker.db"
BACKUP_DIR = "backups"

# Логирование
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('backup')


def create_backup():
    """Создает копию БД"""
    os.makedirs(BACKUP_DIR, exist_ok=True)
    if not os.path.exists(DB_PATH):
        return None

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_file = os.path.join(BACKUP_DIR, f'weight_backup_{timestamp}.db')
    shutil.copy2(DB_PATH, backup_file)
    return backup_file


# ✅ ДОБАВЛЯЕМ ЭТУ ФУНКЦИЮ ДЛЯ backup_command
def backup_database():
    """Создает бэкап и возвращает путь к файлу"""
    return create_backup()


async def send_backup():
    """Создает и отправляет бэкап админу"""
    try:
        # Создаем бэкап
        backup_file = create_backup()
        if not backup_file:
            logger.error("БД не найдена")
            return

        # Отправляем
        bot = Bot(token=TELEGRAM_TOKEN)
        with open(backup_file, 'rb') as f:
            await bot.send_document(
                chat_id=ADMIN_ID,
                document=f,
                caption=f"✅ Бэкап {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}"
            )
        logger.info(f"✅ Бэкап отправлен админу {ADMIN_ID}")

    except Exception as e:
        logger.error(f"❌ Ошибка: {e}")


async def main():
    """Главная функция - бесконечный цикл"""
    logger.info("🚀 Запуск бэкапов каждую минуту")
    while True:
        await send_backup()
        await asyncio.sleep(21600)  # 1 минута


def start_backup_scheduler():
    """Запускает планировщик бэкапов"""
    logger.info("🚀 ЗАПУСК ПЛАНИРОВЩИКА БЭКАПОВ (1 МИНУТА)")

    # Создаём и запускаем поток с asyncio
    import threading
    def run_async():
        asyncio.run(main())

    thread = threading.Thread(target=run_async, daemon=True)
    thread.start()


if __name__ == "__main__":
    if not TELEGRAM_TOKEN:
        print("❌ TELEGRAM_TOKEN не найден!")
        exit(1)
    asyncio.run(main())