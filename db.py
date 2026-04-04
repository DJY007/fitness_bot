"""
db.py - 数据库操作
"""
import sqlite3
from datetime import datetime, date
import typing
from pathlib import Path
from config import DATABASE_PATH, LEVEL_CONFIG

DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)

# ─────────────────────────────────────────────────────────────────────────────
# 初始化
# ─────────────────────────────────────────────────────────────────────────────
def init_db():
    """初始化数据库表"""
    conn = sqlite3.connect(DATABASE_PATH)
    c = conn.cursor()

    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id    INTEGER PRIMARY KEY,
            name       TEXT,
            target_weight REAL,
            current_weight REAL,
            level      INTEGER DEFAULT 1,
            streak     INTEGER DEFAULT 0,
            total_workouts INTEGER DEFAULT 0,
            reminder_time TEXT DEFAULT '08:00',
            last_workout_date DATE,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS workouts (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id    INTEGER,
            date       DATE,
            exercise   TEXT,
            reps       INTEGER,
            sets       INTEGER,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS weights (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id    INTEGER,
            weight     REAL,
            date       DATE,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        )
    """)

    conn.commit()
    conn.close()

# ─────────────────────────────────────────────────────────────────────────────
# 用户操作
# ─────────────────────────────────────────────────────────────────────────────
def get_user(user_id: int) -> typing.Optional[dict]:
    """获取用户信息"""
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    row = c.fetchone()
    conn.close()
    return dict(row) if row else None

def create_user(user_id: int, name: str = None, target_weight: float = None) -> dict:
    """创建新用户"""
    conn = sqlite3.connect(DATABASE_PATH)
    c = conn.cursor()
    c.execute("""
        INSERT OR IGNORE INTO users (user_id, name, target_weight)
        VALUES (?, ?, ?)
    """, (user_id, name, target_weight))
    conn.commit()
    conn.close()
    return get_user(user_id)

def update_user(user_id: int, **kwargs):
    """更新用户字段"""
    conn = sqlite3.connect(DATABASE_PATH)
    c = conn.cursor()
    for key, value in kwargs.items():
        c.execute(f"UPDATE users SET {key} = ? WHERE user_id = ?", (value, user_id))
    conn.commit()
    conn.close()

def get_all_users() -> list:
    """获取所有用户（用于每日推送）"""
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT user_id, reminder_time FROM users")
    rows = c.fetchall()
    conn.close()
    return [dict(r) for r in rows]

# ─────────────────────────────────────────────────────────────────────────────
# 打卡操作
# ─────────────────────────────────────────────────────────────────────────────
def log_workout(user_id: int, exercise: str, reps: int, sets: int) -> dict:
    """记录打卡"""
    today = date.today()
    conn = sqlite3.connect(DATABASE_PATH)
    c = conn.cursor()

    # 插入打卡记录
    c.execute("""
        INSERT INTO workouts (user_id, date, exercise, reps, sets)
        VALUES (?, ?, ?, ?, ?)
    """, (user_id, today, exercise, reps, sets))

    # 更新用户统计
    user = get_user(user_id)
    streak = user["streak"] if user else 0
    last_date = user["last_workout_date"] if user else None

    # 计算连续天数
    if last_date:
        last = datetime.strptime(last_date, "%Y-%m-%d").date()
        diff = (today - last).days
        if diff == 1:  # 连续
            streak += 1
        elif diff > 1:  # 断了
            streak = 1
        # diff == 0 则是同一天重复打卡，不增加streak
    else:
        streak = 1

    # 检查是否升级（每7天完成≥5次）
    c.execute("""
        SELECT COUNT(DISTINCT date) as cnt FROM workouts
        WHERE user_id = ? AND date >= date('now', '-30 days')
    """, (user_id,))
    recent_days = c.fetchone()["cnt"]

    level = user["level"] if user else 1
    new_level = level
    # 每7天升一级（最多10级）
    if recent_days >= 7 * level and level < 10:
        new_level = min(level + 1, 10)

    c.execute("""
        UPDATE users SET
            streak = ?,
            total_workouts = total_workouts + 1,
            last_workout_date = ?,
            level = ?
        WHERE user_id = ?
    """, (streak, today, new_level, user_id))

    conn.commit()
    conn.close()

    return {
        "streak": streak,
        "level": new_level,
        "reps": reps,
        "sets": sets,
        "exercise": exercise
    }

def get_workout_stats(user_id: int) -> dict:
    """获取用户运动统计"""
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    # 本周打卡天数
    c.execute("""
        SELECT COUNT(DISTINCT date) as cnt FROM workouts
        WHERE user_id = ? AND date >= date('now', 'weekday=0', '-7 days')
    """, (user_id,))
    week_days = c.fetchone()["cnt"]

    # 本周总次数
    c.execute("""
        SELECT COUNT(*) as cnt FROM workouts
        WHERE user_id = ? AND date >= date('now', 'weekday=0', '-7 days')
    """, (user_id,))
    week_workouts = c.fetchone()["cnt"]

    # 最近7天打卡记录
    c.execute("""
        SELECT date, exercise, reps, sets FROM workouts
        WHERE user_id = ? AND date >= date('now', '-7 days')
        ORDER BY date DESC
    """, (user_id,))
    recent = [dict(r) for r in c.fetchall()]

    conn.close()

    user = get_user(user_id)
    return {
        "streak": user["streak"] if user else 0,
        "level": user["level"] if user else 1,
        "total_workouts": user["total_workouts"] if user else 0,
        "target_weight": user["target_weight"] if user else None,
        "current_weight": user["current_weight"] if user else None,
        "week_days": week_days,
        "week_workouts": week_workouts,
        "recent": recent,
    }

# ─────────────────────────────────────────────────────────────────────────────
# 体重操作
# ─────────────────────────────────────────────────────────────────────────────
def log_weight(user_id: int, weight: float) -> dict:
    """记录体重"""
    today = date.today()
    conn = sqlite3.connect(DATABASE_PATH)
    c = conn.cursor()

    # 插入或更新（当天只记一次）
    c.execute("""
        INSERT OR REPLACE INTO weights (user_id, weight, date)
        VALUES (?, ?, ?)
    """, (user_id, weight, today))

    # 更新用户当前体重
    update_user(user_id, current_weight=weight)

    # 获取历史对比
    c.execute("""
        SELECT weight, date FROM weights
        WHERE user_id = ? AND weight IS NOT NULL
        ORDER BY date DESC
        LIMIT 30
    """, (user_id,))
    history = [dict(r) for r in c.fetchall()]

    conn.commit()
    conn.close()

    # 计算变化
    change = None
    if len(history) >= 2:
        change = history[0]["weight"] - history[1]["weight"]

    return {
        "weight": weight,
        "change": change,
        "history": history[:7],
    }

def get_weight_history(user_id: int, days: int = 30) -> list:
    """获取体重历史"""
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("""
        SELECT weight, date FROM weights
        WHERE user_id = ? AND date >= date('now', ?)
        ORDER BY date ASC
    """, (user_id, f"-{days} days"))
    rows = c.fetchall()
    conn.close()
    return [dict(r) for r in rows]

# ─────────────────────────────────────────────────────────────────────────────
# 初始化
# ─────────────────────────────────────────────────────────────────────────────
init_db()
