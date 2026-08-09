from __future__ import annotations

import asyncio
import json
import os
import threading
from datetime import datetime
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any

import discord
import pytz
from flask import Flask, jsonify
from discord.ext import commands


DATA_FILE = Path(__file__).resolve().parent / "du_lieu_tien.json"
LEGACY_KEY = "__legacy_balance__"
DATA_LOCK = asyncio.Lock()
VIETNAM_TIMEZONE = pytz.timezone("Asia/Ho_Chi_Minh")

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(
    command_prefix="!",
    intents=intents,
)

app = Flask(__name__)


@app.route("/", methods=["GET"])
def health_check():
    return jsonify(
        {
            "status": "ok",
            "service": "HungAnhAutoCash",
        }
    ), 200


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"}), 200


def keep_alive() -> None:
    """Run the lightweight Flask health server without blocking Discord."""
    port = int(os.getenv("PORT", "8000"))

    app.run(
        host="0.0.0.0",
        port=port,
        debug=False,
        use_reloader=False,
    )


def lay_thoi_gian_vn() -> str:
    return datetime.now(VIETNAM_TIMEZONE).strftime(
        "%H:%M:%S - %d/%m/%Y"
    )


def tao_user_data(tong_tien: int = 0) -> dict[str, Any]:
    return {
        "tong_tien": tong_tien,
        "lich_su": [],
    }


def chuan_hoa_user_data(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise RuntimeError("Dữ liệu tài khoản không hợp lệ.")

    try:
        tong_tien = int(value.get("tong_tien", 0))
    except (TypeError, ValueError) as error:
        raise RuntimeError(
            "Số dư trong dữ liệu tài khoản không hợp lệ."
        ) from error

    lich_su = value.get("lich_su", [])

    if not isinstance(lich_su, list):
        raise RuntimeError(
            "Lịch sử giao dịch trong dữ liệu tài khoản không hợp lệ."
        )

    return {
        "tong_tien": tong_tien,
        "lich_su": lich_su,
    }


def doc_du_lieu() -> dict[str, dict[str, Any]]:
    """
    Read all user accounts and migrate the previous single-balance format.
    """
    if not DATA_FILE.exists():
        return {}

    try:
        with DATA_FILE.open("r", encoding="utf-8") as file:
            raw_data = json.load(file)
    except (OSError, json.JSONDecodeError) as error:
        raise RuntimeError(
            f"Không thể đọc dữ liệu từ {DATA_FILE.name}. "
            "Hãy kiểm tra file dữ liệu."
        ) from error

    if not isinstance(raw_data, dict):
        raise RuntimeError("Định dạng dữ liệu quỹ không hợp lệ.")

    # Preserve the old global balance until the first user invokes a command.
    if "tong_tien" in raw_data:
        return {
            LEGACY_KEY: chuan_hoa_user_data(raw_data)
        }

    return {
        str(user_id): chuan_hoa_user_data(user_data)
        for user_id, user_data in raw_data.items()
    }


def luu_du_lieu(
    data: dict[str, dict[str, Any]]
) -> None:
    """
    Write data atomically so an interrupted write cannot corrupt the file.
    """
    DATA_FILE.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    temporary_path: Path | None = None

    try:
        with NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=DATA_FILE.parent,
            prefix=f"{DATA_FILE.name}.",
            suffix=".tmp",
            delete=False,
        ) as temporary:
            json.dump(
                data,
                temporary,
                ensure_ascii=False,
                indent=4,
            )
            temporary.write("\n")
            temporary_path = Path(temporary.name)

        os.replace(
            temporary_path,
            DATA_FILE,
        )

    except OSError:
        if temporary_path is not None:
            temporary_path.unlink(
                missing_ok=True
            )

        raise


def lay_user_data(
    data: dict[str, dict[str, Any]],
    user_id: int,
) -> dict[str, Any]:
    """
    Get an account, assigning the old global balance
    to the first user who uses it.
    """
    user_key = str(user_id)

    if user_key not in data:
        legacy_data = data.pop(
            LEGACY_KEY,
            None,
        )

        data[user_key] = (
            legacy_data
            or tao_user_data()
        )

    return data[user_key]


