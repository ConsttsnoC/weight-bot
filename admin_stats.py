#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
📊 Admin Statistics Module for Weight Tracker Bot
Вывод статистики по базе данных для админа
"""

import sqlite3
import logging
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)
ADMIN_ID = 203790724


def get_db_stats():
    """Собирает статистику по базе данных"""
    conn = sqlite3.connect('data/weight_tracker.db')
    cursor = conn.cursor()

    stats = {}

    # Общая статистика
    cursor.execute("SELECT COUNT(*) FROM users")
    stats['total_users'] = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM weight_records")
    stats['total_records'] = cursor.fetchone()[0]

    # Статистика по записям
    cursor.execute("""
        SELECT COUNT(DISTINCT user_id) 
        FROM weight_records 
        WHERE date >= date('now', '-7 days')
    """)
    stats['active_users_7d'] = cursor.fetchone()[0]

    cursor.execute("""
        SELECT COUNT(*) 
        FROM weight_records 
        WHERE date >= date('now', '-7 days')
    """)
    stats['records_7d'] = cursor.fetchone()[0]

    cursor.execute("""
        SELECT COUNT(*) 
        FROM weight_records 
        WHERE date >= date('now', '-30 days')
    """)
    stats['records_30d'] = cursor.fetchone()[0]

    # Первая и последняя запись
    cursor.execute("SELECT MIN(date), MAX(date) FROM weight_records")
    first_date, last_date = cursor.fetchone()
    stats['first_record'] = first_date
    stats['last_record'] = last_date

    # Топ пользователей по количеству записей
    cursor.execute("""
        SELECT user_id, COUNT(*) as count 
        FROM weight_records 
        GROUP BY user_id 
        ORDER BY count DESC 
        LIMIT 5
    """)
    stats['top_users'] = cursor.fetchall()

    # Средний вес по всем пользователям
    cursor.execute("SELECT AVG(weight) FROM weight_records")
    stats['avg_weight'] = cursor.fetchone()[0]

    # Минимальный и максимальный вес
    cursor.execute("SELECT MIN(weight), MAX(weight) FROM weight_records")
    stats['min_weight'], stats['max_weight'] = cursor.fetchone()

    conn.close()
    return stats


def get_users_list(limit=20):
    """Получает список пользователей"""
    conn = sqlite3.connect('data/weight_tracker.db')
    cursor = conn.cursor()

    cursor.execute("""
        SELECT 
            u.user_id,
            u.username,
            u.first_name,
            u.last_name,
            u.created_at,
            COUNT(w.id) as records_count,
            MAX(w.date) as last_record
        FROM users u
        LEFT JOIN weight_records w ON u.user_id = w.user_id
        GROUP BY u.user_id
        ORDER BY u.created_at DESC
        LIMIT ?
    """, (limit,))

    users = cursor.fetchall()
    conn.close()
    return users


def get_detailed_user_stats(user_id):
    """Получает детальную статистику по конкретному пользователю"""
    conn = sqlite3.connect('data/weight_tracker.db')
    cursor = conn.cursor()

    # Информация о пользователе
    cursor.execute("""
        SELECT user_id, username, first_name, last_name, created_at
        FROM users WHERE user_id = ?
    """, (user_id,))
    user_info = cursor.fetchone()

    if not user_info:
        conn.close()
        return None

    # Статистика записей
    cursor.execute("""
        SELECT 
            COUNT(*) as total_records,
            AVG(weight) as avg_weight,
            MIN(weight) as min_weight,
            MAX(weight) as max_weight,
            MIN(date) as first_record,
            MAX(date) as last_record
        FROM weight_records 
        WHERE user_id = ?
    """, (user_id,))
    record_stats = cursor.fetchone()

    # Последние 10 записей
    cursor.execute("""
        SELECT weight, date 
        FROM weight_records 
        WHERE user_id = ? 
        ORDER BY date DESC 
        LIMIT 10
    """, (user_id,))
    recent_records = cursor.fetchall()

    conn.close()

    return {
        'user_info': user_info,
        'record_stats': record_stats,
        'recent_records': recent_records
    }


def format_stats_message(stats):
    """Форматирует статистику для вывода"""
    message = "📊 **ОБЩАЯ СТАТИСТИКА БОТА**\n\n"
    message += f"👥 Всего пользователей: **{stats['total_users']}**\n"
    message += f"📝 Всего записей: **{stats['total_records']:,d}**\n"
    message += f"📊 Средний вес: **{stats['avg_weight']:.1f} кг**\n"
    message += f"⬇️ Мин. вес: **{stats['min_weight']:.1f} кг**\n"
    message += f"⬆️ Макс. вес: **{stats['max_weight']:.1f} кг**\n\n"

    message += "📅 **Активность:**\n"
    message += f"🔥 Активных за 7 дней: **{stats['active_users_7d']}**\n"
    message += f"📊 Записей за 7 дней: **{stats['records_7d']}**\n"
    message += f"📊 Записей за 30 дней: **{stats['records_30d']}**\n\n"

    if stats['first_record']:
        first = datetime.strptime(stats['first_record'], '%Y-%m-%d %H:%M:%S')
        last = datetime.strptime(stats['last_record'], '%Y-%m-%d %H:%M:%S')
        message += f"🎯 Первая запись: **{first.strftime('%d.%m.%Y')}**\n"
        message += f"🎯 Последняя запись: **{last.strftime('%d.%m.%Y')}**\n"
        message += f"📆 Всего дней: **{(last - first).days + 1}**\n\n"

    message += "🏆 **Топ-5 пользователей:**\n"
    for i, (user_id, count) in enumerate(stats['top_users'], 1):
        message += f"{i}. ID {user_id}: **{count}** записей\n"

    return message


def format_users_list(users):
    """Форматирует список пользователей"""
    message = "👥 **СПИСОК ПОЛЬЗОВАТЕЛЕЙ**\n\n"

    for user in users:
        user_id, username, first_name, last_name, created_at, records_count, last_record = user

        name = first_name or ""
        if last_name:
            name += f" {last_name}"

        username_display = f"@{username}" if username else "нет username"
        created = datetime.strptime(created_at, '%Y-%m-%d %H:%M:%S').strftime('%d.%m.%Y')

        message += f"🆔 **ID:** `{user_id}`\n"
        message += f"👤 **Имя:** {name}\n"
        message += f"📱 **Username:** {username_display}\n"
        message += f"📅 **Регистрация:** {created}\n"
        message += f"📊 **Записей:** {records_count}\n"

        if last_record:
            last = datetime.strptime(last_record, '%Y-%m-%d %H:%M:%S').strftime('%d.%m.%Y')
            message += f"🕐 **Последняя запись:** {last}\n"

        message += "─" * 30 + "\n"

    return message


def format_user_details(stats):
    """Форматирует детальную статистику пользователя"""
    user_info, record_stats, recent_records = stats['user_info'], stats['record_stats'], stats['recent_records']

    user_id, username, first_name, last_name, created_at = user_info
    total_records, avg_weight, min_weight, max_weight, first_record, last_record = record_stats

    name = f"{first_name or ''} {last_name or ''}".strip()
    username_display = f" (@{username})" if username else ""

    message = f"👤 **ДЕТАЛЬНАЯ СТАТИСТИКА ПОЛЬЗОВАТЕЛЯ**{username_display}\n\n"
    message += f"🆔 **ID:** `{user_id}`\n"
    message += f"👤 **Имя:** {name or 'не указано'}\n"
    message += f"📅 **Регистрация:** {datetime.strptime(created_at, '%Y-%m-%d %H:%M:%S').strftime('%d.%m.%Y %H:%M')}\n\n"

    message += "📊 **Статистика записей:**\n"
    message += f"📝 Всего записей: **{total_records}**\n"
    message += f"📊 Средний вес: **{avg_weight:.1f} кг**\n"
    message += f"⬇️ Мин. вес: **{min_weight:.1f} кг**\n"
    message += f"⬆️ Макс. вес: **{max_weight:.1f} кг**\n"

    if first_record and last_record:
        first = datetime.strptime(first_record, '%Y-%m-%d %H:%M:%S')
        last = datetime.strptime(last_record, '%Y-%m-%d %H:%M:%S')
        message += f"📅 Первая запись: **{first.strftime('%d.%m.%Y')}**\n"
        message += f"📅 Последняя запись: **{last.strftime('%d.%m.%Y')}**\n"
        message += f"📆 Период: **{(last - first).days + 1} дней**\n\n"

    if recent_records:
        message += "📋 **Последние 10 записей:**\n"
        for weight, date in recent_records:
            record_date = datetime.strptime(date, '%Y-%m-%d %H:%M:%S').strftime('%d.%m.%Y %H:%M')
            message += f"   • {record_date}: **{weight} кг**\n"

    return message


async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /stats - общая статистика"""
    user_id = update.effective_user.id

    if user_id != ADMIN_ID:
        await update.message.reply_text("⛔ Эта команда только для администратора")
        return

    await update.message.reply_text("🔄 Собираю статистику...")

    try:
        stats = get_db_stats()
        message = format_stats_message(stats)

        # Кнопки для навигации
        keyboard = [
            [
                InlineKeyboardButton("👥 Список пользователей", callback_data="admin_users"),
            ]
        ]

        await update.message.reply_text(
            message,
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    except Exception as e:
        logger.error(f"Ошибка при получении статистики: {e}")
        await update.message.reply_text(f"❌ Ошибка: {e}")


async def users_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /users - список пользователей"""
    user_id = update.effective_user.id

    if user_id != ADMIN_ID:
        await update.message.reply_text("⛔ Эта команда только для администратора")
        return

    await update.message.reply_text("🔄 Загружаю список пользователей...")

    try:
        users = get_users_list(20)
        message = format_users_list(users)

        # Если сообщение слишком длинное, разбиваем
        if len(message) > 4000:
            parts = [message[i:i + 4000] for i in range(0, len(message), 4000)]
            for part in parts:
                await update.message.reply_text(part, parse_mode='Markdown')
        else:
            await update.message.reply_text(message, parse_mode='Markdown')

    except Exception as e:
        logger.error(f"Ошибка при получении списка пользователей: {e}")
        await update.message.reply_text(f"❌ Ошибка: {e}")


async def user_details_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /user <id> - детальная информация о пользователе"""
    user_id = update.effective_user.id

    if user_id != ADMIN_ID:
        await update.message.reply_text("⛔ Эта команда только для администратора")
        return

    # Получаем ID пользователя из аргументов
    args = context.args
    if not args:
        await update.message.reply_text("❌ Укажите ID пользователя: /user 123456789")
        return

    try:
        target_user_id = int(args[0])
    except ValueError:
        await update.message.reply_text("❌ ID должен быть числом")
        return

    await update.message.reply_text(f"🔄 Загружаю статистику пользователя {target_user_id}...")

    try:
        stats = get_detailed_user_stats(target_user_id)
        if not stats:
            await update.message.reply_text(f"❌ Пользователь с ID {target_user_id} не найден")
            return

        message = format_user_details(stats)
        await update.message.reply_text(message, parse_mode='Markdown')

    except Exception as e:
        logger.error(f"Ошибка при получении статистики пользователя: {e}")
        await update.message.reply_text(f"❌ Ошибка: {e}")


async def admin_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик callback-кнопок для админ-панели"""
    query = update.callback_query
    await query.answer()

    logger.info(f"🔍 admin_callback_handler ВЫЗВАН с data: {query.data}")

    if query.from_user.id != ADMIN_ID:
        logger.warning(f"⛔ Не админ: {query.from_user.id}")
        await query.edit_message_text("⛔ Это действие только для администратора")
        return

    try:
        if query.data == "admin_stats":
            logger.info("📊 Обработка admin_stats")
            stats = get_db_stats()

            # Простое форматирование без Markdown
            message = "📊 ОБЩАЯ СТАТИСТИКА БОТА\n\n"
            message += f"👥 Всего пользователей: {stats['total_users']}\n"
            message += f"📝 Всего записей: {stats['total_records']}\n"
            message += f"📊 Средний вес: {stats['avg_weight']:.1f} кг\n"
            message += f"⬇️ Мин. вес: {stats['min_weight']:.1f} кг\n"
            message += f"⬆️ Макс. вес: {stats['max_weight']:.1f} кг\n\n"

            message += "📅 Активность:\n"
            message += f"🔥 Активных за 7 дней: {stats['active_users_7d']}\n"
            message += f"📊 Записей за 7 дней: {stats['records_7d']}\n"
            message += f"📊 Записей за 30 дней: {stats['records_30d']}\n\n"

            if stats['first_record']:
                first = datetime.strptime(stats['first_record'], '%Y-%m-%d %H:%M:%S')
                last = datetime.strptime(stats['last_record'], '%Y-%m-%d %H:%M:%S')
                message += f"🎯 Первая запись: {first.strftime('%d.%m.%Y')}\n"
                message += f"🎯 Последняя запись: {last.strftime('%d.%m.%Y')}\n"
                message += f"📆 Всего дней: {(last - first).days + 1}\n\n"

            message += "🏆 Топ-5 пользователей:\n"
            for i, (uid, count) in enumerate(stats['top_users'], 1):
                message += f"{i}. ID {uid}: {count} записей\n"

            # Только одна кнопка - список пользователей
            keyboard = [
                [InlineKeyboardButton("👥 Список пользователей", callback_data="admin_users")]
            ]

            await query.edit_message_text(
                text=message,
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            logger.info("✅ admin_stats обработано")

        elif query.data == "admin_users":
            logger.info("👥 Обработка admin_users")
            users = get_users_list(10)

            message = "👥 ПОСЛЕДНИЕ 10 ПОЛЬЗОВАТЕЛЕЙ\n\n"

            for user in users:
                user_id, username, first_name, last_name, created_at, records_count, last_record = user

                name_parts = []
                if first_name:
                    name_parts.append(first_name)
                if last_name:
                    name_parts.append(last_name)
                name = " ".join(name_parts) if name_parts else "нет имени"

                username_str = f"@{username}" if username else "нет username"
                created = datetime.strptime(created_at, '%Y-%m-%d %H:%M:%S').strftime('%d.%m.%Y')

                message += f"🆔 ID: {user_id}\n"
                message += f"👤 Имя: {name}\n"
                message += f"📱 Username: {username_str}\n"
                message += f"📅 Регистрация: {created}\n"
                message += f"📊 Записей: {records_count}\n"

                if last_record:
                    last = datetime.strptime(last_record, '%Y-%m-%d %H:%M:%S').strftime('%d.%m.%Y')
                    message += f"🕐 Последняя запись: {last}\n"

                message += "─" * 30 + "\n"

            # Кнопки: назад к статистике и ещё 10
            keyboard = [
                [
                    InlineKeyboardButton("📊 Назад к статистике", callback_data="admin_stats"),
                    InlineKeyboardButton("🔄 Ещё 10", callback_data="admin_users_more")
                ]
            ]

            # Если сообщение слишком длинное
            if len(message) > 4000:
                await query.edit_message_text(
                    text="👥 Список пользователей (первые 4000 символов):",
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
                await context.bot.send_message(
                    chat_id=ADMIN_ID,
                    text=message[:4000]
                )
            else:
                await query.edit_message_text(
                    text=message,
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
            logger.info("✅ admin_users обработано")

        elif query.data == "admin_users_more":
            logger.info("👥 Обработка admin_users_more")
            users = get_users_list(20)

            message = "👥 ПОЛНЫЙ СПИСОК ПОЛЬЗОВАТЕЛЕЙ (20)\n\n"

            for user in users:
                user_id, username, first_name, last_name, created_at, records_count, last_record = user

                name_parts = []
                if first_name:
                    name_parts.append(first_name)
                if last_name:
                    name_parts.append(last_name)
                name = " ".join(name_parts) if name_parts else "нет имени"

                username_str = f"@{username}" if username else "нет username"
                created = datetime.strptime(created_at, '%Y-%m-%d %H:%M:%S').strftime('%d.%m.%Y')

                message += f"🆔 ID: {user_id}\n"
                message += f"👤 Имя: {name}\n"
                message += f"📱 Username: {username_str}\n"
                message += f"📅 Регистрация: {created}\n"
                message += f"📊 Записей: {records_count}\n"

                if last_record:
                    last = datetime.strptime(last_record, '%Y-%m-%d %H:%M:%S').strftime('%d.%m.%Y')
                    message += f"🕐 Последняя запись: {last}\n"

                message += "─" * 30 + "\n"

            # Только кнопка назад к статистике
            keyboard = [
                [InlineKeyboardButton("📊 Назад к статистике", callback_data="admin_stats")]
            ]

            if len(message) > 4000:
                await query.edit_message_text(
                    text="👥 Полный список пользователей (первые 4000 символов):",
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
                # Отправляем остаток
                remaining = message[4000:8000]
                if remaining:
                    await context.bot.send_message(
                        chat_id=ADMIN_ID,
                        text=remaining
                    )
            else:
                await query.edit_message_text(
                    text=message,
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
            logger.info("✅ admin_users_more обработано")

    except Exception as e:
        logger.error(f"❌ Ошибка: {e}")
        await query.edit_message_text(f"❌ Произошла ошибка: {str(e)}")