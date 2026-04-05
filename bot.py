#!/usr/bin/env python3
"""
bot.py - Fitness5 Telegram Bot 主程序
"""
import logging
import random
from datetime import datetime, date
from pathlib import Path

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    ContextTypes, ConversationHandler, filters,
    CallbackQueryHandler,
)
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from zoneinfo import ZoneInfo

import sys
sys.path.insert(0, str(Path(__file__).parent))

from config import (
    TELEGRAM_BOT_TOKEN, LEVEL_CONFIG, EXERCISES,
    DEFAULT_REMINDER_TIME,
)
import db

# ─────────────────────────────────────────────────────────────────────────────
# 日志
# ─────────────────────────────────────────────────────────────────────────────
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# 状态
# ─────────────────────────────────────────────────────────────────────────────
WAIT_NAME, WAIT_TARGET, WAIT_CATCHUP_DATE, WAIT_CATCHUP_EXERCISE, WAIT_CATCHUP_REPS, WAIT_CATCHUP_SETS = range(6)

# ─────────────────────────────────────────────────────────────────────────────
# 键盘菜单
# ─────────────────────────────────────────────────────────────────────────────
def get_main_menu_keyboard() -> InlineKeyboardMarkup:
    keyboard = [
        [
            InlineKeyboardButton("🏋️ 今日任务", callback_data="cmd_today"),
            InlineKeyboardButton("✅ 打卡", callback_data="cmd_checkin"),
        ],
        [
            InlineKeyboardButton("📊 我的统计", callback_data="cmd_stats"),
            InlineKeyboardButton("⚖️ 记录体重", callback_data="cmd_weight"),
        ],
        [
            InlineKeyboardButton("🔄 补卡", callback_data="cmd_catchup"),
            InlineKeyboardButton("⚙️ 设置时间", callback_data="cmd_settime"),
        ],
        [
            InlineKeyboardButton("📖 帮助", callback_data="cmd_help"),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)

def get_back_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("🔙 返回菜单", callback_data="cmd_menu"),
    ]])

def get_checkin_done_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🏋️ 今日任务", callback_data="cmd_today")],
        [InlineKeyboardButton("🔙 返回菜单", callback_data="cmd_menu")],
    ])

# ─────────────────────────────────────────────────────────────────────────────
# 工具函数
# ─────────────────────────────────────────────────────────────────────────────
def get_daily_exercise(level: int = 1) -> dict:
    ex = random.choice(EXERCISES)
    cfg = LEVEL_CONFIG.get(level, LEVEL_CONFIG[1])
    return {
        "name": ex["name"],
        "emoji": ex["emoji"],
        "desc": ex["desc"],
        "reps": cfg["reps"],
        "sets": cfg["sets"],
        "level_name": cfg["name"],
    }

def format_workout_message(exercise: dict, streak: int = 0) -> str:
    unit = exercise.get('unit', '个')
    msg = f"""🏋️ 今日任务
━━━━━━━━━━━━━━━━━━
动作：{exercise['emoji']} {exercise['name']}
目标：{exercise['reps']}{unit} × {exercise['sets']}组
⏱ 预计时间：3-5分钟
难度：{exercise['level_name']}

{exercise['desc']}

━━━━━━━━━━━━━━━━━━
👇 完成后点击下方「打卡」按钮 👇"""
    if streak > 0:
        msg += f"\n\n🔥 连续打卡：{streak}天"
    return msg

def format_checkin_message(result: dict, stats: dict) -> str:
    return f"""✅ 打卡成功！
━━━━━━━━━━━━━━━━━━
{result['exercise']} {result['reps']}个 × {result['sets']}组 完成

🔥 连续打卡：{result['streak']}天
📊 本周：{stats['week_days']}/7 天
🏆 累计完成：{stats['total_workouts']}次
📶 当前等级：Lv.{stats['level']} {LEVEL_CONFIG[stats['level']]['name']}

💪 明天继续！"""

