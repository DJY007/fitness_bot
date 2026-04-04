# Fitness5 🏋️ - 5分钟微运动 Telegram Bot

每天5分钟，养成运动习惯。

## 部署到 Railway

### 方式一：Railway 图形界面（推荐）

1. 打开 [railway.app](https://railway.app)，用 GitHub 登录
2. 点击 **New Project** → **Deploy from GitHub repo**
3. 选择你的 repo（需要先把 `fitness_bot` 文件夹推送到 GitHub）
4. Railway 会自动检测 Dockerfile 开始构建

5. **设置环境变量**（重要！）：
   - 进入项目 → **Variables**
   - 添加：`TELEGRAM_BOT_TOKEN` = 你的 Bot Token

6. 等待构建完成（约2-3分钟）

7. Bot 自动运行！访问 **Railway 日志** 确认启动成功

---

### 方式二：Railway CLI

```bash
# 安装 Railway CLI
npm install -g @railway/cli

# 登录
railway login

# 进入项目目录
cd fitness_bot

# 关联项目（或创建新项目）
railway init

# 设置环境变量
railway variables set TELEGRAM_BOT_TOKEN=你的Token

# 部署
railway up

# 查看日志
railway logs
```

---

## 本地运行

```bash
cd fitness_bot

# 复制环境变量文件
cp .env.example .env

# 编辑填入你的 Bot Token
nano .env

# 安装依赖
pip install -r requirements.txt

# 运行
python bot.py
```

---

## Bot 命令

| 命令 | 功能 |
|------|------|
| `/start` | 启动 / 打开菜单 |
| `/today` | 今日任务 |
| `/checkin` | 打卡 |
| `/stats` | 运动统计 |
| `/weight 75.5` | 记录体重 |
| `/settime 08:00` | 设置推送时间 |
| `/help` | 帮助 |

---

## 项目结构

```
fitness_bot/
├── bot.py              # 主程序
├── config.py           # 配置
├── db.py               # 数据库
├── requirements.txt     # 依赖
├── Dockerfile          # Docker 部署
├── railway.json         # Railway 配置
├── .env.example        # 环境变量模板
└── data/               # SQLite 数据库（自动创建）
```

---

## 收费说明

- **Free 方案**：每月 $5 免费额度（约 500 小时运行时间）
- Fitness5 Bot 24/7 运行大约用 $2-3/月
- 如果只用付费订阅用户，完全可以覆盖成本 💰
