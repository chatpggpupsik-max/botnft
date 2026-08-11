import subprocess
import os
import sys
import threading
import time

def run_flask():
    from server import app
    port = int(os.environ.get('PORT', 10000))
    # Важно: запускаем без debug=True, без reloader
    app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)

def run_bot():
    import asyncio
    from bot import main
    asyncio.run(main())

if __name__ == '__main__':
    # Flask в отдельном потоке
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    
    # Даём Flask время запуститься
    time.sleep(3)
    print("✅ Flask запущен, порт открыт")
    
    # Бот в основном потоке
    run_bot()
