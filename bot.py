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
WAIT_NAME, WAIT_TARGET = range(2)

# ─────────────────────────────────────────────────────────────────────────────
# 键盘菜单
# ─────────────────────────────────────────────────────────────────────────────

def get_main_menu_keyboard() -> InlineKeyboardMarkup:
    """主菜单键盘"""
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
            InlineKeyboardButton("⚙️ 设置时间", callback_data="cmd_settime"),
            InlineKeyboardButton("📖 帮助", callback_data="cmd_help"),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)

def get_back_menu_keyboard() -> InlineKeyboardMarkup:
    """返回主菜单键盘"""
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("🔙 返回菜单", callback_data="cmd_menu"),
    ]])

def get_checkin_keyboard() -> InlineKeyboardMarkup:
    """打卡后快捷操作"""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ 打卡完成", callback_data="cmd_checkin")],
        [InlineKeyboardButton("🏋️ 今日任务", callback_data="cmd_today")],
        [InlineKeyboardButton("🔙 返回菜单", callback_data="cmd_menu")],
    ])

# ─────────────────────────────────────────────────────────────────────────────
# 工具函数
# ─────────────────────────────────────────────────────────────────────────────
def get_daily_exercise(level: int = 1) -> dict:
    """获取今日运动任务"""
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
    """格式化运动任务消息"""
    msg = f"""🏋️ 今日任务
━━━━━━━━━━━━━━━━━━
动作：{exercise['emoji']} {exercise['name']}
目标：{exercise['reps']}个 × {exercise['sets']}组
⏱ 预计时间：3-5分钟
难度：{exercise['level_name']}

{exercise['desc']}

━━━━━━━━━━━━━━━━━━
👇 点击下方「打卡」按钮完成挑战！"""
    if streak > 0:
        msg += f"\n\n🔥 连续打卡：{streak}天"
    return msg

def format_checkin_message(result: dict, stats: dict) -> str:
    """格式化打卡成功消息"""
    return f"""✅ 打卡成功！
━━━━━━━━━━━━━━━━━━
{result['exercise']} {result['reps']}个 × {result['sets']}组 完成

🔥 连续打卡：{result['streak']}天
📊 本周：{stats['week_days']}/7 天
🏆 累计完成：{stats['total_workouts']}次
📶 当前等级：Lv.{stats['level']} {LEVEL_CONFIG[stats['level']]['name']}

💪 明天继续！"""

def format_stats_message(stats: dict) -> str:
    """格式化统计消息"""
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
        dates_seen = set()
        for r in stats["recent"]:
            d = r["date"][:10] if isinstance(r["date"], str) else str(r["date"])
            if d not in dates_seen:
                dates_seen.add(d)
                msg += f"\n  {d} — {r['exercise']} {r['reps']}×{r['sets']}"
    return msg

# ─────────────────────────────────────────────────────────────────────────────
# 按钮回调处理器
# ─────────────────────────────────────────────────────────────────────────────

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """处理所有按钮点击"""
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    data = query.data

    if data == "cmd_menu":
        await show_menu_inline(query, user_id)
    elif data == "cmd_today":
        await show_today_inline(query, context, user_id)
    elif data == "cmd_checkin":
        await do_checkin_inline(query, context, user_id)
    elif data == "cmd_stats":
        await show_stats_inline(query, user_id)
    elif data == "cmd_weight":
        await query.edit_message_text(
            "⚖️ 请输入你的体重（kg）\n\n格式：发送 /weight 75.5\n\n或直接发送数字，例如：75.5",
            reply_markup=get_back_menu_keyboard(),
        )
    elif data == "cmd_settime":
        user = db.get_user(user_id)
        current = user.get("reminder_time", DEFAULT_REMINDER_TIME) if user else DEFAULT_REMINDER_TIME
        await query.edit_message_text(
            f"⚙️ 当前推送时间：{current}\n\n发送 /settime 08:00 设置新时间\n\n例如：/settime 07:30",
            reply_markup=get_back_menu_keyboard(),
        )
    elif data == "cmd_help":
        await show_help_inline(query)
    else:
        await query.edit_message_text(
            "未知操作，请点击 🔙 返回菜单",
            reply_markup=get_back_menu_keyboard(),
        )

