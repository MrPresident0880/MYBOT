import logging
import sqlite3
from contextlib import closing
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters
)
from datetime import datetime, time, timedelta
import pytz
import re
from dateutil.relativedelta import relativedelta
import calendar
import os

# Конфигурация
TOKEN = "7088016072:AAGXB3VzWWJdiTcrHfLn-kMoudu72RGst8M"
UK_LIST = [f"УК{i}" for i in range(1, 15)]  # УК1 - УК14
TIMEZONE = pytz.timezone('Europe/Moscow')
DAILY_REPORT_TIME = time(19, 0, 0, tzinfo=TIMEZONE)  # 19:00 по Мск
MONTHLY_REPORT_TIME = time(20, 0, 0, tzinfo=TIMEZONE)  # 20:00 по Мск
DATABASE_NAME = "smp_bot.db"
REGISTERED_GROUPS_FILE = "registered_groups.txt"

# Настройка логгирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)


# Инициализация базы данных
def init_database():
    with closing(sqlite3.connect(DATABASE_NAME)) as conn:
        with closing(conn.cursor()) as cursor:
            # Таблица для ежедневных данных
            cursor.execute('''
                         CREATE TABLE IF NOT EXISTS daily_calls (
                             date TEXT NOT NULL,
                             uk TEXT NOT NULL,
                             count INTEGER DEFAULT 0,
                             PRIMARY KEY (date, uk)
                         )
                     ''')

            # Таблица для ежемесячных данных
            cursor.execute('''
                         CREATE TABLE IF NOT EXISTS monthly_calls (
                             month TEXT NOT NULL,
                             uk TEXT NOT NULL,
                             count INTEGER DEFAULT 0,
                             PRIMARY KEY (month, uk)
                         )
                     ''')

            # Таблица для зарегистрированных групп
            cursor.execute('''
                         CREATE TABLE IF NOT EXISTS registered_groups (
                             chat_id TEXT PRIMARY KEY
                         )
                     ''')

            conn.commit()


def save_registered_groups(groups):
    try:
        with open(REGISTERED_GROUPS_FILE, 'w') as f:
            for chat_id in groups:
                f.write(f"{chat_id}\n")
    except Exception as e:
        logger.error(f"Ошибка сохранения групп: {e}")


def load_registered_groups():
    groups = set()
    try:
        if os.path.exists(REGISTERED_GROUPS_FILE):
            with open(REGISTERED_GROUPS_FILE, 'r') as f:
                for line in f:
                    groups.add(line.strip())
    except Exception as e:
        logger.error(f"Ошибка загрузки групп: {e}")
    return groups


# Функции для работы с базой данных
def register_call(uk: str):
    now = datetime.now(TIMEZONE)
    date_str = now.strftime("%Y-%m-%d")
    month_str = now.strftime("%Y-%m")

    with closing(sqlite3.connect(DATABASE_NAME)) as conn:
        with closing(conn.cursor()) as cursor:
            # Обновление ежедневных данных
            cursor.execute('''
                         INSERT INTO daily_calls (date, uk, count)
                         VALUES (?, ?, 1)
                         ON CONFLICT(date, uk) DO UPDATE SET count = count + 1
                     ''', (date_str, uk))

            # Обновление ежемесячных данных
            cursor.execute('''
                         INSERT INTO monthly_calls (month, uk, count)
                         VALUES (?, ?, 1)
                         ON CONFLICT(month, uk) DO UPDATE SET count = count + 1
                     ''', (month_str, uk))

            conn.commit()


def get_daily_data(date: str = None):
    if not date:
        date = datetime.now(TIMEZONE).strftime("%Y-%m-%d")

    data = {}
    with closing(sqlite3.connect(DATABASE_NAME)) as conn:
        with closing(conn.cursor()) as cursor:
            cursor.execute('''
                         SELECT uk, count FROM daily_calls
                         WHERE date = ?
                     ''', (date,))

            for row in cursor.fetchall():
                uk, count = row
                data[uk] = count

    # Добавляем нулевые значения для отсутствующих УК
    for uk in UK_LIST:
        if uk not in data:
            data[uk] = 0

    return data


