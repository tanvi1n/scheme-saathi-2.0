import os
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, ContextTypes, MessageHandler, CommandHandler, CallbackQueryHandler, filters
from agent import handle_message


# Load environment variables
load_dotenv()
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

# In-memory sessions storage
sessions = {}


def create_scheme_category_buttons():
    """Create buttons for scheme category selection"""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🏢 Business Schemes (వ్యాపార పథకాలు)", callback_data="category_business")],
        [InlineKeyboardButton("👤 Individual Schemes (వ్యక్తిగత పథకాలు)", callback_data="category_individual")]
    ])


def create_business_type_buttons():
    """Create buttons for business type selection"""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🏪 Kirana/Grocery (కిరాణా)", callback_data="business_1")],
        [InlineKeyboardButton("✂️ Tailor (టైలర్)", callback_data="business_2")],
        [InlineKeyboardButton("💇 Salon/Beauty (సెలూన్)", callback_data="business_3")],
        [InlineKeyboardButton("🥬 Vegetable Vendor (కూరగాయల వ్యాపారి)", callback_data="business_4")],
        [InlineKeyboardButton("🚗 Auto (ఆటో)", callback_data="business_5")],
        [InlineKeyboardButton("📝 Other (ఇతర)", callback_data="business_6")]
    ])


def create_gender_buttons():
    """Create buttons for gender selection"""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("👨 Male (పురుషుడు)", callback_data="gender_1")],
        [InlineKeyboardButton("👩 Female (స్త్రీ)", callback_data="gender_2")],
        [InlineKeyboardButton("⚧ Other (ఇతర)", callback_data="gender_3")]
    ])


def create_caste_buttons():
    """Create buttons for caste selection"""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("General", callback_data="caste_1")],
        [InlineKeyboardButton("SC", callback_data="caste_2")],
        [InlineKeyboardButton("ST", callback_data="caste_3")],
        [InlineKeyboardButton("OBC", callback_data="caste_4")],
        [InlineKeyboardButton("Minority", callback_data="caste_5")]
    ])


def create_yes_no_buttons(prefix):
    """Create Yes/No buttons with given prefix"""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Yes (అవును)", callback_data=f"{prefix}_1")],
        [InlineKeyboardButton("❌ No (లేదు)", callback_data=f"{prefix}_2")]
    ])


def create_scheme_selection_buttons(num_schemes):
    """Create numbered buttons for scheme selection"""
    buttons = []
    for i in range(1, min(num_schemes + 1, 9)):  # Max 8 schemes
        buttons.append([InlineKeyboardButton(f"{i}", callback_data=f"scheme_{i}")])
    return InlineKeyboardMarkup(buttons)


def get_button_response(text, callback_data):
    """Determine if response needs buttons and which type"""
    if "మీరు ఏ రకమైన పథకాలు" in text:
        return create_scheme_category_buttons()
    elif "మీ వ్యాపార రకం ఎంచుకోండి" in text:
        return create_business_type_buttons()
    elif "మీ లింగం చెప్పండి" in text:
        return create_gender_buttons()
    elif "మీ కులం చెప్పండి" in text:
        return create_caste_buttons()
    elif "GST registration ఉందా" in text:
        return create_yes_no_buttons("gst")
    elif "bank account ఉందా" in text:
        return create_yes_no_buttons("bank")
    elif "white ration card ఉందా" in text:
        return create_yes_no_buttons("ration")
    elif "వ్యవసాయ భూమి ఉందా" in text:
        return create_yes_no_buttons("land")
    elif "ఏది మరింత తెలుసుకోవాలి" in text or "ఏ పథకం గురించి మరింత తెలుసుకోవాలి" in text:
        # Count schemes in the text
        import re
        matches = re.findall(r'^\d+\.', text, re.MULTILINE)
        return create_scheme_selection_buttons(len(matches))
    return None


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
    
    # Check if response needs buttons
    buttons = get_button_response(response, None)
    
    # Send response back to user
    if buttons:
        await update.message.reply_text(response, reply_markup=buttons)
    else:
        await update.message.reply_text(response)


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle button clicks from inline keyboards.
    
    Args:
        update: The update object containing the callback query
        context: The context object
    """
    query = update.callback_query
    await query.answer()  # Acknowledge the button click
    
    user_id = str(query.from_user.id)
    callback_data = query.data
    
    # Convert button callback to text input that agent understands
    button_to_text = {
        # Scheme category
        "category_business": "1",
        "category_individual": "2",
        
        # Business type
        "business_1": "1",
        "business_2": "2", 
        "business_3": "3",
        "business_4": "4",
        "business_5": "5",
        "business_6": "6",
        
        # Gender
        "gender_1": "1",
        "gender_2": "2",
        "gender_3": "3",
        
        # Caste
        "caste_1": "1",
        "caste_2": "2",
        "caste_3": "3",
        "caste_4": "4",
        "caste_5": "5",
        
        # Yes/No questions
        "gst_1": "1", "gst_2": "2",
        "bank_1": "1", "bank_2": "2",
        "ration_1": "1", "ration_2": "2",
        "land_1": "1", "land_2": "2",
        
        # Scheme selection (1-8)
        "scheme_1": "1", "scheme_2": "2", "scheme_3": "3", "scheme_4": "4",
        "scheme_5": "5", "scheme_6": "6", "scheme_7": "7", "scheme_8": "8"
    }
    
    # Convert button click to text input
    text_input = button_to_text.get(callback_data, callback_data)
    
    # Get response from agent
    response = handle_message(user_id, text_input, sessions)
    
    # Check if response needs buttons
    buttons = get_button_response(response, callback_data)
    
    # Send response - try to edit, if fails send new message
    try:
        if buttons:
            await query.edit_message_text(response, reply_markup=buttons)
        else:
            await query.edit_message_text(response)
    except Exception:
        # If edit fails, send new message
        if buttons:
            await query.message.reply_text(response, reply_markup=buttons)
        else:
            await query.message.reply_text(response)


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle /start command.
    
    Args:
        update: The update object containing the message
        context: The context object
    """
    user_id = str(update.effective_user.id)
    
    # Use agent's handle_message with "hi" to trigger proper flow
    response = handle_message(user_id, "hi", sessions)
    
    # Check if response needs buttons
    buttons = get_button_response(response, None)
    
    # Send response with buttons if needed
    if buttons:
        await update.message.reply_text(response, reply_markup=buttons)
    else:
        await update.message.reply_text(response)


def main():
    """Start the Telegram bot."""
    
    if not TELEGRAM_BOT_TOKEN:
        print("Error: TELEGRAM_BOT_TOKEN not found in .env file")
        return
    
    # Create the Application
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    
    # Add /start command handler
    application.add_handler(CommandHandler("start", start_command))
    
    # Add button click handler
    application.add_handler(CallbackQueryHandler(button_handler))
    
    # Add a message handler for all text messages (excluding commands)
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_message))
    
    # Start the bot
    print("🤖 scheme-saathi Telegram bot started!")
    application.run_polling()


if __name__ == "__main__":
    main()
