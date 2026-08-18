from __future__ import annotations
import os
import json
import pytz
import asyncio
import threading
from pathlib import Path
from datetime import datetime
import discord
from discord.ext import commands
from discord.ui import Button, View
from flask import Flask, jsonify

# --- MÃ XÁC NHẬN ADMIN ---
ADMIN_SECRET_CODE = "HungLeeDeptry"

# --- WEB SERVER GIỮ ONLINE ---
app = Flask(__name__)

@app.route('/')
def health():
    return jsonify({'service': 'HungAnhAutoCash', 'status': 'ok'})

def run_flask():
    port = int(os.environ.get('PORT', 10000))
    from werkzeug.serving import run_simple
    run_simple('0.0.0.0', port, app, use_reloader=False)

threading.Thread(target=run_flask, daemon=True).start()

# --- BOT LOGIC ---
DATA_FILE = Path(__file__).resolve().parent / 'du_lieu_tien.json'
ADMIN_FILE = Path(__file__).resolve().parent / 'danh_sach_admin.json'
VIETNAM_TIMEZONE = pytz.timezone('Asia/Ho_Chi_Minh')

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

def lay_thoi_gian_vn():
    return datetime.now(VIETNAM_TIMEZONE).strftime('%H:%M:%S - %d/%m/%Y')

async def doc_du_lieu():
    if not DATA_FILE.exists():
        return {}
    with open(DATA_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)

async def luu_du_lieu(data):
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

async def doc_danh_sach_admin():
    if not ADMIN_FILE.exists():
        return []
    with open(ADMIN_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)

async def luu_danh_sach_admin(admins):
    with open(ADMIN_FILE, 'w', encoding='utf-8') as f:
        json.dump(admins, f, ensure_ascii=False, indent=4)

