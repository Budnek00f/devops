import logging
import sqlite3
from datetime import datetime, time
import schedule
import time as t
from dateutil import parser
import spacy
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackContext

# Настройка логирования
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Загрузка русской модели spacy
nlp = spacy.load("ru_core_news_sm")

# Подключение к БД (SQLite)
conn = sqlite3.connect('reminders.db', check_same_thread=False)
cursor = conn.cursor()
cursor.execute('''CREATE TABLE IF NOT EXISTS reminders
                  (id INTEGER PRIMARY KEY AUTOINCREMENT,
                   user_id INTEGER,
                   reminder_text TEXT,
                   reminder_time DATETIME)''')
conn.commit()

# Функция для парсинга текста с помощью spacy и dateutil
def parse_reminder(text):
    doc = nlp(text)
    reminder_text = text
    parsed_date = None

    # Ищем дату или временные выражения
    for ent in doc.ents:
        if ent.label_ in ["DATE", "TIME"]:
            try:
                parsed_date = parser.parse(ent.text, fuzzy=True, dayfirst=True)
                reminder_text = text.replace(ent.text, "").strip()
                break
            except ValueError:
                continue

    # Если дата не найдена, пробуем dateutil
    if not parsed_date:
        try:
            parsed_date = parser.parse(text, fuzzy=True, dayfirst=True)
            reminder_text = text.replace(parsed_date.strftime('%d %B'), '').strip()
        except ValueError:
            return None, None

    # Если время не указано, ставим 9:00 утра
    if parsed_date.time() == time(0, 0):
        parsed_date = parsed_date.replace(hour=9, minute=0)

    return reminder_text, parsed_date

# Функция для добавления напоминания
async def add_reminder(update: Update, context: CallbackContext):
    user_id = update.message.from_user.id
    text = update.message.text.strip()

    reminder_text, parsed_date = parse_reminder(text)

    if not parsed_date:
        await update.message.reply_text("Не удалось распознать дату. Пример: 'поздравить деда 18 октября' или 'купить молоко в пятницу в 10:00'.")
        return

    # Сохраняем в БД
    cursor.execute("INSERT INTO reminders (user_id, reminder_text, reminder_time) VALUES (?, ?, ?)",
                   (user_id, reminder_text, parsed_date))
    conn.commit()

    await update.message.reply_text(f"Напоминание сохранено: '{reminder_text}' на {parsed_date.strftime('%d %B %Y %H:%M')}")

# Функция для проверки и отправки напоминаний
def check_reminders(context: CallbackContext):
    now = datetime.now()
    cursor.execute("SELECT id, user_id, reminder_text, reminder_time FROM reminders WHERE reminder_time <= ?",
                   (now,))
    overdue = cursor.fetchall()

    for rem in overdue:
        user_id, reminder_text, reminder_time = rem[1], rem[2], rem[3]
        context.bot.send_message(chat_id=user_id, text=f"Напоминание: {reminder_text} (было запланировано на {reminder_time})")
        cursor.execute("DELETE FROM reminders WHERE id = ?", (rem[0],))
        conn.commit()

# Команда /start
async def start(update: Update, context: CallbackContext):
    await update.message.reply_text("Привет! Напиши напоминание с датой, например: 'поздравить деда 18 октября' или 'купить молоко в пятницу'.")

# Основная функция
def main():
    # Замени на свой токен
    application = Application.builder().token('5696379337:AAFOKBjO0wiMZDs2lqsc7RPPFnODOJK4Qi4').build()

    # Хэндлеры
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, add_reminder))

    # Запуск бота
    application.run_polling()

    # Планировщик для проверки напоминаний каждую минуту
    schedule.every(1).minutes.do(check_reminders, context=application)

    while True:
        schedule.run_pending()
        t.sleep(1)

if __name__ == '__main__':
    main()