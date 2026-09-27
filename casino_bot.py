import os
import random
import sqlite3
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    ContextTypes,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
)
from dotenv import load_dotenv
import logging

# --- НАСТРОЙКИ ---
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

load_dotenv()

DB_NAME = "casino.db"
ADMIN_ID = 8762706702

# ID анимаций (видео MP4)
ANIMATION_ROULETTE = "AAMCAQADGQEDmF9marjABoVRagHwqE0_Ub4xe4BsfesAAtsGAAKghpBFwi-Q2tzYUAIBAAdtAAM9BA"
ANIMATION_SLOTS = "AgADHQsAAu_tpFA"
ANIMATION_COIN = "AgADZwcAAtnSJVE"
STICKER_BLACKJACK = None
STICKER_CARD = None

# --- ПРОМОКОДЫ ---
PROMOCODES = {
    "#STARTER":    (100, 500),
    "#LUCKY777":   (500, 2000),
    "#ACEWIN":     (1000, 5000),
    "#BIGBET":     (2000, 10000),
    "#COINFARM":   (50, 300),
    "#NEWPLAYER":  (200, 800),
    "#HIGHROLLER": (3000, 15000),
    "#MEGAACE":    (5000, 20000),
    "#FREEACE":    (100, 400),
    "#JACKPOT":    (10000, 50000),
    "#CASINO2026": (1000, 3000),
    "#SPINWIN":    (300, 1500),
    "#BLKJACK":    (800, 3000),
    "#COINFLIP":   (150, 700),
    "#CARDACE":    (400, 1200),
    "#ROULETTE":   (600, 2500),
    "#SLOTFRENZY": (1000, 4000),
    "#ACEGIFT":    (500, 1000),
    "#LUCKYACE":   (2000, 8000),
    "#GOLDRUSH":   (5000, 25000),
    "#FORTUNE":    (300, 1000),
    "#ACEBONUS":   (1500, 5000),
}

# --- КВЕСТЫ ---
QUESTS = [
    # Лёгкие (2)
    {"id": 1, "desc": "Сыграй первую игру", "reward": 200, "check": lambda s: s["total_games"] >= 1},
    {"id": 2, "desc": "Получи ежедневный бонус", "reward": 300, "check": lambda s: s["bonus_claimed"] >= 1},
    # Средние (10)
    {"id": 3, "desc": "Сыграй 10 игр", "reward": 500, "check": lambda s: s["total_games"] >= 10},
    {"id": 4, "desc": "Победи 5 раз", "reward": 700, "check": lambda s: s["wins"] >= 5},
    {"id": 5, "desc": "Сыграй в 3 разные игры", "reward": 600, "check": lambda s: len(s["games_played"]) >= 3},
    {"id": 6, "desc": "Выиграй 1000 AceCoin суммарно", "reward": 800, "check": lambda s: s["total_won"] >= 1000},
    {"id": 7, "desc": "Сыграй в рулетку 5 раз", "reward": 500, "check": lambda s: s["roulette_plays"] >= 5},
    {"id": 8, "desc": "Выиграй в блэкджек", "reward": 600, "check": lambda s: s["blackjack_wins"] >= 1},
    {"id": 9, "desc": "Совпадение в слотах", "reward": 500, "check": lambda s: s["slots_match"] >= 1},
    {"id": 10, "desc": "Сыграй в слоты 5 раз", "reward": 500, "check": lambda s: s["slots_plays"] >= 5},
    {"id": 11, "desc": "Выиграй в монетку", "reward": 400, "check": lambda s: s["coin_wins"] >= 1},
    {"id": 12, "desc": "Сыграй 20 игр", "reward": 1000, "check": lambda s: s["total_games"] >= 20},
    # Нереально сложные (8)
    {"id": 13, "desc": "Победи 50 раз", "reward": 5000, "check": lambda s: s["wins"] >= 50},
    {"id": 14, "desc": "Выиграй 10000 AceCoin за одну ставку", "reward": 10000, "check": lambda s: s["biggest_win"] >= 10000},
    {"id": 15, "desc": "Три 7️⃣ в слотах", "reward": 15000, "check": lambda s: s["slots_jackpot"] >= 1},
    {"id": 16, "desc": "Выиграй в блэкджек 10 раз", "reward": 8000, "check": lambda s: s["blackjack_wins"] >= 10},
    {"id": 17, "desc": "Сыграй 100 игр", "reward": 10000, "check": lambda s: s["total_games"] >= 100},
    {"id": 18, "desc": "Выиграй 50000 AceCoin суммарно", "reward": 20000, "check": lambda s: s["total_won"] >= 50000},
    {"id": 19, "desc": "Натуральный блэкджек 5 раз", "reward": 12000, "check": lambda s: s["natural_blackjacks"] >= 5},
    {"id": 20, "desc": "Победи 20 раз подряд", "reward": 50000, "check": lambda s: s["max_win_streak"] >= 20},
]


