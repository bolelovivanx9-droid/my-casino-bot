import os
import random
import sqlite3
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, CallbackQueryHandler
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

# --- ТВОЙ TELEGRAM ID ---
# ВПИШИ СЮДА СВОЙ ID БЕЗ ПРОБЕЛОВ!
ADMIN_ID = 8762706702 

# --- ID СТИКЕРОВ (АНИМАЦИЯ) ---
# Найди крутые анимированные стикеры в Telegram, перешли их боту @getidsbot, 
# чтобы узнать их file_id. Вставь их сюда.
# Если не хочешь ставить свои, оставь эти заглушки (бот просто напишет текст, если стикер не найдется).
STICKER_ROULETTE = "AAMCAgADGQEDmFvcari2v_HlCpiqaR-95srvTf2L4iwAAmhvAAL2dKlLNdFghJKsV9wBAAdtAAM9BA"  # Замени на реальный file_id стикера рулетки
STICKER_BLACKJACK = None      # Было: "CAACAgIAAxkBAAIBZn..."
STICKER_SLOTS = "AAMCAgADGQEDmFxJari4I33gO65IVRiHTi44A1NVqcgAAl5bAAIqkThIYxaqKAEWYVIBAAdtAAM9BA"     # Замени на реальный file_id стикера слотов
STICKER_CARD = None           # Было: "CAACAgIAAxkBAAIBZp..."
STICKER_COIN = "AAMCBQADGQEDmFyYari5GmsCOuLYMYsrGJWbKKC4b0oAAkkAA6_zxDVDdNs1jD51_AEAB20AAz0E"      # Замени на реальный file_id стикера монеты

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
    logger.info("База данных инициализирована.")

def get_user(user_id):
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (user_id,))
    conn.commit()
    c.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    user = c.fetchone()
    conn.close()
    return user

def update_balance(user_id, amount):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (amount, user_id))
    conn.commit()
    c.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
    row = c.fetchone()
    conn.close()
    if row:
        return row
    return None

def check_bonus_available(user_id):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT last_bonus FROM users WHERE user_id = ?", (user_id,))
    row = c.fetchone()
    conn.close()
    
    if not row or not row:
        return True
    
    last_bonus_str = row
    now = datetime.now()
    
    try:
        last_bonus = datetime.fromisoformat(last_bonus_str)
        if (now - last_bonus) >= timedelta(hours=24):
            return True
    except ValueError:
        return True # Если дата битая, считаем что можно
        
    return False

def give_bonus_logic(user_id):
    now = datetime.now()
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    
    # Начисляем фишки
    c.execute("UPDATE users SET balance = balance + 200 WHERE user_id = ?", (user_id,))
    # Обновляем время бонуса
    c.execute("UPDATE users SET last_bonus = ? WHERE user_id = ?", (now.isoformat(), user_id))
    conn.commit()
    
    c.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
    new_bal = c.fetchone()
    conn.close()
    return new_bal

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

# --- ХЕНДЛЕРЫ (КОМАНДЫ) ---

async def send_animation(update, sticker_id):
    """Отправляет стикер-анимацию, если ID есть. Если нет (None) — просто ничего не делает."""
    if not sticker_id:
        return  # Если стикера нет, сразу выходим из функции
    
    try:
        await update.message.reply_sticker(sticker=sticker_id)
    except Exception as e:
        logger.warning(f"Не удалось отправить стикер (возможно, ID неверен или удален): {e}")
        # Ошибка не критичная, бот продолжит работу 

async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = get_user(update.effective_user.id)
    if not user:
        await update.message.reply_text("Ошибка профиля.")
        return
    
    # Кнопка бонуса при старте (если доступен)
    keyboard = []
    if check_bonus_available(update.effective_user.id):
        keyboard.append([InlineKeyboardButton("🎁 Забрать бонус 200", callback_data="get_bonus")])
    
    reply_markup = InlineKeyboardMarkup(keyboard) if keyboard else None
    
    text = (f"Привет, {update.effective_user.first_name}!\n"
            f"Твой баланс: {user['balance']} фишек.\n\n"
            f"Быстрые команды:\n"
            f"💵 б — баланс\n"
            f"🎰 рулетка (ставка) цвет\n"
            f"🃏 блекджек (ставка)\n"
            f"🎲 слоты (ставка)\n"
            f"🃟 карта (ставка) выше/ниже\n"
            f"🪙 монетка (ставка) орел/решка")
            
    await update.message.reply_text(text, reply_markup=reply_markup)

