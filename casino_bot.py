import os
import random
import sqlite3
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, CallbackQueryHandler
from dotenv import load_dotenv
import logging

# --- НАСТРОЙКА ЛОГГИРОВАНИЯ ---
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.DEBUG  # Теперь будут видны и INFO, и DEBUG сообщения
)
logger = logging.getLogger(__name__)


load_dotenv()

DB_NAME = "casino.db"

def init_db():
    """Инициализация БД и создание таблицы, если её нет."""
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
    logger.info("База данных инициализирована.")

def get_user(user_id):
    """Получает данные пользователя. Гарантирует создание записи."""
    try:
        conn = sqlite3.connect(DB_NAME)
        conn.row_factory = sqlite3.Row  # Важно: позволяет обращаться по именам колонок
        c = conn.cursor()
        
        # Создаем пользователя, если его нет
        c.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (user_id,))
        
        # Получаем данные
        c.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        user = c.fetchone()
        conn.close()
        return user
    except Exception as e:
        logger.error(f"Ошибка при получении пользователя {user_id}: {e}")
        return None

def update_balance(user_id, amount):
    """Обновляет баланс. Возвращает новый баланс или False при ошибке."""
    try:
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        # Обновляем баланс
        c.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (amount, user_id))
        
        # Сразу проверяем, сколько стало
        c.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
        new_balance = c.fetchone()
        
        conn.commit()
        conn.close()
        logger.debug(f"Баланс пользователя {user_id} изменен на {amount}. Новый баланс: {new_balance}")
        return new_balance
    except Exception as e:
        logger.error(f"Ошибка обновления баланса для {user_id}: {e}")
        return False

def give_bonus(user_id):
    """Выдает ежедневный бонус 200 фишек. Строгая проверка времени."""
    now = datetime.now()
    user = get_user(user_id)
    
    if not user:
        return False

    # user['last_bonus'] теперь доступен по имени благодаря row_factory
    last_bonus_str = user['last_bonus']
    
    # Если бонуса никогда не было (NULL в БД)
    if last_bonus_str is None:
        new_bal = update_balance(user_id, 200)
        if new_bal is not False:
            conn = sqlite3.connect(DB_NAME)
            c = conn.cursor()
            c.execute("UPDATE users SET last_bonus = ? WHERE user_id = ?", (now.isoformat(), user_id))
            conn.commit()
            conn.close()
            return True
        return False
    
    try:
        last_bonus = datetime.fromisoformat(last_bonus_str)
        # Проверка: прошло ли больше 24 часов?
        if (now - last_bonus) >= timedelta(hours=24):
            new_bal = update_balance(user_id, 200)
            if new_bal is not False:
                conn = sqlite3.connect(DB_NAME)
                c = conn.cursor()
                c.execute("UPDATE users SET last_bonus = ? WHERE user_id = ?", (now.isoformat(), user_id))
                conn.commit()
                conn.close()
                return True
    except ValueError:
        logger.warning(f"Неверный формат даты в БД для пользователя {user_id}. Сброс таймера.")
        # Если дата битая, считаем, что можно дать бонус, но фиксируем время
        new_bal = update_balance(user_id, 200)
        if new_bal is not False:
            conn = sqlite3.connect(DB_NAME)
            c = conn.cursor()
            c.execute("UPDATE users SET last_bonus = ? WHERE user_id = ?", (now.isoformat(), user_id))
            conn.commit()
            conn.close()
            return True
        
    return False

def hand_value(hand):
    """Подсчет очков в блэкджеке."""
    value = 0
    aces = sum(1 for c in hand if c == 1)
    for c in hand:
        if c == 1: value += 11
        elif c > 10: value += 10
        else: value += c
    while value > 21 and aces > 0:
        value -= 10
        aces -= 1
    return value

# --- КОМАНДЫ ---