def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        balance INTEGER DEFAULT 1000,
        last_bonus TIMESTAMP,
        wins INTEGER DEFAULT 0,
        losses INTEGER DEFAULT 0
    )""")
    conn.commit()
    conn.close()

    # Миграция: добавляем колонки для статистики
    migrate_columns = [
        ("total_games", "INTEGER DEFAULT 0"),
        ("total_won", "INTEGER DEFAULT 0"),
        ("roulette_plays", "INTEGER DEFAULT 0"),
        ("blackjack_plays", "INTEGER DEFAULT 0"),
        ("blackjack_wins", "INTEGER DEFAULT 0"),
        ("natural_blackjacks", "INTEGER DEFAULT 0"),
        ("slots_plays", "INTEGER DEFAULT 0"),
        ("slots_match", "INTEGER DEFAULT 0"),
        ("slots_jackpot", "INTEGER DEFAULT 0"),
        ("card_plays", "INTEGER DEFAULT 0"),
        ("coin_plays", "INTEGER DEFAULT 0"),
        ("coin_wins", "INTEGER DEFAULT 0"),
        ("games_played", "TEXT DEFAULT ''"),
        ("current_streak", "INTEGER DEFAULT 0"),
        ("max_win_streak", "INTEGER DEFAULT 0"),
        ("bonus_claimed", "INTEGER DEFAULT 0"),
        ("biggest_win", "INTEGER DEFAULT 0"),
    ]
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    for col_name, col_def in migrate_columns:
        try:
            c.execute(f"ALTER TABLE users ADD COLUMN {col_name} {col_def}")
        except sqlite3.OperationalError:
            pass  # колонка уже существует

    # Таблица использованных промокодов
    c.execute("""CREATE TABLE IF NOT EXISTS promocodes_used (
        code TEXT PRIMARY KEY,
        user_id INTEGER,
        used_at TIMESTAMP
    )""")
    # Таблица выполненных квестов
    c.execute("""CREATE TABLE IF NOT EXISTS quests_completed (
        user_id INTEGER,
        quest_id INTEGER,
        completed_at TIMESTAMP,
        PRIMARY KEY (user_id, quest_id)
    )""")
    conn.commit()
    conn.close()
    logger.info("База данных инициализирована.")


def get_user(user_id):
    try:
        conn = sqlite3.connect(DB_NAME)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (user_id,))
        conn.commit()
        c.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        user = c.fetchone()
        conn.close()
        return user
    except Exception as e:
        logger.error(f"Ошибка get_user: {e}")
        return None


def update_balance(user_id, amount):
    try:
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        c.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (amount, user_id))
        conn.commit()
        c.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
        row = c.fetchone()
        conn.close()
        if row:
            return row[0]
        return None
    except Exception as e:
        logger.error(f"Ошибка update_balance: {e}")
        return None


def update_stats(user_id, game_type, won, amount_won):
    """Обновляет статистику игрока и проверяет квесты."""
    try:
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()

        # Получаем текущую статистику
        c.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        user = c.fetchone()
        if not user:
            conn.close()
            return

        col_names = [desc[0] for desc in c.description]
        stats = dict(zip(col_names, user))

        # Обновляем общую статистику
        total_games = stats.get("total_games", 0) + 1
        total_won = stats.get("total_won", 0) + (amount_won if won else 0)
        wins = stats.get("wins", 0) + (1 if won else 0)
        losses = stats.get("losses", 0) + (0 if won else 1)
        biggest_win = max(stats.get("biggest_win", 0), amount_won if won else 0)

        # Серия побед
        current_streak = stats.get("current_streak", 0)
        if won:
            current_streak += 1
        else:
            current_streak = 0
        max_win_streak = max(stats.get("max_win_streak", 0), current_streak)

        # Игры по типам
        games_played_str = stats.get("games_played", "") or ""
        if game_type not in games_played_str:
            games_played_str = (games_played_str + "," + game_type).strip(",")

        updates = {
            "total_games": total_games,
            "total_won": total_won,
            "wins": wins,
            "losses": losses,
            "biggest_win": biggest_win,
            "current_streak": current_streak,
            "max_win_streak": max_win_streak,
            "games_played": games_played_str,
        }

        # Специфичная статистика по играм
        if game_type == "roulette":
            updates["roulette_plays"] = stats.get("roulette_plays", 0) + 1
        elif game_type == "blackjack":
            updates["blackjack_plays"] = stats.get("blackjack_plays", 0) + 1
            if won:
                updates["blackjack_wins"] = stats.get("blackjack_wins", 0) + 1
        elif game_type == "slots":
            updates["slots_plays"] = stats.get("slots_plays", 0) + 1
        elif game_type == "card":
            updates["card_plays"] = stats.get("card_plays", 0) + 1
        elif game_type == "coin":
            updates["coin_plays"] = stats.get("coin_plays", 0) + 1
            if won:
                updates["coin_wins"] = stats.get("coin_wins", 0) + 1

        # Собираем SET-запрос
        set_clause = ", ".join([f"{k} = ?" for k in updates.keys()])
        values = list(updates.values()) + [user_id]
        c.execute(f"UPDATE users SET {set_clause} WHERE user_id = ?", values)
        conn.commit()

        # Обновляем stats для проверки квестов
        stats.update(updates)

        # Проверяем квесты
        c.execute("SELECT quest_id FROM quests_completed WHERE user_id = ?", (user_id,))
        completed_rows = c.fetchall()
        completed_ids = set(row[0] for row in completed_rows)

        for quest in QUESTS:
            if quest["id"] not in completed_ids and quest["check"](stats):
                # Квест выполнен!
                c.execute(
                    "INSERT OR IGNORE INTO quests_completed (user_id, quest_id, completed_at) VALUES (?, ?, ?)",
                    (user_id, quest["id"], datetime.now().isoformat())
                )
                c.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (quest["reward"], user_id))
                conn.commit()
                logger.info(f"Квест #{quest['id']} выполнен пользователем {user_id}. Награда: {quest['reward']} AceCoin.")
        conn.close()
    except Exception as e:
        logger.error(f"Ошибка update_stats: {e}")


def mark_slots_result(user_id, is_match, is_jackpot):
    """Отмечает результат слотов."""
    try:
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        if is_jackpot:
            c.execute("UPDATE users SET slots_jackpot = slots_jackpot + 1 WHERE user_id = ?", (user_id,))
        if is_match:
            c.execute("UPDATE users SET slots_match = slots_match + 1 WHERE user_id = ?", (user_id,))
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"Ошибка mark_slots_result: {e}")


def mark_natural_blackjack(user_id):
    try:
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        c.execute("UPDATE users SET natural_blackjacks = natural_blackjacks + 1 WHERE user_id = ?", (user_id,))
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"Ошибка mark_natural_blackjack: {e}")


def check_bonus_available(user_id):
    try:
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        c.execute("SELECT last_bonus FROM users WHERE user_id = ?", (user_id,))
        row = c.fetchone()
        conn.close()
        if not row or not row[0]:
            return True
        last_bonus_str = row[0]
        if not isinstance(last_bonus_str, str):
            return True
        now = datetime.now()
        try:
            last_bonus = datetime.fromisoformat(last_bonus_str)
            if (now - last_bonus) >= timedelta(hours=24):
                return True
        except (ValueError, TypeError):
            return True
        return False
    except Exception as e:
        logger.error(f"Ошибка check_bonus_available: {e}")
        return True


def give_bonus_logic(user_id):
    try:
        now = datetime.now()
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        c.execute("UPDATE users SET balance = balance + 200 WHERE user_id = ?", (user_id,))
        c.execute("UPDATE users SET last_bonus = ? WHERE user_id = ?", (now.isoformat(), user_id))
        c.execute("UPDATE users SET bonus_claimed = bonus_claimed + 1 WHERE user_id = ?", (user_id,))
        conn.commit()
        c.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
        new_bal = c.fetchone()
        conn.close()

        # Проверяем квесты после получения бонуса
        stats = get_user_stats_raw(user_id)
        if stats:
            stats["bonus_claimed"] = stats.get("bonus_claimed", 0) + 1
            check_quests(user_id, stats)

        return new_bal[0] if new_bal else None
    except Exception as e:
        logger.error(f"Ошибка give_bonus_logic: {e}")
        return None


def get_user_stats_raw(user_id):
    """Получает сырую статистику из БД для проверки квестов."""
    try:
        conn = sqlite3.connect(DB_NAME)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        user = c.fetchone()
        conn.close()
        if user:
            return dict(user)
        return None
    except Exception as e:
        logger.error(f"Ошибка get_user_stats_raw: {e}")
        return None


def check_quests(user_id, stats):
    """Проверяет и завершает квесты на основе статистики."""
    try:
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        c.execute("SELECT quest_id FROM quests_completed WHERE user_id = ?", (user_id,))
        completed_rows = c.fetchall()
        completed_ids = set(row[0] for row in completed_rows)

        for quest in QUESTS:
            if quest["id"] not in completed_ids and quest["check"](stats):
                c.execute(
                    "INSERT OR IGNORE INTO quests_completed (user_id, quest_id, completed_at) VALUES (?, ?, ?)",
                    (user_id, quest["id"], datetime.now().isoformat())
                )
                c.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (quest["reward"], user_id))
                conn.commit()
                logger.info(f"Квест #{quest['id']} выполнен пользователем {user_id}. Награда: {quest['reward']} AceCoin.")
        conn.close()
    except Exception as e:
        logger.error(f"Ошибка check_quests: {e}")


def hand_value(hand):
    value = 0
    aces = sum(1 for c in hand if c == 1)
    for c in hand:
        if c == 1:
            value += 11
        elif c > 10:
            value += 10
        else:
            value += c
    while value > 21 and aces > 0:
        value -= 10
        aces -= 1
    return value


async def send_animation(update, file_id):
    if not file_id:
        return
    try:
        await update.effective_chat.send_video(
            video=file_id,
            supports_streaming=True,
        )
        logger.info(f"✅ Анимация {file_id[:10]}... успешно отправлена.")
    except Exception as e:
        logger.error(f"❌ Не удалось отправить анимацию {file_id[:10]}... Ошибка: {e}")


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"Необработанная ошибка: {context.error}")


async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user = get_user(update.effective_user.id)
        if not user:
            await update.message.reply_text("Ошибка профиля.")
            return
        keyboard = []
        if check_bonus_available(update.effective_user.id):
            keyboard.append([InlineKeyboardButton("🎁 Забрать бонус 200 AceCoin", callback_data="get_bonus")])
        reply_markup = InlineKeyboardMarkup(keyboard) if keyboard else None
        text = (
            f"Привет, {update.effective_user.first_name}!\n"
            f"Твой баланс: {user['balance']} AceCoin.\n\n"
            f"Быстрые команды:\n"
            f"💵 б — баланс\n"
            f"🎰 рулетка (ставка) цвет\n"
            f"🃏 блекджек (ставка)\n"
            f"🎲 слоты (ставка)\n"
            f"🃟 карта (ставка) выше/ниже\n"
            f"🪙 монетка (ставка) орел/решка\n"
            f"💱 п (сумма) — перевод (ответом на сообщение)\n"
            f"🎁 промокод (начинается с #)\n"
            f"📋 кв — квесты\n"
            f"🆔 id — твой ID"
        )
        await update.message.reply_text(text, reply_markup=reply_markup)
    except Exception as e:
        logger.error(f"Ошибка start_cmd: {e}")


async def balance_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user = get_user(update.effective_user.id)
        if not user:
            await update.message.reply_text("Ошибка профиля.")
            return
        keyboard = []
        if check_bonus_available(update.effective_user.id):
            keyboard.append([InlineKeyboardButton("🎁 Забрать бонус 200 AceCoin", callback_data="get_bonus")])
        reply_markup = InlineKeyboardMarkup(keyboard) if keyboard else None
        text = f"💰 Твой баланс: {user['balance']} AceCoin."
        if not check_bonus_available(update.effective_user.id):
            text += "\n⏳ Бонус уже получен, жди 24 часа."
        await update.message.reply_text(text, reply_markup=reply_markup)
    except Exception as e:
        logger.error(f"Ошибка balance_cmd: {e}")


async def bonus_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user_id = update.effective_user.id
        if check_bonus_available(user_id):
            new_bal = give_bonus_logic(user_id)
            await update.message.reply_text(f"🎁 Бонус 200 AceCoin начислен! Новый баланс: {new_bal}")
        else:
            await update.message.reply_text("⏳ Бонус уже получен. Подожди 24 часа.")
    except Exception as e:
        logger.error(f"Ошибка bonus_cmd: {e}")


async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        query = update.callback_query
        await query.answer()
        if query.data == "get_bonus":
            user_id = query.from_user.id
            if check_bonus_available(user_id):
                new_bal = give_bonus_logic(user_id)
                await query.edit_message_text(f"🎁 Бонус 200 AceCoin начислен! Новый баланс: {new_bal}")
            else:
                await query.answer("Бонус уже получен!", show_alert=True)
    except Exception as e:
        logger.error(f"Ошибка handle_callback: {e}")


async def transfer_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if not update.message or not update.message.text:
            return

        # Проверяем, ответил ли пользователь на сообщение
        if not update.message.reply_to_message:
            await update.message.reply_text(
                "💱 Перевод AceCoin:\n"
                "Ответь на сообщение игрока и напиши:\n"
                "/п <сумма>\n\n"
                "Пример: /п 500"
            )
            return

        msg = update.message.text.split()
        if len(msg) < 2:
            await update.message.reply_text("❌ Укажи сумму. Пример: /п 500")
            return

        amount = int(msg[1])
    except ValueError:
        await update.message.reply_text("❌ Сумма должна быть числом. Пример: /п 500")
        return
    except Exception as e:
        logger.error(f"Ошибка transfer_cmd (парсинг): {e}")
        return

    try:
        sender_id = update.effective_user.id
        target_id = update.message.reply_to_message.from_user.id

        if amount <= 0:
            await update.message.reply_text("❌ Сумма должна быть больше нуля.")
            return

        if target_id == sender_id:
            await update.message.reply_text("❌ Нельзя переводить самому себе.")
            return

        if target_id == context.bot.id:
            await update.message.reply_text("❌ Нельзя переводить боту.")
            return

        sender = get_user(sender_id)
        if not sender or sender["balance"] < amount:
            await update.message.reply_text(f"❌ Недостаточно AceCoin. Твой баланс: {sender['balance'] if sender else 0}")
            return

        receiver = get_user(target_id)
        if not receiver:
            await update.message.reply_text("❌ Не удалось найти получателя.")
            return

        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        c.execute("UPDATE users SET balance = balance - ? WHERE user_id = ?", (amount, sender_id))
        c.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (amount, target_id))
        conn.commit()
        c.execute("SELECT balance FROM users WHERE user_id = ?", (sender_id,))
        sender_new = c.fetchone()
        conn.close()

        sender_bal = sender_new[0] if sender_new else 0
        target_name = update.message.reply_to_message.from_user.first_name or "Игрок"

        await update.message.reply_text(
            f"✅ Перевод выполнен!\n"
            f"Получатель: {target_name}\n"
            f"Сумма: {amount} AceCoin\n"
            f"Твой остаток: {sender_bal} AceCoin"
        )

        # Уведомляем получателя
        try:
            await context.bot.send_message(
                chat_id=target_id,
                text=f"💱 Тебе перевели {amount} AceCoin!\nТвой новый баланс: {receiver['balance'] + amount} AceCoin"
            )
        except Exception:
            pass

    except Exception as e:
        logger.error(f"Ошибка transfer_cmd: {e}")
        try:
            await update.message.reply_text("⚠️ Произошла ошибка при переводе.")
        except:
            pass


async def id_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        await update.message.reply_text(f"🆔 Твой ID: {update.effective_user.id}")
    except Exception as e:
        logger.error(f"Ошибка id_cmd: {e}")


async def promocode_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает сообщения, начинающиеся с # — промокоды."""
    try:
        if not update.message or not update.message.text:
            return

        text = update.message.text.strip().upper()
        # Проверяем, есть ли такой промокод
        if text not in PROMOCODES:
            await update.message.reply_text("❌ Неверный промокод.")
            return

        user_id = update.effective_user.id

        # Проверяем, использован ли промокод
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        c.execute("SELECT user_id, used_at FROM promocodes_used WHERE code = ?", (text,))
        row = c.fetchone()

        if row:
            used_by = row[0]
            used_at_str = row[1]
            try:
                used_at = datetime.fromisoformat(used_at_str)
                formatted = used_at.strftime("%d.%m.%Y %H:%M")
            except (ValueError, TypeError):
                formatted = "ранее"
            conn.close()
            await update.message.reply_text(f"❌ Промокод уже использован ({formatted}).")
            return

        # Промокод свободен — начисляем
        min_reward, max_reward = PROMOCODES[text]
        reward = random.randint(min_reward, max_reward)

        c.execute("INSERT INTO promocodes_used (code, user_id, used_at) VALUES (?, ?, ?)", (text, user_id, datetime.now().isoformat()))
        c.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (reward, user_id))
        conn.commit()
        c.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
        new_bal_row = c.fetchone()
        conn.close()

        new_bal = new_bal_row[0] if new_bal_row else 0
        await update.message.reply_text(f"🎁 Промокод активирован!\nТы получил {reward} AceCoin!\nНовый баланс: {new_bal} AceCoin")
    except Exception as e:
        logger.error(f"Ошибка promocode_handler: {e}")
        try:
            await update.message.reply_text("⚠️ Ошибка при активации промокода.")
        except:
            pass


