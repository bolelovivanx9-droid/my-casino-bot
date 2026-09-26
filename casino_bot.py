import os
import random
import sqlite3
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, CallbackQueryHandler

DB_NAME = "casino.db"

def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, balance INTEGER DEFAULT 1000, last_bonus TIMESTAMP, wins INTEGER DEFAULT 0, losses INTEGER DEFAULT 0)")
    conn.commit()
    conn.close()

def get_user(user_id):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
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
    last_bonus = user[2]
    if last_bonus is None or (now - datetime.fromisoformat(last_bonus)) >= timedelta(hours=24):
        update_balance(user_id, 200)
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        c.execute("UPDATE users SET last_bonus = ? WHERE user_id = ?", (now.isoformat(), user_id))
        conn.commit()
        conn.close()
        return True
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
    balance = user[1]
    text = (
        "🎰 Добро пожаловать в казино!\n\n"
        f"💰 Твой баланс: {balance} фишек\n\n"
        "Доступные команды:\n"
        "/start — это сообщение\n"
        "/balance — проверить баланс\n"
        "/bonus — получить ежедневный бонус (200 фишек)\n"
        "/рулетка <ставка> <вариант> — рулетка\n"
        "/блэкджек <ставка> — блэкджек\n"
        "/слоты <ставка> — слоты\n"
        "/карта <ставка> <выше|ниже> — карта выше/ниже\n"
        "/монетка <ставка> <орёл|решка> — орёл и решка\n\n"
        "Примеры:\n"
        "/рулетка 100 красное\n"
        "/слоты 50\n"
        "/монетка 100 орёл"
    )
    await update.message.reply_text(text)

async def balance_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = get_user(update.effective_user.id)
    await update.message.reply_text(f"💰 Твой баланс: {user[1]} фишек.")

async def bonus_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if give_bonus(update.effective_user.id):
        user = get_user(update.effective_user.id)
        await update.message.reply_text(f"🎁 Бонус получен! +200 фишек.\n💰 Твой баланс: {user[1]} фишек.")
    else:
        await update.message.reply_text("⏰ Бонус уже получен. Возвращайся через 24 часа!")

# --- Игры ---

