import os
import requests
import tempfile
import re
import unicodedata
from dotenv import load_dotenv
from gtts import gTTS
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, ContextTypes, MessageHandler, CommandHandler, CallbackQueryHandler, filters
from agent import handle_message


# Load environment variables
load_dotenv()
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

# In-memory sessions storage
sessions = {}


def _detect_tts_language(text: str) -> str:
    """Detect Telugu vs English for TTS voice selection."""
    if re.search(r"[\u0C00-\u0C7F]", text):
        return "te"
    return "en"


def _is_prompt_like_response(text: str, buttons=None) -> bool:
    """Speak prompts/questions so users can hear next step."""
    if buttons:
        return True

    lowered = text.lower()
    prompt_markers = [
        "?", "ఉందా", "చెప్పండి", "ఎంచుకోండి", "type", "టైప్ చేయండి", "more details",
        "which", "ఏది", "ఏ పథకం"
    ]
    return any(marker in lowered for marker in prompt_markers)


def _sanitize_tts_text(text: str) -> str:
    """Remove emojis/decorative symbols so TTS reads cleanly."""
    cleaned = re.sub(r"https?://\S+", " ", text)
    cleaned = re.sub(r"[*_`~#\[\](){}]", " ", cleaned)

    filtered_chars = []
    for char in cleaned:
        category = unicodedata.category(char)
        # So (Symbol, other) includes most emojis/pictographs.
        if category == "So":
            continue
        # Drop emoji variation selector.
        if ord(char) == 0xFE0F:
            continue
        filtered_chars.append(char)

    cleaned = "".join(filtered_chars)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


async def _send_tts_reply(message, text: str, buttons=None) -> None:
    """Send TTS voice note for prompt-like messages."""
    if not text or not _is_prompt_like_response(text, buttons):
        return

    sanitized_text = _sanitize_tts_text(text)
    if not sanitized_text:
        return

    safe_text = sanitized_text[:500]
    lang = _detect_tts_language(safe_text)

    try:
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as temp_audio:
            temp_audio_path = temp_audio.name

        tts = gTTS(text=safe_text, lang=lang)
        tts.save(temp_audio_path)

        with open(temp_audio_path, "rb") as audio_file:
            await message.reply_voice(voice=audio_file)
    except Exception as e:
        print(f"TTS Error: {e}")
    finally:
        if 'temp_audio_path' in locals() and os.path.exists(temp_audio_path):
            os.remove(temp_audio_path)


def _extract_first_number(text: str):
    import re
    match = re.search(r"\d+", text)
    return match.group(0) if match else None


def _map_yes_no(text: str):
    cleaned = text.strip().lower()
    if any(word in cleaned for word in ["అవును", "yes", "yeah", "yep", "ఉంది"]):
        return "1"
    if any(word in cleaned for word in ["లేదు", "లేద", "no", "nope"]):
        return "2"
    return None


def normalize_voice_input(user_id: str, transcribed_text: str) -> str:
    """Map imperfect speech transcription into values expected by the agent state."""
    cleaned = transcribed_text.strip().lower()

    # Global command mapping
    if any(word in cleaned for word in ["restart", "re start", "రిస్టార్ట్", "రీ స్టార్ట్", "మళ్ళీ", "మళ్లీ", "మరు"]):
        return "restart"
    if any(word in cleaned for word in ["documents", "docs", "డాక్యుమెంట్స్", "డాక్యుమెంట్లు", "పత్రాలు"]):
        return "documents"

    session = sessions.get(user_id, {})
    state = session.get("state")
    data = session.get("data", {})
    number_value = _extract_first_number(cleaned)

    if state == "awaiting_scheme_category":
        if any(word in cleaned for word in ["business", "బిజినెస్", "వ్యాపార", "shop", "దుకాణ"]):
            return "1"
        if any(word in cleaned for word in ["individual", "వ్యక్తిగత", "personal"]):
            return "2"

    if state == "awaiting_business_type":
        business_map = {
            "1": ["kirana", "grocery", "కిరాణ"],
            "2": ["tailor", "టైలర్", "సిలాయి", "stitch"],
            "3": ["salon", "beauty", "సెలూన్", "బ్యూటీ"],
            "4": ["vegetable", "కూరగాయ", "వెజిటబుల్"],
            "5": ["auto", "ఆటో", "rickshaw"],
            "6": ["other", "ఇతర"]
        }
        for choice, words in business_map.items():
            if any(word in cleaned for word in words):
                return choice

    if state in ["eligibility", "individual_eligibility"]:
        step = data.get("eligibility_step", 0)

        if step == 0:
            if any(word in cleaned for word in ["male", "man", "పురుష", "అబ్బాయి"]):
                return "1"
            if any(word in cleaned for word in ["female", "woman", "స్త్రీ", "మహిళ", "అమ్మాయి"]):
                return "2"
            if any(word in cleaned for word in ["other", "ఇతర"]):
                return "3"

        if step == 1:
            caste_map = {
                "1": ["general", "oc"],
                "2": ["sc"],
                "3": ["st"],
                "4": ["obc", "bc"],
                "5": ["minority", "మైనారిటీ"]
            }
            for choice, words in caste_map.items():
                if any(word == cleaned or word in cleaned.split() for word in words):
                    return choice

        if step == 2 and number_value:
            return number_value

        if step in [3, 4]:
            yes_no = _map_yes_no(cleaned)
            if yes_no:
                return yes_no

    if state in ["discovered", "individual_discovered"] and number_value:
        return number_value

    if state == "scheme_specific_question":
        pending_q = data.get("pending_question")
        if pending_q == "land_ownership":
            yes_no = _map_yes_no(cleaned)
            if yes_no:
                return yes_no
        if pending_q in ["annual_income", "monthly_units"] and number_value:
            return number_value

    direct_map = {
        "one": "1", "two": "2", "three": "3", "four": "4", "five": "5",
        "six": "6", "seven": "7", "eight": "8",
        "ఒకటి": "1", "రెండు": "2", "మూడు": "3", "నాలుగు": "4", "ఐదు": "5",
        "ఆరు": "6", "ఏడు": "7", "ఎనిమిది": "8",
        "yes": "1", "no": "2", "అవును": "1", "లేదు": "2"
    }
    return direct_map.get(cleaned, transcribed_text)