def format_stats_message(stats: dict) -> str:
    level_cfg = LEVEL_CONFIG.get(stats["level"], LEVEL_CONFIG[1])
    msg = f"""📊 运动统计
━━━━━━━━━━━━━━━━━━
🔥 连续打卡：{stats['streak']}天
📶 当前等级：Lv.{stats['level']} {level_cfg['name']}
🏆 累计完成：{stats['total_workouts']}次
📅 本周进度：{stats['week_days']}/7 天"""
    if stats.get("current_weight"):
        msg += f"\n⚖️ 当前体重：{stats['current_weight']}kg"
    if stats.get("target_weight"):
        msg += f"\n🎯 目标体重：{stats['target_weight']}kg"
        if stats.get("current_weight"):
            diff = stats['current_weight'] - stats['target_weight']
            msg += f"\n📈 距目标：{diff:+.1f}kg"
    if stats.get("recent"):
        msg += "\n\n📅 最近记录："
        for r in stats["recent"]:
            d = str(r["workout_date"])[:10]
            msg += f"\n  {d} — {r['exercise']} {r['reps']}×{r['sets_count']}"
    return msg

async def edit_or_reply(update, text, reply_markup=None):
    """编辑消息，失败则发新消息"""
    try:
        if update.callback_query:
            await update.callback_query.edit_message_text(
                text=text,
                reply_markup=reply_markup,
                parse_mode="HTML",
            )
        elif update.message:
            await update.message.edit_text(
                text=text,
                reply_markup=reply_markup,
                parse_mode="HTML",
            )
    except Exception:
        # 编辑失败（消息太旧），改用回复新消息
        chat_id = None
        if update.callback_query:
            chat_id = update.callback_query.message.chat_id
            await update.callback_query.answer("处理中...", show_alert=False)
        elif update.message:
            chat_id = update.message.chat_id
        if chat_id and update._bot:
            await update._bot.send_message(
                chat_id=chat_id,
                text=text,
                reply_markup=reply_markup,
                parse_mode="HTML",
            )

# ─────────────────────────────────────────────────────────────────────────────
# 按钮回调处理器
# ─────────────────────────────────────────────────────────────────────────────
async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """处理所有按钮点击"""
    query = update.callback_query
    await query.answer()  # 必须先 answer，否则按钮会一直显示 loading
    user_id = query.from_user.id
    data = query.data

    try:
        if data == "cmd_menu":
            user = db.get_user(user_id)
            name = user.get("name", "") if user else ""
            streak = user.get("streak", 0) if user else 0
            level = user.get("level", 1) if user else 1
            msg = f"""🏋️ Fitness5 主菜单
━━━━━━━━━━━━━━━━━━
{name}，准备好了吗？

🔥 连续打卡：{streak}天
📶 当前等级：Lv.{level}

👇 选择操作："""
            await query.edit_message_text(
                text=msg,
                reply_markup=get_main_menu_keyboard(),
                parse_mode="HTML",
            )

        elif data == "cmd_today":
            user = db.get_user(user_id)
            if not user:
                await query.edit_message_text("请先 /start 开始使用！")
                return
            exercise = get_daily_exercise(user["level"])
            context.user_data["today_exercise"] = exercise
            msg = format_workout_message(exercise, user["streak"])
            keyboard = [
                [InlineKeyboardButton("✅ 打卡", callback_data="cmd_checkin")],
                [InlineKeyboardButton("🔙 返回菜单", callback_data="cmd_menu")],
            ]
            await query.edit_message_text(
                text=msg,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode="HTML",
            )

        elif data == "cmd_checkin":
            user = db.get_user(user_id)
            if not user:
                await query.edit_message_text("请先 /start 开始使用！")
                return
            exercise = context.user_data.get("today_exercise") or get_daily_exercise(user["level"])
            result = db.log_workout(user_id, exercise["name"], exercise["reps"], exercise["sets"])
            stats = db.get_workout_stats(user_id)
            streak = result["streak"]
            achievement = None
            if streak == 7: achievement = "🏅 一周战士！连续打卡7天！"
            elif streak == 30: achievement = "🥇 月度冠军！连续打卡30天！"
            elif streak == 100: achievement = "💎 健身达人！累计打卡100次！"
            msg = format_checkin_message(result, stats)
            if achievement: msg += f"\n\n🎉 {achievement}"
            # 发新消息而不是编辑（避免超时问题）
            await context.bot.send_message(
                chat_id=user_id,
                text=msg,
                reply_markup=get_checkin_done_keyboard(),
                parse_mode="HTML",
            )
            # 删掉按钮消息
            try:
                await query.delete_message()
            except Exception:
                pass

        elif data == "cmd_stats":
            stats = db.get_workout_stats(user_id)
            await query.edit_message_text(
                text=format_stats_message(stats),
                reply_markup=get_back_menu_keyboard(),
                parse_mode="HTML",
            )

        elif data == "cmd_weight":
            await query.edit_message_text(
                text="⚖️ 请发送你的体重数字\n\n格式：发送 /weight 75.5\n\n例如：/weight 75.5",
                reply_markup=get_back_menu_keyboard(),
            )

        elif data == "cmd_settime":
            user = db.get_user(user_id)
            current = user.get("reminder_time", DEFAULT_REMINDER_TIME) if user else DEFAULT_REMINDER_TIME
            await query.edit_message_text(
                text=f"⚙️ 当前推送时间：{current}\n\n发送 /settime 08:00 设置新时间\n\n例如：/settime 07:30",
                reply_markup=get_back_menu_keyboard(),
            )

        elif data == "cmd_catchup":
            await update.callback_query.message.reply_text(
                "🔄 发送 /catchup 进入补卡流程",
                reply_markup=get_back_menu_keyboard(),
            )

        elif data == "cmd_help":
            await query.edit_message_text(
                text="""📖 Fitness5 帮助
━━━━━━━━━━━━━━━━━━

🏋️ 今日任务 — 查看今天做什么运动
✅ 打卡 — 完成今日运动打卡
📊 我的统计 — 查看运动记录
⚖️ 记录体重 — 记录今日体重
⚙️ 设置时间 — 修改每日推送时间

💪 每天5分钟，坚持就是胜利！""",
                reply_markup=get_back_menu_keyboard(),
            )

        else:
            await query.answer("未知操作", show_alert=False)

    except Exception as e:
        logger.error(f"按钮处理错误: {e}")
        try:
            await query.answer("出错了，请重试", show_alert=True)
        except Exception:
            pass

