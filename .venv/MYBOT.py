import logging
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters
)йй
from datetime import datetime, time
import pytz
import re
import os
from dotenv import load_dotenv
load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")
# Конфигурация

UK_LIST = [f"УК{i}" for i in range(1, 15)]  # УК1 - УК14
TIMEZONE = pytz.timezone('Europe/Moscow')
DAILY_REPORT_TIME = time(19, 0, 0, tzinfo=TIMEZONE)  # 19:00 по Мск

# Хранение данных в памяти
daily_counts = {}
registered_groups = set()

# Настройка логгирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Отправляет приветственное сообщение"""
    await update.message.reply_text(
        "🚑 Бот для учета вызовов СМП!\n\n"
        "Отправляйте сообщения с указанием учебного корпуса:\n"
        "- Текстовые сообщения: «УК1» или «Вызов из УК3»\n"
        "- Фото с подписью: «УК5»\n\n"
        "Каждый будний день в 19:00 бот пришлет сводку по всем корпусам.\n"
        "Тестовые команды:\n"
        "/test_report - немедленная отправка сводки (и сброс данных)\n"
        "/add_test_data - добавить тестовые данные"
    )


def extract_uk(text: str) -> str | None:
    """Извлекает номер УК из текста с помощью регулярных выражений"""
    try:
        # Приводим текст к нижнему регистру для унификации
        text_lower = text.lower()

        # Ищем все упоминания УК в тексте
        matches = re.findall(r"(ук|uk)[\s\-_]*(\d{1,2})\b", text_lower)

        if matches:
            # Берем первый найденный УК
            uk_prefix, uk_num = matches[0]

            # Форматируем номер (убираем лидирующие нули)
            try:
                num = int(uk_num)
                if 1 <= num <= 14:
                    return f"УК{num}"
            except ValueError:
                pass

        # Дополнительные попытки распознавания
        match = re.search(r"\b(ук|uk)(\d{1,2})\b", text_lower)
        if match:
            try:
                num = int(match.group(2))
                if 1 <= num <= 14:
                    return f"УК{num}"
            except ValueError:
                pass

        return None
    except Exception as e:
        logger.error(f"Ошибка в extract_uk: {e}", exc_info=True)
        return None


async def register_call(update: Update, uk: str, source: str = "текст") -> None:
    """Регистрирует вызов из указанного УК с подробной обратной связью"""
    try:
        # Получаем текущую дату с учетом часового пояса
        now = datetime.now(TIMEZONE)
        today = now.strftime("%Y-%m-%d")
        weekday = now.weekday()
        day_name = ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс'][weekday]
        date_str = now.strftime('%d.%m.%Y')

        # Инициализируем счетчики для дня
        if today not in daily_counts:
            daily_counts[today] = {building: 0 for building in UK_LIST}

        # Проверяем существование УК
        if uk not in UK_LIST:
            await update.message.reply_text(
                f"❌ Ошибка: УК '{uk}' не найден в списке. Допустимые значения: {', '.join(UK_LIST)}"
            )
            return

        # Обновляем счетчик
        daily_counts[today][uk] += 1
        current_count = daily_counts[today][uk]

        # Формируем подробную обратную связь
        response = (
            f"🚑 <b>Вызов СМП зарегистрирован!</b>\n"
            f"• Источник: {source}\n"
            f"• Учебный корпус: <b>{uk}</b>\n"
            f"• Дата вызова: {date_str} ({day_name})\n"
            f"• Всего вызовов из {uk} за сегодня: <b>{current_count}</b>\n\n"
        )

        # Добавляем информацию об общем количестве вызовов
        total_today = sum(daily_counts[today].values())
        response += f"📊 <i>Всего вызовов за сегодня: {total_today}</i>"

        await update.message.reply_text(response, parse_mode='HTML')
        logger.info(f"Вызов из {uk} зарегистрирован. Источник: {source}. Всего: {current_count}")

    except Exception as e:
        logger.error(f"Ошибка регистрации вызова: {e}", exc_info=True)
        await update.message.reply_text("⚠️ Ошибка регистрации вызова")


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обрабатывает текстовые сообщения с указанием УК"""
    try:
        # Логируем информацию о чате
        chat_type = update.message.chat.type
        logger.info(f"Обработка текста в чате типа: {chat_type}")

        text = update.message.text
        if not text:
            return

        logger.info(f"Получено текстовое сообщение: {text}")

        uk = extract_uk(text)

        if not uk:
            logger.info(f"УК не найден в сообщении: '{text}'")
            # Даем обратную связь, что УК не распознан
            await update.message.reply_text(
                "❌ Не удалось определить учебный корпус.\n"
                "Пожалуйста, укажите УК в формате:\n"
                "• УК1\n• Вызов из УК3\n• UK5"
            )
            return

        logger.info(f"Извлечен УК: {uk}")

        if uk not in UK_LIST:
            await update.message.reply_text(
                f"❌ Некорректный номер УК: '{uk}'! Допустимы номера 1-14\n"
                f"Пример корректного формата: «УК7»"
            )
            return

        await register_call(update, uk, "текстовое сообщение")

    except Exception as e:
        logger.error(f"Ошибка обработки текста: {e}", exc_info=True)
        await update.message.reply_text("⚠️ Ошибка обработки сообщения")


async def handle_photo_with_caption(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обрабатывает фотографии с текстовыми подписями"""
    try:
        # Логируем информацию о чате
        chat_type = update.message.chat.type
        logger.info(f"Обработка фото с подписью в чате типа: {chat_type}")

        if not update.message.caption:
            logger.info("Фото без подписи, игнорируем")
            return

        caption = update.message.caption
        logger.info(f"Получена подпись к фото: {caption}")

        uk = extract_uk(caption)

        if not uk:
            logger.info(f"УК не найден в подписи: '{caption}'")
            # Даем обратную связь, что УК не распознан
            await update.message.reply_text(
                "❌ Не удалось определить учебный корпус в подписи к фото.\n"
                "Пожалуйста, укажите УК в формате:\n"
                "• УК1\n• Вызов из УК3\n• UK5"
            )
            return

        logger.info(f"Извлечен УК из подписи: {uk}")

        if uk not in UK_LIST:
            await update.message.reply_text(
                f"❌ Некорректный номер УК: '{uk}'! Допустимы номера 1-14\n"
                f"Пример корректного формата: «УК7»"
            )
            return

        await register_call(update, uk, "фото с подписью")

    except Exception as e:
        logger.error(f"Ошибка обработки фото с подписью: {e}", exc_info=True)
        await update.message.reply_text("⚠️ Ошибка обработки сообщения с фото")


