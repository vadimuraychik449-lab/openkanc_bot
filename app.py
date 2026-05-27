import os
import asyncio
import logging
from datetime import datetime
from flask import Flask, request
from telegram import Bot, Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters

logging.basicConfig(level=logging.INFO)
app = Flask(__name__)

TOKEN = "8649027781:AAGfMeKFm8xcaOhZ8J8Xo4Wn220Y2zn1cgM"

STORES = {
    "rossiyskaya": {
        "name": "O'pen на Российской",
        "address": "Краснодар, Российская ул., 267/6 лит В",
        "area": "Музыкальный м-н, Прикубанский округ, Краснодар, 350024",
        "coordinates": {"lat": 45.092222, "lon": 39.007168},
        "store_code": "rossiyskaya"
    },
    "zhigulenko": {
        "name": "O'pen на Жигуленко",
        "address": "Краснодар, ул. Евгении Жигуленко, 25к1",
        "area": "им. Петра Метальникова м-н, Прикубанский округ, Краснодар, 350087",
        "coordinates": {"lat": 45.100637, "lon": 39.002361},
        "store_code": "zhigulenko"
    }
}

orders = {}

def get_main_keyboard():
    keyboard = [
        [InlineKeyboardButton("🏪 O'pen на Российской", callback_data="store_rossiyskaya")],
        [InlineKeyboardButton("🏪 O'pen на Жигуленко", callback_data="store_zhigulenko")],
        [InlineKeyboardButton("📍 Показать магазины на карте", callback_data="show_stores_map")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_confirmation_keyboard():
    keyboard = [
        [InlineKeyboardButton("✅ Подтвердить заказ", callback_data="confirm")],
        [InlineKeyboardButton("✏️ Изменить заказ", callback_data="edit")]
    ]
    return InlineKeyboardMarkup(keyboard)

def send_to_admin(bot, user_id, user_name, order_data):
    store_code = order_data.get('store')
    if store_code == "rossiyskaya":
        admin_chat_id = os.environ.get("ADMIN_CHAT_ID_ROSSIYSKAYA")
        store_name_for_admin = "Российская"
    elif store_code == "zhigulenko":
        admin_chat_id = os.environ.get("ADMIN_CHAT_ID_ZHIGULENKO")
        store_name_for_admin = "Жигуленко"
    else:
        admin_chat_id = None
        store_name_for_admin = "Неизвестный магазин"
    
    if not admin_chat_id:
        logging.error(f"Не указан ID администратора для магазина {store_code}")
        return False
    
    files_list = "\n".join([f"• {f}" for f in order_data['files']])
    message = f"""📋 *НОВЫЙ ЗАКАЗ НА ПЕЧАТЬ*

👤 *Клиент:* {user_name}
🆔 *User ID:* {user_id}

🏪 *Магазин:* {order_data['store_name']}
📍 *Адрес:* {order_data['store_address']}

📁 *Файлы:* 
{files_list}

💬 *Комментарий:* {order_data['comment']}
⏰ *Время получения:* {order_data['pickup_time']}

📅 *Создан:* {datetime.now().strftime('%d.%m.%Y %H:%M')}
"""
    try:
        bot.send_message(chat_id=admin_chat_id, text=message, parse_mode="Markdown")
        return True
    except Exception as e:
        logging.error(f"Ошибка отправки: {e}")
        return False

def get_all_stores_map_url():
    points = []
    for store in STORES.values():
        coords = store["coordinates"]
        points.append(f"{coords['lon']},{coords['lat']}")
    points_str = "~".join(points)
    return f"https://yandex.ru/maps/?pt={points_str}&z=13"

def get_single_store_map_url(store_code):
    coords = STORES[store_code]["coordinates"]
    address = STORES[store_code]["address"]
    return f"https://yandex.ru/maps/?pt={coords['lon']},{coords['lat']}&z=17&text={address.replace(' ', '%20')}"

async def start(update, context):
    user = update.effective_user
    welcome_text = f"""🖨️ *Добро пожаловать в OPEN Маркет канцелярских товаров*

Здравствуйте, {user.first_name}!

Я помогу вам оформить заказ на печать документов.

*Доступные магазины:*
• O'pen на Российской
• O'pen на Жигуленко

*Как это работает:*
1️⃣ Выберите магазин
2️⃣ Загрузите файлы
3️⃣ Оставьте комментарий
4️⃣ Укажите время получения
5️⃣ Подтвердите заказ

*Форматы файлов:* PDF, DOC, DOCX, JPG, PNG
"""
    await update.message.reply_text(welcome_text, parse_mode="Markdown", reply_markup=get_main_keyboard())

async def show_stores_map(update, context):
    query = update.callback_query
    await query.answer()
    map_url = get_all_stores_map_url()
    stores_text = "\n\n".join([
        f"🏪 *{store['name']}*\n📍 {store['address']}\n🗺️ {store['area']}"
        for store in STORES.values()
    ])
    await query.edit_message_text(
        f"🗺️ *Расположение магазинов:*\n\n{stores_text}\n\n"
        f"[Открыть карту]({map_url})",
        parse_mode="Markdown",
        reply_markup=get_main_keyboard()
    )

async def store_selection(update, context):
    query = update.callback_query
    await query.answer()
    store_code = query.data.replace("store_", "")
    user_id = query.from_user.id
    if user_id not in orders:
        orders[user_id] = {}
    orders[user_id]["store"] = store_code
    orders[user_id]["store_name"] = STORES[store_code]["name"]
    orders[user_id]["store_address"] = STORES[store_code]["address"]
    
    location_keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📍 Показать на карте", callback_data=f"location_{store_code}")]
    ])
    await query.edit_message_text(
        f"✅ *Выбран магазин:* {STORES[store_code]['name']}\n\n"
        f"📍 *Адрес:* {STORES[store_code]['address']}\n\n"
        f"Загрузите файлы. Когда закончите, нажмите /done",
        parse_mode="Markdown",
        reply_markup=location_keyboard
    )

