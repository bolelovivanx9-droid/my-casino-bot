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

# ID анимаций
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
    {"id": 1, "desc": "Сыграй первую игру", "reward": 200, "check": lambda s: s["total_games"] >= 1},
    {"id": 2, "desc": "Получи ежедневный бонус", "reward": 300, "check": lambda s: s["bonus_claimed"] >= 1},
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
    {"id": 13, "desc": "Победи 50 раз", "reward": 5000, "check": lambda s: s["wins"] >= 50},
    {"id": 14, "desc": "Выиграй 10000 AceCoin за одну ставку", "reward": 10000, "check": lambda s: s["biggest_win"] >= 10000},
    {"id": 15, "desc": "Три 7\uufe0f\u20e3 в слотах", "reward": 15000, "check": lambda s: s["slots_jackpot"] >= 1},
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
        ("username", "TEXT DEFAULT ''"),
    ]
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    for col_name, col_def in migrate_columns:
        try:
            c.execute(f"ALTER TABLE users ADD COLUMN {col_name} {col_def}")
        except sqlite3.OperationalError:
            pass

    c.execute("""CREATE TABLE IF NOT EXISTS promocodes_used (
        code TEXT PRIMARY KEY,
        user_id INTEGER,
        used_at TIMESTAMP
    )""")
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
        logger.error(f"get_user: {e}")
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
        logger.error(f"update_balance: {e}")
        return None


def update_stats(user_id, game_type, won, amount_won):
    try:
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        c.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        user = c.fetchone()
        if not user:
            conn.close()
            return
        col_names = [desc[0] for desc in c.description]
        stats = dict(zip(col_names, user))

        total_games = stats.get("total_games", 0) + 1
        total_won = stats.get("total_won", 0) + (amount_won if won else 0)
        wins = stats.get("wins", 0) + (1 if won else 0)
        losses = stats.get("losses", 0) + (0 if won else 1)
        biggest_win = max(stats.get("biggest_win", 0), amount_won if won else 0)
        current_streak = stats.get("current_streak", 0) + 1 if won else 0
        max_win_streak = max(stats.get("max_win_streak", 0), current_streak)
        games_played_str = stats.get("games_played", "") or ""
        if game_type not in games_played_str:
            games_played_str = (games_played_str + "," + game_type).strip(",")

        updates = {
            "total_games": total_games, "total_won": total_won, "wins": wins,
            "losses": losses, "biggest_win": biggest_win,
            "current_streak": current_streak, "max_win_streak": max_win_streak,
            "games_played": games_played_str,
        }
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

        set_clause = ", ".join([f"{k} = ?" for k in updates.keys()])
        values = list(updates.values()) + [user_id]
        c.execute(f"UPDATE users SET {set_clause} WHERE user_id = ?", values)
        conn.commit()
        stats.update(updates)

        c.execute("SELECT quest_id FROM quests_completed WHERE user_id = ?", (user_id,))
        completed_ids = set(row[0] for row in c.fetchall())
        for quest in QUESTS:
            if quest["id"] not in completed_ids and quest["check"](stats):
                c.execute("INSERT OR IGNORE INTO quests_completed (user_id, quest_id, completed_at) VALUES (?, ?, ?)",
                          (user_id, quest["id"], datetime.now().isoformat()))
                c.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (quest["reward"], user_id))
                conn.commit()
                logger.info(f"Quest #{quest['id']} completed by {user_id}. Reward: {quest['reward']}")
        conn.close()
    except Exception as e:
        logger.error(f"update_stats: {e}")


def mark_slots_result(user_id, is_match, is_jackpot):
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
        logger.error(f"mark_slots_result: {e}")


def mark_natural_blackjack(user_id):
    try:
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        c.execute("UPDATE users SET natural_blackjacks = natural_blackjacks + 1 WHERE user_id = ?", (user_id,))
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"mark_natural_blackjack: {e}")


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
        logger.error(f"check_bonus_available: {e}")
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
        stats = get_user_stats_raw(user_id)
        if stats:
            stats["bonus_claimed"] = stats.get("bonus_claimed", 0) + 1
            check_quests(user_id, stats)
        return new_bal[0] if new_bal else None
    except Exception as e:
        logger.error(f"give_bonus_logic: {e}")
        return None


def get_user_stats_raw(user_id):
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
        logger.error(f"get_user_stats_raw: {e}")
        return None


def check_quests(user_id, stats):
    try:
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        c.execute("SELECT quest_id FROM quests_completed WHERE user_id = ?", (user_id,))
        completed_ids = set(row[0] for row in c.fetchall())
        for quest in QUESTS:
            if quest["id"] not in completed_ids and quest["check"](stats):
                c.execute("INSERT OR IGNORE INTO quests_completed (user_id, quest_id, completed_at) VALUES (?, ?, ?)",
                          (user_id, quest["id"], datetime.now().isoformat()))
                c.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (quest["reward"], user_id))
                conn.commit()
                logger.info(f"Quest #{quest['id']} completed by {user_id}. Reward: {quest['reward']}")
        conn.close()
    except Exception as e:
        logger.error(f"check_quests: {e}")


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
        await update.effective_chat.send_video(video=file_id, supports_streaming=True)
        logger.info(f"Animation {file_id[:10]}... sent.")
    except Exception as e:
        logger.error(f"Animation error: {e}")


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"Unhandled error: {context.error}")