def them_giao_dich(
    user_data: dict[str, Any],
    loai: str,
    so_tien: int,
    du_sau: int,
    thoi_gian: str,
) -> None:
    user_data["lich_su"].append(
        {
            "loai": loai,
            "so_tien": so_tien,
            "du_sau": du_sau,
            "thoi_gian": thoi_gian,
        }
    )


def format_money(amount: int) -> str:
    return f"{amount:,}"


async def send_error(
    ctx: commands.Context,
    message: str,
) -> None:
    await ctx.send(
        f"⚠️ {message}"
    )


@bot.event
async def on_ready() -> None:
    if bot.user is not None:
        print(
            f"Bot {bot.user.name} đã sẵn sàng phục vụ!"
        )


@bot.event
async def on_disconnect() -> None:
    print(
        "Discord bị mất kết nối; "
        "đang tự động kết nối lại..."
    )


@bot.event
async def on_resumed() -> None:
    print(
        "Discord đã kết nối lại thành công."
    )


@bot.command()
async def setup(
    ctx: commands.Context,
    so_tien: int,
) -> None:
    """
    Khởi tạo số tiền ban đầu cho tài khoản Discord hiện tại.
    """
    async with DATA_LOCK:
        data = doc_du_lieu()

        user_data = lay_user_data(
            data,
            ctx.author.id,
        )

        user_data["tong_tien"] = so_tien
        thoi_gian = lay_thoi_gian_vn()

        them_giao_dich(
            user_data,
            "Khởi tạo",
            so_tien,
            so_tien,
            thoi_gian,
        )

        luu_du_lieu(data)

    embed = discord.Embed(
        title="⚙️ THIẾT LẬP QUỸ TIỀN TỆ BAN ĐẦU",
        description=(
            f"🎉 Chúc mừng "
            f"**{ctx.author.display_name}** "
            "đã bắt đầu hành trình quản lý tài chính!"
        ),
        color=discord.Color.blue(),
    )

    embed.add_field(
        name="👤 Người thực hiện",
        value=ctx.author.mention,
        inline=True,
    )

    embed.add_field(
        name="💰 Số tiền khởi tạo",
        value=f"**{format_money(so_tien)} VNĐ**",
        inline=True,
    )

    embed.add_field(
        name="⏰ Thời gian thực (VN)",
        value=f"`{thoi_gian}`",
        inline=False,
    )

    embed.set_footer(
        text=(
            "Chúc bạn luôn dồi dào sức khỏe "
            "và tài lộc ngày càng gia tăng! 💪✨"
        )
    )

    await ctx.send(embed=embed)


@bot.command()
async def cong(
    ctx: commands.Context,
    so_tien: int,
) -> None:
    """
    Cộng tiền vào tài khoản Discord hiện tại.
    """
    async with DATA_LOCK:
        data = doc_du_lieu()

        user_data = lay_user_data(
            data,
            ctx.author.id,
        )

        user_data["tong_tien"] += so_tien
        thoi_gian = lay_thoi_gian_vn()

        them_giao_dich(
            user_data,
            "Cộng tiền",
            so_tien,
            user_data["tong_tien"],
            thoi_gian,
        )

        luu_du_lieu(data)

    embed = discord.Embed(
        title="🎉 CHÚC MỪNG TÀI KHOẢN TĂNG BĂNG BĂNG! 🚀",
        description=(
            f"Tuyệt vời quá! "
            f"**{ctx.author.display_name}** "
            "lại vừa tích lũy thêm được một khoản tiền mới nè!"
        ),
        color=discord.Color.green(),
    )

    embed.add_field(
        name="👤 Chủ tài khoản",
        value=ctx.author.mention,
        inline=False,
    )

    embed.add_field(
        name="💵 Số tiền cộng thêm",
        value=f"**+{format_money(so_tien)} VNĐ**",
        inline=True,
    )

    embed.add_field(
        name="💳 Tổng số dư hiện có",
        value=(
            f"**{format_money(user_data['tong_tien'])} VNĐ**"
        ),
        inline=True,
    )

    embed.add_field(
        name="⏰ Ngày giờ ghi nhận (VN)",
        value=f"`{thoi_gian}`",
        inline=False,
    )

    embed.set_footer(
        text=(
            "Chúc bạn dồi dào sức khỏe, "
            "làm ăn phát tài và tiền vào như nước nhé! 🥳💰"
        )
    )

    await ctx.send(embed=embed)