async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = get_user(user_id)

    if not user:
        await update.message.reply_text("Произошла критическая ошибка профиля. Попробуй нажать /start еще раз.")
        return

    balance = user[1]

    await update.message.reply_text(
        f"Привет, {update.effective_user.first_name}!\n"
        f"Твой баланс: {balance} фишек.\n\n"
        f"Доступные игры:\n"
        f"/roulette - рулетка\n"
        f"/blackjack - блэкджек\n"
        f"/slots - слоты\n"
        f"/card - угадай карту (выше/ниже)\n"
        f"/coin - монетка\n\n"
        f"/balance - проверить баланс\n"
        f"/bonus - ежедневный бонус"
    )

async def balance_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = get_user(update.effective_user.id)
    if not user:
        await update.message.reply_text("Ошибка профиля.")
        return
    
    await update.message.reply_text(f"Твой текущий баланс: {user[1]} фишек.")

async def bonus_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if give_bonus(update.effective_user.id):
        await update.message.reply_text("Бонус 200 фишек начислен! Следующий через 24 часа.")
    else:
        await update.message.reply_text("Бонус уже получен. Подожди 24 часа.")

async def roulette_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message.text.split()
    if len(msg) < 3:
        await update.message.reply_text("Рулетка: поставь ставку и выбери вариант.\nПримеры:\n/roulette 100 red\n/roulette 50 even\n/roulette 25 17")
        return
    
    try:
        bet = int(msg[1])
    except ValueError:
        await update.message.reply_text("Укажи корректную ставку числом (например, /roulette 100 red).")
        return

    user = get_user(update.effective_user.id)
    if not user or user[1] < bet:
        await update.message.reply_text("Недостаточно фишек!")
        return

    target = " ".join(msg[2:]).lower()
    number = random.randint(0, 36)
    
    red_numbers = [1,3,5,7,9,12,14,16,18,19,21,23,25,27,30,32,34,36]
    color = "green" if number == 0 else ("red" if number in red_numbers else "black")
    is_even = (number % 2 == 0) if number != 0 else False
    range_1_18 = 1 <= number <= 18

    win = False
    payout = 0

    if target in ["red", "красный", "красное"] and color == "red":
        win = True; payout = 2
    elif target in ["black", "чёрный", "черный"] and color == "black":
        win = True; payout = 2
    elif target == "even" and is_even:
        win = True; payout = 2
    elif target == "odd" and not is_even and number != 0:
        win = True; payout = 2
    elif target == "1-18" and range_1_18:
        win = True; payout = 2
    elif target == "19-36" and not range_1_18 and number != 0:
        win = True; payout = 2
    elif target.isdigit() and int(target) == number:
        win = True; payout = 36

    result_text = f"Выпало: {number} ({color})\n"
    if win:
        winnings = bet * (payout - 1)
        update_balance(update.effective_user.id, winnings)
        result_text += f"Победа! Ты выиграл {winnings} фишек."
    else:
        update_balance(update.effective_user.id, -bet)
        result_text += "Проигрыш. Попробуй снова!"

    await update.message.reply_text(result_text)