# ========== START ==========
async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user_id = update.effective_user.id
        user = get_user(user_id)
        if not user:
            await update.message.reply_text("Error profile.")
            return

        name = update.effective_user.first_name or "Player"
        balance = user['balance']

        # Сохраняем username
        try:
            uname = update.effective_user.username or ""
            conn = sqlite3.connect(DB_NAME)
            c = conn.cursor()
            c.execute("UPDATE users SET username = ? WHERE user_id = ?", (uname, user_id))
            conn.commit()
            conn.close()
        except:
            pass

        has_bonus = check_bonus_available(user_id)
        keyboard = []
        if has_bonus:
            keyboard.append([InlineKeyboardButton("Gift Daily Bonus 200 AceCoin", callback_data="get_bonus")])
        keyboard.append([
            InlineKeyboardButton("Help", callback_data="help_main"),
            InlineKeyboardButton("Quests", callback_data="quests_list"),
            InlineKeyboardButton("Top", callback_data="leaderboard"),
        ])
        reply_markup = InlineKeyboardMarkup(keyboard)

        text = (
            f"\U0001f525 <b>  Ace Casino, {name}!</b> \U0001f525\n\n"
            f"\U0001f4b5 <b>:</b> <code>{balance:,}</code> AceCoin\n"
            f"\U0001f3af <b>Status:</b> Active Player\n\n"
            f"\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\n"
            f"\U0001f3b0 <b>GAMES & BETS</b>\n"
            f"\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\n"
            f"\U0001f3c0 <code>/roulette</code> - Bet on color or number (x36)\n"
            f"\U0001f0cf <code>/blackjack</code> - Beat the dealer\n"
            f"\U0001f3b2 <code>/slots</code> - Spin for the jackpot\n"
            f"\U0001f3df <code>/card</code> - Higher or lower?\n"
            f"\U0001fa99 <code>/coin</code> - Heads or tails!\n\n"
            f"\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\n"
            f"\U0001f4b8 <b>FINANCE & TRANSFERS</b>\n"
            f"\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\n"
            f"\U0001f4b1 <code>/p [amount]</code> - <b>Transfer to friend!</b>\n"
            f"   \U0001f449 Reply to a message and write /p 500\n"
            f"\U0001f194 <code>/id</code> - Your unique ID\n"
            f"\U0001f4b0 <code>/balance</code> - Quick balance check\n"
            f"\U0001f4ca <code>/stats</code> - Your statistics\n"
            f"\U0001f3c6 <code>/top</code> - Leaderboard\n\n"
            f"\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\n"
            f"\U0001f380 <b>BONUSES & QUESTS</b>\n"
            f"\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\n"
            f"\U0001f3ab Enter promocodes in chat: <code>#STARTER</code>, <code>#LUCKY777</code>\n"
            f"\U0001f5ed <code>/quests</code> - Quest list and rewards\n"
            f"\U0001f4cc Daily bonus - don't forget to claim!\n\n"
            f"\U0001f4a1 <b>Tip:</b> Start with the bonus to make your first bet risk-free!"
        )

        await update.message.reply_text(text, parse_mode='HTML', reply_markup=reply_markup)
    except Exception as e:
        logger.error(f"start_cmd: {e}")