async def quests_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user_id = update.effective_user.id
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        c.execute("SELECT quest_id FROM quests_completed WHERE user_id = ?", (user_id,))
        completed_rows = c.fetchall()
        completed_ids = set(row[0] for row in completed_rows)
        conn.close()

        text = "📋 Твои квесты:\n\n"
        for quest in QUESTS:
            status = "✅" if quest["id"] in completed_ids else "❌"
            text += f"{status} #{quest['id']}. {quest['desc']} — +{quest['reward']} AceCoin\n"

        completed_count = len(completed_ids)
        text += f"\nВыполнено: {completed_count}/{len(QUESTS)}"

        await update.message.reply_text(text)
    except Exception as e:
        logger.error(f"Ошибка quests_cmd: {e}")
        try:
            await update.message.reply_text("⚠️ Ошибка при загрузке квестов.")
        except:
            pass


async def roulette_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if not update.message or not update.message.text:
            return
        msg = update.message.text.split()
        if len(msg) < 3:
            await update.message.reply_text("Рулетка: поставь ставку и выбери вариант.\nПример: /рулетка 100 красный")
            return
        bet = int(msg[1])
        if bet <= 0:
            await update.message.reply_text("❌ Ставка должна быть больше нуля.")
            return
    except ValueError:
        await update.message.reply_text("❌ Ставка должна быть числом.")
        return
    except Exception as e:
        logger.error(f"Ошибка roulette_cmd (парсинг): {e}")
        return

    try:
        user = get_user(update.effective_user.id)
        if not user or user["balance"] < bet:
            await update.message.reply_text("❌ Недостаточно AceCoin!")
            return
        target = " ".join(msg[2:]).lower()
        await send_animation(update, ANIMATION_ROULETTE)
        await update.message.reply_text("🌀 Крутим колесо…")
        number = random.randint(0, 36)
        red_numbers = [1, 3, 5, 7, 9, 12, 14, 16, 18, 19, 21, 23, 25, 27, 30, 32, 34, 36]
        color = "green" if number == 0 else ("red" if number in red_numbers else "black")
        color_map = {"красный": "red", "чёрный": "black", "черный": "black"}
        check_color = color_map.get(target, target)
        win = False
        payout = 0
        if check_color == "red" and color == "red":
            win = True
            payout = 2
        elif check_color == "black" and color == "black":
            win = True
            payout = 2
        elif target in ["even", "чётное", "четное"] and number != 0 and number % 2 == 0:
            win = True
            payout = 2
        elif target in ["odd", "нечётное", "нечетное"] and number != 0 and number % 2 != 0:
            win = True
            payout = 2
        elif target.isdigit() and int(target) == number:
            win = True
            payout = 36
        result_text = f"🎱 Выпало: {number} ({color})\n"
        if win:
            winnings = bet * (payout - 1)
            update_balance(update.effective_user.id, winnings)
            result_text += f"🎉 Победа! Ты выиграл {winnings} AceCoin."
            update_stats(update.effective_user.id, "roulette", True, winnings)
        else:
            update_balance(update.effective_user.id, -bet)
            result_text += "😞 Проигрыш. Попробуй снова!"
            update_stats(update.effective_user.id, "roulette", False, 0)
        await update.message.reply_text(result_text)
    except Exception as e:
        logger.error(f"Ошибка roulette_cmd: {e}")
        try:
            await update.message.reply_text("⚠️ Произошла ошибка. Попробуй ещё раз.")
        except:
            pass


