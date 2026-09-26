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
    level=logging.INFO
)
logger = logging.getLogger(__name__)

load_dotenv()

DB_NAME = "casino.db"

def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        balance INTEGER DEFAULT 1000,
        last_bonus TIMESTAMP,
        wins INTEGER DEFAULT 0,
        losses INTEGER DEFAULT 0
    )''')
    conn.commit()
    conn.close()
    logger.info("✅ База данных инициализирована.")

def get_user(user_id):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    # Сначала убедимся, что пользователь есть в базе
    c.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (user_id,))
    c.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    user = c.fetchone()
    conn.close()
    return user

def update_balance(user_id, amount):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (amount, user_id))
    conn.commit()
    conn.close()

def give_bonus(user_id):
    now = datetime.now()
    user = get_user(user_id)
    
    # user = (user_id, balance, last_bonus, wins, losses)
    # last_bonus находится по индексу 2
    last_bonus_str = user 
    
    if last_bonus_str is None:
        update_balance(user_id, 200)
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        c.execute("UPDATE users SET last_bonus = ? WHERE user_id = ?", (now.isoformat(), user_id))
        conn.commit()
        conn.close()
        return True
    
    try:
        last_bonus = datetime.fromisoformat(last_bonus_str)
        if (now - last_bonus) >= timedelta(hours=24):
            update_balance(user_id, 200)
            conn = sqlite3.connect(DB_NAME)
            c = conn.cursor()
            c.execute("UPDATE users SET last_bonus = ? WHERE user_id = ?", (now.isoformat(), user_id))
            conn.commit()
            conn.close()
            return True
    except ValueError:
        # Если дата в базе в неверном формате, считаем, что бонуса не было
        pass
        
    return False

def hand_value(hand):
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

# --- Команды ---

async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = get_user(update.effective_user.id)
    # user - это баланс
    await update.message.reply_text(
        f"👋 Привет, {update.effective_user.first_name}!\n"
        f"💰 Твой баланс: {user} фишек.\n\n"
        f"Доступные игры (команды на английском):\n"
        f"/roulette - рулетка\n"
        f"/blackjack - блэкджек\n"
        f"/slots - слоты\n"
        f"/card - угадай карту (выше/ниже)\n"
        f"/coin - монетка\n\n"
        f"💵 /balance - баланс\n"
        f"🎁 /bonus - ежедневный бонус"
    )

async def balance_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = get_user(update.effective_user.id)
    await update.message.reply_text(f"💰 Твой текущий баланс: {user} фишек.")

async def bonus_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if give_bonus(update.effective_user.id):
        await update.message.reply_text("🎁 Бонус 200 фишек начислен! Следующий через 24 часа.")
    else:
        await update.message.reply_text("⏳ Бонус уже получен. Подожди 24 часа.")

async def roulette_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message.text.split()
    if len(msg) < 3:
        await update.message.reply_text("🎰 Рулетка: поставь ставку и выбери вариант.\nПримеры:\n`/roulette 100 red`\n`/roulette 50 even`\n`/roulette 25 17`", parse_mode='Markdown')
        return
    
    try:
        bet = int(msg)
    except ValueError:
        await update.message.reply_text("❌ Укажи корректную ставку числом.")
        return

    user = get_user(update.effective_user.id)
    if user < bet:
        await update.message.reply_text("💸 Недостаточно фишек!")
        return

    target = " ".join(msg[2:]).lower()
    number = random.randint(0, 36)
    color = "green" if number == 0 else ("red" if number in [1,3,5,7,9,12,14,16,18,19,21,23,25,27,30,32,34,36] else "black")
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

    result_text = f"🎱 Выпало: {number} ({color})\n"
    if win:
        winnings = bet * (payout - 1)
        update_balance(update.effective_user.id, winnings)
        result_text += f"🎉 Победа! Ты выиграл {winnings} фишек."
    else:
        update_balance(update.effective_user.id, -bet)
        result_text += "😞 Проигрыш. Попробуй снова!"

    await update.message.reply_text(result_text)

async def blackjack_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message.text.split()
    if len(msg) < 2:
        await update.message.reply_text("🃏 Блэкджек: укажи ставку.\nПример: `/blackjack 100`", parse_mode='Markdown')
        return
    
    try:
        bet = int(msg)
    except ValueError:
        await update.message.reply_text("❌ Ставка должна быть числом.")
        return

    user = get_user(update.effective_user.id)
    if user < bet:
        await update.message.reply_text("💸 Не хватает фишек.")
        return

    deck = [i for i in range(1, 14)] * 4
    random.shuffle(deck)
    player_hand = [deck.pop(), deck.pop()]
    dealer_hand = [deck.pop(), deck.pop()]

    p_val = hand_value(player_hand)
    d_val = hand_value(dealer_hand)

    if p_val == 21:
        winnings = int(bet * 1.5)
        update_balance(update.effective_user.id, winnings)
        await update.message.reply_text(f"🃏 Натуральный блэкджек! Ты получил {winnings} фишек!")
        return

    # Передаем только первую карту дилера в callback_data
    # Формат: bj_action_bet_p_val_dealer_first
    keyboard = [
        [InlineKeyboardButton("Ещё", callback_data=f"bj_hit_{bet}_{p_val}_{dealer_hand}")],
        [InlineKeyboardButton("Хватит", callback_data=f"bj_stand_{bet}_{p_val}_{dealer_hand}")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        f"🃏 Твои карты: {player_hand} (сумма: {p_val})\nДилер: [{dealer_hand}, ?]\nВыбери действие:",
        reply_markup=reply_markup
    )

async def handle_blackjack_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    data = query.data.split("_")
    # Ожидаемый формат: bj_hit_bet_p_val_dealer_first
    if len(data) < 5:
        await query.edit_message_text("❌ Ошибка сессии. Начни игру заново.")
        return

    action = data # hit или stand
    try:
        bet = int(data)
        p_val = int(data)
        dealer_first = int(data)
    except ValueError:
        await query.edit_message_text("❌ Ошибка данных. Начни игру заново.")
        return

    user_id = update.effective_user.id
    deck = [i for i in range(1, 14)] * 4
    random.shuffle(deck)
    
    dealer_hand = [dealer_first, deck.pop()]
    
    if action == "hit":
        new_card = deck.pop()
        card_val = 11 if new_card == 1 else (10 if new_card > 10 else new_card)
        p_val += card_val
        
        if p_val > 21:
            update_balance(user_id, -bet)
            await query.edit_message_text(f"🃏 Перебор ({p_val})! Ты потерял {bet} фишек.")
            return
            
        keyboard = [
            [InlineKeyboardButton("Ещё", callback_data=f"bj_hit_{bet}_{p_val}_{dealer_first}")],
            [InlineKeyboardButton("Хватит", callback_data=f"bj_stand_{bet}_{p_val}_{dealer_first}")]
        ]
        await query.edit_message_text(
            f"🃏 Твоя сумма: {p_val}. Дилер: [{dealer_first}, ?]\nЧто делаешь?",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return

    # Логика дилера (stand)
    while hand_value(dealer_hand) < 17:
        dealer_hand.append(deck.pop())
    d_val = hand_value(dealer_hand)

    msg = f"🃏 Дилер: {dealer_hand} (сумма: {d_val})\nТы: сумма была {p_val}\n"
    if p_val > 21:
        msg += "😞 Перебор — проигрыш."
        update_balance(user_id, -bet)
    elif d_val > 21 or p_val > d_val:
        msg += f"🎉 Победа! +{bet} фишек."
        update_balance(user_id, bet)
    elif p_val < d_val:
        msg += "😞 Дилер выиграл."
        update_balance(user_id, -bet)
    else:
        msg += "🤝 Ничья — ставка возвращена."

    await query.edit_message_text(msg)

async def slots_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message.text.split()
    if len(msg) < 2:
        await update.message.reply_text("🎲 Слоты: поставь ставку.\nПример: `/slots 50`\nВыплаты: 🍒x3, 🍋x4, 🔔x5, ⭐x10, 💎x20, 7️⃣x50", parse_mode='Markdown')
        return
    
    try:
        bet = int(msg)
    except ValueError:
        await update.message.reply_text("❌ Ставка числом.")
        return

    user = get_user(update.effective_user.id)
    if user < bet:
        await update.message.reply_text("💸 Мало фишек.")
        return

    symbols = ["🍒", "🍋", "🔔", "⭐", "💎", "7️⃣"]
    reels = [random.choice(symbols) for _ in range(3)]
    
    payout_map = {"🍒":3, "🍋":4, "🔔":5, "⭐":10, "💎":20, "7️⃣":50}
    winnings = 0
    
    # Исправленная логика: сравниваем элементы списка по индексам
    if reels == reels == reels:
        winnings = bet * payout_map[reels]
    elif reels == reels or reels == reels or reels == reels:
        winnings = bet

    net = winnings - bet
    update_balance(update.effective_user.id, net)
    
    text = f"🎲 {reels} {reels} {reels}\n"
    if net > 0:
        text += f"🎉 Выигрыш: {net} фишек!"
    elif net == 0:
        text += "🤝 Возврат ставки."
    else:
        text += "😞 Проигрыш."
    await update.message.reply_text(text)

async def card_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message.text.split()
    if len(msg) < 3:
        await update.message.reply_text("🃟 Карта выше/ниже: укажи ставку и выбор.\nПример: `/card 100 higher` или `/card 100 lower`", parse_mode='Markdown')
        return
    
    try:
        bet = int(msg)
        choice = msg.lower()
    except ValueError:
        await update.message.reply_text("❌ Неверный формат.")
        return

    user = get_user(update.effective_user.id)
    if user < bet:
        await update.message.reply_text("💸 Нет фишек.")
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
        await update.message.reply_text(f"🃟 Текущая: {current}, следующая: {next_card}\n🎉 Ты угадал! +{winnings} фишек.")
    else:
        update_balance(update.effective_user.id, -bet)
        await update.message.reply_text(f"🃟 Текущая: {current}, следующая: {next_card}\n😞 Не угадал. -{bet} фишек.")

async def coin_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message.text.split()
    if len(msg) < 3:
        await update.message.reply_text("🪙 Монетка: ставка и сторона.\nПример: `/coin 100 heads` (heads/tails)", parse_mode='Markdown')
        return
    
    try:
        bet = int(msg)
        choice = msg.lower()
    except ValueError:
        await update.message.reply_text("❌ Ошибка формата.")
        return

    user = get_user(update.effective_user.id)
    if user < bet:
        await update.message.reply_text("💸 Фишек нет.")
        return

    side = random.choice(["heads", "tails"])
    if choice == side:
        winnings = int(bet * 0.8)
        update_balance(update.effective_user.id, winnings)
        await update.message.reply_text(f"🪙 Выпало: {side}\n🎉 Победа! Ты выиграл {winnings} фишек.")
    else:
        update_balance(update.effective_user.id, -bet)
        await update.message.reply_text(f"🪙 Выпало: {side}\n😞 Проигрыш. Ты потерял {bet} фишек.")

def main():
    token = os.getenv("BOT_TOKEN")
    
    if not token:
        logger.error("❌ КРИТИЧЕСКАЯ ОШИБКА: Переменная BOT_TOKEN пуста!")
        logger.error("Убедись, что в настройках проекта (или в .env) задана переменная BOT_TOKEN с твоим токеном.")
        return

    logger.info(f"✅ Токен найден. Запуск бота...")
    
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

    logger.info("🚀 Бот запускается и начинает слушать Telegram...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    init_db()
    main()
