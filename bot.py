import asyncio
import sqlite3
from datetime import datetime
from pathlib import Path

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    KeyboardButton,
    Message,
    ReplyKeyboardMarkup,
)
from dotenv import load_dotenv
import os


# Настройки

load_dotenv()

TOKEN = os.getenv("BOT_TOKEN")

if not TOKEN:
    raise RuntimeError("Не найден BOT_TOKEN в файле .env")

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "reminders.db"

bot = Bot(token=TOKEN)
dp = Dispatcher(storage=MemoryStorage())


# Кнопки

main_menu = ReplyKeyboardMarkup(
    keyboard=[
        [
            KeyboardButton(text="📩 Оставить заявку"),
            KeyboardButton(text="⏰ Напоминания"),
        ],
        [KeyboardButton(text="ℹ️ Помощь")],
    ],
    resize_keyboard=True,
)

reminder_menu = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="➕ Создать напоминание")],
        [KeyboardButton(text="📋 Мои напоминания")],
        [KeyboardButton(text="⬅️ Главное меню")],
    ],
    resize_keyboard=True,
)


# Состояния анкеты

class ReminderForm(StatesGroup):
    text = State()
    when = State()


# База данных

def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS reminders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                text TEXT NOT NULL,
                remind_at TEXT NOT NULL,
                sent INTEGER NOT NULL DEFAULT 0
            )
        """)


def save_reminder(user_id: int, text: str, remind_at: datetime):
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """
            INSERT INTO reminders (user_id, text, remind_at)
            VALUES (?, ?, ?)
            """,
            (user_id, text, remind_at.isoformat(timespec="seconds")),
        )


def get_reminders(user_id: int):
    with sqlite3.connect(DB_PATH) as conn:
        return conn.execute(
            """
            SELECT id, text, remind_at
            FROM reminders
            WHERE user_id = ? AND sent = 0
            ORDER BY remind_at
            """,
            (user_id,),
        ).fetchall()


# Команды и меню

@dp.message(F.text == "📩 Оставить заявку")
async def application_placeholder(message: Message):
    await message.answer(
        "📩 Раздел «Оставить заявку» пока в разработке.\n"
        "Мы добавим эту возможность позже."
    )


@dp.message(F.text == "ℹ️ Помощь")
async def help_placeholder(message: Message):
    await message.answer(
        "ℹ️ Раздел «Помощь» пока в разработке.\n"
        "Инструкция по работе с ботом появится позже."
    )

@dp.message(CommandStart())
async def start(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "Привет! 👋\n"
        "Я бот-помощник.\n\n"
        "Выбери действие в меню:",
        reply_markup=main_menu,
    )


@dp.message(Command("cancel"))
async def cancel(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "Действие отменено.",
        reply_markup=reminder_menu,
    )


@dp.message(F.text == "⏰ Напоминания")
async def reminders_menu(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "⏰ Раздел напоминаний\n\n"
        "Здесь ты можешь создать напоминание "
        "или посмотреть список запланированных.",
        reply_markup=reminder_menu,
    )


@dp.message(F.text == "⬅️ Главное меню")
async def back_to_main(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "Главное меню:",
        reply_markup=main_menu,
    )


# Создание напоминания

@dp.message(F.text == "➕ Создать напоминание")
async def create_reminder(message: Message, state: FSMContext):
    await state.set_state(ReminderForm.text)
    await message.answer(
        "Напиши текст напоминания.\n\n"
        "Например: Проверить домашнее задание\n\n"
        "Для отмены отправь /cancel."
    )


@dp.message(ReminderForm.text)
async def receive_reminder_text(message: Message, state: FSMContext):
    if not message.text or not message.text.strip():
        await message.answer("Пожалуйста, введи текст сообщением.")
        return

    await state.update_data(reminder_text=message.text.strip())
    await state.set_state(ReminderForm.when)

    await message.answer(
        "Теперь укажи дату и время напоминания.\n\n"
        "Формат: ДД.ММ.ГГГГ ЧЧ:ММ\n"
        "Например: 27.10.2026 18:30"
    )


@dp.message(ReminderForm.when)
async def receive_reminder_time(message: Message, state: FSMContext):
    if not message.text:
        await message.answer(
            "Введи дату и время текстом, например 27.10.2026 18:30."
        )
        return

    try:
        remind_at = datetime.strptime(
            message.text.strip(),
            "%d.%m.%Y %H:%M",
        )
    except ValueError:
        await message.answer(
            "Не удалось распознать дату.\n"
            "Используй формат ДД.ММ.ГГГГ ЧЧ:ММ\n"
            "Например: 27.10.2026 18:30"
        )
        return

    if remind_at <= datetime.now():
        await message.answer(
            "Это время уже прошло. Укажи будущую дату и время."
        )
        return

    data = await state.get_data()
    reminder_text = data["reminder_text"]

    save_reminder(
        user_id=message.from_user.id,
        text=reminder_text,
        remind_at=remind_at,
    )

    await state.clear()

    await message.answer(
        "✅ Напоминание сохранено!\n\n"
        f"📝 {reminder_text}\n"
        f"📅 {remind_at.strftime('%d.%m.%Y в %H:%M')}\n\n"
        "Бот отправит сообщение в указанное время, "
        "пока он запущен.",
        reply_markup=reminder_menu,
    )


# Просмотр напоминаний

@dp.message(F.text == "📋 Мои напоминания")
async def list_reminders(message: Message):
    reminders = get_reminders(message.from_user.id)

    if not reminders:
        await message.answer(
            "У тебя пока нет ожидающих напоминаний.",
            reply_markup=reminder_menu,
        )
        return

    lines = ["📋 Твои напоминания:\n"]

    for reminder_id, text, remind_at in reminders:
        date = datetime.fromisoformat(remind_at)
        lines.append(
            f"#{reminder_id} — {text}\n"
            f"📅 {date.strftime('%d.%m.%Y в %H:%M')}"
        )

    await message.answer("\n\n".join(lines), reply_markup=reminder_menu)


# Проверка времени

async def reminder_worker():
    while True:
        try:
            now = datetime.now().isoformat(timespec="seconds")

            with sqlite3.connect(DB_PATH) as conn:
                due_reminders = conn.execute(
                    """
                    SELECT id, user_id, text
                    FROM reminders
                    WHERE sent = 0 AND remind_at <= ?
                    ORDER BY remind_at
                    """,
                    (now,),
                ).fetchall()

            for reminder_id, user_id, text in due_reminders:
                try:
                    await bot.send_message(
                        user_id,
                        f"🔔 Напоминание!\n\n{text}",
                    )

                    with sqlite3.connect(DB_PATH) as conn:
                        conn.execute(
                            "UPDATE reminders SET sent = 1 WHERE id = ?",
                            (reminder_id,),
                        )

                except Exception as error:
                    print(
                        f"Не удалось отправить напоминание "
                        f"#{reminder_id}: {error}"
                    )

        except Exception as error:
            print(f"Ошибка проверки напоминаний: {error}")

        await asyncio.sleep(10)


# Запуск

async def main():
    init_db()
    print("Бот запущен!")

    worker = asyncio.create_task(reminder_worker())

    try:
        await dp.start_polling(bot)
    finally:
        worker.cancel()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())