from __future__ import annotations

import asyncio
from datetime import datetime
import json
import os
from pathlib import Path
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
DATA_LOCK = asyncio.Lock()
VIETNAM_TIMEZONE = pytz.timezone('Asia/Ho_Chi_Minh')

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix='!', intents=intents)


def lay_thoi_gian_vn() -> str:
  return datetime.now(VIETNAM_TIMEZONE).strftime('%H:%M:%S - %d/%m/%Y')


async def doc_du_lieu() -> dict[str, Any]:
  async with DATA_LOCK:
    if not DATA_FILE.exists():
      return {}
    try:
      with open(DATA_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)
    except Exception:
      return {}


async def luu_du_lieu(data: dict[str, Any]):
  async with DATA_LOCK:
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
      json.dump(data, f, ensure_ascii=False, indent=4)


@bot.event
async def on_ready():
  print(f'Bot đã đăng nhập thành công: {bot.user}')


@bot.command(name='setup')
async def setup(ctx: commands.Context, so_tien: int):
  user_id = str(ctx.author.id)
  data = await doc_du_lieu()

  data[user_id] = {
      'tong_tien': so_tien,
      'lich_su': [{
          'loai': 'SETUP',
          'so_tien': so_tien,
          'thoi_gian': lay_thoi_gian_vn(),
      }],
  }
  await luu_du_lieu(data)

  embed = discord.Embed(
      title='⚙️ THIẾT LẬP QUỸ TIỀN TỆ BAN ĐẦU', color=discord.Color.blue()
  )
  embed.description = f'🎉 Chúc mừng **{ctx.author.display_name}** đã bắt đầu hành trình quản lý tài chính!'
  embed.add_field(
      name='👤 Người thực hiện', value=ctx.author.mention, inline=False
  )
  embed.add_field(
      name='💰 Số tiền khởi tạo', value=f'{so_tien:,} VNĐ', inline=False
  )
  embed.add_field(
      name='⏰ Thời gian thực (VN)',
      value=f'`{lay_thoi_gian_vn()}`',
      inline=False,
  )
  embed.set_footer(
      text='Chúc bạn luôn dồi dào sức khỏe và tài lộc ngày càng gia tăng! 💪✨'
  )

  await ctx.send(embed=embed)


@bot.command(name='xem')
async def xem(ctx: commands.Context):
  user_id = str(ctx.author.id)
  data = await doc_du_lieu()

  if user_id not in data:
    await ctx.send(
        f'❌ {ctx.author.mention} Bạn chưa thiết lập quỹ tiền! Dùng lệnh'
        ' `!setup <số_tiền>` để bắt đầu.'
    )
    return

  tong_tien = data[user_id].get('tong_tien', 0)
  embed = discord.Embed(
      title='📊 THÔNG TIN TÀI CHÍNH', color=discord.Color.green()
  )
  embed.add_field(
      name='👤 Chủ tài khoản', value=ctx.author.mention, inline=False
  )
  embed.add_field(
      name='💵 Tổng số tiền hiện tại', value=f'**{tong_tien:,} VNĐ**', inline=False
  )
  embed.add_field(
      name='⏰ Cập nhật lúc', value=f'`{lay_thoi_gian_vn()}`', inline=False
  )
  await ctx.send(embed=embed)


@bot.command(name='lichsu')
async def lichsu(ctx: commands.Context):
  user_id = str(ctx.author.id)
  data = await doc_du_lieu()

  if user_id not in data or not data[user_id].get('lich_su'):
    await ctx.send(f'❌ {ctx.author.mention} Chưa có lịch sử giao dịch nào.')
    return

  lich_su_list = data[user_id]['lich_su'][-5:]  # Lấy 5 giao dịch gần nhất
  noi_dung = ''
  for item in lich_su_list:
    noi_dung += f"• **{item['loai']}**: {item['so_tien']:,} VNĐ (`{item['thoi_gian']}`)\n"

  embed = discord.Embed(
      title='📜 LỊCH SỬ GIAO DỊCH GẦN ĐÂY',
      description=noi_dung,
      color=discord.Color.gold(),
  )
  await ctx.send(embed=embed)


# --- KÍCH HOẠT CHẠY BOT ---
TOKEN = os.getenv('DISCORD_TOKEN')

if __name__ == '__main__':
  if TOKEN:
    bot.run(TOKEN)
  else:
    print('Lỗi: Chưa cài đặt DISCORD_TOKEN trong Environment của Render!')
  
