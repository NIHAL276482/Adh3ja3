import logging
import requests
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ChatPermissions,
    ParseMode,
)
from telegram.ext import (
    Updater,
    CommandHandler,
    MessageHandler,
    Filters,
    CallbackContext,
    CallbackQueryHandler,
)
import time
import psutil
import random
from functools import wraps
from datetime import datetime
import ast
import operator

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# Constants
TINYURL_API_KEY = "s2Eun99SKdluOdpsOWGaxQtfWeRVr45LefNjb3NGtLRhNrzL3rA15HEIWbQ0"
OWNER_ID = 7187126565  # Your chat ID

# Storage (Use a database in production)
afk_users = {}
warnings = {}
muted_users = {}
rules = "No rules set yet."
welcome_message = "Welcome to the group!"
start_time = time.time()
group_locked = False
warn_limit = 3
group_link = ""
flood_settings = {"max_messages": 5, "time_window": 10}
user_messages = {}
disabled_commands = set()
user_nicknames = {}
chat_users = {}

# ================== Helper Functions ================== #

# Check if user is owner
def is_owner(user_id: int) -> bool:
    return user_id == OWNER_ID

# Owner-only decorator
def owner_only(func):
    @wraps(func)
    def wrapper(update: Update, context: CallbackContext):
        if not is_owner(update.effective_user.id):
            update.message.reply_text("🚫 This command is restricted to the owner only!")
            return
        return func(update, context)
    return wrapper

# Admin decorator
def check_admin(func):
    @wraps(func)
    def wrapper(update: Update, context: CallbackContext):
        user = update.effective_user
        chat = update.effective_chat
        if chat.type == "private":
            update.message.reply_text("This command only works in groups!")
            return
        member = chat.get_member(user.id)
        if member.status not in ["administrator", "creator"]:
            update.message.reply_text("You need to be admin to use this!")
            return
        return func(update, context)
    return wrapper

# Get user ID
def get_user_id(update: Update, context: CallbackContext):
    if not context.args:
        return None
    if update.message.reply_to_message:
        return update.message.reply_to_message.from_user.id
    if context.args[0].startswith("@"):
        username = context.args[0][1:]
        try:
            user = context.bot.get_chat_member(update.effective_chat.id, username).user
            return user.id
        except:
            return None
    elif context.args[0].isdigit():
        return int(context.args[0])
    return None

# URL Shortener
def shorten_url(url: str) -> str:
    try:
        response = requests.post(
            "https://api.tinyurl.com/create",
            headers={"Authorization": f"Bearer {TINYURL_API_KEY}"},
            json={"url": url}
        )
        if response.status_code == 200:
            return response.json()["data"]["tiny_url"]
        return url  # Fallback to original URL
    except Exception as e:
        logger.error(f"Error shortening URL: {e}")
        return url

# ================== Commands ================== #

# Help Command
def help_command(update: Update, context: CallbackContext):
    update.message.reply_text(
        "Available commands:\n"
        "/start - Start the bot\n"
        "/help - Show this help message\n"
        "/warn <user> - Warn a user\n"
        "/ban <user> - Ban a user\n"
        "/kick <user> - Kick a user\n"
        "/mute <user> - Mute a user\n"
        "/unmute <user> - Unmute a user\n"
        "/purge <number> - Purge messages\n"
        "/promote <user> - Promote a user to admin\n"
        "/lock - Lock the group\n"
        "/unlock - Unlock the group\n"
        "/setrules <rules> - Set group rules\n"
        "/setwelcome <message> - Set welcome message\n"
        "/warnings <user> - Check warnings for a user\n"
        "/kickme - Leave the group\n"
        "/afk <reason> - Set AFK status\n"
        "/unafk - Remove AFK status\n"
        "/rules - Show group rules\n"
        "/feedback <message> - Send feedback\n"
        "/suggest <message> - Suggest something\n"
        "/cpuusage - Show CPU usage\n"
        "/memusage - Show memory usage\n"
        "/uptime - Show bot uptime\n"
        "/status - Show bot status\n"
        "/translate <text> - Translate text\n"
        "/poll <question> - Create a poll\n"
        "/tag <message> - Tag all users\n"
        "/shorten <url> - Shorten a URL\n"
        "/broadcast <message> - Broadcast a message (Owner only)"
    )