# ========== HELP ==========
async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        text = (
            "\U0001f4d6 <b>ACE CASINO - </b>\U0001f4d6\n\n"
            f"      AceCoin -      . "
            f"      ,   ,  !\n\n"
            f"\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\n"
            f"\U0001f3b0 <b></b>\n"
            f"\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\n\n"
            f"\U0001f3c0 <b></b> <code>/roulette [bet] [target]</code>\n"
            f"   :   0  36.   :\n"
            f"   \U0001f534  -  2\n"
            f"   \U0001f7cf  -  2\n"
            f"   \U0001f7e2  -  2\n"
            f"    -  36\n"
            f"  : <code>/roulette 100 </code>\n\n"
            f"\U0001f0cf <b></b> <code>/blackjack [bet]</code>\n"
            f"    21.   :\n"
            f"   -     ( 1.5 )\n"
            f"     17\n"
            f"    -    \n"
            f"  : <code>/blackjack 100</code>\n\n"
            f"\U0001f3b2 <b></b> <code>/slots [bet]</code>\n"
            f"    3  :\n"
            f"   3  7\ufe0f\u20e3 -  50 ( )\n"
            f"   3   -   3  20\n"
            f"   2   -  \n"
            f"  : <code>/slots 50</code>\n\n"
            f"\U0001f3df <b></b> <code>/card [bet] [higher/lower]</code>\n"
            f"  ,       .\n"
            f"    1.8 .\n"
            f"  : <code>/card 100 </code>\n\n"
            f"\U0001fa99 <b></b> <code>/coin [bet] [heads/tails]</code>\n"
            f"    .\n"
            f"    0.8 .\n"
            f"  : <code>/coin 100 </code>\n\n"
            f"\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\n"
            f"\U0001f4b8 <b></b>\n"
            f"\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\n\n"
            f"\U0001f4b0 <b></b> <code>/balance</code> -  AceCoin\n"
            f"\U0001f4b1 <b></b> <code>/p [amount]</code> -  \n"
            f"       !\n"
            f"\U0001f194 <b> ID</b> <code>/id</code> -    \n"
            f"\U0001f4ca <b></b> <code>/stats</code> -   \n"
            f"\U0001f3c6 <b></b> <code>/top</code> -  \n\n"
            f"\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\n"
            f"\U0001f380 <b></b>\n"
            f"\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\n\n"
            f"\U0001f3ab <b></b> -    ,   <code>#</code>\n"
            f"   : <code>#STARTER</code>, <code>#LUCKY777</code>, <code>#JACKPOT</code>\n"
            f"       !\n\n"
            f"\U0001f5ed <b></b> <code>/quests</code>\n"
            f"   20 !         .\n"
            f"  -   ,  - .\n\n"
            f"\U0001f381 <b> </b> -  200 AceCoin   24 .\n"
            f"      !\n\n"
            f"\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\n"
            f"\U0001f4a1 <b></b>\n"
            f"\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\n\n"
            f"     1000 AceCoin.\n"
            f"      !\n"
            f"  -       .\n"
            f"      ,     !\n\n"
            f"  ! \U0001f525"
        )
        await update.message.reply_text(text, parse_mode='HTML')
    except Exception as e:
        logger.error(f"help_cmd: {e}")


# ========== STATS ==========
async def stats_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user_id = update.effective_user.id
        stats = get_user_stats_raw(user_id)
        if not stats:
            await update.message.reply_text(" .  /start.")
            return

        winrate = 0
        total = stats.get("wins", 0) + stats.get("losses", 0)
        if total > 0:
            winrate = round(stats.get("wins", 0) / total * 100, 1)

        text = (
            f"\U0001f4ca <b> </b>\n\n"
            f"\U0001f4b0 <b>:</b> <code>{stats.get('balance', 0):,}</code> AceCoin\n"
            f"\U0001f3c6 <b>:</b> {stats.get('wins', 0)}\n"
            f"\U0001f4e9 <b>:</b> {stats.get('losses', 0)}\n"
            f"\U0001f4c8 <b> :</b> {winrate}%\n"
            f"\U0001f3af <b> :</b> {stats.get('total_games', 0)}\n"
            f"\U0001f4b8 <b>  :</b> <code>{stats.get('total_won', 0):,}</code> AceCoin\n"
            f"\U0001f451 <b>  :</b> <code>{stats.get('biggest_win', 0):,}</code> AceCoin\n"
            f"\U0001f525 <b>  :</b> {stats.get('max_win_streak', 0)}\n\n"
            f"\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\n"
            f"\U0001f3b0 <b> </b>\n"
            f"\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\n\n"
            f"\U0001f3c0 <b>:</b> {stats.get('roulette_plays', 0)} \n"
            f"\U0001f0cf <b>:</b> {stats.get('blackjack_plays', 0)} \n"
            f"   \U0001f3c5  : {stats.get('blackjack_wins', 0)} \n"
            f"   \U0001f31f  : {stats.get('natural_blackjacks', 0)} \n"
            f"\U0001f3b2 <b>:</b> {stats.get('slots_plays', 0)} \n"
            f"   \U0001f3c5  : {stats.get('slots_match', 0)} \n"
            f"   \U0001f3b0  : {stats.get('slots_jackpot', 0)} \n"
            f"\U0001f3df <b>:</b> {stats.get('card_plays', 0)} \n"
            f"\U0001fa99 <b>:</b> {stats.get('coin_plays', 0)} \n"
            f"   \U0001f3c5  : {stats.get('coin_wins', 0)} \n\n"
            f"\U0001f381 <b> :</b> {stats.get('bonus_claimed', 0)} \n"
        )
        await update.message.reply_text(text, parse_mode='HTML')
    except Exception as e:
        logger.error(f"stats_cmd: {e}")


