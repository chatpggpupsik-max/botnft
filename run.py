import subprocess
import os
import sys
import threading
import time
from flask import Flask

def run_flask():
    # Импортируем внутри чтобы избежать конфликтов
    import server
    port = int(os.environ.get('PORT', 10000))
    server.app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)

def run_bot():
    import asyncio
    import bot
    asyncio.run(bot.main())

if __name__ == '__main__':
    print(f"Starting services on port {os.environ.get('PORT', 10000)}...")
    
    # Flask в отдельном потоке
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    
    # Ждём запуска Flask
    time.sleep(5)
    print("✅ All services started")
    
    # Бот
    run_bot()
