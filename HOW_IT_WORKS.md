# How We Built scheme-saathi 🤝

A Telugu-friendly Telegram bot that helps small business owners discover government schemes they're eligible for.

---

## 📋 Step 1 — Got the Data

We researched all government schemes for small businesses in Telangana and created a comprehensive JSON database with 12+ schemes. Each scheme includes:

- **Eligibility criteria** (age, gender, caste, GST requirement, bank account)
- **Loan amounts** (min/max)
- **Required documents** (Aadhaar, GST, Bank Passbook, etc.)
- **Application details** (online URL, offline location, helpline)
- **Processing time** and success rates
- **Telugu translations** for all scheme names

Data file: `data/schemes.json`

---

## 🔧 Step 2 — Built 3 Core Skills in Python

### **discover.py** — Find Matching Schemes
```python
discover_schemes(business_type, gender="any", caste="any")
```
- Takes user's business type (e.g., "kirana", "tailor", "street vendor")
- Uses flexible substring matching with keyword mapping
- Returns matching schemes with amounts in Telugu
- ✅ "tailor" matches "Tailors"
- ✅ "kirana" matches "Retail Trade" or "Small Shops"

### **eligibility.py** — Check Qualification
```python
check_eligibility(scheme_id, user_profile)
```
- Takes scheme ID and user's profile (gender, caste, age, GST status, bank account)
- Validates against scheme's eligibility criteria


### **documents.py** — Get Document Guide
```python
get_document_guide(scheme_id)
```
- Returns complete document checklist for a scheme
- Shows where to get each document
- Includes application location, online URL, helpline number
- Example: "Aadhaar Card → దగ్గర Aadhaar Seva Kendra లో తీయవచ్చు"

---

## 🎯 Step 3 — Built the Conversation Flow

**agent.py** manages the chat as a state machine with 5 states:

```
START
  ↓ (User says "hello" or business type)
AWAITING_BUSINESS_TYPE
  ↓ (discover_schemes() → show 5 schemes)
DISCOVERED
  ↓ (User picks scheme #1)
ELIGIBILITY
  ↓ (Gather gender, caste, age, GST, bank account)
ELIGIBILITY_RESULT
  ↓ (Show result + option for documents)
  → "documents" → Show guide
  → "restart" → Back to START
```

Each state asks one question at a time and validates input before moving forward.

---

## 📱 Step 4 — Connected to Telegram

**telegram_bot.py** uses the `python-telegram-bot` library (v20+)

**Handler Flow:**
```
User sends message
    ↓
/start command? → send_welcome()
    ↓
Regular text? → handle_message(user_id, text, sessions)
    ↓
Get response from agent.py
    ↓
Send response back to user
```

**Key features:**
- Async message handling
- In-memory session storage (one session per user_id)
- Token loaded from `.env` file

---

## 🛠️ Tools Used

| Tool | Purpose |
|------|---------|
| **Python 3** | Core language |
| **python-telegram-bot** | Telegram integration |
| **python-dotenv** | Environment variable management |
| **JSON** | Scheme data storage |
| **Gemini/Claude** | Scheme research & data validation |

---

## 🚀 Getting Started

### 1. **Create Telegram Bot & Get Token**

Steps to get your `TELEGRAM_BOT_TOKEN`:

1. Open Telegram and search for **@BotFather**
2. Click **Start** button
3. Send: `/newbot`
4. BotFather asks for bot name: Type **scheme-saathi** (or your name)
5. BotFather asks for username: Type **scheme_saathi_bot** (must end with `_bot`)
6. BotFather sends you the **token** (looks like: `123456789:ABCDefGhIjKlMnOpQrStUvWxYz`)
7. Copy this token

### 2. **Set Up Environment**

```bash
# Clone/download the project
cd scheme-saathi

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install python-telegram-bot python-dotenv
```