# ========== LEADERBOARD ==========
async def leaderboard_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        c.execute("SELECT user_id, balance, wins, total_games, username FROM users ORDER BY balance DESC LIMIT 10")
        rows = c.fetchall()
        conn.close()

        if not rows:
            await update.message.reply_text("    .")
            return

        medals = ["\U0001f947", "\U0001f948", "\U0001f949", "4\ufe0f\u20e3", "5\ufe0f\u20e3", "6\ufe0f\u20e3", "7\ufe0f\u20e3", "8\ufe0f\u20e3", "9\ufe0f\u20e3", "\U0001f51f"]

        text = "\U0001f3c6 <b> Ace Casino</b>\U0001f3c6\n\n"
        text += "<b>  </b>\n"
        text += "\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\n\n"

        for i, row in enumerate(rows):
            uid, balance, wins, total_games, username = row
            display_name = f"@{username}" if username else f"ID: {uid}"
            medal = medals[i] if i < len(medals) else f"{i+1}"
            text += f"{medal} <b>{display_name}</b>\n"
            text += f"    \U0001f4b0 {balance:,} AceCoin"
            if wins:
                text += f" | \U0001f3c5 {wins}  | \U0001f3af {total_games} "
            text += "\n\n"

        # Топ по победам
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        c.execute("SELECT user_id, wins, username FROM users WHERE wins > 0 ORDER BY wins DESC LIMIT 5")
        win_rows = c.fetchall()
        conn.close()

        if win_rows:
            text += "\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\n"
            text += "<b>  </b>\n"
            text += "\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\n\n"
            for i, row in enumerate(win_rows):
                uid, wins, username = row
                display_name = f"@{username}" if username else f"ID: {uid}"
                medal = medals[i] if i < len(medals) else f"{i+1}"
                text += f"{medal} <b>{display_name}</b> - \U0001f3c5 {wins} \n"

        await update.message.reply_text(text, parse_mode='HTML')
    except Exception as e:
        logger.error(f"leaderboard_cmd: {e}")


# ========== BALANCE ==========
async def balance_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user = get_user(update.effective_user.id)
        if not user:
            await update.message.reply_text(" .")
            return
        keyboard = []
        if check_bonus_available(update.effective_user.id):
            keyboard.append([InlineKeyboardButton("\U0001f380  200 AceCoin", callback_data="get_bonus")])
        reply_markup = InlineKeyboardMarkup(keyboard) if keyboard else None
        text = f"\U0001f4b0  : <code>{user['balance']:,}</code> AceCoin"
        if not check_bonus_available(update.effective_user.id):
            text += "\n\u23f3   24 ."
        await update.message.reply_text(text, parse_mode='HTML', reply_markup=reply_markup)
    except Exception as e:
        logger.error(f"balance_cmd: {e}")


# ========== BONUS ==========
async def bonus_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user_id = update.effective_user.id
        if check_bonus_available(user_id):
            new_bal = give_bonus_logic(user_id)
            await update.message.reply_text(f"\U0001f380  200 AceCoin!  : {new_bal}")
        else:
            await update.message.reply_text("\u23f3   .  24 .")
    except Exception as e:
        logger.error(f"bonus_cmd: {e}")


# ========== CALLBACKS ==========
async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        query = update.callback_query
        await query.answer()
        if query.data == "get_bonus":
            user_id = query.from_user.id
            if check_bonus_available(user_id):
                new_bal = give_bonus_logic(user_id)
                await query.edit_message_text(f"\U0001f380  200 AceCoin!  : {new_bal}")
            else:
                await query.answer("  !", show_alert=True)
        elif query.data == "help_main":
            text = (
                "\U0001f4d6 <b> </b>\U0001f4d6\n\n"
                f"\U0001f3b0 <b>:</b> /roulette, /blackjack, /slots, /card, /coin\n"
                f"\U0001f4b8 <b>:</b> /balance, /p, /id, /stats, /top\n"
                f"\U0001f380 <b>:</b>  #, /quests,   \n\n"
                f"   : <code>/help</code>"
            )
            await query.edit_message_text(text, parse_mode='HTML')
        elif query.data == "quests_list":
            await quests_cmd_inline(query)
        elif query.data == "leaderboard":
            await leaderboard_cmd_inline(query)
    except Exception as e:
        logger.error(f"handle_callback: {e}")


async def quests_cmd_inline(query):
    try:
        user_id = query.from_user.id
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        c.execute("SELECT quest_id FROM quests_completed WHERE user_id = ?", (user_id,))
        completed_ids = set(row[0] for row in c.fetchall())
        conn.close()
        text = "\U0001f5ed <b> </b>\n\n"
        for quest in QUESTS:
            status = "\u2705" if quest["id"] in completed_ids else "\u274c"
            text += f"{status} #{quest['id']}. {quest['desc']} - +{quest['reward']} AceCoin\n"
        completed_count = len(completed_ids)
        text += f"\n : {completed_count}/{len(QUESTS)}"
        await query.edit_message_text(text, parse_mode='HTML')
    except Exception as e:
        logger.error(f"quests_cmd_inline: {e}")


