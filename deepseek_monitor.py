# -*- coding: utf-8 -*-
"""
DeepSeek Token Monitor — 实时消耗监控面板
功能：余额查询 / 今日用量 / 本月消耗 / 剩余余额 / 实时波形图 / 置顶窗口
"""

import tkinter as tk
from tkinter import ttk, messagebox
import json
import os
import sys

# 解决 matplotlib 缓存目录权限问题
os.environ.setdefault('MPLCONFIGDIR', os.path.join(os.environ.get('TEMP', os.path.expanduser('~')), 'matplotlib_cache'))
os.makedirs(os.environ['MPLCONFIGDIR'], exist_ok=True)

import time
import threading
from datetime import datetime, timedelta
from collections import deque

import requests
import matplotlib
matplotlib.use("TkAgg")
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import matplotlib.ticker as mticker
import numpy as np

# ─── 配置 ─────────────────────────────────────────────
CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ds_monitor_config.json")
HISTORY_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ds_monitor_history.json")

DEEPSEEK_BALANCE_URL = "https://api.deepseek.com/user/balance"
DEEPSEEK_USAGE_URL = "https://api.deepseek.com/platform/usage/overview"

POLL_INTERVAL = 30  # 秒

# 科技风配色
COLORS = {
    "bg_dark":       "#080c14",
    "bg_card":       "#111827",
    "bg_input":      "#1a1f2e",
    "accent_cyan":   "#00e5ff",
    "accent_purple": "#7c4dff",
    "accent_green":  "#00e676",
    "accent_orange": "#ff9100",
    "accent_red":    "#ff1744",
    "text_primary":  "#e0e0e0",
    "text_secondary":"#9e9e9e",
    "text_dim":      "#616161",
    "border":        "#1e293b",
    "glow_cyan":     "#004d5e",
    "glow_purple":   "#2a1458",
}

FONT_TITLE = ("Microsoft YaHei UI", 11, "bold")
FONT_LABEL = ("Microsoft YaHei UI", 9)
FONT_VALUE = ("Consolas", 18, "bold")
FONT_SMALL = ("Microsoft YaHei UI", 8)
FONT_MONO  = ("Consolas", 10)

# DeepSeek 模型定价 (CNY / 百万 tokens)
PRICING = {
    "deepseek-chat":      {"input": 1.0,  "output": 4.0},
    "deepseek-reasoner":  {"input": 4.0,  "output": 16.0},
}


# ─── 数据存储 ──────────────────────────────────────────
def load_config():
    defaults = {"api_key": "", "always_on_top": True, "poll_interval": POLL_INTERVAL}
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            defaults.update(data)
    return defaults


def save_config(cfg):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)


def load_history():
    defaults = {
        "balance_history": [],       # [(ts, balance), ...]
        "usage_history": [],         # [(ts, tokens_used), ...]
        "today_usage": 0,
        "month_usage": 0,
        "last_balance": None,
        "last_update": None,
    }
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            defaults.update(data)
    return defaults


def save_history(h):
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(h, f, indent=2, ensure_ascii=False, default=str)


# ─── DeepSeek API 客户端 ───────────────────────────────
class DeepSeekAPI:
    def __init__(self, api_key=""):
        self.api_key = api_key
        self.session = requests.Session()
        self.session.headers.update({
            "Accept": "application/json",
            "User-Agent": "DeepSeek-Monitor/1.0"
        })

    def set_key(self, key):
        self.api_key = key

    def _headers(self):
        return {"Authorization": f"Bearer {self.api_key}"}

    def get_balance(self):
        """获取账户余额"""
        if not self.api_key:
            return None
        try:
            resp = self.session.get(DEEPSEEK_BALANCE_URL, headers=self._headers(), timeout=15)
            if resp.status_code == 200:
                data = resp.json()
                if data.get("is_available") and data.get("balance_infos"):
                    info = data["balance_infos"][0]
                    return {
                        "currency": info.get("currency", "CNY"),
                        "total_balance": float(info.get("total_balance", "0")),
                        "topped_up_balance": float(info.get("topped_up_balance", "0")),
                        "granted_balance": float(info.get("granted_balance", "0")),
                    }
            return None
        except Exception:
            return None

    def get_usage(self):
        """尝试获取用量统计"""
        if not self.api_key:
            return None
        try:
            today = datetime.now().strftime("%Y-%m-%d")
            month_start = datetime.now().strftime("%Y-%m-01")
            params = {"start_date": month_start, "end_date": today}
            resp = self.session.get(DEEPSEEK_USAGE_URL, headers=self._headers(),
                                    params=params, timeout=15)
            if resp.status_code == 200:
                data = resp.json()
                return data
            return None
        except Exception:
            return None