# ─────────────────────────────────────────────────────────────────────────────
# 命令处理器
# ─────────────────────────────────────────────────────────────────────────────
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """新用户注册"""
    user_id = update.effective_user.id
    user = db.get_user(user_id)

    if user:
        name = user.get("name", "")
        streak = user.get("streak", 0)
        level = user.get("level", 1)
        msg = f"""🏋️ Fitness5
━━━━━━━━━━━━━━━━━━
欢迎回来，{name}！

🔥 连续打卡：{streak}天
📶 当前等级：Lv.{level}

👇 选择操作："""
        await update.message.reply_text(
            text=msg,
            reply_markup=get_main_menu_keyboard(),
            parse_mode="HTML",
        )
        return

    await update.message.reply_text("""🏋️ 欢迎来到 Fitness5！

每天5分钟，养成运动习惯。

请告诉我你的名字：""")
    return WAIT_NAME

async def wait_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = update.message.text.strip()
    context.user_data["name"] = name
    await update.message.reply_text(f"""好的 {name}！👋

最后，告诉我你的目标体重（kg）：
（比如：75）""")
    return WAIT_TARGET

async def wait_target(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    name = context.user_data.get("name", "朋友")
    try:
        target = float(update.message.text.strip())
    except ValueError:
        await update.message.reply_text("请输入有效数字，比如：75")
        return WAIT_TARGET

    db.create_user(user_id, name=name, target_weight=target)
    exercise = get_daily_exercise(level=1)
    context.user_data["today_exercise"] = exercise

    keyboard = [
        [InlineKeyboardButton("🏋️ 今日任务", callback_data="cmd_today")],
        [InlineKeyboardButton("🔙 返回菜单", callback_data="cmd_menu")],
    ]
    await update.message.reply_text(f"""✅ 注册完成！
━━━━━━━━━━━━━━━━━━
{name}，加油！💪

目标体重：{target}kg
📊 等级：Lv.1 初学者
🔥 连续打卡：0天

👇 开始你的第一个任务：""")
    await update.message.reply_text(
        text=format_workout_message(exercise, streak=0),
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="HTML",
    )
    return ConversationHandler.END

async def checkin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = db.get_user(user_id)
    if not user:
        await update.message.reply_text("请先 /start 绑定账号")
        return
    exercise = context.user_data.get("today_exercise") or get_daily_exercise(user["level"])
    result = db.log_workout(user_id, exercise["name"], exercise["reps"], exercise["sets"])
    stats = db.get_workout_stats(user_id)
    streak = result["streak"]
    achievement = None
    if streak == 7: achievement = "🏅 一周战士！"
    elif streak == 30: achievement = "🥇 月度冠军！"
    elif streak == 100: achievement = "💎 健身达人！"
    msg = format_checkin_message(result, stats)
    if achievement: msg += f"\n\n🎉 {achievement}"
    await update.message.reply_text(
        text=msg,
        reply_markup=get_checkin_done_keyboard(),
        parse_mode="HTML",
    )
    new_exercise = get_daily_exercise(user["level"])
    context.user_data["today_exercise"] = new_exercise

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = db.get_user(user_id)
    if not user:
        await update.message.reply_text("请先 /start 绑定账号")
        return
    await update.message.reply_text(
        text=format_stats_message(db.get_workout_stats(user_id)),
        reply_markup=get_back_menu_keyboard(),
        parse_mode="HTML",
    )

async def weight_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = db.get_user(user_id)
    if not user:
        await update.message.reply_text("请先 /start 绑定账号")
        return
    text = update.message.text.replace("/weight", "").strip()
    if not text:
        history = db.get_weight_history(user_id, days=30)
        if not history:
            await update.message.reply_text(
                "还没有体重记录，格式：/weight 75.5",
                reply_markup=get_back_menu_keyboard(),
            )
            return
        msg = "📊 体重记录：\n"
        for h in history[-7:]:
            d = str(h["weight_date"])[:10]
            msg += f"{d} — {h['weight']}kg\n"
        await update.message.reply_text(msg, reply_markup=get_back_menu_keyboard())
        return
    try:
        weight = float(text)
    except ValueError:
        await update.message.reply_text("请输入有效数字，比如：/weight 75.5")
        return
    result = db.log_weight(user_id, weight)
    msg = f"✅ 体重已记录：{weight}kg"
    if result["change"] is not None:
        change = result["change"]
        sign = "+" if change > 0 else ""
        msg += f"\n📈 较上次：{sign}{change:.1f}kg"
    await update.message.reply_text(msg, reply_markup=get_back_menu_keyboard())

async def today_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = db.get_user(user_id)
    if not user:
        await update.message.reply_text("请先 /start 绑定账号")
        return
    exercise = get_daily_exercise(user["level"])
    context.user_data["today_exercise"] = exercise
    keyboard = [
        [InlineKeyboardButton("✅ 打卡", callback_data="cmd_checkin")],
        [InlineKeyboardButton("🔙 返回菜单", callback_data="cmd_menu")],
    ]
    await update.message.reply_text(
        text=format_workout_message(exercise, user["streak"]),
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="HTML",
    )

async def settime_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = db.get_user(user_id)
    if not user:
        await update.message.reply_text("请先 /start 绑定账号")
        return
    text = update.message.text.replace("/settime", "").strip()
    if not text:
        current = user.get("reminder_time", DEFAULT_REMINDER_TIME)
        await update.message.reply_text(
            f"当前推送时间：{current}\n\n设置新时间格式：/settime 08:00",
            reply_markup=get_back_menu_keyboard(),
        )
        return
    try:
        datetime.strptime(text, "%H:%M")
    except ValueError:
        await update.message.reply_text("时间格式错误，请使用 HH:MM，如：08:00")
        return
    db.update_user(user_id, reminder_time=text)
    await update.message.reply_text(
        f"✅ 推送时间已设置为每天 {text}",
        reply_markup=get_back_menu_keyboard(),
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        """📖 Fitness5 命令说明

🏋️ /today     — 今日任务
✅ /checkin   — 打卡
📊 /stats     — 运动统计
⚖️ /weight    — 记录体重
🔄 /catchup   — 补录昨天或之前的打卡
⚙️ /settime   — 设置推送时间
📖 /help      — 显示帮助

💪 每天5分钟，坚持就是胜利！""",
        reply_markup=get_back_menu_keyboard(),
    )

# ─────────────────────────────────────────────────────────────────────────────
# 补卡流程
# ─────────────────────────────────────────────────────────────────────────────

CATCHUP_EXERCISES = [
    {"name": "俯卧撑", "emoji": "💪", "unit": "个"},
    {"name": "深蹲", "emoji": "🦵", "unit": "个"},
    {"name": "开合跳", "emoji": "⭐", "unit": "个"},
    {"name": "平板支撑", "emoji": "🧘", "unit": "秒"},
    {"name": "登山者", "emoji": "🏔️", "unit": "秒"},
    {"name": "仰卧起坐", "emoji": "🙆", "unit": "个"},
    {"name": "箭步蹲", "emoji": "🚶", "unit": "个"},
    {"name": "高抬腿", "emoji": "🏃", "unit": "秒"},
    {"name": "波比跳", "emoji": "💥", "unit": "个"},
]

def get_catchup_exercise_keyboard():
    keyboard = []
    row = []
    for i, ex in enumerate(CATCHUP_EXERCISES):
        row.append(InlineKeyboardButton(f"{ex['emoji']}{ex['name']}", callback_data=f"catchup_ex_{i}"))
        if len(row) == 2:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)
    keyboard.append([InlineKeyboardButton("🔙 取消", callback_data="catchup_cancel")])
    return InlineKeyboardMarkup(keyboard)