def generate_report() -> str:
    """Генерирует текст отчета без отправки"""
    now = datetime.now(TIMEZONE)
    today = now.strftime("%Y-%m-%d")
    weekday = now.weekday()
    day_name = ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс'][weekday]
    date_str = now.strftime('%d.%m.%Y')

    # Формируем отчет
    report_lines = [
        f"📊 <b>Сводка вызовов СМП за {date_str} ({day_name}):</b>"
    ]

    if today in daily_counts:
        total_calls = sum(daily_counts[today].values())
        report_lines.append(f"\n🚑 Всего вызовов за день: <b>{total_calls}</b>\n")

        for uk in UK_LIST:
            count = daily_counts[today].get(uk, 0)
            if count > 0:
                report_lines.append(f"  - {uk}: 🚑 {count} вызов(ов)")
            else:
                report_lines.append(f"  - {uk}: ✅ вызовов не было")
    else:
        report_lines.append("\nℹ️ За сегодня не было зарегистрировано вызовов")
        for uk in UK_LIST:
            report_lines.append(f"  - {uk}: ✅ вызовов не было")

    return "\n".join(report_lines)


def reset_daily_counters():
    """Сбрасывает счетчики за текущий день"""
    today = datetime.now(TIMEZONE).strftime("%Y-%m-%d")
    if today in daily_counts:
        del daily_counts[today]
        logger.info(f"Счетчики за {today} сброшены")


