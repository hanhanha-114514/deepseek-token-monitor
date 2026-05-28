# DeepSeek Token Monitor ⚡ | DeepSeek Token 监控面板

> Real-time DeepSeek API token consumption & balance monitor with a cyberpunk-themed desktop dashboard.
> 实时监控 DeepSeek API Token 消耗与余额的桌面面板，赛博朋克科技风 UI。

---

## ✨ Features | 功能

| Feature | 功能 |
|---------|------|
| 💰 Real-time balance query via DeepSeek API | 通过 DeepSeek API 实时查询余额 |
| 🔥 Today / Monthly cost tracking | 今日 / 本月累计消耗追踪 |
| 📈 Balance waveform chart (24h) | 余额波形图（最近 24 小时） |
| 📊 Token cost delta waveform | Token 消耗增量波形 |
| 📌 Always-on-top window | 窗口置顶 |
| ⏱ Adjustable refresh interval (5s~) | 可调刷新间隔（最短 5 秒） |
| 🎨 Dark cyberpunk UI | 暗黑科技风 UI |

## 🚀 Quick Start | 快速开始

### Prerequisites | 环境要求
- Python 3.10+
- Windows / macOS / Linux

### Install | 安装

```bash
pip install requests matplotlib
```

### Run | 运行

```bash
python deepseek_monitor.py
```

Or double-click `启动监控.bat` (Windows only).
或双击 `启动监控.bat`（仅 Windows）。

### Setup | 配置

1. Click **"⚙ 设置 API Key"** button
2. Paste your DeepSeek API Key from [platform.deepseek.com](https://platform.deepseek.com)
3. Click save — monitoring starts automatically

---

1. 点击 **"⚙ 设置 API Key"** 按钮
2. 填入 [platform.deepseek.com](https://platform.deepseek.com) 获取的 API Key
3. 保存后自动开始监控

## 📸 Screenshots | 截图

<!-- Add screenshots here -->

## 🛠 Tech Stack | 技术栈

| Tech | 技术 |
|------|------|
| Python 3.12 | Python 3.12 |
| Tkinter GUI | Tkinter 图形界面 |
| Matplotlib charts | Matplotlib 图表 |
| DeepSeek Balance API | DeepSeek 余额接口 |
| Requests | HTTP 请求 |

## 📁 Project Structure | 项目结构

```
deepseek-token-monitor/
├── deepseek_monitor.py   # Main application | 主程序
├── 启动监控.bat           # Windows launcher | Windows 启动脚本
├── .gitignore
└── README.md
```

## 📝 License

MIT