### 3. **Add Token to .env**

Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```

Edit `.env` and paste your token:
```
TELEGRAM_BOT_TOKEN=123456789:ABCDefGhIjKlMnOpQrStUvWxYz
```

### 4. **Run the Bot**

```bash
python3 telegram_bot.py
```

You'll see:
```
🤖 scheme-saathi Telegram bot started!
```

### 5. **Test on Telegram**

1. Open Telegram
2. Search for your bot name (scheme_saathi_bot)
3. Click **Start**
4. Type "kirana" or any business type
5. Follow the guided flow!

---

## 📁 Project Structure

```
scheme-saathi/
├── agent.py                    # Conversation state machine
├── telegram_bot.py             # Telegram bot handlers
├── skills/
│   ├── discover.py            # Find matching schemes
│   ├── eligibility.py         # Check qualification
│   └── documents.py           # Document guide
├── data/
│   └── schemes.json           # All scheme data
├── .env                       # Bot token (create from .env.example)
├── .env.example               # Template
├── requirements.txt           # Python dependencies
└── README.md                  # Project info
```

---

## 🔄 Conversation Example

```
User: /start
Bot: నమస్కారం! 🙏 మీ వ్యాపార రకం చెప్పండి (ఉదా: kirana, tailor, salon)

User: kirana
Bot: మీకు 5 పథకాలు అర్హత ఉన్నాయి...
     1. ముద్రా శిశు రుణం — ₹50000
     2. ముద్రా కిషోర్ రుణం — ₹500000
     [... more schemes ...]

User: 1
Bot: మీ వ్యక్తిగత వివరాలు అడుగుతూ ఉన్నాను...
     (1) మీ లింగం చెప్పండి (male/female/other):

User: male
Bot: (2) మీ కులం చెప్పండి (general/sc/st/obc):

User: general
Bot: (3) మీ వయసు చెప్పండి (సంఖ్యలో):

User: 30
Bot: (4) మీకు GST registration ఉందా? (yes/no):

User: yes
Bot: (5) మీకు bank account ఉందా? (yes/no):

User: yes
Bot: ✅ మీరు ముద్రా శిశు రుణం కి అర్హులు!
     కావలసిన documents:
     • Identity Proof
     • Address Proof
     • Business Identity Proof
     • Passport Photos
     
     📋 డాక్యుమెంట్‌ల కోసం, 'documents' టైప్ చేయండి.

User: documents
Bot: 📋 ముద్రా శిశు రుణం - Documents గైడ్:
     1. Identity Proof
        📌 Aadhaar / Voter ID / Passport
     2. Address Proof
        📌 Aadhaar / Electricity bill / Rent agreement
     3. Business Identity Proof
        📌 Shop photo + rent agreement
     4. Passport Photos
        📌 దగ్గర photo studio లో తీయవచ్చు
     
     📍 Apply చేయడానికి: Public/Private Sector Banks
     🌐 Online: www.udyamimitra.in
     📞 Helpline: 18001801111
```

---

## ✨ Features

✅ Telugu language support throughout  
✅ Flexible business type matching (handles variations)  
✅ Step-by-step eligibility checking  
✅ Complete document guide with locations  
✅ Multiple user sessions (Telegram handles user_id)  
✅ Easy to extend with more schemes  
✅ No database required (JSON-based)  

---

## 🚦 Next Steps

Want to improve the bot? Try:

1. **Add more schemes** — Edit `data/schemes.json`
2. **Support more languages** — Add translations to scheme names
3. **Add database** — Replace JSON with SQLite/PostgreSQL
4. **Deployment** — Use Railway, Heroku, or AWS to keep bot running 24/7
5. **Analytics** — Track which schemes are most searched

---

## 📞 Support

- **Telegram BotFather Help**: @BotFather on Telegram
- **python-telegram-bot Docs**: https://docs.python-telegram-bot.org
- **Scheme Data Issues**: Check `data/schemes.json` format

Happy scheme hunting! 🎉