async def balance_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = get_user(update.effective_user.id)
    if not user:
        await update.message.reply_text("Ошибка профиля.")
        return

    # Логика кнопки бонуса
    keyboard = []
    if check_bonus_available(update.effective_user.id):
        keyboard.append([InlineKeyboardButton("🎁 Забрать бонус 200", callback_data="get_bonus")])
    
    reply_markup = InlineKeyboardMarkup(keyboard) if keyboard else None
    
    text = f"💰 Твой баланс: {user['balance']} фишек."
    if not check_bonus_available(update.effective_user.id):
        text += "\n⏳ Бонус уже получен, жди 24 часа."
    
    await update.message.reply_text(text, reply_markup=reply_markup)

async def bonus_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Эта команда нужна, если пользователь пишет /bonus вручную
    user_id = update.effective_user.id
    if check_bonus_available(user_id):
        new_bal = give_bonus_logic(user_id)
        await update.message.reply_text(f"🎁 Бонус 200 фишек начислен! Новый баланс: {new_bal}")
    else:
        await update.message.reply_text("⏳ Бонус уже получен. Подожди 24 часа.")

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data == "get_bonus":
        user_id = query.from_user.id
        if check_bonus_available(user_id):
            new_bal = give_bonus_logic(user_id)
            await query.edit_message_text(f"🎁 Бонус 200 фишек начислен! Новый баланс: {new_bal}")
        else:
            await query.answer("Бонус уже получен!", show_alert=True)

# --- ИГРЫ С АНИМАЦИЕЙ ---

