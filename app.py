import os
import json
import logging
from datetime import datetime
from flask import Flask, request
import requests

logging.basicConfig(level=logging.INFO)
app = Flask(__name__)

TOKEN = "8649027781:AAGfMeKFm8xcaOhZ8J8Xo4Wn220Y2zn1cgM"
TELEGRAM_API_URL = f"https://api.telegram.org/bot{TOKEN}"

STORES = {
    "rossiyskaya": {
        "name": "O'pen на Российской",
        "address": "Краснодар, Российская ул., 267/6 лит В",
        "area": "Музыкальный м-н, Прикубанский округ, Краснодар, 350024",
        "coordinates": {"lat": 45.092222, "lon": 39.007168},
        "admin_id": os.environ.get("ADMIN_CHAT_ID_ROSSIYSKAYA")
    },
    "zhigulenko": {
        "name": "O'pen на Жигуленко",
        "address": "Краснодар, ул. Евгении Жигуленко, 25к1",
        "area": "им. Петра Метальникова м-н, Прикубанский округ, Краснодар, 350087",
        "coordinates": {"lat": 45.100637, "lon": 39.002361},
        "admin_id": os.environ.get("ADMIN_CHAT_ID_ZHIGULENKO")
    }
}

orders = {}

def send_message(chat_id, text, reply_markup=None):
    url = f"{TELEGRAM_API_URL}/sendMessage"
    data = {"chat_id": chat_id, "text": text, "parse_mode": "Markdown"}
    if reply_markup:
        data["reply_markup"] = json.dumps(reply_markup)
    try:
        response = requests.post(url, json=data)
        return response.ok
    except Exception as e:
        logging.error(f"Send error: {e}")
        return False

def edit_message(chat_id, message_id, text, reply_markup=None):
    url = f"{TELEGRAM_API_URL}/editMessageText"
    data = {"chat_id": chat_id, "message_id": message_id, "text": text, "parse_mode": "Markdown"}
    if reply_markup:
        data["reply_markup"] = json.dumps(reply_markup)
    try:
        response = requests.post(url, json=data)
        return response.ok
    except Exception as e:
        logging.error(f"Edit error: {e}")
        return False

def send_to_admin(admin_id, user_name, user_id, order_data):
    if not admin_id:
        logging.error("Admin ID is missing")
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
    return send_message(admin_id, message)

def get_main_keyboard():
    return {
        "inline_keyboard": [
            [{"text": "🏪 O'pen на Российской", "callback_data": "store_rossiyskaya"}],
            [{"text": "🏪 O'pen на Жигуленко", "callback_data": "store_zhigulenko"}],
            [{"text": "📍 Показать магазины на карте", "callback_data": "show_stores_map"}]
        ]
    }

def get_location_keyboard(store_code):
    return {
        "inline_keyboard": [
            [{"text": "📍 Показать на карте", "callback_data": f"location_{store_code}"}]
        ]
    }

def get_confirmation_keyboard():
    return {
        "inline_keyboard": [
            [{"text": "✅ Подтвердить заказ", "callback_data": "confirm"}],
            [{"text": "✏️ Изменить заказ", "callback_data": "edit"}]
        ]
    }

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

