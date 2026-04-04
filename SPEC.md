# Fitness5 - 5分钟微运动 Telegram Bot

## Concept & Vision

一个帮你在5-15分钟内完成每日运动的 Telegram Bot。
每天固定时间推送一个简单动作，你跟着做，做完打卡，就这么简单。
不用想、不用查、不用去健身房。5分钟，改变从这一刻开始。

## Bot Information

- **Name**: Fitness5 🏋️
- **Username**: @fitness5_bot
- **Token**: 待配置
- **Language**: 中文（新加坡用户为主）
- **Tone**: 简洁、直接、有温度

---

## Core Features

### 1. 每日运动推送
- 每天固定时间推送当日运动任务（可配置时间，默认 08:00）
- 动作包含：俯卧撑、深蹲、平板支撑、开合跳、登山者等徒手动作
- 每组次数根据用户当前等级自动调整（第1周10个 → 第2周15个 → ...）
- 包含动作说明 + 简单图示（emoji表达）

### 2. 打卡记录
- 用户回复「打卡」或「done」即记录完成
- 支持记录实际完成次数
- 自动记录打卡时间

### 3. 体重追踪
- `/weight <数字>` 快速记录今日体重
- `/progress` 查看体重变化曲线（ASCII art 简单图）
- `/stats` 查看整体统计

### 4. 成就系统
- 连续7天 → 🏅 一周战士
- 连续30天 → 🥇 月度冠军
- 累计100次 → 💎 健身达人
- 打破个人记录 → 📈 新高

### 5. 等级系统
- 每周完成≥5天 → 升一级
- 等级1: 10个/组
- 等级2: 15个/组
- 等级3: 20个/组
- ...
- 最高等级10: 50个/组

### 6. 设置
- `/start` - 启动 + 欢迎
- `/settime <HH:MM>` - 设置每日推送时间
- `/help` - 帮助说明

---

## User States

### 首次用户
```
欢迎来到 Fitness5 🏋️
每天5分钟，养成运动习惯

请告诉我你的目标体重（kg）：
```

### 已激活用户
收到每日推送：
```
🏋️ 今日任务
━━━━━━━━━━━━━━━━━
动作：俯卧撑
目标：15个 × 3组
⏱ 预计时间：3-5分钟

回复「打卡」完成今日挑战！
```

### 打卡后
```
✅ 打卡成功！
━━━━━━━━━━━━━━━━━
俯卧撑 15个 × 3组 完成
连续打卡：5天 🔥
本周进度：5/7

💪 明天继续！
```

---

## Technical Architecture

### Stack
- **Runtime**: Python 3.9+
- **Bot Framework**: python-telegram-bot (同步) 或 aiogram (异步)
- **Database**: SQLite（用户数据、打卡记录、体重记录）
- **Scheduler**: APScheduler（每日推送定时任务）
- **Config**: .env 文件

### Data Model

**users**
| 字段 | 类型 | 说明 |
|------|------|------|
| user_id | INTEGER PK | Telegram user ID |
| name | TEXT | 用户昵称 |
| target_weight | FLOAT | 目标体重 |
| current_weight | FLOAT | 当前体重 |
| level | INTEGER | 当前等级（1-10） |
| streak | INTEGER | 连续打卡天数 |
| total_workouts | INTEGER | 累计完成次数 |
| reminder_time | TEXT | 推送时间 HH:MM |
| created_at | DATETIME | 注册时间 |

**workouts**
| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER PK | 记录ID |
| user_id | INTEGER FK | 用户ID |
| date | DATE | 打卡日期 |
| exercise | TEXT | 动作名称 |
| reps | INTEGER | 完成次数 |
| sets | INTEGER | 完成组数 |
| created_at | DATETIME | 打卡时间 |

**weights**
| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER PK | 记录ID |
| user_id | INTEGER FK | 用户ID |
| weight | FLOAT | 体重kg |
| date | DATE | 记录日期 |
| created_at | DATETIME | 记录时间 |

### Exercise Library
```
俯卧撑 | Push-up | 初级
深蹲 | Squat | 初级
平板支撑 | Plank | 中级
开合跳 | Jumping Jack | 初级
登山者 | Mountain Climber | 中级
仰卧起坐 | Sit-up | 初级
箭步蹲 | Lunge | 中级
波比跳 | Burpee | 高级
```

---

## File Structure

```
fitness_bot/
├── config.py          # 配置（token、数据库路径）
├── bot.py             # 主程序入口
├── db.py              # 数据库操作
├── exercises.py        # 动作库
├── scheduler.py        # 定时任务
├── handlers/          # 命令处理器
│   ├── __init__.py
│   ├── start.py
│   ├── checkin.py
│   ├── weight.py
│   └── stats.py
├── .env.example       # 环境变量模板
├── requirements.txt    # 依赖清单
└── README.md          # 使用说明
```

---

## MVP Scope（最小可行版本）

**第一版只做：**
1. `/start` 启动 + 基本信息收集
2. 每日08:00推送运动任务
3. 打卡功能
4. `/stats` 查看统计
5. SQLite 数据持久化

**暂不做：**
- 体重追踪图表
- 成就系统
- 等级升级
- 多用户管理（先做单用户）

---

## Configuration

```env
TELEGRAM_BOT_TOKEN=your_bot_token_here
DATABASE_URL=./data/fitness.db
REMINDER_TIME=08:00
```