# --- VIEW PHÂN TRANG CHO LỊCH SỬ ---
class HistoryPaginator(View):
    def __init__(self, author, history, per_page=10):
        super().__init__(timeout=60)
        self.author = author
        self.history = list(reversed(history))
        self.per_page = per_page
        self.current_page = 0
        self.total_pages = max(1, (len(self.history) + per_page - 1) // per_page)
        self.update_buttons()

    def update_buttons(self):
        self.children[0].disabled = (self.current_page == 0)
        self.children[1].disabled = (self.current_page >= self.total_pages - 1)

    def get_embed(self):
        embed = discord.Embed(
            title="📜 LỊCH SỬ GIAO DỊCH GẦN ĐÂY",
            color=discord.Color.purple()
        )
        
        start = self.current_page * self.per_page
        end = start + self.per_page
        page_items = self.history[start:end]

        description_lines = []
        for idx, item in enumerate(page_items, start=start + 1):
            loai_str = "CỘNG" if item['loai'] in ['CONG', 'KHOI_TAO'] else ("TRỪ" if item['loai'] == 'TRU' else "ADMIN SET")
            li_do = item.get('li_do', 'Không có')
            so_tien_fmt = f"`{item['so_tien']:,} VNĐ`"
            thoi_gian_fmt = f"*`{item['thoi_gian']}`*"
            
            line = f"**{idx}.** **{loai_str} ({li_do}):** {so_tien_fmt} - {thoi_gian_fmt}"
            description_lines.append(line)

        embed.description = "\n\n".join(description_lines)
        embed.set_footer(text=f"Trang {self.current_page + 1}/{self.total_pages} • Tổng số giao dịch: {len(self.history)}")
        return embed

    @discord.ui.button(label="◀ Trang trước", style=discord.ButtonStyle.primary)
    async def prev_button(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id != self.author.id:
            return await interaction.response.send_message("Bạn không thể dùng nút này!", ephemeral=True)
        self.current_page -= 1
        self.update_buttons()
        await interaction.response.edit_message(embed=self.get_embed(), view=self)

    @discord.ui.button(label="Trang sau ▶", style=discord.ButtonStyle.primary)
    async def next_button(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id != self.author.id:
            return await interaction.response.send_message("Bạn không thể dùng nút này!", ephemeral=True)
        self.current_page += 1
        self.update_buttons()
        await interaction.response.edit_message(embed=self.get_embed(), view=self)

# --- LỆNH NHẬN QUYỀN ADMIN ---
@bot.command(name='admin')
async def nhan_quyen_admin(ctx, code: str = None):
    try:
        await ctx.message.delete()
    except Exception:
        pass

    if not code:
        return

    admins = await doc_danh_sach_admin()

    if ctx.author.id in admins:
        return await ctx.send(f"👑 {ctx.author.mention} Bạn đã là Admin rồi!", delete_after=5)

    if len(admins) >= 2:
        return await ctx.send("❌ Đã đủ số lượng 2 Admin quy định!", delete_after=5)

    if code == ADMIN_SECRET_CODE:
        admins.append(ctx.author.id)
        await luu_danh_sach_admin(admins)
        await ctx.send(f"🎉 **Chúc mừng {ctx.author.mention} đã trở thành Admin thành công!**", delete_after=10)

# --- CÁC LỆNH DÀNH CHO BẠN BÈ ---

@bot.command(name='setup')
async def setup(ctx, so_tien: int):
    data = await doc_du_lieu()
    data[str(ctx.author.id)] = {
        'tong_tien': so_tien,
        'lich_su': [{'loai': 'KHOI_TAO', 'so_tien': so_tien, 'li_do': 'Thiết lập ban đầu', 'thoi_gian': lay_thoi_gian_vn()}]
    }
    await luu_du_lieu(data)
    await ctx.send(f"✅ Đã thiết lập quỹ cho {ctx.author.mention} với số tiền khởi tạo: **{so_tien:,} VNĐ**")

@bot.command(name='xem')
async def xem(ctx):
    data = await doc_du_lieu()
    user_id = str(ctx.author.id)
    
    if user_id not in data:
        await ctx.send(f"❌ {ctx.author.mention} Bạn chưa thiết lập quỹ tiền! Dùng lệnh `!setup <số_tiền>` để bắt đầu.")
        return

    embed = discord.Embed(
        title="📊 BÁO CÁO TÀI CHÍNH HIỆN TẠI",
        description=f"Đây là tổng số tiền hiện có trong quỹ của **{ctx.author.display_name}**:",
        color=discord.Color.gold()
    )
    embed.add_field(name="👤 Người dùng", value=ctx.author.mention, inline=False)
    embed.add_field(name="💰 Tổng số dư tài khoản", value=f"**{data[user_id]['tong_tien']:,} VNĐ**", inline=False)
    embed.add_field(name="⏰ Cập nhật lúc (VN)", value=f"`{lay_thoi_gian_vn()}`", inline=False)
    embed.set_footer(text="Cố gắng duy trì phong độ và gia tăng thu nhập mỗi ngày nhé! 🌟")

    await ctx.send(embed=embed)

@bot.command(name='cong')
async def cong(ctx, so_tien: int, *, li_do: str = "Không có"):
    data = await doc_du_lieu()
    user_id = str(ctx.author.id)
    
    if user_id not in data:
        return await ctx.send("❌ Bạn chưa khởi tạo quỹ! Dùng lệnh `!setup <số_tiền>` trước.")

    data[user_id]['tong_tien'] += so_tien
    thoi_gian_now = lay_thoi_gian_vn()
    data[user_id]['lich_su'].append({'loai': 'CONG', 'so_tien': so_tien, 'li_do': li_do, 'thoi_gian': thoi_gian_now})
    await luu_du_lieu(data)
    
    embed = discord.Embed(
        title="📈 CỘNG TIỀN VÀO QUỸ",
        color=discord.Color.green()
    )
    embed.add_field(name="💵 Số tiền cộng", value=f"+{so_tien:,} VNĐ", inline=False)
    embed.add_field(name="📝 Lý do", value=li_do, inline=False)
    embed.add_field(name="💰 Tổng dư mới", value=f"**{data[user_id]['tong_tien']:,} VNĐ**", inline=False)
    embed.add_field(name="⏰ Thời gian", value=f"`{thoi_gian_now}`", inline=False)

    await ctx.send(embed=embed)

@bot.command(name='tru')
async def tru(ctx, so_tien: int, *, li_do: str = "Không có"):
    data = await doc_du_lieu()
    user_id = str(ctx.author.id)
    
    if user_id not in data:
        return await ctx.send("❌ Bạn chưa khởi tạo quỹ! Dùng lệnh `!setup <số_tiền>` trước.")

    data[user_id]['tong_tien'] -= so_tien
    thoi_gian_now = lay_thoi_gian_vn()
    data[user_id]['lich_su'].append({'loai': 'TRU', 'so_tien': so_tien, 'li_do': li_do, 'thoi_gian': thoi_gian_now})
    await luu_du_lieu(data)
    
    embed = discord.Embed(
        title="📉 TRỪ TIỀN TỪ QUỸ",
        color=discord.Color.red()
    )
    embed.add_field(name="💸 Số tiền trừ", value=f"-{so_tien:,} VNĐ", inline=False)
    embed.add_field(name="📝 Lý do", value=li_do, inline=False)
    embed.add_field(name="💰 Tổng dư còn lại", value=f"**{data[user_id]['tong_tien']:,} VNĐ**", inline=False)
    embed.add_field(name="⏰ Thời gian", value=f"`{thoi_gian_now}`", inline=False)

    await ctx.send(embed=embed)

@bot.command(name='lichsu')
async def lichsu(ctx):
    data = await doc_du_lieu()
    user_id = str(ctx.author.id)
    
    if user_id not in data or 'lich_su' not in data[user_id] or not data[user_id]['lich_su']:
        return await ctx.send("❌ Chưa có dữ liệu lịch sử giao dịch!")

    paginator = HistoryPaginator(ctx.author, data[user_id]['lich_su'], per_page=10)
    await ctx.send(embed=paginator.get_embed(), view=paginator)

@bot.command(name='reset')
async def reset(ctx):
    data = await doc_du_lieu()
    user_id = str(ctx.author.id)
    
    if user_id in data:
        del data[user_id]
        await luu_du_lieu(data)
        await ctx.send(f"⚠️ Đã xóa toàn bộ dữ liệu quỹ tiền và lịch sử của {ctx.author.mention}!")
    else:
        await ctx.send("❌ Bạn chưa có dữ liệu nào để reset.")

# --- LỆNH ADMIN ĐẶC QUYỀN ---
@bot.command(name='setmoney')
async def setmoney(ctx, member: discord.Member, so_tien_moi: int):
    admins = await doc_danh_sach_admin()
    
    if ctx.author.id not in admins:
        return

    data = await doc_du_lieu()
    user_id = str(member.id)

    if user_id not in data:
        data[user_id] = {'tong_tien': 0, 'lich_su': []}

    data[user_id]['tong_tien'] = so_tien_moi
    data[user_id]['lich_su'].append({
        'loai': 'ADMIN_SET',
        'so_tien': so_tien_moi,
        'li_do': f'Admin {ctx.author.display_name} điều chỉnh',
        'thoi_gian': lay_thoi_gian_vn()
    })

    await luu_du_lieu(data)
    
    await ctx.send(
        f"👑 **[ADMIN]** Đã chỉnh sửa số dư của {member.mention} thành **{so_tien_moi:,} VNĐ**!",
        delete_after=3
    )

bot.run(os.getenv('DISCORD_TOKEN'))
    