def transcribe_voice_to_text(audio_file_path: str) -> str:
    """
    Transcribe audio file to text using Groq Whisper API.
    
    Args:
        audio_file_path: Path to the audio file
        
    Returns:
        Transcribed text or error message
    """
    try:
        GROQ_API_KEY = os.getenv("GROQ_API_KEY")
        if not GROQ_API_KEY:
            return "❌ Voice API not configured. Please contact administrator."
        
        with open(audio_file_path, "rb") as f:
            response = requests.post(
                "https://api.groq.com/openai/v1/audio/transcriptions",
                headers={"Authorization": f"Bearer {GROQ_API_KEY}"},
                files={"file": ("audio.ogg", f, "audio/ogg")},
                data={
                    "model": "whisper-large-v3",
                    "temperature": "0",
                    "prompt": "Audio may contain Telugu, English, and Hinglish terms about government schemes, business types, numbers, and yes/no answers."
                },
                timeout=30
            )
        
        if response.status_code == 200:
            transcribed_text = response.json().get("text", "").strip()
            if transcribed_text:
                return transcribed_text
            else:
                return "❌ Could not understand the audio. Please try speaking clearly."
        else:
            error_msg = response.json().get("error", {}).get("message", "Unknown error")
            print(f"Groq API Error: {error_msg}")
            return f"❌ Transcription error: {error_msg[:50]}"
    except Exception as e:
        print(f"Voice Transcription Error: {e}")
        return f"❌ Error processing voice message: {str(e)[:50]}"


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

    await _send_tts_reply(update.message, response, buttons)


async def handle_voice_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle incoming voice messages from users.
    
    Args:
        update: The update object containing the voice message
        context: The context object
    """
    try:
        user_id = str(update.effective_user.id)
        
        # Show typing indicator
        await update.message.chat.send_action("typing")
        
        # Download voice file
        voice_file = await update.message.voice.get_file()
        
        # Save to temporary file
        with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as tmp_file:
            tmp_file_path = tmp_file.name
        
        # Download to file
        await voice_file.download_to_drive(tmp_file_path)
        
        try:
            # Transcribe voice to text
            transcribed_text = transcribe_voice_to_text(tmp_file_path)
            
            # If transcription failed, send error
            if transcribed_text.startswith("❌"):
                await update.message.reply_text(transcribed_text)
                return
            final_text = normalize_voice_input(user_id, transcribed_text)
            
            # Send transcribed text back to user
            display_text = f"🎤 Your message:\n\n{final_text}"
            if final_text != transcribed_text:
                display_text += f"\n\n(heard as: {transcribed_text})"
            await update.message.reply_text(display_text)
            
            # Get response from agent
            response = handle_message(user_id, final_text, sessions)
            
            # Check if response needs buttons
            buttons = get_button_response(response, None)
            
            # Send response back to user
            if buttons:
                await update.message.reply_text(response, reply_markup=buttons)
            else:
                await update.message.reply_text(response)

            await _send_tts_reply(update.message, response, buttons)
        finally:
            # Clean up temporary file
            if os.path.exists(tmp_file_path):
                os.remove(tmp_file_path)
    except Exception as e:
        print(f"Voice Message Handler Error: {e}")
        try:
            await update.message.reply_text(f"❌ Error processing voice message: {str(e)[:100]}")
        except Exception:
            print("Voice error reply failed")


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

        await _send_tts_reply(query.message, response, buttons)
    except Exception:
        # If edit fails, send new message
        if buttons:
            await query.message.reply_text(response, reply_markup=buttons)
        else:
            await query.message.reply_text(response)

        await _send_tts_reply(query.message, response, buttons)


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

    await _send_tts_reply(update.message, response, buttons)


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

    await _send_tts_reply(update.message, response, buttons)


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
    
    # Add voice message handler
    application.add_handler(MessageHandler(filters.VOICE, handle_voice_message))
    
    # Add a message handler for all text messages (excluding commands)
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_message))
    
    # Start the bot
    print("🤖 scheme-saathi Telegram bot started!")
    print("📋 Commands available: /start, /help, /restart, /documents, /about")
    print("🎤 Voice input: Send voice messages for transcription and processing!")
    print("🧠 Voice parser: v2 (state-aware normalization enabled)")
    application.run_polling()


if __name__ == "__main__":
    main()