# ─── 波形图画布 ────────────────────────────────────────
class WaveformChart:
    def __init__(self, parent, title="Waveform", line_color=None, y_fmt="¥%.2f",
                 fill_from_zero=False):
        self.parent = parent
        self.max_points = 120
        self.line_color = line_color or COLORS["accent_cyan"]
        self.fill_from_zero = fill_from_zero

        self.figure = Figure(figsize=(5, 2.2), dpi=100, facecolor=COLORS["bg_card"])
        self.figure.subplots_adjust(left=0.08, right=0.95, top=0.85, bottom=0.20)

        self.ax = self.figure.add_subplot(111)
        self.ax.set_facecolor(COLORS["bg_card"])
        self.ax.spines["top"].set_visible(False)
        self.ax.spines["right"].set_visible(False)
        self.ax.spines["left"].set_color(COLORS["border"])
        self.ax.spines["bottom"].set_color(COLORS["border"])
        self.ax.tick_params(colors=COLORS["text_secondary"], labelsize=7)
        self.ax.yaxis.set_major_formatter(mticker.FormatStrFormatter(y_fmt))
        self.ax.set_title(title, color=COLORS["text_secondary"],
                          fontsize=8, loc="left", pad=2)

        self.line, = self.ax.plot([], [], color=self.line_color, linewidth=1.5,
                                  alpha=0.9, zorder=3)
        self.fill = None
        self.ax.grid(True, color=COLORS["border"], linewidth=0.4, alpha=0.5)

        self.canvas = FigureCanvasTkAgg(self.figure, master=parent)
        self.canvas.draw()
        self.widget = self.canvas.get_tk_widget()

    def update(self, history, value_index=1):
        """history: [(ts, val), ...]"""
        if not history:
            return
        recent = history[-self.max_points:]
        xs = list(range(len(recent)))
        ys = [p[value_index] for p in recent]
        labels = []
        for p in recent:
            try:
                t = datetime.fromisoformat(p[0])
                labels.append(t.strftime("%H:%M"))
            except Exception:
                labels.append("")

        self.line.set_data(xs, ys)

        if self.fill:
            self.fill.remove()
        if ys:
            baseline = 0 if self.fill_from_zero else min(ys) * 0.98
            self.fill = self.ax.fill_between(xs, baseline, ys,
                                             color=self.line_color, alpha=0.12)

        self.ax.set_xlim(0, max(len(xs) - 1, 1))
        if ys:
            y_min = min(ys)
            y_max = max(ys)
            if y_max == y_min:
                y_min -= 0.005
                y_max += 0.005
            margin = max((y_max - y_min) * 0.1, 0.002)
            self.ax.set_ylim(y_min - margin, y_max + margin)

        if len(labels) > 0:
            step = max(1, len(labels) // 5)
            tick_positions = list(range(0, len(labels), step))
            self.ax.set_xticks(tick_positions)
            self.ax.set_xticklabels([labels[i] for i in tick_positions], rotation=0)

        self.canvas.draw_idle()


# ─── 主应用 ─────────────────────────────────────────────
class DeepSeekMonitor:
    def __init__(self):
        self.config = load_config()
        self.api = DeepSeekAPI(self.config.get("api_key", ""))
        self.history = load_history()
        self.poll_interval = self.config.get("poll_interval", POLL_INTERVAL)
        self.running = True
        self.last_balance = self.history.get("last_balance")

        # 构建 UI
        self.root = tk.Tk()
        self.root.title("DeepSeek Monitor")
        self.root.geometry("460x820")
        self.root.minsize(400, 720)
        self.root.configure(bg=COLORS["bg_dark"])
        self.root.attributes("-topmost", self.config.get("always_on_top", True))

        # 图标(emoji 兜底)
        try:
            self.root.iconbitmap(default="")
        except Exception:
            pass

        self._build_ui()
        self._apply_initial_data()

        # 启动后台轮询
        self.poll_thread = threading.Thread(target=self._poll_loop, daemon=True)
        self.poll_thread.start()

        # 关闭事件
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    # ── UI 构建 ─────────────────────────────────────
    def _build_ui(self):
        # ── 标题栏 ──
        title_frame = tk.Frame(self.root, bg=COLORS["bg_dark"], height=52)
        title_frame.pack(fill="x", padx=16, pady=(14, 0))
        title_frame.pack_propagate(False)

        title_label = tk.Label(title_frame, text="⚡ DeepSeek Monitor",
                               font=("Microsoft YaHei UI", 14, "bold"),
                               fg=COLORS["accent_cyan"], bg=COLORS["bg_dark"])
        title_label.pack(side="left")

        self.status_dot = tk.Canvas(title_frame, width=10, height=10,
                                    bg=COLORS["bg_dark"], highlightthickness=0)
        self.status_dot.pack(side="right", padx=(0, 4))
        self._dot = self.status_dot.create_oval(1, 1, 9, 9,
                                                 fill=COLORS["text_dim"], outline="")

        self.status_text = tk.Label(title_frame, text="● 未连接",
                                    font=FONT_SMALL, fg=COLORS["text_dim"],
                                    bg=COLORS["bg_dark"])
        self.status_text.pack(side="right", padx=(0, 12))

        # ── 余额卡片 ──
        balance_frame = tk.Frame(self.root, bg=COLORS["bg_card"],
                                 highlightthickness=1,
                                 highlightbackground=COLORS["accent_cyan"],
                                 highlightcolor=COLORS["accent_cyan"])
        balance_frame.pack(fill="x", padx=16, pady=12)

        inner = tk.Frame(balance_frame, bg=COLORS["bg_card"])
        inner.pack(padx=20, pady=16, fill="x")

        tk.Label(inner, text="剩余余额", font=FONT_LABEL,
                 fg=COLORS["text_secondary"], bg=COLORS["bg_card"]).pack(anchor="w")

        self.balance_value = tk.Label(inner, text="¥ ---",
                                      font=("Consolas", 28, "bold"),
                                      fg=COLORS["accent_green"], bg=COLORS["bg_card"])
        self.balance_value.pack(anchor="w", pady=(2, 0))

        self.balance_detail = tk.Label(inner, text="充值余额: ---  |  赠送余额: ---",
                                       font=FONT_SMALL, fg=COLORS["text_dim"],
                                       bg=COLORS["bg_card"])
        self.balance_detail.pack(anchor="w", pady=(4, 0))

        # ── 用量卡片行 ──
        cards_frame = tk.Frame(self.root, bg=COLORS["bg_dark"])
        cards_frame.pack(fill="x", padx=16, pady=(0, 8))

        # 今日消耗 Token
        card1 = tk.Frame(cards_frame, bg=COLORS["bg_card"],
                         highlightthickness=1, highlightbackground=COLORS["border"])
        card1.pack(side="left", fill="both", expand=True, padx=(0, 4))
        tk.Label(card1, text="📊 今日消耗", font=FONT_LABEL,
                 fg=COLORS["text_secondary"], bg=COLORS["bg_card"]).pack(anchor="w", padx=14, pady=(12, 0))
        self.today_tokens = tk.Label(card1, text="---",
                                     font=("Consolas", 15, "bold"),
                                     fg=COLORS["text_primary"], bg=COLORS["bg_card"])
        self.today_tokens.pack(anchor="w", padx=14, pady=(2, 12))

        # 今日金额
        card2 = tk.Frame(cards_frame, bg=COLORS["bg_card"],
                         highlightthickness=1, highlightbackground=COLORS["border"])
        card2.pack(side="left", fill="both", expand=True, padx=2)
        tk.Label(card2, text="💰 今日金额", font=FONT_LABEL,
                 fg=COLORS["text_secondary"], bg=COLORS["bg_card"]).pack(anchor="w", padx=14, pady=(12, 0))
        self.today_cost = tk.Label(card2, text="¥ ---",
                                   font=("Consolas", 15, "bold"),
                                   fg=COLORS["accent_orange"], bg=COLORS["bg_card"])
        self.today_cost.pack(anchor="w", padx=14, pady=(2, 12))

        # 本月消耗
        card3 = tk.Frame(cards_frame, bg=COLORS["bg_card"],
                         highlightthickness=1, highlightbackground=COLORS["border"])
        card3.pack(side="left", fill="both", expand=True, padx=(4, 0))
        tk.Label(card3, text="📅 本月消耗", font=FONT_LABEL,
                 fg=COLORS["text_secondary"], bg=COLORS["bg_card"]).pack(anchor="w", padx=14, pady=(12, 0))
        self.month_cost = tk.Label(card3, text="¥ ---",
                                   font=("Consolas", 15, "bold"),
                                   fg=COLORS["accent_purple"], bg=COLORS["bg_card"])
        self.month_cost.pack(anchor="w", padx=14, pady=(2, 12))

        # ── 余额波形图 ──
        chart_label = tk.Label(self.root, text="📈 余额波形",
                               font=FONT_LABEL, fg=COLORS["text_secondary"],
                               bg=COLORS["bg_dark"])
        chart_label.pack(anchor="w", padx=20, pady=(8, 2))

        chart_container = tk.Frame(self.root, bg=COLORS["bg_card"],
                                   highlightthickness=1,
                                   highlightbackground=COLORS["border"])
        chart_container.pack(fill="both", expand=True, padx=16, pady=(0, 4))

        self.balance_chart = WaveformChart(chart_container, title="Balance (CNY)",
                                           line_color=COLORS["accent_cyan"],
                                           y_fmt="¥%.2f")
        self.balance_chart.widget.pack(fill="both", expand=True, padx=6, pady=6)

        # ── 消耗波形图 ──
        usage_label = tk.Label(self.root, text="🔥 Token 消耗波形",
                               font=FONT_LABEL, fg=COLORS["text_secondary"],
                               bg=COLORS["bg_dark"])
        usage_label.pack(anchor="w", padx=20, pady=(6, 2))

        usage_container = tk.Frame(self.root, bg=COLORS["bg_card"],
                                   highlightthickness=1,
                                   highlightbackground=COLORS["border"])
        usage_container.pack(fill="both", expand=True, padx=16, pady=(0, 8))

        self.usage_chart = WaveformChart(usage_container, title="Token Cost Delta (CNY/poll)",
                                         line_color=COLORS["accent_purple"],
                                         y_fmt="¥%.4f",
                                         fill_from_zero=True)
        self.usage_chart.widget.pack(fill="both", expand=True, padx=6, pady=6)

        # ── 底部控制栏 ──
        ctrl_frame = tk.Frame(self.root, bg=COLORS["bg_dark"], height=44)
        ctrl_frame.pack(fill="x", padx=16, pady=(0, 10))
        ctrl_frame.pack_propagate(False)

        self.topmost_var = tk.BooleanVar(value=self.config.get("always_on_top", True))
        topmost_cb = tk.Checkbutton(ctrl_frame, text="置顶", variable=self.topmost_var,
                                    command=self._toggle_topmost,
                                    font=FONT_SMALL, fg=COLORS["text_secondary"],
                                    bg=COLORS["bg_dark"], selectcolor=COLORS["bg_card"],
                                    activebackground=COLORS["bg_dark"],
                                    activeforeground=COLORS["accent_cyan"])
        topmost_cb.pack(side="left", padx=(0, 8))

        # 轮询间隔
        tk.Label(ctrl_frame, text="刷新(s):", font=FONT_SMALL,
                 fg=COLORS["text_dim"], bg=COLORS["bg_dark"]).pack(side="left")

        self.interval_var = tk.StringVar(value=str(self.poll_interval))
        interval_entry = tk.Entry(ctrl_frame, textvariable=self.interval_var,
                                  width=4, font=FONT_SMALL,
                                  fg=COLORS["text_primary"], bg=COLORS["bg_input"],
                                  insertbackground=COLORS["accent_cyan"],
                                  relief="flat", borderwidth=0)
        interval_entry.pack(side="left", padx=(4, 16))

        tk.Button(ctrl_frame, text="应用", command=self._apply_interval,
                  font=FONT_SMALL, fg=COLORS["bg_dark"], bg=COLORS["accent_cyan"],
                  activebackground=COLORS["accent_cyan"],
                  relief="flat", padx=10, pady=2, borderwidth=0,
                  cursor="hand2").pack(side="left", padx=(0, 8))

        tk.Button(ctrl_frame, text="⚙ 设置 API Key",
                  command=self._open_settings,
                  font=FONT_SMALL, fg=COLORS["accent_cyan"], bg=COLORS["bg_card"],
                  activebackground=COLORS["bg_input"],
                  relief="flat", padx=12, pady=3, borderwidth=0,
                  cursor="hand2").pack(side="right")

        self.update_time = tk.Label(ctrl_frame, text="",
                                    font=FONT_SMALL, fg=COLORS["text_dim"],
                                    bg=COLORS["bg_dark"])
        self.update_time.pack(side="right", padx=(0, 12))

    # ── 设置窗口 ─────────────────────────────────────
    def _open_settings(self):
        win = tk.Toplevel(self.root)
        win.title("API 设置")
        win.geometry("420x240")
        win.configure(bg=COLORS["bg_card"])
        win.resizable(False, False)
        win.transient(self.root)
        win.grab_set()

        try:
            win.attributes("-topmost", True)
        except Exception:
            pass

        # 标题
        tk.Label(win, text="🔑 DeepSeek API Key", font=FONT_TITLE,
                 fg=COLORS["accent_cyan"], bg=COLORS["bg_card"]).pack(pady=(16, 10))

        tk.Label(win, text="在 platform.deepseek.com → API Keys 获取",
                 font=FONT_SMALL, fg=COLORS["text_dim"], bg=COLORS["bg_card"]).pack()

        key_var = tk.StringVar(value=self.config.get("api_key", ""))
        key_entry = tk.Entry(win, textvariable=key_var, show="•",
                             font=("Consolas", 10), fg=COLORS["text_primary"],
                             bg=COLORS["bg_input"], insertbackground=COLORS["accent_cyan"],
                             relief="flat", borderwidth=0)
        key_entry.pack(fill="x", padx=24, pady=12, ipady=6)

        btn_frame = tk.Frame(win, bg=COLORS["bg_card"])
        btn_frame.pack(pady=(4, 12))

        def save_key():
            new_key = key_var.get().strip()
            self.config["api_key"] = new_key
            save_config(self.config)
            self.api.set_key(new_key)
            self._set_status("connecting", "连接中...")
            threading.Thread(target=self._do_poll, daemon=True).start()
            win.destroy()

        tk.Button(btn_frame, text="保存并连接", command=save_key,
                  font=FONT_LABEL, fg=COLORS["bg_dark"], bg=COLORS["accent_cyan"],
                  activebackground=COLORS["accent_cyan"],
                  relief="flat", padx=20, pady=6, borderwidth=0,
                  cursor="hand2").pack(side="left", padx=4)

        tk.Button(btn_frame, text="取消", command=win.destroy,
                  font=FONT_LABEL, fg=COLORS["text_secondary"], bg=COLORS["bg_input"],
                  activebackground=COLORS["bg_input"],
                  relief="flat", padx=20, pady=6, borderwidth=0,
                  cursor="hand2").pack(side="left", padx=4)

    # ── 逻辑方法 ─────────────────────────────────────
    def _toggle_topmost(self):
        on = self.topmost_var.get()
        self.root.attributes("-topmost", on)
        self.config["always_on_top"] = on
        save_config(self.config)

    def _apply_interval(self):
        try:
            v = int(self.interval_var.get())
            if v < 5:
                v = 5
                self.interval_var.set("5")
            self.poll_interval = v
            self.config["poll_interval"] = v
            save_config(self.config)
        except ValueError:
            self.interval_var.set(str(self.poll_interval))

    def _set_status(self, state, text):
        colors_map = {
            "connected": COLORS["accent_green"],
            "connecting": COLORS["accent_orange"],
            "error": COLORS["accent_red"],
            "disconnected": COLORS["text_dim"],
        }
        color = colors_map.get(state, COLORS["text_dim"])
        self.status_dot.itemconfig(self._dot, fill=color)
        self.status_text.config(text=text, fg=color)

    def _do_poll(self):
        """执行一次轮询"""
        balance = self.api.get_balance()
        now = datetime.now()

        if balance:
            total = balance["total_balance"]
            ts = now.isoformat()

            # 计算用量（基于余额变化，排除充值导致的增加）
            prev_balance = self.history.get("last_balance")
            if prev_balance is not None:
                diff = prev_balance - total
                # diff > 0: 余额减少 = 消耗
                # diff < 0: 余额增加 = 可能是充值，不计入消耗
                if 0 < diff < 10000:  # 合理消耗范围
                    self.history["today_usage"] = self.history.get("today_usage", 0) + diff
                    self.history["month_usage"] = self.history.get("month_usage", 0) + diff
                elif diff < -0.5:
                    # 余额明显增加（充值），重置消耗累计
                    pass  # 保留历史累计，不重置

            # 重置当日/当月统计
            today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

            # 更新余额历史
            self.history.setdefault("balance_history", [])
            self.history["balance_history"].append([ts, total])

            # 记录本次消耗 delta
            if prev_balance is not None:
                delta = prev_balance - total
                if 0 < delta < 10000:
                    self.history.setdefault("usage_history", [])
                    self.history["usage_history"].append([ts, delta])

            # 清理旧数据 (24h)
            for key in ["balance_history", "usage_history"]:
                if key in self.history:
                    self.history[key] = [
                        p for p in self.history[key]
                        if datetime.fromisoformat(p[0]) > now - timedelta(hours=24)
                    ]

            self.history["last_balance"] = total
            self.history["last_update"] = ts

            # 更新 UI (主线程)
            self.root.after(0, self._update_ui, balance)
            self._set_status("connected", "● 已连接")
        else:
            self._set_status("error", "● 连接失败")
            self.root.after(0, self._update_time_label, now)

        save_history(self.history)

    def _update_ui(self, balance):
        total = balance["total_balance"]
        topped = balance["topped_up_balance"]
        granted = balance["granted_balance"]

        self.balance_value.config(text=f"¥ {total:.2f}")
        self.balance_detail.config(
            text=f"充值余额: ¥{topped:.2f}  |  赠送余额: ¥{granted:.2f}"
        )

        # 余额颜色
        if total > 50:
            self.balance_value.config(fg=COLORS["accent_green"])
        elif total > 10:
            self.balance_value.config(fg=COLORS["accent_orange"])
        else:
            self.balance_value.config(fg=COLORS["accent_red"])

        # 今日用量（实际金额 = 余额差值，无需估算 token 数）
        today_usage = self.history.get("today_usage", 0)
        # 显示估算 tokens（假设均价 ¥1/M）
        est_tokens = today_usage * 1000000 / 1.0 if today_usage > 0 else 0
        self.today_tokens.config(text=f"~{est_tokens:,.0f} tokens")
        self.today_cost.config(text=f"¥ {today_usage:.4f}")

        # 本月消耗
        month_usage = self.history.get("month_usage", 0)
        self.month_cost.config(text=f"¥ {month_usage:.4f}")

        # 更新余额波形
        self.balance_chart.update(self.history.get("balance_history", []))
        # 更新消耗波形
        self.usage_chart.update(self.history.get("usage_history", []))

        now = datetime.now()
        self._update_time_label(now)

    def _update_time_label(self, now):
        self.update_time.config(text=f"更新: {now.strftime('%H:%M:%S')}")

    def _apply_initial_data(self):
        """应用历史数据显示"""
        h = self.history
        if h.get("last_balance"):
            balance = {
                "total_balance": h["last_balance"],
                "topped_up_balance": 0,
                "granted_balance": 0,
            }
            self._update_ui(balance)

        # 初始状态
        api_key = self.config.get("api_key", "")
        if api_key:
            self._set_status("connecting", "● 连接中...")

    def _poll_loop(self):
        """后台轮询线程"""
        # 首次延迟 1 秒让 UI 渲染
        time.sleep(1)
        if self.config.get("api_key"):
            self._do_poll()

        while self.running:
            time.sleep(self.poll_interval)
            if not self.running:
                break
            if self.config.get("api_key"):
                self._do_poll()

    def _on_close(self):
        self.running = False
        save_history(self.history)
        self.root.destroy()

    def run(self):
        self.root.mainloop()


# ─── 入口 ────────────────────────────────────────────────
if __name__ == "__main__":
    try:
        app = DeepSeekMonitor()
        app.run()
    except Exception as e:
        import traceback
        msg = f"Startup Error:\n{traceback.format_exc()}"
        log_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "monitor_error.log")
        with open(log_path, "w", encoding="utf-8") as f:
            f.write(msg)
        try:
            import tkinter.messagebox as mb
            mb.showerror("DeepSeek Monitor Error", msg)
        except Exception:
            print(msg)
        sys.exit(1)