def get_monthly_data(month: str = None):
    if not month:
        month = datetime.now(TIMEZONE).strftime("%Y-%m")

    data = {}
    with closing(sqlite3.connect(DATABASE_NAME)) as conn:
        with closing(conn.cursor()) as cursor:
            cursor.execute('''
                         SELECT uk, count FROM monthly_calls
                         WHERE month = ?
                     ''', (month,))

            for row in cursor.fetchall():
                uk, count = row
                data[uk] = count

    # Добавляем нулевые значения для отсутствующих УК
    for uk in UK_LIST:
        if uk not in data:
            data[uk] = 0

    return data


def add_test_data():
    now = datetime.now(TIMEZONE)
    date_str = now.strftime("%Y-%m-%d")
    month_str = now.strftime("%Y-%m")

    test_calls = {
        "УК1": 3,
        "УК5": 2,
        "УК10": 1,
        "УК13": 4
    }

    with closing(sqlite3.connect(DATABASE_NAME)) as conn:
        with closing(conn.cursor()) as cursor:
            for uk, count in test_calls.items():
                # Добавление ежедневных тестовых данных
                cursor.execute('''
                             INSERT INTO daily_calls (date, uk, count)
                             VALUES (?, ?, ?)
                             ON CONFLICT(date, uk) DO UPDATE SET count = count + ?
                         ''', (date_str, uk, count, count))

                # Добавление ежемесячных тестовых данных
                cursor.execute('''
                             INSERT INTO monthly_calls (month, uk, count)
                             VALUES (?, ?, ?)
                             ON CONFLICT(month, uk) DO UPDATE SET count = count + ?
                         ''', (month_str, uk, count, count))

            conn.commit()

    return test_calls


# Основные функции бота
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "🚑 Бот для учета вызовов СМП!\n\n"
        "Отправляйте сообщения с указанием учебного корпуса:\n"
        "- Текстовые сообщения: «УК1» или «Вызов из УК3»\n"
        "- Фото с подписью: «УК5»\n\n"
        "Отчеты:\n"
        "• Ежедневный - будни в 19:00\n"
        "• Ежемесячный - последний рабочий день месяца в 20:00\n\n"
        "Тестовые команды:\n"
        "/daily_report - немедленная отправка дневной сводки\n"
        "/monthly_report - немедленная отправка месячной сводки\n"
        "/add_test_data - добавить тестовые данные"
    )


def extract_uk(text: str) -> str | None:
    try:
        text_lower = text.lower()
        matches = re.findall(r"(ук|uk)[\s\-_]*(\d{1,2})\b", text_lower)

        if matches:
            uk_prefix, uk_num = matches[0]
            try:
                num = int(uk_num)
                if 1 <= num <= 14:
                    return f"УК{num}"
            except ValueError:
                pass

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


async def handle_call(update: Update, uk: str, source: str = "текст") -> None:
    try:
        # Регистрируем вызов в БД
        register_call(uk)

        # Формируем ответ
        now = datetime.now(TIMEZONE)
        date_str = now.strftime("%d.%m.%Y")
        month_str = now.strftime("%B %Y").lower()

        # Получаем текущие данные
        daily_data = get_daily_data()
        monthly_data = get_monthly_data()

        response = (
            f"🚑 <b>Вызов СМП зарегистрирован!</b>\n"
            f"• Учебный корпус: <b>{uk}</b>\n"
            f"• Дата: {date_str}\n"
            f"• Вызовов из {uk} сегодня: <b>{daily_data[uk]}</b>\n"
            f"• Вызовов из {uk} в этом месяце: <b>{monthly_data[uk]}</b>"
        )

        await update.message.reply_text(response, parse_mode='HTML')
        logger.info(f"Вызов из {uk} зарегистрирован. Источник: {source}")

    except Exception as e:
        logger.error(f"Ошибка регистрации вызова: {e}", exc_info=True)
        await update.message.reply_text("⚠️ Ошибка регистрации вызова")


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        text = update.message.text
        if not text:
            return

        uk = extract_uk(text)
        if not uk:
            await update.message.reply_text(
                "❌ Не удалось определить учебный корпус.\n"
                "Пожалуйста, укажите УК в формате:\n"
                "• УК1\n• Вызов из УК3\n• UK5"
            )
            return

        if uk not in UK_LIST:
            await update.message.reply_text(
                f"❌ Некорректный номер УК: '{uk}'! Допустимы номера 1-14"
            )
            return

        await handle_call(update, uk, "текстовое сообщение")

    except Exception as e:
        logger.error(f"Ошибка обработки текста: {e}", exc_info=True)
        await update.message.reply_text("⚠️ Ошибка обработки сообщения")