async def catchup_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """开始补卡流程"""
    user_id = update.effective_user.id
    user = db.get_user(user_id)
    if not user:
        await update.message.reply_text("请先 /start 绑定账号")
        return

    from datetime import timedelta
    yesterday = date.today() - timedelta(days=1)
    context.user_data["catchup_date"] = yesterday

    await update.message.reply_text(
        f"""🔄 补卡功能
━━━━━━━━━━━━━━━━━━
请选择你要补录的运动日期：
（默认：{yesterday.strftime('%Y-%m-%d')}）

直接回复日期，格式：YYYY-MM-DD
例如：{yesterday.strftime('%Y-%m-%d')}""",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("📅 昨天", callback_data="catchup_yesterday"),
            InlineKeyboardButton("📅 前天", callback_data="catchup_2days"),
            InlineKeyboardButton("🔙 取消", callback_data="catchup_cancel"),
        ]]),
    )
    return WAIT_CATCHUP_DATE

async def catchup_date_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """处理补卡日期输入"""
    text = update.message.text.strip()
    try:
        catchup_date = datetime.strptime(text, "%Y-%m-%d").date()
        if catchup_date > date.today():
            await update.message.reply_text("日期不能是未来哦！请重新输入：")
            return WAIT_CATCHUP_DATE
        context.user_data["catchup_date"] = catchup_date
    except ValueError:
        await update.message.reply_text("日期格式不对，请用 YYYY-MM-DD，例如：2026-04-03")
        return WAIT_CATCHUP_DATE

    await update.message.reply_text(
        f"""📅 补卡日期：{catchup_date.strftime('%Y-%m-%d')}

现在选择运动项目：""",
        reply_markup=get_catchup_exercise_keyboard(),
    )
    return WAIT_CATCHUP_EXERCISE