async def leaderboard_cmd_inline(query):
    try:
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        c.execute("SELECT user_id, balance, wins, username FROM users ORDER BY balance DESC LIMIT 10")
        rows = c.fetchall()
        conn.close()
        if not rows:
            await query.edit_message_text("    .")
            return
        medals = ["\U0001f947", "\U0001f948", "\U0001f949", "4\ufe0f\u20e3", "5\ufe0f\u20e3", "6\ufe0f\u20e3", "7\ufe0f\u20e3", "8\ufe0f\u20e3", "9\ufe0f\u20e3", "\U0001f51f"]
        text = "\U0001f3c6 <b> Ace Casino</b>\U0001f3c6\n\n"
        for i, row in enumerate(rows):
            uid, balance, wins, username = row
            display_name = f"@{username}" if username else f"ID: {uid}"
            medal = medals[i] if i < len(medals) else f"{i+1}"
            text += f"{medal} <b>{display_name}</b> - \U0001f4b0 {balance:,} AceCoin"
            if wins:
                text += f" | \U0001f3c5 {wins}"
            text += "\n"
        await query.edit_message_text(text, parse_mode='HTML')
    except Exception as e:
        logger.error(f"leaderboard_cmd_inline: {e}")


# ========== TRANSFER ==========
async def transfer_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if not update.message or not update.message.text:
            return
        if not update.message.reply_to_message:
            await update.message.reply_text(
                "\U0001f4b1  AceCoin:\n"
                "      :\n"
                "/p <\n\n"
                ": /p 500"
            )
            return
        msg = update.message.text.split()
        if len(msg) < 2:
            await update.message.reply_text("\u274c  . : /p 500")
            return
        amount = int(msg[1])
    except ValueError:
        await update.message.reply_text("\u274c   . : /p 500")
        return
    except Exception as e:
        logger.error(f"transfer_cmd parse: {e}")
        return

    try:
        sender_id = update.effective_user.id
        target_id = update.message.reply_to_message.from_user.id
        if amount <= 0:
            await update.message.reply_text("\u274c    .")
            return
        if target_id == sender_id:
            await update.message.reply_text("\u274c    .")
            return
        if target_id == context.bot.id:
            await update.message.reply_text("\u274c    .")
            return
        sender = get_user(sender_id)
        if not sender or sender["balance"] < amount:
            await update.message.reply_text(f"\u274c  AceCoin.  : {sender['balance'] if sender else 0}")
            return
        receiver = get_user(target_id)
        if not receiver:
            await update.message.reply_text("\u274c   .")
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
        target_name = update.message.reply_to_message.from_user.first_name or ""
        await update.message.reply_text(
            f"\u2705  !\n"
            f": {target_name}\n"
            f": {amount} AceCoin\n"
            f"  : {sender_bal} AceCoin"
        )
        try:
            await context.bot.send_message(
                chat_id=target_id,
                text=f"\U0001f4b1   {amount} AceCoin!\n  : {receiver['balance'] + amount} AceCoin"
            )
        except Exception:
            pass
    except Exception as e:
        logger.error(f"transfer_cmd: {e}")
        try:
            await update.message.reply_text("\u26a0\ufe0f   .")
        except:
            pass


# ========== ID ==========
async def id_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        await update.message.reply_text(f"\U0001f194  ID: <code>{update.effective_user.id}</code>", parse_mode='HTML')
    except Exception as e:
        logger.error(f"id_cmd: {e}")


# ========== PROMOCODES ==========
async def promocode_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if not update.message or not update.message.text:
            return
        text = update.message.text.strip().upper()
        if text not in PROMOCODES:
            await update.message.reply_text("\u274c  .")
            return
        user_id = update.effective_user.id
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        c.execute("SELECT user_id, used_at FROM promocodes_used WHERE code = ?", (text,))
        row = c.fetchone()
        if row:
            used_at_str = row[1]
            try:
                used_at = datetime.fromisoformat(used_at_str)
                formatted = used_at.strftime("%d.%m.%Y %H:%M")
            except (ValueError, TypeError):
                formatted = ""
            conn.close()
            await update.message.reply_text(f"\u274c   ({formatted}).")
            return
        min_reward, max_reward = PROMOCODES[text]
        reward = random.randint(min_reward, max_reward)
        c.execute("INSERT INTO promocodes_used (code, user_id, used_at) VALUES (?, ?, ?)", (text, user_id, datetime.now().isoformat()))
        c.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (reward, user_id))
        conn.commit()
        c.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
        new_bal_row = c.fetchone()
        conn.close()
        new_bal = new_bal_row[0] if new_bal_row else 0
        await update.message.reply_text(f"\U0001f380  !\n  {reward} AceCoin!\n : {new_bal} AceCoin")
    except Exception as e:
        logger.error(f"promocode_handler: {e}")


# ========== QUESTS ==========
async def quests_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user_id = update.effective_user.id
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        c.execute("SELECT quest_id FROM quests_completed WHERE user_id = ?", (user_id,))
        completed_ids = set(row[0] for row in c.fetchall())
        conn.close()
        text = "\U0001f5ed <b> </b>\n\n"
        for quest in QUESTS:
            status = "\u2705" if quest["id"] in completed_ids else "\u274c"
            text += f"{status} #{quest['id']}. {quest['desc']} - +{quest['reward']} AceCoin\n"
        completed_count = len(completed_ids)
        text += f"\n : {completed_count}/{len(QUESTS)}"
        await update.message.reply_text(text, parse_mode='HTML')
    except Exception as e:
        logger.error(f"quests_cmd: {e}")