async def show_menu_inline(query, user_id: int):
    """显示主菜单"""
    user = db.get_user(user_id)
    name = user.get("name", "") if user else ""
    streak = user.get("streak", 0) if user else 0
    level = user.get("level", 1) if user else 1
    msg = f"""🏋️ Fitness5 主菜单
━━━━━━━━━━━━━━━━━━
{name}，准备好了吗？

🔥 连续打卡：{streak}天
📶 当前等级：Lv.{level} {LEVEL_CONFIG[level]['name']}

👇 选择操作："""
    await query.edit_message_text(
        msg,
        reply_markup=get_main_menu_keyboard(),
        parse_mode="HTML",
    )

async def show_today_inline(query, context, user_id: int):
    """显示今日任务"""
    user = db.get_user(user_id)
    if not user:
        await query.edit_message_text("请先 /start 开始使用！")
        return
    exercise = get_daily_exercise(user["level"])
    context.user_data["today_exercise"] = exercise
    msg = format_workout_message(exercise, user["streak"])
    keyboard = [
        [InlineKeyboardButton("✅ 打卡完成", callback_data="cmd_checkin")],
        [InlineKeyboardButton("🔙 返回菜单", callback_data="cmd_menu")],
    ]
    await query.edit_message_text(
        msg,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="HTML",
    )

async def do_checkin_inline(query, context, user_id: int):
    """执行打卡"""
    user = db.get_user(user_id)
    if not user:
        await query.edit_message_text("请先 /start 开始使用！")
        return
    exercise = context.user_data.get("today_exercise") or get_daily_exercise(user["level"])
    result = db.log_workout(user_id, exercise["name"], exercise["reps"], exercise["sets"])
    stats = db.get_workout_stats(user_id)
    streak = result["streak"]
    achievement = None
    if streak == 7:
        achievement = "🏅 一周战士！连续打卡7天！"
    elif streak == 30:
        achievement = "🥇 月度冠军！连续打卡30天！"
    elif streak == 100:
        achievement = "💎 健身达人！累计打卡100次！"
    msg = format_checkin_message(result, stats)
    if achievement:
        msg += f"\n\n🎉 {achievement}"
    keyboard = [
        [InlineKeyboardButton("🏋️ 新任务", callback_data="cmd_today")],
        [InlineKeyboardButton("🔙 返回菜单", callback_data="cmd_menu")],
    ]
    await query.edit_message_text(
        msg,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="HTML",
    )

async def show_stats_inline(query, user_id: int):
    """显示统计"""
    stats = db.get_workout_stats(user_id)
    await query.edit_message_text(
        format_stats_message(stats),
        reply_markup=get_back_menu_keyboard(),
        parse_mode="HTML",
    )

async def show_help_inline(query):
    """显示帮助"""
    await query.edit_message_text(
        """📖 Fitness5 帮助
━━━━━━━━━━━━━━━━━━

🏋️ 今日任务 — 查看今天做什么运动
✅ 打卡 — 完成今日运动打卡
📊 我的统计 — 查看运动记录
⚖️ 记录体重 — 记录今日体重
⚙️ 设置时间 — 修改每日推送时间

💪 每天5分钟，坚持就是胜利！""",
        reply_markup=get_back_menu_keyboard(),
    )

# ─────────────────────────────────────────────────────────────────────────────
# 命令处理器
# ─────────────────────────────────────────────────────────────────────────────

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/start 命令"""
    user_id = update.effective_user.id
    user = db.get_user(user_id)

    if user:
        # 老用户：显示主菜单
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
            msg,
            reply_markup=get_main_menu_keyboard(),
            parse_mode="HTML",
        )
        return

    # 新用户：引导设置
    await update.message.reply_text("""🏋️ 欢迎来到 Fitness5！

每天5分钟，养成运动习惯。

请告诉我你的名字：""")
    return WAIT_NAME

async def menu_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/menu 命令"""
    user_id = update.effective_user.id
    user = db.get_user(user_id)
    if not user:
        await update.message.reply_text("请先 /start 开始使用！")
        return
    await show_menu_inline(type('obj', (object,), {'edit_message_text': update.message.reply_text, 'from_user': type('obj', (object,), {'id': user_id})()})(), user_id)

async def wait_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """等待输入名字"""
    name = update.message.text.strip()
    context.user_data["name"] = name
    await update.message.reply_text(f"""好的 {name}！👋

最后，告诉我你的目标体重（kg）：
（比如：75）""")
    return WAIT_TARGET

async def wait_target(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """等待输入目标体重"""
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
        format_workout_message(exercise, streak=0),
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="HTML",
    )
    return ConversationHandler.END