@bot.command()
async def tru(
    ctx: commands.Context,
    so_tien: int,
) -> None:
    """
    Trừ tiền khỏi tài khoản; số dư có thể xuống âm.
    """
    async with DATA_LOCK:
        data = doc_du_lieu()

        user_data = lay_user_data(
            data,
            ctx.author.id,
        )

        user_data["tong_tien"] -= so_tien
        thoi_gian = lay_thoi_gian_vn()

        them_giao_dich(
            user_data,
            "Trừ tiền",
            so_tien,
            user_data["tong_tien"],
            thoi_gian,
        )

        luu_du_lieu(data)

    embed = discord.Embed(
        title="😭 ÔI KHÔNG... LẠI VỪA RƠI MẤT TIỀN RỒI! 💸",
        description=(
            f"Ví của **{ctx.author.display_name}** "
            "vừa nhẹ đi một chút rồi, thương quá đi mất..."
        ),
        color=discord.Color.red(),
    )

    embed.add_field(
        name="👤 Chủ tài khoản",
        value=ctx.author.mention,
        inline=False,
    )

    embed.add_field(
        name="📉 Số tiền bị trừ",
        value=f"**-{format_money(so_tien)} VNĐ**",
        inline=True,
    )

    embed.add_field(
        name="💳 Số dư còn lại",
        value=(
            f"**{format_money(user_data['tong_tien'])} VNĐ**"
        ),
        inline=True,
    )

    embed.add_field(
        name="⏰ Ngày giờ chi tiêu (VN)",
        value=f"`{thoi_gian}`",
        inline=False,
    )

    embed.set_footer(
        text=(
            "Nhớ giữ gìn sức khỏe và chi tiêu tiết kiệm, "
            "hợp lý hơn nha! 🥺💔"
        )
    )

    await ctx.send(embed=embed)


@bot.command()
async def xem(
    ctx: commands.Context,
) -> None:
    """
    Xem số dư của tài khoản Discord hiện tại.
    """
    async with DATA_LOCK:
        data = doc_du_lieu()

        user_data = lay_user_data(
            data,
            ctx.author.id,
        )

        thoi_gian = lay_thoi_gian_vn()
        luu_du_lieu(data)

    embed = discord.Embed(
        title="📊 BÁO CÁO TÀI CHÍNH HIỆN TẠI",
        description=(
            "Đây là tổng số tiền hiện có trong quỹ của "
            f"**{ctx.author.display_name}**:"
        ),
        color=discord.Color.gold(),
    )

    embed.add_field(
        name="👤 Người dùng",
        value=ctx.author.mention,
        inline=True,
    )

    embed.add_field(
        name="💰 Tổng số dư tài khoản",
        value=(
            f"**{format_money(user_data['tong_tien'])} VNĐ**"
        ),
        inline=True,
    )

    embed.add_field(
        name="⏰ Cập nhật lúc (VN)",
        value=f"`{thoi_gian}`",
        inline=False,
    )

    embed.set_footer(
        text=(
            "Cố gắng duy trì phong độ "
            "và gia tăng thu nhập mỗi ngày nhé! 🌟"
        )
    )

    await ctx.send(embed=embed)


@bot.command()
async def lichsu(
    ctx: commands.Context,
) -> None:
    """
    Hiển thị tối đa 10 giao dịch gần nhất.
    """
    async with DATA_LOCK:
        data = doc_du_lieu()

        user_data = lay_user_data(
            data,
            ctx.author.id,
        )

        lich_su = user_data.get(
            "lich_su",
            [],
        )

        luu_du_lieu(data)

    embed = discord.Embed(
        title="📜 LỊCH SỬ THU CHI TÀI CHÍNH",
        description=(
            f"Lịch sử giao dịch gần nhất của "
            f"**{ctx.author.display_name}**:"
        ),
        color=discord.Color.purple(),
    )

    if not lich_su:
        embed.add_field(
            name="Chưa có lịch sử",
            value="Bạn chưa thực hiện giao dịch nào!",
            inline=False,
        )
    else:
        noi_dung = ""

        for index, giao_dich in enumerate(
            reversed(lich_su[-10:]),
            1,
        ):
            loai = giao_dich.get(
                "loai",
                "Giao dịch",
            )

            dau = (
                "+"
                if loai in {"Cộng tiền", "Khởi tạo"}
                else "-"
            )

            noi_dung += (
                f"**{index}. [{loai}]** "
                f"`{giao_dich.get('thoi_gian', 'Không rõ')}`\n"
            )

            noi_dung += (
                f"└ Biến động: "
                f"`{dau}{giao_dich.get('so_tien', 0):,} VNĐ` "
                f"➔ Số dư: "
                f"`{giao_dich.get('du_sau', 0):,} VNĐ`\n\n"
            )

        embed.add_field(
            name="Các giao dịch gần đây",
            value=noi_dung,
            inline=False,
        )

    embed.set_footer(
        text=(
            f"Hiện tại có tổng cộng "
            f"{len(lich_su)} giao dịch trong lịch sử."
        )
    )

    await ctx.send(embed=embed)