async def catchup_exercise_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """处理补卡运动选择"""
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "catchup_cancel":
        await query.edit_message_text("已取消补卡，返回菜单 👇", reply_markup=get_main_menu_keyboard())
        return ConversationHandler.END

    if data in ["catchup_yesterday", "catchup_2days"]:
        from datetime import timedelta
        days = 1 if data == "catchup_yesterday" else 2
        context.user_data["catchup_date"] = date.today() - timedelta(days=days)

    if data.startswith("catchup_ex_"):
        idx = int(data.split("_")[-1])
        exercise = CATCHUP_EXERCISES[idx]
        context.user_data["catchup_exercise"] = exercise
        context.user_data["catchup_unit"] = exercise["unit"]
        d = context.user_data["catchup_date"]
        await query.edit_message_text(
            (f"{exercise['emoji']} {exercise['name']}（{d.strftime('%Y-%m-%d')}）\n\n"
             f"请输入完成的数量（{exercise['unit']}）："),
            reply_markup=None,
        )
        return WAIT_CATCHUP_REPS

    if data.startswith("catchup_date_"):
        d = datetime.strptime(data.replace("catchup_date_",""), "%Y-%m-%d").date()
        context.user_data["catchup_date"] = d
        await query.edit_message_text(f"日期已设为：{d.strftime('%Y-%m-%d')}\n\n现在选择运动：", reply_markup=get_catchup_exercise_keyboard())
        return WAIT_CATCHUP_EXERCISE

