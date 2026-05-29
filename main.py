import telebot
from telebot import types
import os
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

# ================= НАСТРОЙКИ (ЗАМЕНИТЕ НА СВОИ) =================
API_TOKEN = '8856437407:AAFCPsaE9X6tbqRRdXNG9z6t-MbW8ew5p3w'
ADMIN_ID = 5105755553  # СЮДА ВСТАВЬ СВОЙ ID ИЗ @getmyid_bot
REQUISITES = "СБП / Тинькофф / Сбербанк: +7 (999) 123-45-67 (Получатель: Иван И.)"
PRICE_PER_STAR = 1.25  # Цена за 1 звезду
# ================================================================

bot = telebot.TeleBot(API_TOKEN)
orders = {}

# --- КОСТЫЛЬ ДЛЯ БЕСПЛАТНОГО ТАРИФА RENDER ---
# Создаем фейковый веб-сервер, чтобы Render думал, что это сайт, и держал его бесплатно
class TinyServer(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain; charset=utf-8")
        self.end_headers()
        self.wfile.write("Бот запущен и работает!".encode("utf-8"))

def run_web_server():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(("0.0.0.0", port), TinyServer)
    print(f"Фейковый сервер запущен на порту {port}")
    server.serve_forever()
# ---------------------------------------------

@bot.message_handler(commands=['start'])
def start_cmd(message):
    chat_id = message.chat.id
    orders[chat_id] = {}
    
    markup = types.InlineKeyboardMarkup(row_width=2)
    btn_self = types.InlineKeyboardButton("Себе 👤", callback_data="recipient_self")
    btn_friend = types.InlineKeyboardButton("Другу 🎁", callback_data="recipient_friend")
    markup.add(btn_self, btn_friend)
    
    bot.send_message(
        chat_id, 
        "👋 **Добро пожаловать!**\n\n"
        "В нашем боте вы можете приобрести Telegram Stars намного дешевле, чем напрямую через приложение.\n"
        f"🔥 Текущий курс: **1 Звезда = {PRICE_PER_STAR} ₽**\n\n"
        "Кому вы хотите отправить звезды?",
        parse_mode="Markdown",
        reply_markup=markup
    )

@bot.callback_query_handler(func=lambda call: call.data.startswith("recipient_"))
# Обработка выбора получателя
@bot.callback_query_handler(func=lambda call: call.data.startswith("recipient_"))
def handle_recipient(call):
    chat_id = call.message.chat.id
    recipient_type = call.data.split("_")[1]
    
    orders[chat_id]['recipient_type'] = recipient_type
    
    if recipient_type == "self":
        # АВТОМАТИЧЕСКИ ПОЛУЧАЕМ ЮЗЕРНЕЙМ
        if call.from_user.username:
            username = "@" + call.from_user.username
        else:
            # Если у человека нет юзернейма (@...), берем его Имя и ID
            username = f"{call.from_user.first_name} (ID: {call.from_user.id})"
            
        orders[chat_id]['username'] = username
        
        # Сразу переходим к запросу количества звезд
        msg = bot.send_message(chat_id, f"✅ Вы выбрали: себе ({username})\n\n🔢 Какое количество звезд вы хотите приобрести? (Введите число):")
        bot.register_next_step_handler(msg, get_amount)
        
    else:
        # Если выбрали "Другу", спрашиваем юзернейм как раньше
        msg = bot.send_message(chat_id, "✍️ Укажите юзернейм вашего друга (например, `@friend_username`):")
        bot.register_next_step_handler(msg, get_username)
def get_username(message):
    chat_id = message.chat.id
    username = message.text.strip()
    if not username.startswith('@'):
        username = '@' + username
    orders[chat_id]['username'] = username
    msg = bot.send_message(chat_id, "🔢 Какое количество звезд вы хотите приобрести? (Введите число):")
    bot.register_next_step_handler(msg, get_amount)

def get_amount(message):
    chat_id = message.chat.id
    text = message.text.strip()
    
    if not text.isdigit() or int(text) <= 0:
        msg = bot.send_message(chat_id, "❌ Пожалуйста, введите корректное число звезд:")
        bot.register_next_step_handler(msg, get_amount)
        return
        
    amount = int(text)
    total_cost = round(amount * PRICE_PER_STAR, 2)
    
    orders[chat_id]['amount'] = amount
    orders[chat_id]['cost'] = total_cost
    
    markup = types.InlineKeyboardMarkup()
    btn_confirm = types.InlineKeyboardButton("✅ Я оплатил(а)", callback_data="confirm_payment")
    btn_cancel = types.InlineKeyboardButton("❌ Отмена", callback_data="cancel_order")
    markup.add(btn_confirm, btn_cancel)
    
    bot.send_message(
        chat_id,
        f"📊 **Ваш заказ сформирован**\n"
        f"Получатель: {orders[chat_id]['username']}\n"
        f"Количество звезд: {amount} 🌟\n"
        f"Сумма к оплате: **{total_cost} ₽**\n\n"
        f"💳 **Реквизиты для оплаты:**\n`{REQUISITES}`\n\n"
        f"⚠️ Переведите точную сумму ({total_cost} ₽) по реквизитам выше. "
        f"После перевода нажмите кнопку **«Я оплатил(а)»** ниже.",
        parse_mode="Markdown",
        reply_markup=markup
    )

@bot.callback_query_handler(func=lambda call: call.data in ["confirm_payment", "cancel_order"])
def handle_payment_status(call):
    chat_id = call.message.chat.id
    
    if call.data == "cancel_order":
        bot.send_message(chat_id, "❌ Заказ отменен. Чтобы начать заново, напишите /start")
        orders[chat_id] = {}
        return

    order = orders.get(chat_id)
    if not order or 'amount' not in order:
        bot.send_message(chat_id, "⚠️ Произошла ошибка. Пожалуйста, начните заново, прописав /start")
        return
    
    buyer_info = f"@{call.from_user.username}" if call.from_user.username else f"ID: {chat_id}"
    admin_message = (
        f"🔔 **НОВЫЙ ЗАКАЗ ОПЛАЧЕН!**\n\n"
        f"👤 Покупатель: {buyer_info}\n"
        f"👉 Кому отправлять: **{order['username']}**\n"
        f"🌟 Количество звезд: **{order['amount']}** шт.\n"
        f"💰 Ожидаемая сумма: **{order['cost']} ₽**\n\n"
        f"Проверьте поступление денег и выполните отправку!"
    )
    
    try:
        bot.send_message(ADMIN_ID, admin_message, parse_mode="Markdown")
    except Exception as e:
        print(f"Не удалось отправить сообщение админу: {e}")

    bot.send_message(
        chat_id, 
        "🎉 **Заявка отправлена на проверку!**\n"
        "Администратор проверяет оплату и отправит вам звезды в ближайшее время. Спасибо за покупку!"
    )
    orders[chat_id] = {}

if __name__ == "__main__":
    # Запускаем веб-сервер в отдельном потоке (для Render)
    threading.Thread(target=run_web_server, daemon=True).start()
    
    # Запускаем бота
    print("Бот запущен...")
    bot.infinity_polling()