async def show_single_location(update, context):
    query = update.callback_query
    await query.answer()
    store_code = query.data.replace("location_", "")
    map_url = get_single_store_map_url(store_code)
    store = STORES[store_code]
    await query.edit_message_text(
        f"📍 *{store['name']} на карте:*\n\n"
        f"[Открыть в Яндекс.Картах]({map_url})",
        parse_mode="Markdown"
    )

async def handle_file(update, context):
    user_id = update.effective_user.id
    file = update.message.document or update.message.photo
    if user_id not in orders:
        orders[user_id] = {}
    if "files" not in orders[user_id]:
        orders[user_id]["files"] = []
    if file == update.message.document:
        file_name = file.file_name
    else:
        file_name = f"photo_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
    orders[user_id]["files"].append(file_name)
    await update.message.reply_text(
        f"✅ Файл *{file_name}* получен! Всего: {len(orders[user_id]['files'])}.\nНажмите /done",
        parse_mode="Markdown"
    )

async def done_upload(update, context):
    user_id = update.effective_user.id
    if user_id not in orders or "files" not in orders[user_id] or len(orders[user_id]["files"]) == 0:
        await update.message.reply_text("❌ Нет файлов.")
        return
    await update.message.reply_text(
        "📝 Напишите *комментарий* к заказу.\nПример: цветная печать, 2 экземпляра",
        parse_mode="Markdown"
    )
    context.user_data["awaiting_comment"] = True

async def handle_comment(update, context):
    user_id = update.effective_user.id
    comment = update.message.text
    orders[user_id]["comment"] = comment
    await update.message.reply_text(
        f"💬 Комментарий сохранён.\n\n⏰ Напишите *время получения*.\nПример: сегодня 18:30",
        parse_mode="Markdown"
    )
    context.user_data["awaiting_time"] = True

async def handle_pickup_time(update, context):
    user_id = update.effective_user.id
    pickup_time = update.message.text
    orders[user_id]["pickup_time"] = pickup_time
    files_list = "\n".join([f"• {f}" for f in orders[user_id]["files"]])
    order_summary = f"""📋 *Ваш заказ:*

🏪 *Магазин:* {orders[user_id].get('store_name')}
📍 *Адрес:* {orders[user_id].get('store_address')}

📁 *Файлы ({len(orders[user_id]['files'])} шт.):*
{files_list}

💬 *Комментарий:* {orders[user_id].get('comment')}
⏰ *Время получения:* {pickup_time}

*Всё верно?*
"""
    await update.message.reply_text(order_summary, parse_mode="Markdown", reply_markup=get_confirmation_keyboard())

async def confirm_order(update, context):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    user_name = query.from_user.first_name
    
    if query.data == "confirm":
        order_data = orders.get(user_id, {})
        success = send_to_admin(context.bot, user_id, user_name, order_data)
        if success:
            store_code = order_data.get('store', 'rossiyskaya')
            await query.edit_message_text(
                f"✅ *Заказ подтверждён!*\n\n"
                f"Приходите в {order_data.get('pickup_time')} по адресу:\n"
                f"{order_data.get('store_address')}\n\n"
                f"📍 [Показать на карте]({get_single_store_map_url(store_code)})\n\n"
                f"Спасибо за заказ! 🖨️",
                parse_mode="Markdown"
            )
        else:
            await query.edit_message_text("❌ Ошибка. Попробуйте позже.")
        orders.pop(user_id, None)
    elif query.data == "edit":
        await query.edit_message_text("✏️ Напишите /start и создайте новый заказ.")

@app.route("/health")
def health():
    return "OK", 200

@app.route("/")
def index():
    return "🤖 OPEN Print Bot работает!"

async def setup_webhook():
    render_url = os.environ.get("RENDER_EXTERNAL_URL")
    if not render_url:
        print("⚠️ RENDER_EXTERNAL_URL не найден")
        return
    bot = Bot(token=TOKEN)
    webhook_url = f"{render_url}/webhook/{TOKEN}"
    try:
        await bot.set_webhook(webhook_url)
        print(f"✅ Webhook установлен: {webhook_url}")
    except Exception as e:
        print(f"❌ Ошибка: {e}")

if __name__ == "__main__":
    asyncio.run(setup_webhook())
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
