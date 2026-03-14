import os
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, ContextTypes, MessageHandler, CommandHandler, filters
from agent import handle_message


# Load environment variables
load_dotenv()
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

# In-memory sessions storage
sessions = {}


async def handle_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle incoming text messages from users.
    
    Args:
        update: The update object containing the message
        context: The context object
    """
    # Get user ID and message text
    user_id = str(update.effective_user.id)
    message_text = update.message.text
    
    # Get response from agent
    response = handle_message(user_id, message_text, sessions)
    
    # Send response back to user
    await update.message.reply_text(response)


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle /start command.
    
    Args:
        update: The update object containing the message
        context: The context object
    """
    user_id = str(update.effective_user.id)
    
    # Send welcome message
    welcome_msg = "నమస్కారం! 🙏 మీ వ్యాపార రకం చెప్పండి (ఉదా: kirana, tailor, salon)"
    await update.message.reply_text(welcome_msg)


def main():
    """Start the Telegram bot."""
    
    if not TELEGRAM_BOT_TOKEN:
        print("Error: TELEGRAM_BOT_TOKEN not found in .env file")
        return
    
    # Create the Application
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    
    # Add /start command handler
    application.add_handler(CommandHandler("start", start_command))
    
    # Add a message handler for all text messages (excluding commands)
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_message))
    
    # Start the bot
    print("🤖 scheme-saathi Telegram bot started!")
    application.run_polling()


if __name__ == "__main__":
    main()
