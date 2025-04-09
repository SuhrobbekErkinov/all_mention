import logging
import sqlite3
from datetime import datetime, timedelta
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters
import os
from dotenv import load_dotenv
# Enable logging
load_dotenv()

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Replace with your bot token
BOT_TOKEN = os.getenv("BOT_TOKEN")


# Database setup
def setup_database():
    conn = sqlite3.connect('group_members.db')
    cursor = conn.cursor()
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS members (
        user_id INTEGER,
        chat_id INTEGER,
        username TEXT,
        first_name TEXT,
        last_active TIMESTAMP,
        PRIMARY KEY (user_id, chat_id)
    )
    ''')
    conn.commit()
    return conn


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /start is issued."""
    await update.message.reply_text(
        "Hi! I'm a mention-all bot. Add me to a group and use /all to mention everyone who has been active in the group."
    )


async def track_user(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Track users who send messages in the group."""
    if update.effective_chat.type in ["group", "supergroup"]:
        user = update.effective_user
        chat_id = update.effective_chat.id

        if user and not user.is_bot:
            conn = setup_database()
            cursor = conn.cursor()

            # Update or insert user info
            cursor.execute('''
            INSERT OR REPLACE INTO members (user_id, chat_id, username, first_name, last_active)
            VALUES (?, ?, ?, ?, ?)
            ''', (user.id, chat_id, user.username, user.first_name, datetime.now().isoformat()))

            conn.commit()
            conn.close()


async def mention_all(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Mention all tracked users in the group."""
    if update.effective_chat.type in ["group", "supergroup"]:
        chat_id = update.effective_chat.id

        # Get active users from database (active in the last 30 days)
        conn = setup_database()
        cursor = conn.cursor()

        # Calculate date 30 days ago
        thirty_days_ago = (datetime.now() - timedelta(days=30)).isoformat()

        cursor.execute('''
        SELECT user_id, username, first_name FROM members
        WHERE chat_id = ? AND last_active > ?
        ''', (chat_id, thirty_days_ago))

        members = cursor.fetchall()
        conn.close()

        if not members:
            await update.message.reply_text(
                "No active members found yet. As members send messages in the group, I'll start tracking them."
            )
            return

        # Create mention text
        mention_text = "🔔 Attention everyone!\n"

        for user_id, username, first_name in members:
            if username:
                mention_text += f"@{username} "
            else:
                mention_text += f"[{first_name}](tg://user?id={user_id}) "

        # Send the mention message (split into chunks if needed)
        if len(mention_text) > 4000:
            parts = []
            current_part = "🔔 Attention everyone!\n"

            for user_id, username, first_name in members:
                mention = f"@{username} " if username else f"[{first_name}](tg://user?id={user_id}) "

                if len(current_part) + len(mention) > 4000:
                    parts.append(current_part)
                    current_part = mention
                else:
                    current_part += mention

            if current_part:
                parts.append(current_part)

            for part in parts:
                await update.message.reply_text(part, parse_mode="Markdown")
        else:
            await update.message.reply_text(mention_text, parse_mode="Markdown")
    else:
        await update.message.reply_text("This command only works in groups.")


def main() -> None:
    """Start the bot."""
    # Create the database
    setup_database()

    # Create the Application
    application = Application.builder().token(BOT_TOKEN).build()

    # Add command handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("all", mention_all))

    # Handle messages with @all
    application.add_handler(MessageHandler(
        filters.Regex(r'^@all') & filters.ChatType.GROUPS,
        mention_all
    ))

    # Track all messages in groups
    application.add_handler(MessageHandler(
        filters.ChatType.GROUPS,
        track_user
    ))

    # Run the bot
    application.run_polling()


if __name__ == "__main__":
    main()