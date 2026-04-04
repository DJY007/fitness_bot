"""
db.py - 数据库操作（PostgreSQL）
"""
import os
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime, date
from contextlib import contextmanager
from config import DATABASE_URL

# ─────────────────────────────────────────────────────────────────────────────
# 连接管理
# ─────────────────────────────────────────────────────────────────────────────
@contextmanager
def get_conn():
    """获取数据库连接"""
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL not set")
    conn = psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)
    try:
        yield conn
    finally:
        conn.close()

# ─────────────────────────────────────────────────────────────────────────────
# 初始化
# ─────────────────────────────────────────────────────────────────────────────
def init_db():
    """初始化数据库表"""
    with get_conn() as conn:
        c = conn.cursor()

        c.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id    BIGINT PRIMARY KEY,
                name       TEXT,
                target_weight REAL,
                current_weight REAL,
                level      INTEGER DEFAULT 1,
                streak     INTEGER DEFAULT 0,
                total_workouts INTEGER DEFAULT 0,
                reminder_time TEXT DEFAULT '08:00',
                last_workout_date DATE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        c.execute("""
            CREATE TABLE IF NOT EXISTS workouts (
                id         SERIAL PRIMARY KEY,
                user_id    BIGINT,
                workout_date DATE,
                exercise   TEXT,
                reps       INTEGER,
                sets_count INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        """)

        c.execute("""
            CREATE TABLE IF NOT EXISTS weights (
                id         SERIAL PRIMARY KEY,
                user_id    BIGINT,
                weight     REAL,
                weight_date DATE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        """)

        c.execute("CREATE INDEX IF NOT EXISTS idx_workouts_user ON workouts(user_id)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_weights_user ON weights(user_id)")

        conn.commit()

# ─────────────────────────────────────────────────────────────────────────────
# 用户操作
# ─────────────────────────────────────────────────────────────────────────────
def get_user(user_id: int):
    with get_conn() as conn:
        c = conn.cursor()
        c.execute("SELECT * FROM users WHERE user_id = %s", (user_id,))
        row = c.fetchone()
        return dict(row) if row else None

def create_user(user_id: int, name: str = None, target_weight: float = None):
    with get_conn() as conn:
        c = conn.cursor()
        c.execute("""
            INSERT INTO users (user_id, name, target_weight)
            VALUES (%s, %s, %s)
            ON CONFLICT (user_id) DO NOTHING
        """, (user_id, name, target_weight))
        conn.commit()
    return get_user(user_id)

def update_user(user_id: int, **kwargs):
    if not kwargs:
        return
    sets = ", ".join(f"{k} = %s" for k in kwargs.keys())
    values = list(kwargs.values()) + [user_id]
    with get_conn() as conn:
        c = conn.cursor()
        c.execute(f"UPDATE users SET {sets} WHERE user_id = %s", values)
        conn.commit()

def get_all_users():
    with get_conn() as conn:
        c = conn.cursor()
        c.execute("SELECT user_id, reminder_time FROM users")
        rows = c.fetchall()
        return [dict(r) for r in rows]

# ─────────────────────────────────────────────────────────────────────────────
# 打卡操作
# ─────────────────────────────────────────────────────────────────────────────
def log_workout(user_id: int, exercise: str, reps: int, sets_count: int):
    today = date.today()
    with get_conn() as conn:
        c = conn.cursor()

        c.execute("""
            INSERT INTO workouts (user_id, workout_date, exercise, reps, sets_count)
            VALUES (%s, %s, %s, %s, %s)
        """, (user_id, today, exercise, reps, sets_count))

        user = get_user(user_id)
        streak = user["streak"] if user else 0
        last_date = user["last_workout_date"] if user else None

        if last_date:
            last = last_date if isinstance(last_date, date) else datetime.strptime(str(last_date), "%Y-%m-%d").date()
            diff = (today - last).days
            if diff == 1:
                streak += 1
            elif diff > 1:
                streak = 1
        else:
            streak = 1

        c.execute("""
            SELECT COUNT(DISTINCT workout_date) as cnt FROM workouts
            WHERE user_id = %s AND workout_date >= CURRENT_DATE - INTERVAL '30 days'
        """, (user_id,))
        recent_days = c.fetchone()["cnt"]

        level = user["level"] if user else 1
        new_level = level
        if recent_days >= 7 * level and level < 10:
            new_level = min(level + 1, 10)

        c.execute("""
            UPDATE users SET
                streak = %s,
                total_workouts = total_workouts + 1,
                last_workout_date = %s,
                level = %s
            WHERE user_id = %s
        """, (streak, today, new_level, user_id))

        conn.commit()

        return {
            "streak": streak,
            "level": new_level,
            "reps": reps,
            "sets": sets_count,
            "exercise": exercise,
        }

def get_workout_stats(user_id: int):
    with get_conn() as conn:
        c = conn.cursor()

        c.execute("""
            SELECT COUNT(DISTINCT workout_date) as cnt FROM workouts
            WHERE user_id = %s AND workout_date >= DATE_TRUNC('week', CURRENT_DATE)
        """, (user_id,))
        week_days = c.fetchone()["cnt"]

        c.execute("""
            SELECT COUNT(*) as cnt FROM workouts
            WHERE user_id = %s AND workout_date >= DATE_TRUNC('week', CURRENT_DATE)
        """, (user_id,))
        week_workouts = c.fetchone()["cnt"]

        c.execute("""
            SELECT workout_date, exercise, reps, sets_count FROM workouts
            WHERE user_id = %s AND workout_date >= CURRENT_DATE - INTERVAL '7 days'
            ORDER BY workout_date DESC
        """, (user_id,))
        recent = [dict(r) for r in c.fetchall()]

        conn.commit()

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
def log_weight(user_id: int, weight: float):
    today = date.today()
    with get_conn() as conn:
        c = conn.cursor()

        c.execute("""
            INSERT INTO weights (user_id, weight, weight_date)
            VALUES (%s, %s, %s)
        """, (user_id, weight, today))

        c.execute("""
            UPDATE users SET current_weight = %s WHERE user_id = %s
        """, (weight, user_id))

        c.execute("""
            SELECT weight, weight_date FROM weights
            WHERE user_id = %s AND weight IS NOT NULL
            ORDER BY weight_date DESC
            LIMIT 30
        """, (user_id,))
        history = [dict(r) for r in c.fetchall()]

        conn.commit()

    change = None
    if len(history) >= 2:
        change = history[0]["weight"] - history[1]["weight"]

    return {
        "weight": weight,
        "change": change,
        "history": history[:7],
    }

def get_weight_history(user_id: int, days: int = 30):
    with get_conn() as conn:
        c = conn.cursor()
        c.execute("""
            SELECT weight, weight_date FROM weights
            WHERE user_id = %s AND weight_date >= CURRENT_DATE - INTERVAL %s
            ORDER BY weight_date ASC
        """, (user_id, f"{days} days"))
        rows = c.fetchall()
        conn.commit()
        return [dict(r) for r in rows]

# ─────────────────────────────────────────────────────────────────────────────
# 初始化
# ─────────────────────────────────────────────────────────────────────────────
init_db()