# ========== ROULETTE ==========
async def roulette_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if not update.message or not update.message.text:
            return
        msg = update.message.text.split()
        if len(msg) < 3:
            await update.message.reply_text(":    .\n: /roulette 100 ")
            return
        bet = int(msg[1])
        if bet <= 0:
            await update.message.reply_text("\u274c    .")
            return
    except ValueError:
        await update.message.reply_text("\u274c   .")
        return
    except Exception as e:
        logger.error(f"roulette_cmd parse: {e}")
        return
    try:
        user = get_user(update.effective_user.id)
        if not user or user["balance"] < bet:
            await update.message.reply_text("\u274c  AceCoin!")
            return
        target = " ".join(msg[2:]).lower()
        await send_animation(update, ANIMATION_ROULETTE)
        await update.message.reply_text("\U0001f300  ...")
        number = random.randint(0, 36)
        red_numbers = [1, 3, 5, 7, 9, 12, 14, 16, 18, 19, 21, 23, 25, 27, 30, 32, 34, 36]
        color = "green" if number == 0 else ("red" if number in red_numbers else "black")
        color_map = {"": "red", "": "black", "": "black"}
        check_color = color_map.get(target, target)
        win = False
        payout = 0
        if check_color == "red" and color == "red":
            win = True; payout = 2
        elif check_color == "black" and color == "black":
            win = True; payout = 2
        elif target in ["even", "", ""] and number != 0 and number % 2 == 0:
            win = True; payout = 2
        elif target in ["odd", "", ""] and number != 0 and number % 2 != 0:
            win = True; payout = 2
        elif target.isdigit() and int(target) == number:
            win = True; payout = 36
        result_text = f"\U0001f3b1 : {number} ({color})\n"
        if win:
            winnings = bet * (payout - 1)
            update_balance(update.effective_user.id, winnings)
            result_text += f"\U0001f389 !   {winnings} AceCoin."
            update_stats(update.effective_user.id, "roulette", True, winnings)
        else:
            update_balance(update.effective_user.id, -bet)
            result_text += "\U0001f61e .   !"
            update_stats(update.effective_user.id, "roulette", False, 0)
        await update.message.reply_text(result_text)
    except Exception as e:
        logger.error(f"roulette_cmd: {e}")


