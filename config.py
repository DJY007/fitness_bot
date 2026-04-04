"""
config.py - 配置文件
"""
import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).parent
load_dotenv(BASE_DIR / ".env")

# Telegram Bot Token
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()

# PostgreSQL 数据库（Railway 自动提供 DATABASE_URL）
DATABASE_URL = os.getenv("DATABASE_URL", "")

# 每日推送时间（HH:MM，24小时制）
DEFAULT_REMINDER_TIME = "08:00"

# 等级配置（每级次数）
LEVEL_CONFIG = {
    1:  {"name": "初学者", "reps": 10, "sets": 3},
    2:  {"name": "初学者", "reps": 15, "sets": 3},
    3:  {"name": "进阶者", "reps": 20, "sets": 3},
    4:  {"name": "进阶者", "reps": 25, "sets": 3},
    5:  {"name": "熟练者", "reps": 30, "sets": 3},
    6:  {"name": "熟练者", "reps": 30, "sets": 4},
    7:  {"name": "高手", "reps": 40, "sets": 4},
    8:  {"name": "高手", "reps": 40, "sets": 5},
    9:  {"name": "专家", "reps": 50, "sets": 5},
    10: {"name": "大师", "reps": 60, "sets": 5},
}

# 动作库
EXERCISES = [
    {"name": "俯卧撑", "emoji": "💪", "unit": "个", "difficulty": "初级", "desc": "标准俯卧撑，注意腰背挺直"},
    {"name": "深蹲", "emoji": "🦵", "unit": "个", "difficulty": "初级", "desc": "膝盖不超过脚尖，下蹲到大腿与地面平行"},
    {"name": "开合跳", "emoji": "⭐", "unit": "个", "difficulty": "初级", "desc": "手脚同时打开，节奏稳定"},
    {"name": "平板支撑", "emoji": "🧘", "unit": "秒", "difficulty": "中级", "desc": "肘部撑地，身体呈直线，保持不动"},
    {"name": "登山者", "emoji": "🏔️", "unit": "秒", "difficulty": "中级", "desc": "俯卧撑姿势，快速交替提膝"},
    {"name": "仰卧起坐", "emoji": "🙆", "unit": "个", "difficulty": "初级", "desc": "双手放耳边，不要抱头拉脖子"},
    {"name": "箭步蹲", "emoji": "🚶", "unit": "个", "difficulty": "中级", "desc": "前后弓步，下蹲时后膝接近地面"},
    {"name": "高抬腿", "emoji": "🏃", "unit": "秒", "difficulty": "初级", "desc": "膝盖尽量抬高，原地跑步姿势"},
    {"name": "波比跳", "emoji": "💥", "unit": "个", "difficulty": "高级", "desc": "全身运动，俯卧撑+跳起，体力消耗大"},
]

# 成就配置
ACHIEVEMENTS = {
    7:   {"name": "🏅 一周战士", "desc": "连续打卡7天"},
    30:  {"name": "🥇 月度冠军", "desc": "连续打卡30天"},
    100: {"name": "💎 健身达人", "desc": "累计打卡100次"},
    7:   {"name": "📈 新高", "desc": "体重创下新低"},
}