async def roulette_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message.text.split()
    # Поддержка команды "рулетка" вместо "/roulette"
    # msg может быть "рулетка" или "/roulette"
    
    if len(msg) < 3:
        await update.message.reply_text("🎰 Рулетка: поставь ставку и выбери вариант.\nПример: рулетка 100 красный")
        return

    try:
        bet = int(msg)
    except ValueError:
        await update.message.reply_text("❌ Ставка должна быть числом.")
        return

    user = get_user(update.effective_user.id)
    if not user or user["balance"] < bet:
        await update.message.reply_text("💸 Недостаточно фишек!")
        return

    target = " ".join(msg[2:]).lower()
    
    # 1. ОТПРАВЛЯЕМ АНИМАЦИЮ
    await send_animation(update, STICKER_ROULETTE)
    
    # Небольшая задержка не нужна, Telegram сам покажет стикер, но можно добавить текст "Крутим..."
    await update.message.reply_text("🌀 Крутим колесо...")

    number = random.randint(0, 36)
    red_numbers = [1, 3, 5, 7, 9, 12, 14, 16, 18, 19, 21, 23, 25, 27, 30, 32, 34, 36]
    color = "green" if number == 0 else ("red" if number in red_numbers else "black")
    
    # Маппинг русских слов на английские для проверки
    color_map = {"красный": "red", "чёрный": "black", "черный": "black"}
    check_color = color_map.get(target, target)

    win = False
    payout = 0

    if check_color == "red" and color == "red": win = True; payout = 2
    elif check_color == "black" and color == "black": win = True; payout = 2
    elif target in ["even", "чётное", "четное"] and number != 0 and number % 2 == 0: win = True; payout = 2
    elif target in ["odd", "нечётное", "нечетное"] and number != 0 and number % 2 != 0: win = True; payout = 2
    elif target.isdigit() and int(target) == number: win = True; payout = 36

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
        await update.message.reply_text("🃏 Блэкджек: укажи ставку.\nПример: блекджек 100")
        return

    try:
        bet = int(msg)
    except ValueError:
        await update.message.reply_text("❌ Ставка должна быть числом.")
        return

    user = get_user(update.effective_user.id)
    if not user or user["balance"] < bet:
        await update.message.reply_text("💸 Не хватает фишек.")
        return

    # 1. АНИМАЦИЯ
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
        await update.message.reply_text(f"🃏 Натуральный блэкджек! Ты получил {winnings} фишек!")
        return

    p_hand_str = ",".join(map(str, player_hand))
    d_first_str = str(dealer_hand)

    keyboard = [
        [InlineKeyboardButton("🃏 Ещё карту", callback_data=f"bj_hit_{bet}_{p_hand_str}_{d_first_str}")],
        [InlineKeyboardButton("✋ Хватит", callback_data=f"bj_stand_{bet}_{p_hand_str}_{d_first_str}")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        f"🃏 Твои карты: {player_hand} (сумма: {p_val})\nДилер: [{dealer_hand}, ?]\nВыбери действие:",
        reply_markup=reply_markup
    )

# Обработчик кнопок блэкджека (оставляем как было, он уже рабочий)
async def handle_blackjack_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data.split("_")
    if len(data) < 5:
        await query.edit_message_text("❌ Ошибка сессии.")
        return

    action = data
    try:
        bet = int(data)
        p_hand_str = data
        d_first_str = data
        player_hand = list(map(int, p_hand_str.split(",")))
        dealer_first = int(d_first_str)
    except (ValueError, IndexError):
        await query.edit_message_text("❌ Ошибка данных.")
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
            await query.edit_message_text(f"🃏 Перебор ({p_val})! Ты потерял {bet} фишек.")
            return
        p_hand_str_new = ",".join(map(str, player_hand))
        keyboard = [
            [InlineKeyboardButton("🃏 Ещё карту", callback_data=f"bj_hit_{bet}_{p_hand_str_new}_{d_first_str}")],
            [InlineKeyboardButton("✋ Хватит", callback_data=f"bj_stand_{bet}_{p_hand_str_new}_{d_first_str}")]
        ]
        await query.edit_message_text(
            f"🃏 Твоя сумма: {p_val}. Дилер: [{dealer_first}, ?]\nЧто делаешь?",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return

    while hand_value(dealer_hand) < 17:
        if not deck: break
        dealer_hand.append(deck.pop())

    d_val = hand_value(dealer_hand)
    p_val = hand_value(player_hand)
    msg = f"🃏 Дилер: {dealer_hand} (сумма: {d_val})\nТы: {player_hand} (сумма: {p_val})\n\n"

    if p_val > 21:
        msg += "😞 Перебор — проигрыш."
        update_balance(user_id, -bet)
    elif d_val > 21 or p_val > d_val:
        winnings = bet
        msg += f"🎉 Победа! +{winnings} фишек."
        update_balance(user_id, winnings)
    elif p_val < d_val:
        msg += "😞 Дилер выиграл."
        update_balance(user_id, -bet)
    else:
        msg += "🤝 Ничья — ставка возвращена."
    await query.edit_message_text(msg)

async def slots_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message.text.split()
    if len(msg) < 2:
        await update.message.reply_text("🎲 Слоты: поставь ставку.\nПример: слоты 50")
        return

    try:
        bet = int(msg)
    except ValueError:
        await update.message.reply_text("❌ Ставка должна быть числом.")
        return

    user = get_user(update.effective_user.id)
    if not user or user["balance"] < bet:
        await update.message.reply_text("💸 Мало фишек.")
        return

    # 1. АНИМАЦИЯ
    await send_animation(update, STICKER_SLOTS)
    await update.message.reply_text("🎰 Барабаны крутятся...")

    symbols = ["🍒", "🍋", "🔔", "⭐", "💎", "7️⃣"]
    reels = [random.choice(symbols) for _ in range(3)]
    payout_map = {"🍒": 3, "🍋": 4, "🔔": 5, "⭐": 10, "💎": 20, "7️⃣": 50}
    winnings = 0

    if reels == reels == reels:
        winnings = bet * payout_map[reels]
    elif reels == reels or reels == reels or reels == reels:
        winnings = bet

    net = winnings - bet
    update_balance(update.effective_user.id, net)

    text = f"🎲 {reels} {reels} {reels}\n"
    if net > 0: text += f"🎉 Выигрыш: {net} фишек!"
    elif net == 0: text += "🤝 Возврат ставки."
    else: text += "😞 Проигрыш."
    await update.message.reply_text(text)

async def card_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message.text.split()
    if len(msg) < 3:
        await update.message.reply_text("🃟 Карта выше/ниже: укажи ставку и выбор.\nПример: карта 100 выше")
        return

    try:
        bet = int(msg)
        choice = msg.lower()
    except ValueError:
        await update.message.reply_text("❌ Неверный формат.")
        return

    user = get_user(update.effective_user.id)
    if not user or user["balance"] < bet:
        await update.message.reply_text("💸 Нет фишек.")
        return

    # 1. АНИМАЦИЯ
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
        await update.message.reply_text(f"🃟 Текущая: {current}, следующая: {next_card}\n🎉 Ты угадал! +{winnings} фишек.")
    else:
        update_balance(update.effective_user.id, -bet)
        await update.message.reply_text(f"🃟 Текущая: {current}, следующая: {next_card}\n😞 Не угадал. -{bet} фишек.")

async def coin_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message.text.split()
    if len(msg) < 3:
        await update.message.reply_text("🪙 Монетка: ставка и сторона.\nПример: монетка 100 орел")
        return

    try:
        bet = int(msg)
        choice = msg.lower()
    except ValueError:
        await update.message.reply_text("❌ Ошибка формата.")
        return

    user = get_user(update.effective_user.id)
    if not user or user["balance"] < bet:
        await update.message.reply_text("💸 Фишек нет.")
        return

    # 1. АНИМАЦИЯ
    await send_animation(update, STICKER_COIN)
    await update.message.reply_text("🪙 Монетка летит...")

    side = random.choice(["орел", "решка"])
    if choice == side:
        winnings = int(bet * 0.8)
        update_balance(update.effective_user.id, winnings)
        await update.message.reply_text(f"🪙 Выпало: {side}\n🎉 Победа! Ты выиграл {winnings} фишек.")
    else:
        update_balance(update.effective_user.id, -bet)
        await update.message.reply_text(f"🪙 Выпало: {side}\n😞 Проигрыш. Ты потерял {bet} фишек.")

async def give_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != ADMIN_ID:
        await update.message.reply_text("❌ У тебя нет прав на эту команду.")
        return
    msg = update.message.text.split()
    if len(msg) < 2:
        await update.message.reply_text("Используй: /give 10000")
        return
    try:
        amount = int(msg)
    except ValueError:
        await update.message.reply_text("Число должно быть целым.")
        return
    new_bal = update_balance(user_id, amount)
    if new_bal is not None:
        await update.message.reply_text(f"✅ Начислено {amount} фишек. Новый баланс: {new_bal}")

def main():
    token = os.getenv("BOT_TOKEN")
    if not token:
        logger.error("КРИТИЧЕСКАЯ ОШИБКА: Переменная BOT_TOKEN пуста!")
        return

    application = ApplicationBuilder().token(token).build()

    # --- РЕГИСТРАЦИЯ КОМАНД (С КОРОТКИМИ НАЗВАНИЯМИ) ---
    # Мы регистрируем и стандартные, и русские/короткие версии
    
    # Баланс
    application.add_handler(CommandHandler("balance", balance_cmd))
    application.add_handler(CommandHandler("б", balance_cmd))
    
    # Рулетка
    application.add_handler(CommandHandler("roulette", roulette_cmd))
    application.add_handler(CommandHandler("рулетка", roulette_cmd))
    
    # Блэкджек
    application.add_handler(CommandHandler("blackjack", blackjack_cmd))
    application.add_handler(CommandHandler("блекджек", blackjack_cmd))
    
    # Слоты
    application.add_handler(CommandHandler("slots", slots_cmd))
    application.add_handler(CommandHandler("слоты", slots_cmd))
    
    # Карта
    application.add_handler(CommandHandler("card", card_cmd))
    application.add_handler(CommandHandler("карта", card_cmd))
    
    # Монетка
    application.add_handler(CommandHandler("coin", coin_cmd))
    application.add_handler(CommandHandler("монетка", coin_cmd))
    
    # Бонус
    application.add_handler(CommandHandler("bonus", bonus_cmd))
    
    # Админ
    application.add_handler(CommandHandler("give", give_cmd))
    
    # Обработчики кнопок
    application.add_handler(CallbackQueryHandler(handle_callback))
    application.add_handler(CallbackQueryHandler(handle_blackjack_callback))

    logger.info("🚀 Бот запускается...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    init_db()
    main()