async def roulette_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message.text.split()
    if len(msg) < 2:
        await update.message.reply_text(
            "🎰 Рулетка: поставь ставку и выбери вариант.\n"
            "Примеры:\n"
            "/рулетка 100 красное\n"
            "/рулетка 50 чёт\n"
            "/рулетка 25 17"
        )
        return
    try:
        bet = int(msg[1])
    except ValueError:
        await update.message.reply_text("❌ Укажи корректную ставку числом.")
        return

    user = get_user(update.effective_user.id)
    if user[1] < bet:
        await update.message.reply_text("💸 Недостаточно фишек!")
        return

    target = " ".join(msg[2:]).lower()
    number = random.randint(0, 36)
    color = "зелёный" if number == 0 else ("красный" if number in [1,3,5,7,9,12,14,16,18,19,21,23,25,27,30,32,34,36] else "чёрный")
    is_even = (number % 2 == 0) if number != 0 else False
    range_1_18 = 1 <= number <= 18

    win = False
    payout = 0

    if target in ["красное", "красный"] and color == "красный":
        win = True; payout = 2
    elif target in ["чёрное", "черный"] and color == "чёрный":
        win = True; payout = 2
    elif target == "чёт" and is_even:
        win = True; payout = 2
    elif target == "нечёт" and not is_even and number != 0:
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
        await update.message.reply_text("🃏 Блэкджек: укажи ставку.\nПример: /блэкджек 100")
        return
    try:
        bet = int(msg[1])
    except ValueError:
        await update.message.reply_text("❌ Ставка должна быть числом.")
        return

    user = get_user(update.effective_user.id)
    if user[1] < bet:
        await update.message.reply_text("💸 Не хватает фишек.")
        return

    deck = [i for i in range(1, 14)] * 4
    random.shuffle(deck)
    player_hand = [deck.pop(), deck.pop()]
    dealer_hand = [deck.pop(), deck.pop()]

    p_val = hand_value(player_hand)

    if p_val == 21:
        update_balance(update.effective_user.id, int(bet * 1.5))
        await update.message.reply_text(f"🃏 Натуральный блэкджек! Ты получил {int(bet*1.5)} фишек!")
        return

    keyboard = [
        [InlineKeyboardButton("Ещё", callback_data=f"bj_hit_{bet}_{p_val}_{dealer_hand[0]}")],
        [InlineKeyboardButton("Хватит", callback_data=f"bj_stand_{bet}_{p_val}_{dealer_hand[0]}")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        f"🃏 Твои карты: {player_hand} (сумма: {p_val})\nДилер: [{dealer_hand[0]}, ?]\nВыбери действие:",
        reply_markup=reply_markup
    )

async def handle_blackjack_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data.split("_")
    action, bet_str, p_val_str, dealer_first = data[1], data[2], data[3], data[4]
    bet = int(bet_str)
    p_val = int(p_val_str)
    user_id = update.effective_user.id

    deck = [i for i in range(1, 14)] * 4
    random.shuffle(deck)
    dealer_hand = [int(dealer_first), deck.pop()]

    if action == "hit":
        new_card = deck.pop()
        p_val += 11 if new_card == 1 else (10 if new_card > 10 else new_card)
        if p_val > 21:
            update_balance(user_id, -bet)
            await query.edit_message_text(f"🃏 Перебор! Ты потерял {bet} фишек.")
            return
        keyboard = [
            [InlineKeyboardButton("Ещё", callback_data=f"bj_hit_{bet}_{p_val}_{dealer_hand[0]}")],
            [InlineKeyboardButton("Хватит", callback_data=f"bj_stand_{bet}_{p_val}_{dealer_hand[0]}")]
        ]
        await query.edit_message_text(
            f"🃏 Твоя сумма: {p_val}. Дилер: [{dealer_hand[0]}, ?]\nЧто делаешь?",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return

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
        await update.message.reply_text(
            "🎲 Слоты: поставь ставку.\nПример: /слоты 50\n"
            "Выплаты: 🍓x3, 🍋x4, 🔔x5, ⭐x10, 💎x20, 7️⃣x50"
        )
        return
    try:
        bet = int(msg[1])
    except ValueError:
        await update.message.reply_text("❌ Ставка числом.")
        return

    user = get_user(update.effective_user.id)
    if user[1] < bet:
        await update.message.reply_text("💸 Мало фишек.")
        return

    symbols = ["🍓", "🍋", "🔔", "⭐", "💎", "7️⃣"]
    reels = [random.choice(symbols) for _ in range(3)]

    payout_map = {"🍓":3, "🍋":4, "🔔":5, "⭐":10, "💎":20, "7️⃣":50}
    winnings = 0
    if reels[0] == reels[1] == reels[2]:
        winnings = bet * payout_map[reels[0]]
    elif reels[0] == reels[1] or reels[1] == reels[2] or reels[0] == reels[2]:
        winnings = bet

    net = winnings - bet
    update_balance(update.effective_user.id, net)

    text = f"🎲 {reels[0]} {reels[1]} {reels[2]}\n"
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
        await update.message.reply_text(
            "🃟 Карта выше/ниже: укажи ставку и выбор.\n"
            "Пример: /карта 100 выше или /карта 100 ниже"
        )
        return
    try:
        bet = int(msg[1])
        choice = msg[2].lower()
    except ValueError:
        await update.message.reply_text("❌ Неверный формат.")
        return

    user = get_user(update.effective_user.id)
    if user[1] < bet:
        await update.message.reply_text("💸 Нет фишек.")
        return

    cards = list(range(2, 15))
    random.shuffle(cards)
    current = cards.pop()
    next_card = cards.pop()

    won = (choice == "выше" and next_card > current) or (choice == "ниже" and next_card < current)
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
        await update.message.reply_text("🪙 Монетка: ставка и сторона.\nПример: /монетка 100 орёл")
        return
    try:
        bet = int(msg[1])
        choice = msg[2].lower()
    except ValueError:
        await update.message.reply_text("❌ Ошибка формата.")
        return

    user = get_user(update.effective_user.id)
    if user[1] < bet:
        await update.message.reply_text("💸 Фишек нет.")
        return

    side = random.choice(["орёл", "решка"])
    if choice == side:
        winnings = int(bet * 0.8)
        update_balance(update.effective_user.id, winnings)
        await update.message.reply_text(f"🪙 Выпало: {side}\n🎉 Ты угадал! +{winnings} фишек.")
    else:
        update_balance(update.effective_user.id, -bet)
        await update.message.reply_text(f"🪙 Выпало: {side}\n😞 Не угадал. -{bet} фишек.")

# --- Запуск ---

def main():
    token = os.getenv("BOT_TOKEN")
    if not token:
        raise ValueError("BOT_TOKEN not found! Check env vars in Bothost panel.")

    application = ApplicationBuilder().token(token).build()

    application.add_handler(CommandHandler("start", start_cmd))
    application.add_handler(CommandHandler("balance", balance_cmd))
    application.add_handler(CommandHandler("bonus", bonus_cmd))
    application.add_handler(CommandHandler("рулетка", roulette_cmd))
    application.add_handler(CommandHandler("блэкджек", blackjack_cmd))
    application.add_handler(CommandHandler("слоты", slots_cmd))
    application.add_handler(CommandHandler("карта", card_cmd))
    application.add_handler(CommandHandler("монетка", coin_cmd))
    application.add_handler(CallbackQueryHandler(handle_blackjack_callback))

    print("Bot starting...")
    application.run_polling()

if __name__ == "__main__":
    init_db()
    main()