# Warn User
@check_admin
def warn_user(update: Update, context: CallbackContext):
    user_id = get_user_id(update, context)
    if not user_id:
        update.message.reply_text("Please reply to a user or specify a user ID/username.")
        return

    if user_id not in warnings:
        warnings[user_id] = 0
    warnings[user_id] += 1

    if warnings[user_id] >= warn_limit:
        context.bot.kick_chat_member(update.effective_chat.id, user_id)
        update.message.reply_text(f"User {user_id} has been banned for exceeding warning limits!")
    else:
        update.message.reply_text(f"User {user_id} has been warned! ({warnings[user_id]}/{warn_limit})")

# Ban User
@check_admin
def ban_user(update: Update, context: CallbackContext):
    user_id = get_user_id(update, context)
    if not user_id:
        update.message.reply_text("Please reply to a user or specify a user ID/username.")
        return

    try:
        context.bot.kick_chat_member(update.effective_chat.id, user_id)
        update.message.reply_text(f"User {user_id} has been banned!")
    except Exception as e:
        update.message.reply_text(f"❌ Failed to ban user: {e}")

# Kick User
@check_admin
def kick_user(update: Update, context: CallbackContext):
    user_id = get_user_id(update, context)
    if not user_id:
        update.message.reply_text("Please reply to a user or specify a user ID/username.")
        return

    try:
        context.bot.kick_chat_member(update.effective_chat.id, user_id)
        context.bot.unban_chat_member(update.effective_chat.id, user_id)
        update.message.reply_text(f"User {user_id} has been kicked!")
    except Exception as e:
        update.message.reply_text(f"❌ Failed to kick user: {e}")

# Mute User
@check_admin
def mute_user(update: Update, context: CallbackContext):
    user_id = get_user_id(update, context)
    if not user_id:
        update.message.reply_text("Please reply to a user or specify a user ID/username.")
        return

    try:
        context.bot.restrict_chat_member(
            update.effective_chat.id,
            user_id,
            ChatPermissions(can_send_messages=False),
        )
        muted_users[user_id] = True
        update.message.reply_text(f"🔇 User {user_id} has been muted!")
    except Exception as e:
        update.message.reply_text(f"❌ Failed to mute user: {e}")

# Unmute User
@check_admin
def unmute_user(update: Update, context: CallbackContext):
    user_id = get_user_id(update, context)
    if not user_id:
        update.message.reply_text("Please reply to a user or specify a user ID/username.")
        return

    try:
        context.bot.restrict_chat_member(
            update.effective_chat.id,
            user_id,
            ChatPermissions(can_send_messages=True),
        )
        muted_users.pop(user_id, None)
        update.message.reply_text(f"🔊 User {user_id} has been unmuted!")
    except Exception as e:
        update.message.reply_text(f"❌ Failed to unmute user: {e}")

# Purge Messages
@check_admin
def purge_messages(update: Update, context: CallbackContext):
    if not context.args or not context.args[0].isdigit():
        update.message.reply_text("Usage: /purge <number>")
        return

    num_messages = int(context.args[0])
    if num_messages <= 0:
        update.message.reply_text("Please specify a positive number.")
        return

    chat_id = update.effective_chat.id
    message_id = update.message.message_id
    messages_to_delete = []

    for i in range(1, num_messages + 1):
        messages_to_delete.append(message_id - i)

    try:
        context.bot.delete_messages(chat_id, messages_to_delete)
        update.message.reply_text(f"Purged {num_messages} messages!")
    except Exception as e:
        update.message.reply_text(f"❌ Failed to purge messages: {e}")

# Promote User
@check_admin
def promote_user(update: Update, context: CallbackContext):
    user_id = get_user_id(update, context)
    if not user_id:
        update.message.reply_text("Please reply to a user or specify a user ID/username.")
        return

    try:
        context.bot.promote_chat_member(
            update.effective_chat.id,
            user_id,
            can_change_info=True,
            can_delete_messages=True,
            can_invite_users=True,
            can_restrict_members=True,
            can_pin_messages=True,
            can_promote_members=True,
        )
        update.message.reply_text(f"User {user_id} has been promoted to admin!")
    except Exception as e:
        update.message.reply_text(f"❌ Failed to promote user: {e}")

# Lock Group
@check_admin
def lock_group(update: Update, context: CallbackContext):
    global group_locked
    group_locked = True
    update.message.reply_text("🔒 Group has been locked!")

# Unlock Group
@check_admin
def unlock_group(update: Update, context: CallbackContext):
    global group_locked
    group_locked = False
    update.message.reply_text("🔓 Group has been unlocked!")