async def send_daily_report(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Отправляет ежедневный отчет и сбрасывает данные"""
    try:
        now = datetime.now(TIMEZONE)
        today = now.strftime("%Y-%m-%d")
        weekday = now.weekday()

        # Только будние дни (0-4 = Пн-Пт)
        if weekday > 4:
            logger.info("Сегодня выходной, отчет не требуется")
            return

        report = generate_report()

        # Отправляем во все зарегистрированные группы
        failed_chats = []
        for chat_id in registered_groups.copy():
            try:
                await context.bot.send_message(
                    chat_id=chat_id,
                    text=report,
                    parse_mode='HTML'
                )
                logger.info(f"Отчет отправлен в группу {chat_id}")
            except Exception as e:
                logger.error(f"Ошибка отправки в группу {chat_id}: {e}")
                failed_chats.append(chat_id)

        # Удаляем недоступные чаты
        for chat_id in failed_chats:
            registered_groups.discard(chat_id)
            logger.warning(f"Группа {chat_id} удалена из рассылки")

        # Сбрасываем счетчики только если отчет успешно отправлен хотя бы в одну группу
        if today in daily_counts and registered_groups:
            reset_daily_counters()  # Сбрасываем счетчики

    except Exception as e:
        logger.error(f"Критическая ошибка при отправке отчета: {e}", exc_info=True)


async def test_report(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Немедленная отправка тестового отчета и сброс данных"""
    try:
        report = generate_report()
        await update.message.reply_text(report, parse_mode='HTML')
        logger.info("Тестовый отчет отправлен по запросу")

        # Сбрасываем счетчики после тестового отчета
        reset_daily_counters()
        await update.message.reply_text("🔄 Данные сброшены после тестового отчета")

    except Exception as e:
        logger.error(f"Ошибка отправки тестового отчета: {e}", exc_info=True)
        await update.message.reply_text("⚠️ Ошибка при отправке тестового отчета")


async def add_test_data(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Добавляет тестовые данные"""
    try:
        now = datetime.now(TIMEZONE)
        today = now.strftime("%Y-%m-%d")

        # Инициализируем счетчики для дня
        if today not in daily_counts:
            daily_counts[today] = {uk: 0 for uk in UK_LIST}

        # Добавляем тестовые вызовы
        daily_counts[today]["УК1"] = 3
        daily_counts[today]["УК5"] = 2
        daily_counts[today]["УК10"] = 1

        await update.message.reply_text(
            "✅ <b>Тестовые данные добавлены:</b>\n"
            "- УК1: 3 вызова\n"
            "- УК5: 2 вызова\n"
            "- УК10: 1 вызов\n\n"
            "Используйте /test_report для просмотра сводки и сброса данных",
            parse_mode='HTML'
        )
        logger.info("Тестовые данные добавлены")
    except Exception as e:
        logger.error(f"Ошибка добавления тестовых данных: {e}", exc_info=True)
        await update.message.reply_text("⚠️ Ошибка при добавлении тестовых данных")


async def register_group(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Регистрирует группу для получения отчетов"""
    chat_id = update.message.chat.id
    chat_type = update.message.chat.type

    logger.info(f"Попытка регистрации чата: ID={chat_id}, тип={chat_type}")

    if chat_id not in registered_groups:
        registered_groups.add(chat_id)
        logger.info(f"Зарегистрирована новая группа: ID={chat_id}, тип={chat_type}")

        # Отправляем сообщение только если это группа/супергруппа
        if chat_type in ["group", "supergroup"]:
            await update.message.reply_text(
                "✅ <b>Группа зарегистрирована!</b>\n"
                "Бот будет присылать ежедневные отчеты в 19:00 по будням.\n\n"
                "<b>Тестовые команды:</b>\n"
                "/test_report - немедленная отправка сводки (и сброс данных)\n"
                "/add_test_data - добавить тестовые данные\n\n"
                "<b>Для регистрации вызова</b> отправьте:\n"
                "- Текстовое сообщение вида «УК5»\n"
                "- Или фото с подписью «Вызов из УК3»",
                parse_mode='HTML'
            )
    else:
        logger.info(f"Чат {chat_id} уже зарегистрирован")


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик неотловленных ошибок"""
    logger.error(f'Ошибка: {context.error}', exc_info=True)

    if update and isinstance(update, Update) and update.message:
        await update.message.reply_text("⚠️ Произошла внутренняя ошибка. Попробуйте позже")


def main() -> None:
    """Запускает бота"""
    # Создаем Application
    application = Application.builder().token(TOKEN).build()

    # Регистрируем обработчики
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("test_report", test_report))
    application.add_handler(CommandHandler("add_test_data", add_test_data))

    # Обработчики сообщений
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    application.add_handler(MessageHandler(filters.PHOTO & filters.CAPTION, handle_photo_with_caption))

    # Регистрация групп при любом сообщении в группе
    application.add_handler(MessageHandler(
        filters.ChatType.GROUPS | filters.ChatType.SUPERGROUP,
        register_group
    ))

    # Регистрируем обработчик ошибок
    application.add_error_handler(error_handler)

    # Настраиваем ежедневный отчет (если JobQueue доступен)
    if application.job_queue:
        application.job_queue.run_daily(
            send_daily_report,
            time=DAILY_REPORT_TIME,
            days=tuple(range(5))  # Пн-Пт (0-4)
        )
        logger.info("JobQueue настроен для ежедневных отчетов")
    else:
        logger.error("JobQueue недоступен! Ежедневные отчеты работать не будут")

    # Запускаем бота
    logger.info("Бот запущен и ожидает сообщений...")
    application.run_polling()


if __name__ == '__main__':
    main()