async def catchup_reps_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """处理补卡数量输入"""
    text = update.message.text.strip()
    try:
        reps = int(text)
        if reps <= 0:
            raise ValueError()
    except ValueError:
        unit = context.user_data.get("catchup_unit", "个")
        await update.message.reply_text(f"请输入有效数字（{unit}）：")
        return WAIT_CATCHUP_REPS

    context.user_data["catchup_reps"] = reps
    exercise = context.user_data.get("catchup_exercise", {})
    unit = context.user_data.get("catchup_unit", "个")

    await update.message.reply_text(
        (f"{exercise.get('emoji','🏋️')} {exercise.get('name','运动')} × {reps}{unit}\n\n"
         f"默认 3 组，直接发送数字修改组数，或发送「确认」完成补卡："),
    )
    return WAIT_CATCHUP_SETS

async def catchup_sets_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """处理补卡组数确认"""
    text = update.message.text.strip()

    if text in ["确认", "ok", "好", "确定"]:
        sets = 3
    else:
        try:
            sets = int(text)
            if sets <= 0:
                raise ValueError()
        except ValueError:
            await update.message.reply_text("发送「确认」完成补卡，或发送数字修改组数：")
            return WAIT_CATCHUP_SETS

    user_id = update.effective_user.id
    exercise = context.user_data.get("catchup_exercise", {})
    reps = context.user_data.get("catchup_reps", 10)
    catchup_date = context.user_data.get("catchup_date", date.today())

    result = db.log_workout(user_id, exercise["name"], reps, sets, workout_date=catchup_date)

    await update.message.reply_text(
        (f"✅ 补卡成功！\n━━━━━━━━━━━━━━━━━━\n"
         f"📅 日期：{catchup_date.strftime('%Y-%m-%d')}\n"
         f"🏋️ {exercise.get('emoji','')} {exercise.get('name','')} × "
         f"{reps}{exercise.get('unit','个')} × {sets}组\n\n"
         f"💪 继续保持！"),
        reply_markup=get_main_menu_keyboard(),
    )
    # 清理
    for key in ["catchup_date","catchup_exercise","catchup_reps","catchup_unit"]:
        context.user_data.pop(key, None)
    return ConversationHandler.END

async def catchup_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """处理补卡流程中的按钮"""
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "catchup_cancel":
        await query.edit_message_text("已取消补卡 👋", reply_markup=get_main_menu_keyboard())
        return ConversationHandler.END

    if data == "catchup_yesterday":
        from datetime import timedelta
        context.user_data["catchup_date"] = date.today() - timedelta(days=1)
        d = context.user_data["catchup_date"]
        await query.edit_message_text(f"日期：{d.strftime('%Y-%m-%d')}\n\n现在选择运动：", reply_markup=get_catchup_exercise_keyboard())
        return WAIT_CATCHUP_EXERCISE

    if data == "catchup_2days":
        from datetime import timedelta
        context.user_data["catchup_date"] = date.today() - timedelta(days=2)
        d = context.user_data["catchup_date"]
        await query.edit_message_text(f"日期：{d.strftime('%Y-%m-%d')}\n\n现在选择运动：", reply_markup=get_catchup_exercise_keyboard())
        return WAIT_CATCHUP_EXERCISE

    return WAIT_CATCHUP_DATE

