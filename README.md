# DeepSeek Token Monitor ⚡

实时监控 DeepSeek API 的 Token 消耗与余额，科技风桌面面板。

## 功能

- 💰 **实时余额** — 通过 DeepSeek API 查询账户余额
- 🔥 **消耗追踪** — 今日/本月累计消耗金额
- 📈 **余额波形图** — 最近 24 小时余额走势
- 📊 **消耗波形图** — 每次轮询的费用增量波形
- 📌 **置顶窗口** — 始终悬浮在其他窗口之上
- ⏱ **可调刷新** — 默认 30 秒，最短 5 秒

## 使用方法

```bash
# 安装依赖
pip install requests matplotlib

# 启动
python deepseek_monitor.py
```

或双击 `启动监控.bat`

首次使用点击 **"⚙ 设置 API Key"**，填入 [platform.deepseek.com](https://platform.deepseek.com) 的 API Key。

## 截图

（运行后截图放这里）

## 技术栈

- Python 3.12 + Tkinter
- Matplotlib 波形图
- DeepSeek Balance API
- 暗黑科技风 UI
