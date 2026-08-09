from __future__ import annotations

import asyncio
from datetime import datetime
import json
import os
from pathlib import Path
from tempfile import NamedTemporaryFile
import threading
from typing import Any

import discord
from discord.ext import commands
from flask import Flask, jsonify
import pytz

# --- WEB SERVER FLASK GIỮ RENDER ONLINE ---
app = Flask(__name__)


@app.route('/', methods=['GET'])
@app.route('/health', methods=['GET'])
def health_check():
  return jsonify({'status': 'ok', 'service': 'HungAnhAutoCash'}), 200


def run_flask():
  port = int(os.environ.get('PORT', 10000))
  from werkzeug.serving import run_simple

  run_simple('0.0.0.0', port, app, use_reloader=False, use_debugger=False)


flask_thread = threading.Thread(target=run_flask, daemon=True)
flask_thread.start()

# --- DISCORD BOT LOGIC ---
DATA_FILE = Path(__file__).resolve().parent / 'du_lieu_tien.json'
LEGACY_KEY = '_legacy_balance_'
DATA_LOCK = asyncio.Lock()
VIETNAM_TIMEZONE = pytz.timezone('Asia/Ho_Chi_Minh')

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(
    command_prefix='!',
    intents=intents,
)


def lay_thoi_gian_vn() -> str:
  return datetime.now(VIETNAM_TIMEZONE).strftime('%H:%M:%S - %d/%m/%Y')


def tao_user_data(tong_tien: int = 0) -> dict[str, Any]:
  return {
      'tong_tien': tong_tien,
      'lich_su': [],
  }


def chuan_hoa_user_data(value: Any) -> dict[str, Any]:
  if not isinstance(value, dict):
    raise RuntimeError('Dữ liệu tài khoản không hợp lệ.')
  try:
    tong_tien = int(value.get('tong_tien', 0))
  except (TypeError, ValueError) as error:
    raise RuntimeError('Tổng tiền không hợp lệ.') from error

  lich_su_raw = value.get('lich_su', [])
  lich_su = lich_su_raw if isinstance(lich_su_raw, list) else []
  return {
      'tong_tien': tong_tien,
      'lich_su': lich_su,
  }


@bot.event
async def on_ready():
  print(f'Bot đã đăng nhập thành công: {bot.user}')


# --- KÍCH HOẠT CHẠY BOT ---
TOKEN = os.getenv('DISCORD_TOKEN')

if __name__ == '__main__':
  if TOKEN:
    bot.run(TOKEN)
  else:
    print('Lỗi: Chưa cài đặt DISCORD_TOKEN trong Environment của Render!')
    
