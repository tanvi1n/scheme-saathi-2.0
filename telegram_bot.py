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


def create_eligibility_result_buttons():
    """Create buttons for eligibility result actions"""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📋 Documents చూడండి", callback_data="result_documents"),
            InlineKeyboardButton("🔄 మళ్ళీ మొదలు", callback_data="result_restart")
        ]
    ])


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
    elif "📋 డాక్యుమెంట్ల కోసం" in text and "🔄 మరొక పథకం కోసం" in text:
        return create_eligibility_result_buttons()
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
        "scheme_5": "5", "scheme_6": "6", "scheme_7": "7", "scheme_8": "8",
        
        # Eligibility result actions
        "result_documents": "documents",
        "result_restart": "restart"
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


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle /help command - Show usage guide.
    
    Args:
        update: The update object containing the message
        context: The context object
    """
    help_text = """🤝 *scheme-saathi సహాయం* 🤝

scheme-saathi అనేది విస్తృత సరकార పథకాల గురించి తెలుసుకోవడానికి సహాయం చేసే బాట్.

*ఎలా ఉపయోగించాలి:*

1️⃣ /start నొక్కండి లేదా "start" టైప్ చేయండి
2️⃣ మీ వ్యాపార రకం चెप్పండి (kirana, tailor, salon, etc.)
3️⃣ లభ్యమైన పథకాలను చూడండి
4️⃣ అర్హతను తనిఖీ చేయండి (3-4 ప్రశ్నలకు సమాధానం ఇవ్వండి)
5️⃣ అవసరమైన డాక్యుమెంట్‌ల జాబితాను పొందండి

*ఎక్కువ సమాచారం:*
• /about - బాట్ గురించి తెలుసుకోండి
• /restart - కొత్త సెషన్ ప్రారంభించండి
• /documents - డాక్యుమెంట్‌ల గురించి సూచనలు

ఏ సమయ కూడా తెలుసుకోవడానికి సంకోచించవద్దు! 😊"""
    
    await update.message.reply_text(help_text, parse_mode="Markdown")


async def restart_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle /restart command - Clear session and start fresh.
    
    Args:
        update: The update object containing the message
        context: The context object
    """
    user_id = str(update.effective_user.id)
    
    # Clear user session
    if user_id in sessions:
        sessions.pop(user_id)
    
    # Send restart message
    response_text = "✅ సెషన్ క్లియర్ చేయబడింది! కొత్త వృత్తం ప్రారంభమవుతోంది... \n\n"
    
    # Restart the conversation
    response = handle_message(user_id, "hi", sessions)
    response_text += response
    
    # Check if response needs buttons
    buttons = get_button_response(response, None)
    
    # Send response with buttons if needed
    if buttons:
        await update.message.reply_text(response_text, reply_markup=buttons)
    else:
        await update.message.reply_text(response_text)


async def documents_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle /documents command - Show document guide information.
    
    Args:
        update: The update object containing the message
        context: The context object
    """
    docs_text = """📄 *డాక్యుమెంట్‌ల గురించి సమాచారం* 📄

scheme-saathi బాట్ ఏ పథకం కోసం ఏ నిర్దిష్ట డాక్యుమెంట్‌లు అవసరమైనవో చెప్పుతుంది.

*సాధారణ డాక్యుమెంట్‌లు (చాలా పథకాలకు అవసరం):*
✅ Aadhaar Card (ఆధార్ కార్డు)
✅ Bank Passbook - మొదటి పేజీ (బ్యాంక్ పాస్‌బుక్)
✅ Phone Number (ఫోన్ నంబర్)

*కమ్యూనిటీ ఆధారిత డాక్యుమెంట్‌లు:*
📋 Caste Certificate (కులం సర్టిఫికేట్) → MeeSeva కేంద్రం
📋 Income Certificate (ఆదాయ సర్టిఫికేట్) → TahasildarOffice
📋 Ration Card (నిషేధ కార్డు) → FoodSupply

*GST సంబంధిత డాక్యుమెంట్‌లు (వ్యాపారం కోసం):*
💼 GST Certificate (జిఎస్టీ సర్టిఫికేట్) - GST Portal నుండి
💼 ITR/Form 16 - TDS సంబంధిత

*ఎక్కువ సమాచారం:*
📍 /start ఉపయోగించిన తర్వాత, పథకం ఎంచుకున్న తర్వాత సరిసరి డాక్యుమెంట్‌ల జాబితా పొందుతారు!

❓ ఇంకా సమస్యలు ఉండితే /help చూడండి!"""
    
    await update.message.reply_text(docs_text, parse_mode="Markdown")


async def about_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle /about command - Show information about the bot.
    
    Args:
        update: The update object containing the message
        context: The context object
    """
    about_text = """🤝 *scheme-saathi గురించి* 🤝

*సమస్య:*
తెలంగాణలో 50+ సరకార పథకాలు ఉన్నాయి, కానీ చిన్న వ్యాపారులకు ఎవరు అర్హులు అని తెలియదు. దలాళ్లు ₹5,000–₹50,000 వసూలు చేస్తారు!

*పరిష్కారం:*
scheme-saathi వంటి పరిష్కారం:
✅ తెలుగులో పూర్తిగా నిరంకుశ సహాయం
✅ అర్హతను 3-4 ప్రశ్నలలో తనిఖీ చేయండి
✅ డాక్యుమెంట్ గైడ్ తక్షణమే పొందండి
✅ దాకుံలు దూరం - స్వేచ్ఛా సేవ!

*సమర్థిత పథకాలు:*
📌 PM Vishwakarma (నెసీ స్కీమ్)
📌 Mudra Loan Yojana (మూడ్రా లోన్)
📌 PMEGP (ఎంటర్‌ప్రెన్యూర్‌షిప్ స్కీమ్)
📌 WE-HUB (మహిళా ఎంటర్‌ప్రెన్యూర్‌షిప్)
📌 చిన్న వ్యాపారం పథకాలు

*సంపర్క సమాచారం:*
📞 సమస్యలు? /help నొక్కండి
📧 ఇతర సందేహాలు? supported@scheme-saathi.com

*సంస్కరణ:* 1.0
*భాష:* తెలుగు + English
*ప్ల్యాట్‌ఫారమ్:* Telegram

ధన్యవాదాలు! scheme-saathiని ఉపయోగించినందుకు! 🙏"""
    
    await update.message.reply_text(about_text, parse_mode="Markdown")


def main():
    """Start the Telegram bot."""
    
    if not TELEGRAM_BOT_TOKEN:
        print("Error: TELEGRAM_BOT_TOKEN not found in .env file")
        return
    
    # Create the Application
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    
    # Add command handlers
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("restart", restart_command))
    application.add_handler(CommandHandler("documents", documents_command))
    application.add_handler(CommandHandler("about", about_command))
    
    # Add button click handler
    application.add_handler(CallbackQueryHandler(button_handler))
    
    # Add a message handler for all text messages (excluding commands)
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_message))
    
    # Start the bot
    print("🤖 scheme-saathi Telegram bot started!")
    print("📋 Commands available: /start, /help, /restart, /documents, /about")
    application.run_polling()


if __name__ == "__main__":
    main()