# Set Rules
@check_admin
def set_rules(update: Update, context: CallbackContext):
    global rules
    if not context.args:
        update.message.reply_text("Usage: /setrules <rules>")
        return

    rules = " ".join(context.args)
    update.message.reply_text("✅ Rules have been updated!")

# Set Welcome
@check_admin
def set_welcome(update: Update, context: CallbackContext):
    global welcome_message
    if not context.args:
        update.message.reply_text("Usage: /setwelcome <message>")
        return

    welcome_message = " ".join(context.args)
    update.message.reply_text("✅ Welcome message has been updated!")

# Check Warnings
def check_warnings(update: Update, context: CallbackContext):
    user_id = get_user_id(update, context)
    if not user_id:
        update.message.reply_text("Please reply to a user or specify a user ID/username.")
        return

    if user_id in warnings:
        update.message.reply_text(f"User {user_id} has {warnings[user_id]} warnings.")
    else:
        update.message.reply_text(f"User {user_id} has no warnings.")

# Kickme Command
def kickme_command(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    try:
        context.bot.kick_chat_member(update.effective_chat.id, user_id)
        context.bot.unban_chat_member(update.effective_chat.id, user_id)
        update.message.reply_text("You have left the group!")
    except Exception as e:
        update.message.reply_text(f"❌ Failed to kick you: {e}")

# AFK Command
def afk_command(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    reason = " ".join(context.args) if context.args else "No reason provided"
    afk_users[user_id] = reason
    update.message.reply_text(f"🚶 You are now AFK: {reason}")

# UnAFK Command
def unafk_command(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    if user_id in afk_users:
        afk_users.pop(user_id)
        update.message.reply_text("✅ You are no longer AFK!")

# Rules Command
def rules_command(update: Update, context: CallbackContext):
    update.message.reply_text(f"📜 Group Rules:\n{rules}")

# Feedback Command
def feedback_command(update: Update, context: CallbackContext):
    if not context.args:
        update.message.reply_text("Usage: /feedback <message>")
        return

    feedback = " ".join(context.args)
    context.bot.send_message(OWNER_ID, f"📝 Feedback from {update.effective_user.id}:\n{feedback}")
    update.message.reply_text("✅ Feedback sent!")

# Suggest Command
def suggest_command(update: Update, context: CallbackContext):
    if not context.args:
        update.message.reply_text("Usage: /suggest <message>")
        return

    suggestion = " ".join(context.args)
    context.bot.send_message(OWNER_ID, f"💡 Suggestion from {update.effective_user.id}:\n{suggestion}")
    update.message.reply_text("✅ Suggestion sent!")

# CPU Usage Command
def cpu_usage_command(update: Update, context: CallbackContext):
    cpu_usage = psutil.cpu_percent()
    update.message.reply_text(f"🖥️ CPU Usage: {cpu_usage}%")

# Memory Usage Command
def mem_usage_command(update: Update, context: CallbackContext):
    mem_usage = psutil.virtual_memory().percent
    update.message.reply_text(f"🧠 Memory Usage: {mem_usage}%")

# Uptime Command
def uptime_command(update: Update, context: CallbackContext):
    uptime = time.time() - start_time
    hours, remainder = divmod(uptime, 3600)
    minutes, seconds = divmod(remainder, 60)
    update.message.reply_text(f"⏱️ Uptime: {int(hours)}h {int(minutes)}m {int(seconds)}s")

# Status Command
def status_command(update: Update, context: CallbackContext):
    update.message.reply_text("🤖 Bot is online and running!")

# Translate Command
def translate_command(update: Update, context: CallbackContext):
    if not context.args:
        update.message.reply_text("Usage: /translate <text>")
        return

    text = " ".join(context.args)
    # Add translation logic here (e.g., using an API)
    update.message.reply_text(f"🌐 Translation: {text} (Placeholder)")

# Poll Command
def poll_command(update: Update, context: CallbackContext):
    if not context.args:
        update.message.reply_text("Usage: /poll <question>")
        return

    question = " ".join(context.args)
    options = ["Yes", "No"]
    context.bot.send_poll(update.effective_chat.id, question, options)

# Tag Command
def tag_command(update: Update, context: CallbackContext):
    if not context.args:
        update.message.reply_text("Usage: /tag <message>")
        return

    message = " ".join(context.args)
    tagged_users = " ".join([f"@{user}" for user in chat_users])
    update.message.reply_text(f"{tagged_users}\n{message}")

# URL Shortener Command
def shorten_command(update: Update, context: CallbackContext):
    if not context.args:
        update.message.reply_text("Usage: /shorten <url>")
        return

    url = context.args[0]
    shortened_url = shorten_url(url)
    update.message.reply_text(f"🔗 Shortened URL:\n{shortened_url}")

# Broadcast Command (Owner Only)
@owner_only
def broadcast_command(update: Update, context: CallbackContext):
    if not context.args:
        update.message.reply_text("Usage: /broadcast <message>")
        return

    message = " ".join(context.args)
    for user_id in chat_users:
        try:
            context.bot.send_message(user_id, f"📢 Broadcast:\n{message}")
        except:
            pass
    update.message.reply_text("📢 Broadcast sent to all users!")

# ================== Handler Setup ================== #

def main():
    TOKEN = "8131621643:AAFw7fB6bSNScQTiPdp7wTrJ6mUEdlw18SU"  # Replace with your bot token
    updater = Updater(TOKEN, use_context=True)
    dp = updater.dispatcher

    # Command Handlers
    dp.add_handler(CommandHandler("start", help_command))
    dp.add_handler(CommandHandler("help", help_command))
    dp.add_handler(CommandHandler("warn", warn_user))
    dp.add_handler(CommandHandler("ban", ban_user))
    dp.add_handler(CommandHandler("kick", kick_user))  # Fixed indentation
    dp.add_handler(CommandHandler("mute", mute_user))
    dp.add_handler(CommandHandler("unmute", unmute_user))
    dp.add_handler(CommandHandler("purge", purge_messages))
    dp.add_handler(CommandHandler("promote", promote_user))
    dp.add_handler(CommandHandler("lock", lock_group))
    dp.add_handler(CommandHandler("unlock", unlock_group))
    dp.add_handler(CommandHandler("setrules", set_rules))
    dp.add_handler(CommandHandler("setwelcome", set_welcome))
    dp.add_handler(CommandHandler("warnings", check_warnings))
    dp.add_handler(CommandHandler("kickme", kickme_command))
    dp.add_handler(CommandHandler("afk", afk_command))
    dp.add_handler(CommandHandler("unafk", unafk_command))
    dp.add_handler(CommandHandler("rules", rules_command))
    dp.add_handler(CommandHandler("feedback", feedback_command))
    dp.add_handler(CommandHandler("suggest", suggest_command))
    dp.add_handler(CommandHandler("cpuusage", cpu_usage_command))
    dp.add_handler(CommandHandler("memusage", mem_usage_command))
    dp.add_handler(CommandHandler("uptime", uptime_command))
    dp.add_handler(CommandHandler("status", status_command))
    dp.add_handler(CommandHandler("translate", translate_command))
    dp.add_handler(CommandHandler("poll", poll_command))
    dp.add_handler(CommandHandler("tag", tag_command))
    dp.add_handler(CommandHandler("shorten", shorten_command))
    dp.add_handler(CommandHandler("broadcast", broadcast_command))

    # Message Handlers
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_message))

    # Error Handler
    dp.add_error_handler(error_handler)

    # Start the Bot
    updater.start_polling()
    updater.idle()

# ================== Message Handlers ================== #

def handle_message(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id

    # Track user messages for flood control
    if user_id not in user_messages:
        user_messages[user_id] = []
    user_messages[user_id].append(time.time())

    # Flood control logic
    messages = user_messages[user_id]
    current_time = time.time()
    messages_in_window = [msg_time for msg_time in messages if current_time - msg_time <= flood_settings["time_window"]]

    if len(messages_in_window) > flood_settings["max_messages"]:
        context.bot.restrict_chat_member(
            chat_id,
            user_id,
            ChatPermissions(can_send_messages=False),
        )
        update.message.reply_text(f"🔇 User {user_id} has been muted for flooding!")
        user_messages[user_id] = []

    # Check if user is AFK
    if user_id in afk_users:
        reason = afk_users[user_id]
        update.message.reply_text(f"🚶 User is AFK: {reason}")

    # Update chat users
    if user_id not in chat_users:
        chat_users[user_id] = update.effective_user.username or f"User_{user_id}"

# ================== Error Handler ================== #

def error_handler(update: Update, context: CallbackContext):
    logger.error(f"Update {update} caused error {context.error}")

# ================== Main Execution ================== #

if __name__ == "__main__":
    main()