async def unknown_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()

    # 懒人打卡：任何数字都当打卡
    try:
        num = float(text)
        await checkin_command(update, context)
        return
    except ValueError:
        pass

    text_lower = text.lower()
    if text_lower in ["打卡", "done", "完成了", "打", "ok", "好", "✅"]:
        await checkin_command(update, context)
    else:
        await update.message.reply_text(
            "点击主菜单按钮操作，或发送 /help 查看命令",
            reply_markup=get_main_menu_keyboard(),
        )

# ─────────────────────────────────────────────────────────────────────────────
# 每日定时提醒
# ─────────────────────────────────────────────────────────────────────────────

async def send_daily_reminder(app: Application):
    """发送每日运动提醒给所有用户"""
    users = db.get_all_users()
    for user in users:
        try:
            user_id = user["user_id"]
            reminder_time = user.get("reminder_time", DEFAULT_REMINDER_TIME)
            # 获取用户的今日任务
            level = user.get("level", 1)
            exercise = get_daily_exercise(level)
            streak = user.get("streak", 0)
            name = user.get("name", "")

            msg = f"""☀️ 早安 {name}！

🏋️ 今日任务
━━━━━━━━━━━━━━━━━━
动作：{exercise['emoji']} {exercise['name']}
目标：{exercise['reps']}{exercise.get('unit','个')} × {exercise['sets']}组
⏱ 预计时间：3-5分钟

{exercise['desc']}

━━━━━━━━━━━━━━━━━━
👇 完成后回复「打卡」或点击按钮！"""

            keyboard = [
                [InlineKeyboardButton("✅ 打卡", callback_data="cmd_checkin")],
                [InlineKeyboardButton("📊 查看统计", callback_data="cmd_stats")],
            ]

            await app.bot.send_message(
                chat_id=user_id,
                text=msg,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode="HTML",
            )
            logger.info(f"每日提醒已发送给用户 {user_id}")
        except Exception as e:
            logger.error(f"发送每日提醒失败（用户 {user.get('user_id')}）：{e}")

def get_weekly_report(user_id: int):
    """生成周报内容"""
    user = db.get_user(user_id)
    if not user:
        return None

    import datetime
    today = datetime.date.today()
    week_ago = today - datetime.timedelta(days=7)

    stats = db.get_workout_stats(user_id)
    name = user.get("name", "")

    # 获取本周打卡记录
    with db.get_conn() as conn:
        c = conn.cursor()
        c.execute("""
            SELECT workout_date, exercise, reps, sets_count
            FROM workouts
            WHERE user_id = %s AND workout_date >= %s
            ORDER BY workout_date DESC
        """, (user_id, week_ago))
        rows = [dict(r) for r in c.fetchall()]

    total_workouts = len(rows)
    total_reps = sum(r["reps"] * r["sets_count"] for r in rows)

    # 今日体重
    weight = user.get("current_weight")
    target = user.get("target_weight")

    msg = f"""📊 本周运动报告
━━━━━━━━━━━━━━━━━━
👤 {name}，这是你的一周总结：

🏋️ 本周运动：{total_workouts} 次
💪 完成动作：{total_reps} 个（总计）
🔥 连续打卡：{stats['streak']} 天
🏆 累计完成：{stats['total_workouts']} 次"""

    if weight:
        msg += f"\n⚖️ 当前体重：{weight}kg"
    if target:
        diff = weight - target if weight else 0
        msg += f"\n🎯 距目标：{diff:+.1f}kg"

    if rows:
        msg += "\n\n📅 本周记录："
        dates_seen = set()
        for r in rows:
            d = str(r["workout_date"])[:10]
            if d not in dates_seen:
                dates_seen.add(d)
                msg += f"\n  {d} — {r['exercise']} {r['reps']}×{r['sets_count']}"

    # 鼓励语
    if total_workouts >= 5:
        msg += "\n\n💪 太棒了！一周5次运动，继续保持！"
    elif total_workouts >= 3:
        msg += "\n\n👍 不错的开始，下周争取更多！"
    elif total_workouts >= 1:
        msg += "\n\n📈 动起来就是进步，下周加油！"
    else:
        msg += "\n\n💤 这周有点懒哦，下周动起来！"

    msg += "\n\n━━━━━━━━━━━━━━━━━━"
    return msg

