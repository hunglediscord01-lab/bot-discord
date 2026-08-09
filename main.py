from __future__ import annotations

import asyncio
from datetime import datetime
import json
import os
from pathlib import Path
from tempfile import NamedTemporaryFile
from threading import Thread
from typing import Any

import discord
from discord.ext import commands
from flask import Flask, jsonify
import pytz

# --- Khởi tạo Web Server Flask để Render không bị sleep & chạy đúng Cổng (Port) ---
app = Flask(__name__)


@app.route("/", methods=["GET"])
def health_check():
  return jsonify({"status": "ok", "service": "HungAnhAutoCash"}), 200


@app.route("/health", methods=["GET"])
def health():
  return jsonify({"status": "ok"}), 200


def run():
  # Render yêu cầu dùng cổng PORT động do hệ thống cấp
  port = int(os.environ.get("PORT", 10000))
  app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)


def keep_alive() -> None:
  t = Thread(target=run)
  t.daemon = True
  t.start()


# Chạy Web Server Flask
keep_alive()

# --- Phần Code Bot bên dưới giữ nguyên cấu trúc cũ của bạn ---
DATA_FILE = Path(__file__).resolve().parent / "du_lieu_tien.json"
LEGACY_KEY = "_legacy_balance_"
DATA_LOCK = asyncio.Lock()
VIETNAM_TIMEZONE = pytz.timezone("Asia/Ho_Chi_Minh")

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(
    command_prefix="!",
    intents=intents,
)


def lay_thoi_gian_vn() -> str:
  return datetime.now(VIETNAM_TIMEZONE).strftime("%H:%M:%S - %d/%m/%Y")


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
    raise RuntimeError("Tổng tiền không hợp lệ.") from error

  lich_su_raw = value.get("lich_su", [])
  lich_su = lich_su_raw if isinstance(lich_su_raw, list) else []
  return {
      "tong_tien": tong_tien,
      "lich_su": lich_su,
  }


# (Các đoạn code logic bot xử lý file du_lieu_tien.json và lệnh discord tiếp tục phía dưới)