async def checkin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/checkin 打卡"""
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
    if streak == 7: achievement = "🏅 一周战士！连续打卡7天！"
    elif streak == 30: achievement = "🥇 月度冠军！连续打卡30天！"
    elif streak == 100: achievement = "💎 健身达人！累计打卡100次！"
    msg = format_checkin_message(result, stats)
    if achievement: msg += f"\n\n🎉 {achievement}"
    keyboard = [
        [InlineKeyboardButton("🏋️ 新任务", callback_data="cmd_today")],
        [InlineKeyboardButton("🔙 返回菜单", callback_data="cmd_menu")],
    ]
    await update.message.reply_text(
        msg,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="HTML",
    )
    new_exercise = get_daily_exercise(user["level"])
    context.user_data["today_exercise"] = new_exercise

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/stats 查看统计"""
    user_id = update.effective_user.id
    user = db.get_user(user_id)
    if not user:
        await update.message.reply_text("请先 /start 绑定账号")
        return
    stats = db.get_workout_stats(user_id)
    keyboard = [
        [InlineKeyboardButton("🔙 返回菜单", callback_data="cmd_menu")],
    ]
    await update.message.reply_text(
        format_stats_message(stats),
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="HTML",
    )

async def weight_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/weight <数字> 记录体重"""
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
            d = h["date"][:10] if isinstance(h["date"], str) else str(h["date"])
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
    keyboard = [
        [InlineKeyboardButton("🔙 返回菜单", callback_data="cmd_menu")],
    ]
    await update.message.reply_text(msg, reply_markup=InlineKeyboardMarkup(keyboard))

async def today_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/today 重新获取今日任务"""
    user_id = update.effective_user.id
    user = db.get_user(user_id)
    if not user:
        await update.message.reply_text("请先 /start 绑定账号")
        return
    exercise = get_daily_exercise(user["level"])
    context.user_data["today_exercise"] = exercise
    keyboard = [
        [InlineKeyboardButton("✅ 打卡完成", callback_data="cmd_checkin")],
        [InlineKeyboardButton("🔙 返回菜单", callback_data="cmd_menu")],
    ]
    await update.message.reply_text(
        format_workout_message(exercise, user["streak"]),
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="HTML",
    )

async def settime_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/settime <HH:MM> 设置推送时间"""
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
    keyboard = [
        [InlineKeyboardButton("🔙 返回菜单", callback_data="cmd_menu")],
    ]
    await update.message.reply_text(
        f"✅ 推送时间已设置为每天 {text}",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/help 帮助"""
    keyboard = [
        [InlineKeyboardButton("🔙 返回菜单", callback_data="cmd_menu")],
    ]
    await update.message.reply_text(
        """📖 Fitness5 命令说明

🏋️ /today  — 今日任务
✅ /checkin — 打卡
📊 /stats   — 运动统计
⚖️ /weight  — 记录体重
⚙️ /settime — 设置推送时间
📖 /help    — 显示帮助

💪 每天5分钟，坚持就是胜利！""",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )

async def unknown_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """未知消息处理"""
    text = update.message.text.strip().lower()
    if text in ["打卡", "done", "完成了", "打", "✅"]:
        await checkin_command(update, context)
    else:
        await update.message.reply_text(
            "试试 /help 查看所有命令，或点击主菜单按钮操作 👇",
            reply_markup=get_main_menu_keyboard(),
        )

# ─────────────────────────────────────────────────────────────────────────────
# 主程序
# ─────────────────────────────────────────────────────────────────────────────
def main():
    if not TELEGRAM_BOT_TOKEN:
        print("❌ 请先设置 TELEGRAM_BOT_TOKEN")
        print("   创建 .env 文件，填入你的 Bot Token")
        return

    app = (
        Application.builder()
        .token(TELEGRAM_BOT_TOKEN)
        .connection_pool_size(2)
        .build()
    )

    # 按钮回调（必须放在命令处理器之前）
    app.add_handler(CallbackQueryHandler(button_callback))

    # 命令处理器
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("today", today_command))
    app.add_handler(CommandHandler("checkin", checkin_command))
    app.add_handler(CommandHandler("stats", stats_command))
    app.add_handler(CommandHandler("weight", weight_command))
    app.add_handler(CommandHandler("settime", settime_command))

    # 文字消息
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start_command)],
        states={
            WAIT_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, wait_name)],
            WAIT_TARGET: [MessageHandler(filters.TEXT & ~filters.COMMAND, wait_target)],
        },
        fallbacks=[],
    )
    app.add_handler(conv_handler)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, unknown_message))

    print("🏋️ Fitness5 Bot 已启动！")
    print("   发送 /start 开始使用")
    print("   发送 /help 查看帮助")

    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