async def handle_photo_with_caption(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        if not update.message.caption:
            return

        caption = update.message.caption
        uk = extract_uk(caption)

        if not uk:
            await update.message.reply_text(
                "❌ Не удалось определить УК в подписи.\n"
                "Пожалуйста, укажите УК в формате:\n"
                "• УК1\n• Вызов из УК3\n• UK5"
            )
            return

        if uk not in UK_LIST:
            await update.message.reply_text(
                f"❌ Некорректный номер УК: '{uk}'! Допустимы номера 1-14"
            )
            return

        await handle_call(update, uk, "фото с подписью")

    except Exception as e:
        logger.error(f"Ошибка обработки фото: {e}", exc_info=True)
        await update.message.reply_text("⚠️ Ошибка обработки сообщения с фото")


def generate_daily_report(date: str = None) -> str:
    if not date:
        date = datetime.now(TIMEZONE).strftime("%Y-%m-%d")

    daily_data = get_daily_data(date)
    report_date = datetime.strptime(date, "%Y-%m-%d").strftime("%d.%m.%Y")

    report_lines = [
        f"📊 <b>Дневная сводка вызовов СМП за {report_date}:</b>"
    ]

    total = 0
    for uk in UK_LIST:
        count = daily_data.get(uk, 0)
        if count > 0:
            report_lines.append(f"  - {uk}: 🚑 {count} вызов(ов)")
            total += count

    if total > 0:
        report_lines.append(f"\n🚑 Всего за день: <b>{total}</b>")
    else:
        report_lines.append("\nℹ️ Вызовов не было")

    return "\n".join(report_lines)


def generate_monthly_report(month: str = None) -> str:
    if not month:
        month = datetime.now(TIMEZONE).strftime("%Y-%m")

    monthly_data = get_monthly_data(month)
    report_month = datetime.strptime(month + "-01", "%Y-%m-%d").strftime("%B %Y").lower()

    report_lines = [
        f"📈 <b>Месячная сводка вызовов СМП за {report_month}:</b>"
    ]

    total = 0
    for uk in UK_LIST:
        count = monthly_data.get(uk, 0)
        if count > 0:
            report_lines.append(f"  - {uk}: 🚑 {count} вызов(ов)")
            total += count

    if total > 0:
        report_lines.append(f"\n🚑 Всего за месяц: <b>{total}</b>")
    else:
        report_lines.append("\nℹ️ Вызовов не было")

    return "\n".join(report_lines)


async def send_daily_report(context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        now = datetime.now(TIMEZONE)
        if now.weekday() > 4:  # Выходные
            return

        report = generate_daily_report()
        registered_groups = load_registered_groups()

        for chat_id in registered_groups:
            try:
                await context.bot.send_message(
                    chat_id=chat_id,
                    text=report,
                    parse_mode='HTML'
                )
                logger.info(f"Дневной отчет отправлен в группу {chat_id}")
            except Exception as e:
                logger.error(f"Ошибка отправки в группу {chat_id}: {e}")

    except Exception as e:
        logger.error(f"Ошибка отправки дневного отчета: {e}", exc_info=True)


def get_last_weekday_of_month(year: int, month: int) -> datetime:
    last_day = calendar.monthrange(year, month)[1]
    date = datetime(year, month, last_day, tzinfo=TIMEZONE)

    # Ищем последнюю пятницу
    while date.weekday() != 4:  # 4 = пятница
        date -= timedelta(days=1)
    return date


async def send_monthly_report(context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        report = generate_monthly_report()
        registered_groups = load_registered_groups()

        for chat_id in registered_groups:
            try:
                await context.bot.send_message(
                    chat_id=chat_id,
                    text=report,
                    parse_mode='HTML'
                )
                logger.info(f"Месячный отчет отправлен в группу {chat_id}")
            except Exception as e:
                logger.error(f"Ошибка отправки в группу {chat_id}: {e}")

    except Exception as e:
        logger.error(f"Ошибка отправки месячного отчета: {e}", exc_info=True)


async def daily_report(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        report = generate_daily_report()
        await update.message.reply_text(report, parse_mode='HTML')
        logger.info("Тестовый дневной отчет отправлен")
    except Exception as e:
        logger.error(f"Ошибка отправки дневного отчета: {e}", exc_info=True)
        await update.message.reply_text("⚠️ Ошибка при отправке отчета")


async def monthly_report(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        report = generate_monthly_report()
        await update.message.reply_text(report, parse_mode='HTML')
        logger.info("Тестовый месячный отчет отправлен")
    except Exception as e:
        logger.error(f"Ошибка отправки месячного отчета: {e}", exc_info=True)
        await update.message.reply_text("⚠️ Ошибка при отправке отчета")


async def add_test_data_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        test_calls = add_test_data()
        response = (
                "✅ <b>Тестовые данные добавлены:</b>\n" +
                "\n".join([f"- {uk}: {count} вызовов" for uk, count in test_calls.items()]) +
                "\n\nИспользуйте:\n/daily_report - дневной отчет\n/monthly_report - месячный отчет"
        )

        await update.message.reply_text(response, parse_mode='HTML')
    except Exception as e:
        logger.error(f"Ошибка добавления тестовых данных: {e}", exc_info=True)
        await update.message.reply_text("⚠️ Ошибка при добавлении тестовых данных")


async def register_group(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = str(update.message.chat.id)
    registered_groups = load_registered_groups()

    if chat_id not in registered_groups:
        registered_groups.add(chat_id)
        save_registered_groups(registered_groups)

        await update.message.reply_text(
            "✅ <b>Группа зарегистрирована!</b>\n"
            "Бот будет присылать:\n"
            "- Ежедневные отчеты в 19:00 по будням\n"
            "- Ежемесячные отчеты в последний рабочий день месяца в 20:00\n\n"
            "<b>Тестовые команды:</b>\n"
            "/daily_report - дневная сводка\n"
            "/monthly_report - месячная сводка\n"
            "/add_test_data - тестовые данные\n\n"
            "<b>Для регистрации вызова</b> отправьте:\n"
            "- Текст: «УК5» или «Вызов из УК3»\n"
            "- Фото с подписью",
            parse_mode='HTML'
        )
        logger.info(f"Зарегистрирована новая группа: {chat_id}")
    else:
        logger.info(f"Группа {chat_id} уже зарегистрирована")
        await update.message.reply_text("ℹ️ Группа уже зарегистрирована")


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.error(f'Ошибка: {context.error}', exc_info=True)
    if update and isinstance(update, Update) and update.message:
        await update.message.reply_text("⚠️ Произошла внутренняя ошибка. Попробуйте позже")


def schedule_monthly_report(job_queue):
    now = datetime.now(TIMEZONE)
    last_weekday = get_last_weekday_of_month(now.year, now.month)

    if last_weekday < now:
        next_month = now + relativedelta(months=1)
        last_weekday = get_last_weekday_of_month(next_month.year, next_month.month)

    report_time = last_weekday.replace(
        hour=MONTHLY_REPORT_TIME.hour,
        minute=MONTHLY_REPORT_TIME.minute,
        second=0,
        microsecond=0
    )

    job_queue.run_once(send_monthly_report, when=report_time)
    logger.info(f"Месячный отчет запланирован на {report_time.strftime('%d.%m.%Y %H:%M')}")


def main() -> None:
    # Инициализация базы данных
    init_database()
    logger.info("База данных инициализирована")

    # Создание Application
    application = Application.builder().token(TOKEN).build()

    # Регистрация обработчиков
    handlers = [
        CommandHandler("start", start),
        CommandHandler("daily_report", daily_report),
        CommandHandler("monthly_report", monthly_report),
        CommandHandler("add_test_data", add_test_data_cmd),
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text),
        MessageHandler(filters.PHOTO & filters.CAPTION, handle_photo_with_caption),
        MessageHandler(filters.ChatType.GROUPS | filters.ChatType.SUPERGROUP, register_group)
    ]

    for handler in handlers:
        application.add_handler(handler)

    application.add_error_handler(error_handler)

    # Настройка расписаний
    if application.job_queue:
        # Ежедневный отчет
        application.job_queue.run_daily(
            send_daily_report,
            time=DAILY_REPORT_TIME,
            days=tuple(range(5))  # Пн-Пт
        )

        # Ежемесячный отчет
        schedule_monthly_report(application.job_queue)

        # Перепланировка после отправки
        application.job_queue.run_once(
            lambda ctx: schedule_monthly_report(application.job_queue),
            when=timedelta(days=30)
        )
    else:
        logger.error("JobQueue недоступен! Отчеты работать не будут")

    # Запуск бота
    logger.info("Бот запущен и ожидает сообщений...")
    application.run_polling()


if __name__ == '__main__':
    main()