async def send_weekly_report(app: Application):
    """每周日晚上发送周报"""
    users = db.get_all_users()
    for user in users:
        try:
            report = get_weekly_report(user["user_id"])
            if report:
                keyboard = [
                    [InlineKeyboardButton("🏋️ 今日任务", callback_data="cmd_today")],
                    [InlineKeyboardButton("📊 我的统计", callback_data="cmd_stats")],
                ]
                await app.bot.send_message(
                    chat_id=user["user_id"],
                    text=report,
                    reply_markup=InlineKeyboardMarkup(keyboard),
                    parse_mode="HTML",
                )
                logger.info(f"周报已发送给用户 {user['user_id']}")
        except Exception as e:
            logger.error(f"发送周报失败（用户 {user.get('user_id')}）：{e}")

def start_scheduler(app: Application):
    """启动定时任务调度器"""
    scheduler = BackgroundScheduler()

    # 每天早上 8:00 发提醒
    try:
        scheduler.add_job(
            send_daily_reminder,
            CronTrigger(hour=8, minute=0, timezone=ZoneInfo("Asia/Singapore")),
            args=[app],
            id="daily_reminder",
            replace_existing=True,
            misfire_grace_time=3600,
        )

        # 每周日晚上 20:00 发周报
        scheduler.add_job(
            send_weekly_report,
            CronTrigger(day_of_week="sun", hour=20, minute=0, timezone=ZoneInfo("Asia/Singapore")),
            args=[app],
            id="weekly_report",
            replace_existing=True,
            misfire_grace_time=7200,
        )

        scheduler.start()
        logger.info("调度器已启动（每日 08:00 + 每周日 20:00）")
    except Exception as e:
        logger.error(f"调度器启动失败：{e}")

    return scheduler

# ─────────────────────────────────────────────────────────────────────────────
# 主程序
# ─────────────────────────────────────────────────────────────────────────────
def main():
    if not TELEGRAM_BOT_TOKEN:
        print("❌ 请先设置 TELEGRAM_BOT_TOKEN")
        return

    app = (
        Application.builder()
        .token(TELEGRAM_BOT_TOKEN)
        .connection_pool_size(2)
        .build()
    )

    # 补卡按钮回调（独立处理，不走普通按钮逻辑）
    app.add_handler(CallbackQueryHandler(catchup_callback_handler, pattern=r"^catchup_"))

    # 补卡对话
    catchup_conv = ConversationHandler(
        entry_points=[CommandHandler("catchup", catchup_command)],
        states={
            WAIT_CATCHUP_DATE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, catchup_date_handler),
                CallbackQueryHandler(catchup_callback_handler, pattern=r"^catchup_"),
            ],
            WAIT_CATCHUP_EXERCISE: [
                CallbackQueryHandler(catchup_exercise_callback, pattern=r"^catchup_"),
            ],
            WAIT_CATCHUP_REPS: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, catchup_reps_handler),
            ],
            WAIT_CATCHUP_SETS: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, catchup_sets_handler),
            ],
        },
        fallbacks=[],
        allow_reentry=True,
    )
    app.add_handler(catchup_conv)

    app.add_handler(CallbackQueryHandler(button_callback, pattern=r"^cmd_"))

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start_command)],
        states={
            WAIT_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, wait_name)],
            WAIT_TARGET: [MessageHandler(filters.TEXT & ~filters.COMMAND, wait_target)],
        },
        fallbacks=[],
    )

    app.add_handler(conv_handler)
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("today", today_command))
    app.add_handler(CommandHandler("checkin", checkin_command))
    app.add_handler(CommandHandler("stats", stats_command))
    app.add_handler(CommandHandler("weight", weight_command))
    app.add_handler(CommandHandler("settime", settime_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, unknown_message))

    # 启动每日提醒调度器
    sched = start_scheduler(app)

    print("🏋️ Fitness5 Bot 已启动！")
    print("⏰ 调度器：每日 08:00 提醒 + 每周日 20:00 周报")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