# ========== BLACKJACK ==========
async def blackjack_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if not update.message or not update.message.text:
            return
        msg = update.message.text.split()
        if len(msg) < 2:
            await update.message.reply_text("\U0001f0cf  :  .\n: /blackjack 100")
            return
        bet = int(msg[1])
        if bet <= 0:
            await update.message.reply_text("\u274c    .")
            return
    except ValueError:
        await update.message.reply_text("\u274c   .")
        return
    except Exception as e:
        logger.error(f"blackjack_cmd parse: {e}")
        return
    try:
        user = get_user(update.effective_user.id)
        if not user or user["balance"] < bet:
            await update.message.reply_text("\U0001f4b8   AceCoin.")
            return
        await send_animation(update, STICKER_BLACKJACK)
        await update.message.reply_text("\U0001f0cf  ...")
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
            await update.message.reply_text(f"\U0001f0cf   !   {winnings} AceCoin!")
            return
        p_hand_str = ",".join(map(str, player_hand))
        d_first_str = str(dealer_hand[0])
        keyboard = [
            [InlineKeyboardButton("\U0001f0cf  ", callback_data=f"bj_hit_{bet}_{p_hand_str}_{d_first_str}")],
            [InlineKeyboardButton("\u270d ", callback_data=f"bj_stand_{bet}_{p_hand_str}_{d_first_str}")],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(
            f"\U0001f0cf  : {player_hand} (: {p_val})\n: [{dealer_hand[0]}, ?]\n :",
            reply_markup=reply_markup,
        )
    except Exception as e:
        logger.error(f"blackjack_cmd: {e}")


async def handle_blackjack_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        query = update.callback_query
        await query.answer()
        data = query.data.split("_")
        if len(data) < 5:
            await query.edit_message_text("\u274c  .")
            return
        action = data[1]
        bet = int(data[2])
        p_hand_str = data[3]
        d_first_str = data[4]
        player_hand = list(map(int, p_hand_str.split(",")))
        dealer_first = int(d_first_str)
    except (ValueError, IndexError):
        try:
            await query.edit_message_text("\u274c  .")
        except:
            pass
        return
    except Exception as e:
        logger.error(f"handle_blackjack_callback parse: {e}")
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
                await query.edit_message_text(f"\U0001f0cf  ({p_val})!   {bet} AceCoin.")
                return
            p_hand_str_new = ",".join(map(str, player_hand))
            keyboard = [
                [InlineKeyboardButton("\U0001f0cf  ", callback_data=f"bj_hit_{bet}_{p_hand_str_new}_{d_first_str}")],
                [InlineKeyboardButton("\u270d ", callback_data=f"bj_stand_{bet}_{p_hand_str_new}_{d_first_str}")],
            ]
            await query.edit_message_text(
                f"\U0001f0cf  : {p_val}. : [{dealer_first}, ?]\n ?",
                reply_markup=InlineKeyboardMarkup(keyboard),
            )
            return
        while hand_value(dealer_hand) < 17:
            if not deck:
                break
            dealer_hand.append(deck.pop())
        d_val = hand_value(dealer_hand)
        p_val = hand_value(player_hand)
        msg = f"\U0001f0cf : {dealer_hand} (: {d_val})\n: {player_hand} (: {p_val})\n\n"
        if p_val > 21:
            msg += "\U0001f61e   ."
            update_balance(user_id, -bet)
            update_stats(user_id, "blackjack", False, 0)
        elif d_val > 21 or p_val > d_val:
            winnings = bet
            msg += f"\U0001f389 ! +{winnings} AceCoin."
            update_balance(user_id, winnings)
            update_stats(user_id, "blackjack", True, winnings)
        elif p_val < d_val:
            msg += "\U0001f61e  ."
            update_balance(user_id, -bet)
            update_stats(user_id, "blackjack", False, 0)
        else:
            msg += "\U0001f91d   ."
        await query.edit_message_text(msg)
    except Exception as e:
        logger.error(f"handle_blackjack_callback: {e}")


# ========== SLOTS ==========
async def slots_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if not update.message or not update.message.text:
            return
        msg = update.message.text.split()
        if len(msg) < 2:
            await update.message.reply_text("\U0001f3b2  :  .\n: /slots 50")
            return
        bet = int(msg[1])
        if bet <= 0:
            await update.message.reply_text("\u274c    .")
            return
    except ValueError:
        await update.message.reply_text("\u274c   .")
        return
    except Exception as e:
        logger.error(f"slots_cmd parse: {e}")
        return
    try:
        user = get_user(update.effective_user.id)
        if not user or user["balance"] < bet:
            await update.message.reply_text("\U0001f4b8  AceCoin.")
            return
        await send_animation(update, ANIMATION_SLOTS)
        await update.message.reply_text("\U0001f3b0  ...")
        symbols = ["\U0001f352", "\U0001f34b", "\U0001f514", "\U0001f31f", "\U0001f48e", "7\ufe0f\u20e3"]
        reels = [random.choice(symbols) for _ in range(3)]
        payout_map = {"\U0001f352": 3, "\U0001f34b": 4, "\U0001f514": 5, "\U0001f31f": 10, "\U0001f48e": 20, "7\ufe0f\u20e3": 50}
        winnings = 0
        is_match = False
        is_jackpot = False
        if reels[0] == reels[1] == reels[2]:
            winnings = bet * payout_map[reels[0]]
            is_match = True
            if reels[0] == "7\ufe0f\u20e3":
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
        text = f"\U0001f3b2 {reels[0]} {reels[1]} {reels[2]}\n"
        if net > 0:
            text += f"\U0001f389 : {net} AceCoin!"
            if is_jackpot:
                text += " \U0001f3b0 !"
        elif net == 0:
            text += "\U0001f91d   ."
        else:
            text += "\U0001f61e ."
        await update.message.reply_text(text)
    except Exception as e:
        logger.error(f"slots_cmd: {e}")


# ========== CARD ==========
async def card_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if not update.message or not update.message.text:
            return
        msg = update.message.text.split()
        if len(msg) < 3:
            await update.message.reply_text("\U0001f3df  /:    .\n: /card 100 ")
            return
        bet = int(msg[1])
        choice = msg[2].lower()
        if bet <= 0:
            await update.message.reply_text("\u274c    .")
            return
    except ValueError:
        await update.message.reply_text("\u274c  .")
        return
    except Exception as e:
        logger.error(f"card_cmd parse: {e}")
        return
    try:
        user = get_user(update.effective_user.id)
        if not user or user["balance"] < bet:
            await update.message.reply_text("\U0001f4b8  AceCoin.")
            return
        await send_animation(update, STICKER_CARD)
        await update.message.reply_text("\U0001f3df  ...")
        cards = list(range(2, 15))
        random.shuffle(cards)
        current = cards.pop()
        next_card = cards.pop()
        won = (choice == "" and next_card > current) or (choice == "" and next_card < current)
        multiplier = 1.8
        if won:
            winnings = int(bet * (multiplier - 1))
            update_balance(update.effective_user.id, winnings)
            update_stats(update.effective_user.id, "card", True, winnings)
            await update.message.reply_text(f"\U0001f3df : {current}, : {next_card}\n\U0001f389  ! +{winnings} AceCoin.")
        else:
            update_balance(update.effective_user.id, -bet)
            update_stats(update.effective_user.id, "card", False, 0)
            await update.message.reply_text(f"\U0001f3df : {current}, : {next_card}\n\U0001f61e  . -{bet} AceCoin.")
    except Exception as e:
        logger.error(f"card_cmd: {e}")


# ========== COIN ==========
async def coin_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if not update.message or not update.message.text:
            return
        msg = update.message.text.split()
        if len(msg) < 3:
            await update.message.reply_text("\U0001fa99 :   .\n: /coin 100 ")
            return
        bet = int(msg[1])
        choice = msg[2].lower()
        if bet <= 0:
            await update.message.reply_text("\u274c    .")
            return
    except ValueError:
        await update.message.reply_text("\u274c  .")
        return
    except Exception as e:
        logger.error(f"coin_cmd parse: {e}")
        return
    try:
        user = get_user(update.effective_user.id)
        if not user or user["balance"] < bet:
            await update.message.reply_text("\U0001f4b8  AceCoin.")
            return
        await send_animation(update, ANIMATION_COIN)
        await update.message.reply_text("\U0001fa99  ...")
        side = random.choice(["", ""])
        if choice == side:
            winnings = int(bet * 0.8)
            update_balance(update.effective_user.id, winnings)
            update_stats(update.effective_user.id, "coin", True, winnings)
            await update.message.reply_text(f"\U0001fa99 : {side}\n\U0001f389 !   {winnings} AceCoin.")
        else:
            update_balance(update.effective_user.id, -bet)
            update_stats(update.effective_user.id, "coin", False, 0)
            await update.message.reply_text(f"\U0001fa99 : {side}\n\U0001f61e .   {bet} AceCoin.")
    except Exception as e:
        logger.error(f"coin_cmd: {e}")


# ========== GIVE ==========
async def give_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user_id = update.effective_user.id
        if user_id != ADMIN_ID:
            await update.message.reply_text("\u274c     .")
            return
        msg = update.message.text.split()
        if len(msg) < 2:
            await update.message.reply_text(": /give 10000")
            return
        amount = int(msg[1])
        new_bal = update_balance(user_id, amount)
        if new_bal is not None:
            await update.message.reply_text(f"\u2705  {amount} AceCoin.  : {new_bal}")
    except ValueError:
        await update.message.reply_text("   .")
    except Exception as e:
        logger.error(f"give_cmd: {e}")


# ========== MAIN ==========
def main():
    token = os.getenv("BOT_TOKEN")
    if not token:
        logger.error(": BOT_TOKEN !")
        return

    application = ApplicationBuilder().token(token).build()

    application.add_handler(CommandHandler("start", start_cmd))
    application.add_handler(CommandHandler("help", help_cmd))
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
    application.add_handler(CommandHandler("stats", stats_cmd))
    application.add_handler(CommandHandler("top", leaderboard_cmd))

    # Cyrillic commands
    application.add_handler(MessageHandler(filters.Regex(r'^/\u0431($|\s)'), balance_cmd))
    application.add_handler(MessageHandler(filters.Regex(r'^/\u043f($|\s)'), transfer_cmd))
    application.add_handler(MessageHandler(filters.Regex(r'^/\u0440\u0443\u043b\u0435\u0442\u043a\u0430($|\s)'), roulette_cmd))
    application.add_handler(MessageHandler(filters.Regex(r'^/\u0431\u043b\u0435\u043a\u0434\u0436\u0435\u043a($|\s)'), blackjack_cmd))
    application.add_handler(MessageHandler(filters.Regex(r'^/\u0441\u043b\u043e\u0442\u044b($|\s)'), slots_cmd))
    application.add_handler(MessageHandler(filters.Regex(r'^/\u043a\u0430\u0440\u0442\u0430($|\s)'), card_cmd))
    application.add_handler(MessageHandler(filters.Regex(r'^/\u043c\u043e\u043d\u0435\u0442\u043a\u0430($|\s)'), coin_cmd))
    application.add_handler(MessageHandler(filters.Regex(r'^/\u043a\u0432($|\s)'), quests_cmd))
    application.add_handler(MessageHandler(filters.Regex(r'^/\u0441\u0442\u0430\u0442($|\s)'), stats_cmd))
    application.add_handler(MessageHandler(filters.Regex(r'^/\u0442\u043e\u043f($|\s)'), leaderboard_cmd))
    application.add_handler(MessageHandler(filters.Regex(r'^/\u043f\u043e\u043c\u043e\u0449\u044c($|\s)'), help_cmd))

    # Promocodes
    application.add_handler(MessageHandler(filters.Regex(r'^#'), promocode_handler))

    # Callbacks
    application.add_handler(CallbackQueryHandler(handle_callback, pattern="^get_bonus$|^help_main$|^quests_list$|^leaderboard$"))
    application.add_handler(CallbackQueryHandler(handle_blackjack_callback, pattern="^bj_"))

    # Error handler
    application.add_error_handler(error_handler)

    logger.info(" Bot ...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    init_db()
    main()