@bot.command()
async def resetchitieu(
    ctx: commands.Context,
) -> None:
    """
    Đặt số dư và lịch sử của tài khoản hiện tại về 0.
    """
    async with DATA_LOCK:
        data = doc_du_lieu()

        data[str(ctx.author.id)] = tao_user_data()
        luu_du_lieu(data)

        thoi_gian = lay_thoi_gian_vn()

    embed = discord.Embed(
        title="🔄 ĐÃ RESET LỊCH SỬ THU CHI",
        description=(
            f"Toàn bộ số dư và lịch sử thu chi của "
            f"**{ctx.author.display_name}** "
            "đã được đặt lại về 0!"
        ),
        color=discord.Color.orange(),
    )

    embed.add_field(
        name="👤 Thực hiện bởi",
        value=ctx.author.mention,
        inline=False,
    )

    embed.add_field(
        name="⏰ Thời gian thực hiện (VN)",
        value=f"`{thoi_gian}`",
        inline=False,
    )

    embed.set_footer(
        text=(
            "Bạn có thể bắt đầu lại bằng lệnh "
            "!setup hoặc !cong nhé!"
        )
    )

    await ctx.send(embed=embed)


@bot.event
async def on_command_error(
    ctx: commands.Context,
    error: commands.CommandError,
) -> None:
    if isinstance(error, commands.CommandNotFound):
        return

    if isinstance(error, commands.MissingRequiredArgument):
        command_name = (
            ctx.command.name
            if ctx.command
            else "lệnh"
        )

        await send_error(
            ctx,
            f"Thiếu số tiền. Dùng `!{command_name} <số tiền>`.",
        )
        return

    if isinstance(error, commands.BadArgument):
        await send_error(
            ctx,
            (
                "Số tiền phải là một số nguyên, "
                "ví dụ: `150000` hoặc `-150000`."
            ),
        )
        return

    await send_error(
        ctx,
        "Đã xảy ra lỗi khi xử lý lệnh. Vui lòng thử lại.",
    )


async def run_discord_bot(token: str) -> None:
    """
    Keep the Discord client alive and retry unexpected session failures.
    """
    while True:
        try:
            # discord.py handles websocket reconnects internally.
            await bot.start(
                token,
                reconnect=True,
            )

            if bot.is_closed():
                return

            print(
                "Discord client đã dừng ngoài dự kiến; "
                "đang khởi động lại..."
            )

        except discord.LoginFailure:
            print(
                "DISCORD_BOT_TOKEN không hợp lệ "
                "hoặc đã hết hiệu lực."
            )
            raise

        except (
            discord.DiscordException,
            OSError,
        ) as error:
            print(
                f"Discord gặp lỗi kết nối: {error!r}. "
                "Thử lại sau 1 giây..."
            )

            if not bot.is_closed():
                await bot.close()

            await asyncio.sleep(1)


def main() -> None:
    token = os.getenv(
        "DISCORD_BOT_TOKEN"
    )

    if not token:
        raise RuntimeError(
            "Thiếu DISCORD_BOT_TOKEN trong Replit Secrets."
        )

    threading.Thread(
        target=keep_alive,
        name="flask-keep-alive",
        daemon=True,
    ).start()

    asyncio.run(
        run_discord_bot(token)
    )


if __name__ == "__main__":
    main()