def process_message(chat_id, text, user_id, user_name):
    if user_id in orders:
        state = orders[user_id].get("state", "store_selected")
        
        if state == "awaiting_files":
            if text == "/done":
                if orders[user_id].get("files"):
                    orders[user_id]["state"] = "awaiting_comment"
                    send_message(chat_id, "📝 Теперь напишите *комментарий* к заказу.\n\nПример: цветная печать, 2 экземпляра, скрепить")
                else:
                    send_message(chat_id, "❌ Вы ещё не загрузили ни одного файла.")
            else:
                send_message(chat_id, "❓ Нажмите /done, когда загрузите все файлы.")
            return
        
        elif state == "awaiting_comment":
            orders[user_id]["comment"] = text
            orders[user_id]["state"] = "awaiting_time"
            send_message(chat_id, "⏰ Напишите *время получения*.\n\nПример: *сегодня 18:30* или *завтра 14:00*")
            return
        
        elif state == "awaiting_time":
            orders[user_id]["pickup_time"] = text
            orders[user_id]["state"] = "confirming"
            
            files_list = "\n".join([f"• {f}" for f in orders[user_id]["files"]])
            summary = f"""📋 *Ваш заказ:*

🏪 *Магазин:* {orders[user_id]['store_name']}
📍 *Адрес:* {orders[user_id]['store_address']}

📁 *Файлы ({len(orders[user_id]['files'])} шт.):*
{files_list}

💬 *Комментарий:* {orders[user_id]['comment']}
⏰ *Время получения:* {text}

*Всё верно?*
"""
            send_message(chat_id, summary, reply_markup=get_confirmation_keyboard())
            return
    
    if text == "/start":
        user_name = user_name or "Пользователь"
        welcome = f"""🖨️ *Добро пожаловать в OPEN Маркет канцелярских товаров*

Здравствуйте, {user_name}!

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
        send_message(chat_id, welcome, reply_markup=get_main_keyboard())
    else:
        send_message(chat_id, "❓ Напишите /start, чтобы начать")

def process_callback(chat_id, callback_data, message_id, user_id, user_name):
    if callback_data.startswith("store_"):
        store_code = callback_data.replace("store_", "")
        store = STORES[store_code]
        
        orders[user_id] = {
            "store_code": store_code,
            "store_name": store["name"],
            "store_address": store["address"],
            "files": [],
            "state": "awaiting_files",
            "admin_id": store["admin_id"]
        }
        
        text = f"✅ *Выбран магазин:* {store['name']}\n\n📍 *Адрес:* {store['address']}\n\nЗагрузите файлы для печати. Когда закончите, нажмите /done"
        edit_message(chat_id, message_id, text, reply_markup=get_location_keyboard(store_code))
        
    elif callback_data == "show_stores_map":
        map_url = get_all_stores_map_url()
        stores_text = "\n\n".join([
            f"🏪 *{store['name']}*\n📍 {store['address']}\n🗺️ {store['area']}"
            for store in STORES.values()
        ])
        text = f"🗺️ *Расположение магазинов:*\n\n{stores_text}\n\n[Открыть карту]({map_url})"
        edit_message(chat_id, message_id, text, reply_markup=get_main_keyboard())
        
    elif callback_data.startswith("location_"):
        store_code = callback_data.replace("location_", "")
        map_url = get_single_store_map_url(store_code)
        store = STORES[store_code]
        text = f"📍 *{store['name']} на карте:*\n\n[Открыть в Яндекс.Картах]({map_url})"
        edit_message(chat_id, message_id, text)
        send_message(chat_id, "Вернитесь к заказу и нажмите /start для оформления")
        
    elif callback_data == "confirm":
        order_data = orders.get(user_id, {})
        admin_id = order_data.get("admin_id")
        if admin_id:
            success = send_to_admin(admin_id, user_name, user_id, order_data)
            if success:
                text = f"✅ *Заказ подтверждён!*\n\nПриходите в {order_data['pickup_time']} по адресу:\n{order_data['store_address']}\n\n📍 [Показать на карте]({get_single_store_map_url(order_data['store_code'])})\n\nСпасибо, что выбрали OPEN! 🖨️"
            else:
                text = "❌ Ошибка при отправке заказа. Попробуйте позже."
        else:
            text = "❌ Ошибка: не указан администратор магазина. Пожалуйста, сообщите разработчику."
        edit_message(chat_id, message_id, text)
        orders.pop(user_id, None)
        
    elif callback_data == "edit":
        edit_message(chat_id, message_id, "✏️ Напишите /start, чтобы создать новый заказ")
        orders.pop(user_id, None)

def process_file(chat_id, user_id, file_name):
    if user_id not in orders:
        orders[user_id] = {"state": "awaiting_files", "files": []}
    if "files" not in orders[user_id]:
        orders[user_id]["files"] = []
    orders[user_id]["files"].append(file_name)
    send_message(chat_id, f"✅ Файл *{file_name}* получен! Всего: {len(orders[user_id]['files'])}.\nНажмите /done, когда закончите")

@app.route(f"/webhook/{TOKEN}", methods=["POST"])
def webhook():
    try:
        data = request.get_json(force=True)
        
        if "message" in data:
            msg = data["message"]
            chat_id = msg["chat"]["id"]
            user_id = msg["from"]["id"]
            user_name = msg["from"].get("first_name", "Пользователь")
            
            if "text" in msg:
                text = msg["text"]
                process_message(chat_id, text, user_id, user_name)
            elif "document" in msg:
                file_name = msg["document"]["file_name"]
                process_file(chat_id, user_id, file_name)
            elif "photo" in msg:
                process_file(chat_id, user_id, "photo.jpg")
                
        elif "callback_query" in data:
            callback = data["callback_query"]
            chat_id = callback["message"]["chat"]["id"]
            message_id = callback["message"]["message_id"]
            callback_data = callback["data"]
            user_id = callback["from"]["id"]
            user_name = callback["from"].get("first_name", "Пользователь")
            process_callback(chat_id, callback_data, message_id, user_id, user_name)
            
        return "ok", 200
    except Exception as e:
        logging.error(f"Webhook error: {e}")
        return "error", 500

@app.route("/health")
def health():
    return "OK", 200

@app.route("/")
def index():
    return "OPEN Print Bot works"

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
