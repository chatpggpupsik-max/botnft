import subprocess
import os
import sys
import threading
import time

# Запускаем Flask в отдельном потоке
def run_flask():
    from server import app
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)

# Запускаем бота
def run_bot():
    import asyncio
    from bot import main
    asyncio.run(main())

if __name__ == '__main__':
    # Flask в фоне
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    
    # Бот в основном потоке
    run_bot()
