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

# --- WEB SERVER GIỮ ONLINE ---
app = Flask(__name__)
@app.route('/')
def health(): return jsonify({'status': 'ok'})

def run_flask():
    port = int(os.environ.get('PORT', 10000))
    from werkzeug.serving import run_simple
    run_simple('0.0.0.0', port, app, use_reloader=False)

threading.Thread(target=run_flask, daemon=True).start()

# --- BOT LOGIC ---
DATA_FILE = Path(__file__).resolve().parent / 'du_lieu_tien.json'
VIETNAM_TIMEZONE = pytz.timezone('Asia/Ho_Chi_Minh')
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

def lay_thoi_gian_vn(): return datetime.now(VIETNAM_TIMEZONE).strftime('%H:%M:%S - %d/%m/%Y')

async def doc_du_lieu():
    if not DATA_FILE.exists(): return {}
    with open(DATA_FILE, 'r', encoding='utf-8') as f: return json.load(f)

async def luu_du_lieu(data):
    with open(DATA_FILE, 'w', encoding='utf-8') as f: json.dump(data, f, ensure_ascii=False, indent=4)

@bot.command(name='setup')
async def setup(ctx, so_tien: int):
    data = await doc_du_lieu()
    data[str(ctx.author.id)] = {'tong_tien': so_tien, 'lich_su': [{'loai': 'KHOI_TAO', 'so_tien': so_tien, 'thoi_gian': lay_thoi_gian_vn()}]}
    await luu_du_lieu(data)
    await ctx.send(f"✅ Đã thiết lập quỹ cho {ctx.author.mention} với {so_tien:,} VNĐ")

@bot.command(name='xem')
async def xem(ctx):
    data = await doc_du_lieu()
    user = str(ctx.author.id)
    if user not in data:
        await ctx.send("❌ Bạn chưa thiết lập quỹ! Dùng lệnh `!setup <số_tiền>` để bắt đầu.")
        return
    embed = discord.Embed(title='📊 BÁO CÁO TÀI CHÍNH', color=discord.Color.gold())
    embed.add_field(name='💰 Tổng dư', value=f"**{data[user]['tong_tien']:,} VNĐ**", inline=False)
    embed.set_footer(text=f"Cập nhật lúc: {lay_thoi_gian_vn()}")
    await ctx.send(embed=embed)

@bot.command(name='cong')
async def cong(ctx, so_tien: int):
    data = await doc_du_lieu()
    user = str(ctx.author.id)
    if user not in data: return await ctx.send("❌ Chưa setup!")
    data[user]['tong_tien'] += so_tien
    await luu_du_lieu(data)
    await ctx.send(f"✅ Đã cộng {so_tien:,} VNĐ. Tổng: {data[user]['tong_tien']:,} VNĐ")

@bot.command(name='tru')
async def tru(ctx, so_tien: int):
    data = await doc_du_lieu()
    user = str(ctx.author.id)
    if user not in data: return await ctx.send("❌ Chưa setup!")
    data[user]['tong_tien'] -= so_tien
    await luu_du_lieu(data)
    await ctx.send(f"✅ Đã trừ {so_tien:,} VNĐ. Còn: {data[user]['tong_tien']:,} VNĐ")

bot.run(os.getenv('DISCORD_TOKEN'))