async def blackjack_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message.text.split()
    if len(msg) < 2:
        await update.message.reply_text("Блэкджек: укажи ставку.\nПример: /blackjack 100")
        return
    
    try:
        bet = int(msg[1])
    except ValueError:
        await update.message.reply_text("Ставка должна быть числом.")
        return

    user = get_user(update.effective_user.id)
    if not user or user[1] < bet:
        await update.message.reply_text("Не хватает фишек.")
        return

    deck = [i for i in range(1, 14)] * 4
    random.shuffle(deck)
    
    player_hand = [deck.pop(), deck.pop()]
    dealer_hand = [deck.pop(), deck.pop()]

    p_val = hand_value(player_hand)

    if p_val == 21:
        winnings = int(bet * 1.5)
        update_balance(update.effective_user.id, winnings)
        await update.message.reply_text(f"Натуральный блэкджек! Ты получил {winnings} фишек!")
        return

    p_hand_str = ",".join(map(str, player_hand))
    d_first_str = str(dealer_hand[0])
    
    keyboard = [
        [InlineKeyboardButton("Ещё карту", callback_data=f"bj_hit_{bet}_{p_hand_str}_{d_first_str}")],
        [InlineKeyboardButton("Хватит", callback_data=f"bj_stand_{bet}_{p_hand_str}_{d_first_str}")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        f"Твои карты: {player_hand} (сумма: {p_val})\nДилер: [{dealer_hand[0]}, ?]\nВыбери действие:",
        reply_markup=reply_markup
    )

async def handle_blackjack_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    data = query.data.split("_")
    if len(data) < 5:
        await query.edit_message_text("Ошибка сессии. Начни игру заново.")
        return

    action = data[1]
    try:
        bet = int(data[2])
        p_hand_str = data[3]
        d_first_str = data[4]
        
        player_hand = list(map(int, p_hand_str.split(",")))
        dealer_first = int(d_first_str)
    except (ValueError, IndexError):
        await query.edit_message_text("Ошибка данных. Начни игру заново.")
        return

    user_id = update.effective_user.id
    
    deck = [i for i in range(1, 14)] * 4
    for card in player_hand:
        if card in deck: deck.remove(card)
    if dealer_first in deck: deck.remove(dealer_first)
    random.shuffle(deck)
    
    dealer_hand = [dealer_first, deck.pop()]
    
    if action == "hit":
        new_card = deck.pop()
        player_hand.append(new_card)
        p_val = hand_value(player_hand)
        
        if p_val > 21:
            update_balance(user_id, -bet)
            await query.edit_message_text(f"Перебор ({p_val})! Ты потерял {bet} фишек.")
            return
            
        p_hand_str_new = ",".join(map(str, player_hand))
        keyboard = [
            [InlineKeyboardButton("Ещё карту", callback_data=f"bj_hit_{bet}_{p_hand_str_new}_{d_first_str}")],
            [InlineKeyboardButton("Хватит", callback_data=f"bj_stand_{bet}_{p_hand_str_new}_{d_first_str}")]
        ]
        await query.edit_message_text(
            f"Твоя сумма: {p_val}. Дилер: [{dealer_first}, ?]\nЧто делаешь?",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return

    while hand_value(dealer_hand) < 17:
        if not deck: break
        dealer_hand.append(deck.pop())
    
    d_val = hand_value(dealer_hand)
    p_val = hand_value(player_hand)

    msg = f"Дилер: {dealer_hand} (сумма: {d_val})\nТы: {player_hand} (сумма: {p_val})\n\n"
    
    if p_val > 21:
        msg += "Перебор — проигрыш."
        update_balance(user_id, -bet)
    elif d_val > 21 or p_val > d_val:
        winnings = bet
        msg += f"Победа! +{winnings} фишек."
        update_balance(user_id, winnings)
    elif p_val < d_val:
        msg += "Дилер выиграл."
        update_balance(user_id, -bet)
    else:
        msg += "Ничья — ставка возвращена."

    await query.edit_message_text(msg)

async def slots_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message.text.split()
    if len(msg) < 2:
        await update.message.reply_text("Слоты: поставь ставку.\nПример: /slots 50\nВыплаты: x3, x4, x5, x10, x20, x50")
        return
    
    try:
        bet = int(msg[1])
    except ValueError:
        await update.message.reply_text("Ставка должна быть числом.")
        return

    user = get_user(update.effective_user.id)
    if not user or user[1] < bet:
        await update.message.reply_text("Мало фишек.")
        return

    symbols = ["🍒", "🍋", "🔔", "⭐", "💎", "7️⃣"]
    reels = [random.choice(symbols) for _ in range(3)]
    
    payout_map = {"🍒":3, "🍋":4, "🔔":5, "⭐":10, "💎":20, "7️⃣":50}
    winnings = 0
    
    if reels[0] == reels[1] == reels[2]:
        winnings = bet * payout_map[reels[0]]
    elif reels[0] == reels[1] or reels[1] == reels[2] or reels[0] == reels[2]:
        winnings = bet

    net = winnings - bet
    update_balance(update.effective_user.id, net)
    
    text = f"🎲 {reels[0]} {reels[1]} {reels[2]}\n"
    if net > 0:
        text += f"Выигрыш: {net} фишек!"
    elif net == 0:
        text += "Возврат ставки."
    else:
        text += "Проигрыш."
    await update.message.reply_text(text)

async def card_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message.text.split()
    if len(msg) < 3:
        await update.message.reply_text("Карта выше/ниже: укажи ставку и выбор.\nПример: /card 100 higher или /card 100 lower")
        return
    
    try:
        bet = int(msg[1])
        choice = msg[2].lower()
    except ValueError:
        await update.message.reply_text("Неверный формат. Используй: /card 100 higher")
        return

    user = get_user(update.effective_user.id)
    if not user or user[1] < bet:
        await update.message.reply_text("Нет фишек.")
        return

    cards = list(range(2, 15))
    random.shuffle(cards)
    current = cards.pop()
    next_card = cards.pop()

    won = (choice == "higher" and next_card > current) or (choice == "lower" and next_card < current)
    multiplier = 1.8
    
    if won:
        winnings = int(bet * (multiplier - 1))
        update_balance(update.effective_user.id, winnings)
        await update.message.reply_text(f"Текущая: {current}, следующая: {next_card}\nТы угадал! +{winnings} фишек.")
    else:
        update_balance(update.effective_user.id, -bet)
        await update.message.reply_text(f"Текущая: {current}, следующая: {next_card}\nНе угадал. -{bet} фишек.")

async def coin_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message.text.split()
    if len(msg) < 3:
        await update.message.reply_text("Монетка: ставка и сторона.\nПример: /coin 100 heads (heads/tails)")
        return
    
    try:
        bet = int(msg[1])
        choice = msg[2].lower()
    except ValueError:
        await update.message.reply_text("Ошибка формата.")
        return

    user = get_user(update.effective_user.id)
    if not user or user[1] < bet:
        await update.message.reply_text("Фишек нет.")
        return

    side = random.choice(["heads", "tails"])
    if choice == side:
        winnings = int(bet * 0.8)
        update_balance(update.effective_user.id, winnings)
        await update.message.reply_text(f"Выпало: {side}\nПобеда! Ты выиграл {winnings} фишек.")
    else:
        update_balance(update.effective_user.id, -bet)
        await update.message.reply_text(f"Выпало: {side}\nПроигрыш. Ты потерял {bet} фишек.")

def main():
    token = os.getenv("BOT_TOKEN")
    
    if not token:
        logger.error("КРИТИЧЕСКАЯ ОШИБКА: Переменная BOT_TOKEN пуста!")
        logger.error("Убедись, что в настройках проекта (или в .env) задана переменная BOT_TOKEN с твоим токеном.")
        return

    logger.info("Токен найден. Запуск бота...")
    
    application = ApplicationBuilder().token(token).build()

    application.add_handler(CommandHandler("start", start_cmd))
    application.add_handler(CommandHandler("roulette", roulette_cmd))
    application.add_handler(CommandHandler("blackjack", blackjack_cmd))
    application.add_handler(CommandHandler("slots", slots_cmd))
    application.add_handler(CommandHandler("card", card_cmd))
    application.add_handler(CommandHandler("coin", coin_cmd))
    application.add_handler(CommandHandler("balance", balance_cmd))
    application.add_handler(CommandHandler("bonus", bonus_cmd))

    application.add_handler(CallbackQueryHandler(handle_blackjack_callback))

    logger.info("Бот запускается и начинает слушать Telegram...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    init_db()
    main()