async def blackjack_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if not update.message or not update.message.text:
            return
        msg = update.message.text.split()
        if len(msg) < 2:
            await update.message.reply_text("🃏 Блэкджек: укажи ставку.\nПример: /блекджек 100")
            return
        bet = int(msg[1])
        if bet <= 0:
            await update.message.reply_text("❌ Ставка должна быть больше нуля.")
            return
    except ValueError:
        await update.message.reply_text("❌ Ставка должна быть числом.")
        return
    except Exception as e:
        logger.error(f"Ошибка blackjack_cmd (парсинг): {e}")
        return

    try:
        user = get_user(update.effective_user.id)
        if not user or user["balance"] < bet:
            await update.message.reply_text("💸 Не хватает AceCoin.")
            return
        await send_animation(update, STICKER_BLACKJACK)
        await update.message.reply_text("🃏 Раздаем карты...")
        deck = [i for i in range(1, 14)] * 4
        random.shuffle(deck)
        player_hand = [deck.pop(), deck.pop()]
        dealer_hand = [deck.pop(), deck.pop()]
        p_val = hand_value(player_hand)
        if p_val == 21:
            winnings = int(bet * 1.5)
            update_balance(update.effective_user.id, winnings)
            mark_natural_blackjack(update.effective_user.id)
            update_stats(update.effective_user.id, "blackjack", True, winnings)
            await update.message.reply_text(f"🃏 Натуральный блэкджек! Ты получил {winnings} AceCoin!")
            return
        p_hand_str = ",".join(map(str, player_hand))
        d_first_str = str(dealer_hand[0])
        keyboard = [
            [InlineKeyboardButton("🃏 Ещё карту", callback_data=f"bj_hit_{bet}_{p_hand_str}_{d_first_str}")],
            [InlineKeyboardButton("✋ Хватит", callback_data=f"bj_stand_{bet}_{p_hand_str}_{d_first_str}")],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(
            f"🃏 Твои карты: {player_hand} (сумма: {p_val})\nДилер: [{dealer_hand[0]}, ?]\nВыбери действие:",
            reply_markup=reply_markup,
        )
    except Exception as e:
        logger.error(f"Ошибка blackjack_cmd: {e}")
        try:
            await update.message.reply_text("⚠️ Произошла ошибка. Попробуй ещё раз.")
        except:
            pass


async def handle_blackjack_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        query = update.callback_query
        await query.answer()
        data = query.data.split("_")
        if len(data) < 5:
            await query.edit_message_text("❌ Ошибка сессии.")
            return
        action = data[1]
        bet = int(data[2])
        p_hand_str = data[3]
        d_first_str = data[4]
        player_hand = list(map(int, p_hand_str.split(",")))
        dealer_first = int(d_first_str)
    except (ValueError, IndexError):
        try:
            await query.edit_message_text("❌ Ошибка данных.")
        except:
            pass
        return
    except Exception as e:
        logger.error(f"Ошибка handle_blackjack_callback (парсинг): {e}")
        return

    try:
        user_id = update.effective_user.id
        deck = [i for i in range(1, 14)] * 4
        for card in player_hand:
            if card in deck:
                deck.remove(card)
        if dealer_first in deck:
            deck.remove(dealer_first)
        random.shuffle(deck)
        dealer_hand = [dealer_first, deck.pop()]
        if action == "hit":
            new_card = deck.pop()
            player_hand.append(new_card)
            p_val = hand_value(player_hand)
            if p_val > 21:
                update_balance(user_id, -bet)
                update_stats(user_id, "blackjack", False, 0)
                await query.edit_message_text(f"🃏 Перебор ({p_val})! Ты потерял {bet} AceCoin.")
                return
            p_hand_str_new = ",".join(map(str, player_hand))
            keyboard = [
                [InlineKeyboardButton("🃏 Ещё карту", callback_data=f"bj_hit_{bet}_{p_hand_str_new}_{d_first_str}")],
                [InlineKeyboardButton("✋ Хватит", callback_data=f"bj_stand_{bet}_{p_hand_str_new}_{d_first_str}")],
            ]
            await query.edit_message_text(
                f"🃏 Твоя сумма: {p_val}. Дилер: [{dealer_first}, ?]\nЧто делаешь?",
                reply_markup=InlineKeyboardMarkup(keyboard),
            )
            return
        while hand_value(dealer_hand) < 17:
            if not deck:
                break
            dealer_hand.append(deck.pop())
        d_val = hand_value(dealer_hand)
        p_val = hand_value(player_hand)
        msg = f"🃏 Дилер: {dealer_hand} (сумма: {d_val})\nТы: {player_hand} (сумма: {p_val})\n\n"
        if p_val > 21:
            msg += "😞 Перебор — проигрыш."
            update_balance(user_id, -bet)
            update_stats(user_id, "blackjack", False, 0)
        elif d_val > 21 or p_val > d_val:
            winnings = bet
            msg += f"🎉 Победа! +{winnings} AceCoin."
            update_balance(user_id, winnings)
            update_stats(user_id, "blackjack", True, winnings)
        elif p_val < d_val:
            msg += "😞 Дилер выиграл."
            update_balance(user_id, -bet)
            update_stats(user_id, "blackjack", False, 0)
        else:
            msg += "🤝 Ничья — ставка возвращена."
        await query.edit_message_text(msg)
    except Exception as e:
        logger.error(f"Ошибка handle_blackjack_callback: {e}")
        try:
            await query.edit_message_text("⚠️ Произошла ошибка. Начни новую игру.")
        except:
            pass


async def slots_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if not update.message or not update.message.text:
            return
        msg = update.message.text.split()
        if len(msg) < 2:
            await update.message.reply_text("🎲 Слоты: поставь ставку.\nПример: /слоты 50")
            return
        bet = int(msg[1])
        if bet <= 0:
            await update.message.reply_text("❌ Ставка должна быть больше нуля.")
            return
    except ValueError:
        await update.message.reply_text("❌ Ставка должна быть числом.")
        return
    except Exception as e:
        logger.error(f"Ошибка slots_cmd (парсинг): {e}")
        return

    try:
        user = get_user(update.effective_user.id)
        if not user or user["balance"] < bet:
            await update.message.reply_text("💸 Мало AceCoin.")
            return
        await send_animation(update, ANIMATION_SLOTS)
        await update.message.reply_text("🎰 Барабаны крутятся...")
        symbols = ["🍒", "🍋", "🔔", "⭐", "💎", "7️⃣"]
        reels = [random.choice(symbols) for _ in range(3)]
        payout_map = {"🍒": 3, "🍋": 4, "🔔": 5, "⭐": 10, "💎": 20, "7️⃣": 50}
        winnings = 0
        is_match = False
        is_jackpot = False
        if reels[0] == reels[1] == reels[2]:
            winnings = bet * payout_map[reels[0]]
            is_match = True
            if reels[0] == "7️⃣":
                is_jackpot = True
        elif reels[0] == reels[1] or reels[1] == reels[2] or reels[0] == reels[2]:
            winnings = bet
            is_match = True
        net = winnings - bet
        update_balance(update.effective_user.id, net)
        mark_slots_result(update.effective_user.id, is_match, is_jackpot)
        if net > 0:
            update_stats(update.effective_user.id, "slots", True, net)
        else:
            update_stats(update.effective_user.id, "slots", False, 0)
        text = f"🎲 {reels[0]} {reels[1]} {reels[2]}\n"
        if net > 0:
            text += f"🎉 Выигрыш: {net} AceCoin!"
            if is_jackpot:
                text += " 🎰 ДЖЕКПОТ!"
        elif net == 0:
            text += "🤝 Возврат ставки."
        else:
            text += "😞 Проигрыш."
        await update.message.reply_text(text)
    except Exception as e:
        logger.error(f"Ошибка slots_cmd: {e}")
        try:
            await update.message.reply_text("⚠️ Произошла ошибка. Попробуй ещё раз.")
        except:
            pass


async def card_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if not update.message or not update.message.text:
            return
        msg = update.message.text.split()
        if len(msg) < 3:
            await update.message.reply_text("🃟 Карта выше/ниже: укажи ставку и выбор.\nПример: /карта 100 выше")
            return
        bet = int(msg[1])
        choice = msg[2].lower()
        if bet <= 0:
            await update.message.reply_text("❌ Ставка должна быть больше нуля.")
            return
    except ValueError:
        await update.message.reply_text("❌ Неверный формат.")
        return
    except Exception as e:
        logger.error(f"Ошибка card_cmd (парсинг): {e}")
        return

    try:
        user = get_user(update.effective_user.id)
        if not user or user["balance"] < bet:
            await update.message.reply_text("💸 Нет AceCoin.")
            return
        await send_animation(update, STICKER_CARD)
        await update.message.reply_text("🃟 Тянем карту...")
        cards = list(range(2, 15))
        random.shuffle(cards)
        current = cards.pop()
        next_card = cards.pop()
        won = (choice == "выше" and next_card > current) or (choice == "ниже" and next_card < current)
        multiplier = 1.8
        if won:
            winnings = int(bet * (multiplier - 1))
            update_balance(update.effective_user.id, winnings)
            update_stats(update.effective_user.id, "card", True, winnings)
            await update.message.reply_text(f"🃟 Текущая: {current}, следующая: {next_card}\n🎉 Ты угадал! +{winnings} AceCoin.")
        else:
            update_balance(update.effective_user.id, -bet)
            update_stats(update.effective_user.id, "card", False, 0)
            await update.message.reply_text(f"🃟 Текущая: {current}, следующая: {next_card}\n😞 Не угадал. -{bet} AceCoin.")
    except Exception as e:
        logger.error(f"Ошибка card_cmd: {e}")
        try:
            await update.message.reply_text("⚠️ Произошла ошибка. Попробуй ещё раз.")
        except:
            pass


async def coin_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if not update.message or not update.message.text:
            return
        msg = update.message.text.split()
        if len(msg) < 3:
            await update.message.reply_text("🪙 Монетка: ставка и сторона.\nПример: /монетка 100 орел")
            return
        bet = int(msg[1])
        choice = msg[2].lower()
        if bet <= 0:
            await update.message.reply_text("❌ Ставка должна быть больше нуля.")
            return
    except ValueError:
        await update.message.reply_text("❌ Ошибка формата.")
        return
    except Exception as e:
        logger.error(f"Ошибка coin_cmd (парсинг): {e}")
        return

    try:
        user = get_user(update.effective_user.id)
        if not user or user["balance"] < bet:
            await update.message.reply_text("💸 Нет AceCoin.")
            return
        await send_animation(update, ANIMATION_COIN)
        await update.message.reply_text("🪙 Монетка летит...")
        side = random.choice(["орел", "решка"])
        if choice == side:
            winnings = int(bet * 0.8)
            update_balance(update.effective_user.id, winnings)
            update_stats(update.effective_user.id, "coin", True, winnings)
            await update.message.reply_text(f"🪙 Выпало: {side}\n🎉 Победа! Ты выиграл {winnings} AceCoin.")
        else:
            update_balance(update.effective_user.id, -bet)
            update_stats(update.effective_user.id, "coin", False, 0)
            await update.message.reply_text(f"🪙 Выпало: {side}\n😞 Проигрыш. Ты потерял {bet} AceCoin.")
    except Exception as e:
        logger.error(f"Ошибка coin_cmd: {e}")
        try:
            await update.message.reply_text("⚠️ Произошла ошибка. Попробуй ещё раз.")
        except:
            pass


async def give_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user_id = update.effective_user.id
        if user_id != ADMIN_ID:
            await update.message.reply_text("❌ У тебя нет прав на эту команду.")
            return
        msg = update.message.text.split()
        if len(msg) < 2:
            await update.message.reply_text("Используй: /give 10000")
            return
        amount = int(msg[1])
        new_bal = update_balance(user_id, amount)
        if new_bal is not None:
            await update.message.reply_text(f"✅ Начислено {amount} AceCoin. Новый баланс: {new_bal}")
    except ValueError:
        await update.message.reply_text("Число должно быть целым.")
    except Exception as e:
        logger.error(f"Ошибка give_cmd: {e}")


def main():
    token = os.getenv("BOT_TOKEN")
    if not token:
        logger.error("КРИТИЧЕСКАЯ ОШИБКА: Переменная BOT_TOKEN пуста!")
        return

    application = ApplicationBuilder().token(token).build()

    # Латинские команды
    application.add_handler(CommandHandler("start", start_cmd))
    application.add_handler(CommandHandler("balance", balance_cmd))
    application.add_handler(CommandHandler("roulette", roulette_cmd))
    application.add_handler(CommandHandler("blackjack", blackjack_cmd))
    application.add_handler(CommandHandler("slots", slots_cmd))
    application.add_handler(CommandHandler("card", card_cmd))
    application.add_handler(CommandHandler("coin", coin_cmd))
    application.add_handler(CommandHandler("bonus", bonus_cmd))
    application.add_handler(CommandHandler("give", give_cmd))
    application.add_handler(CommandHandler("transfer", transfer_cmd))
    application.add_handler(CommandHandler("id", id_cmd))
    application.add_handler(CommandHandler("quests", quests_cmd))

    # Кириллические команды
    application.add_handler(MessageHandler(filters.Regex(r'^/б($|\s)'), balance_cmd))
    application.add_handler(MessageHandler(filters.Regex(r'^/п($|\s)'), transfer_cmd))
    application.add_handler(MessageHandler(filters.Regex(r'^/рулетка($|\s)'), roulette_cmd))
    application.add_handler(MessageHandler(filters.Regex(r'^/блекджек($|\s)'), blackjack_cmd))
    application.add_handler(MessageHandler(filters.Regex(r'^/слоты($|\s)'), slots_cmd))
    application.add_handler(MessageHandler(filters.Regex(r'^/карта($|\s)'), card_cmd))
    application.add_handler(MessageHandler(filters.Regex(r'^/монетка($|\s)'), coin_cmd))
    application.add_handler(MessageHandler(filters.Regex(r'^/кв($|\s)'), quests_cmd))

    # Промокоды (любое сообщение, начинающееся с #)
    application.add_handler(MessageHandler(filters.Regex(r'^#'), promocode_handler))

    # Кнопки
    application.add_handler(CallbackQueryHandler(handle_callback, pattern="^get_bonus$"))
    application.add_handler(CallbackQueryHandler(handle_blackjack_callback, pattern="^bj_"))

    # Глобальный обработчик ошибок
    application.add_error_handler(error_handler)

    logger.info("🚀 Бот запускается...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    init_db()
    main()
