"""Optional Telegram delivery. Off by default; credentials stay in the environment."""
import json
import os
from pathlib import Path
import requests
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / '.env')

def send_telegram_update():
    if os.environ.get('ENABLE_TELEGRAM', 'false').lower() != 'true':
        print('Telegram delivery is disabled.')
        return
    token = os.environ.get('TELEGRAM_BOT_TOKEN')
    if not token:
        raise ValueError('Set TELEGRAM_BOT_TOKEN locally')
    subscribers_file = ROOT / 'data' / 'bot_subscribers.json'
    subscribers = json.loads(subscribers_file.read_text()) if subscribers_file.exists() else []
    for chat_id in subscribers:
        for path in (ROOT / 'data' / 'gantt and tracking table').glob('gantt_*.png'):
            with path.open('rb') as image:
                response = requests.post(f'https://api.telegram.org/bot{token}/sendPhoto', data={'chat_id': chat_id}, files={'photo': image}, timeout=30)
            if not response.ok:
                raise RuntimeError(f'Telegram delivery failed (HTTP {response.status_code})')

if __name__ == '__main__':
    send_telegram_update()
