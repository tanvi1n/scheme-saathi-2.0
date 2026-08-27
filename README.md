# scheme-saathi 🤝

> Telugu-first Telegram bot that helps small business owners in Telangana discover and apply for government schemes — for free, without middlemen.

---

## The problem

50+ government schemes exist specifically for kirana owners, tailors, vegetable vendors, salon workers, and women entrepreneurs in Telangana — PM Vishwakarma, Mudra Loan, PMEGP, WE-HUB, Dalit Bandhu, and more.

Most people never apply because:

- All information is in English on complex government portals
- They don't know which schemes they qualify for
- Document requirements are unclear
- Middlemen charge ₹5,000–₹50,000 to "help" — and often cheat them
- Result: they take private loans at 24–60% interest instead of 5–8% government loans

---

## What scheme-saathi does

A user describes their business in Telugu. The bot asks a few short questions, shows which schemes they likely qualify for, explains exactly which documents to collect and where to get them, and tells them where to apply.

```
User:  నేను టైలరింగ్ షాప్ నడుపుతున్నాను
Bot:   మీకు పథకాలు కనుగొనబడ్డాయి:
       1. ✅ పీఎం విశ్వకర్మ యోజన — ₹3,00,000
       2. ❓ రాజీవ్ యువ వికాసం — మరింత సమాచారం అవసరం

User:  1
Bot:   ✅ పీఎం విశ్వకర్మ యోజన
       📝 సాంప్రదాయ కళాకారులకు నైపుణ్య శిక్షణ మరియు రుణ సహాయం.
       💰 లాభం: ₹15,000 - ₹3,00,000
       మీరు ఈ పథకానికి అర్హులు! ✅
       📋 డాక్యుమెంట్ల కోసం, 'documents' టైప్ చేయండి.
```

---

## How AI is used — and where it is not

The LLM handles language. Deterministic code makes the decisions.

| Layer | What runs there |
|---|---|
| Language understanding | LLM (Groq `llama-3.1-8b-instant`) — interprets Telugu, Hinglish, mixed input, free-text scheme questions |
| Voice transcription | Groq Whisper — converts voice messages to text |
| Eligibility decisions | `eligibility_engine.py` — pure Python, no LLM, no guessing |
| Scheme data | `data/schemes.json` — verified structured data, not generated |
| Document guidance | `skills/documents.py` — deterministic lookup, not generated |

The LLM is never asked whether a user qualifies for a scheme. That decision is made by the eligibility engine using the scheme's actual rules. If information is missing, the engine returns `NEEDS_VERIFICATION` — it does not guess.

---

## Eligibility engine

The core of the system is `eligibility_engine.py` — a standalone, independently testable module.

**Input:** a `UserProfile` (gender, caste, age, GST status, bank account, and scheme-specific fields) plus a scheme dict.

**Output:** an `EligibilityResult` with one of three statuses:

| Status | Meaning |
|---|---|
| `LIKELY_ELIGIBLE` | All known requirements are satisfied |
| `NEEDS_VERIFICATION` | A mandatory field hasn't been collected yet |
| `LIKELY_NOT_ELIGIBLE` | At least one requirement is not met |

`NEEDS_VERIFICATION` is the key design principle. Missing data is never silently treated as a pass or a fail. The engine uses an `UNKNOWN` sentinel that is distinct from `False`, `None`, and `0`.

The engine returns structured reasons for every decision — which criteria passed, which failed, and which fields still need to be collected. The conversation layer renders these into Telugu.

---

## Architecture

```
User
  ↓
Telegram / Voice input
  ↓
telegram_bot.py
  ├── Voice: Groq Whisper → text → state-aware normalizer
  ├── TTS: gTTS → voice reply for prompt-style responses
  └── Inline keyboards for guided input
  ↓
agent.py  (conversation state machine)
  ├── LLM Q&A for free-text scheme questions (grounded in schemes.json)
  └── Eligibility flow: collect profile → call engine → render result
  ↓
eligibility_engine.py  (pure function, no I/O, no LLM)
  ↓
data/schemes.json  (19 schemes, verified structure)
  ↓
skills/documents.py  (document checklists + where to get each)
```

---

## Schemes database

19 government schemes covering:

- Central: PM Vishwakarma, Mudra Shishu/Kishor, PMEGP, PM SVANidhi, Stand Up India, CGTMSE
- Telangana business: T-IDEA, T-PRIDE, WE-HUB, Dalit Bandhu, Rajiv Yuva Vikasam, PM Swarozgar (Auto/Taxi)
- Telangana individual: Mahalakshmi, Rythu Bharosa, Gruha Jyothi, Indiramma Indlu, Rajiv Aarogyasri, Kalyana Lakshmi/Shaadi Mubarak

Each scheme has: eligibility criteria (gender, caste, age, GST, bank account), benefit amount, required documents, application URL, offline application location, and helpline. Scheme-specific rules (land ownership, income limits, electricity usage) are encoded as `special_requirements` — no hardcoded scheme IDs in the engine.

---

## What the bot actually does today

- Accepts Telugu, English, and Telugu-English mixed input
- Accepts voice messages (transcribed via Whisper)
- Guides users through a short profile questionnaire (gender, caste, age, GST, bank account)
- Runs eligibility engine across all matching schemes
- Shows ✅ for confirmed eligible, ❓ for schemes needing one more answer
- Asks follow-up questions for ❓ schemes (land ownership, income, electricity units)
- Shows document checklist with where to obtain each document
- Sends TTS voice replies for all prompt-type responses
- Handles Indian number formatting: `1,50,000` is accepted everywhere

---

## What it does not do yet

- Application tracking after submission
- Natural-language multi-field profile extraction (currently asks one question at a time)
- Web UI
- Scheme comparison view
- Official verification dates on scheme data

---

## Tech stack

| Component | Technology |
|---|---|
| Interface | Telegram Bot (`python-telegram-bot`) |
| LLM | Groq `llama-3.1-8b-instant` |
| Voice transcription | Groq Whisper (`whisper-large-v3`) |
| TTS | gTTS |
| Eligibility engine | Pure Python (`eligibility_engine.py`) |
| Scheme data | JSON (`data/schemes.json`) |
| Language | Python 3.10+ |

---

## Quick start

```bash
# 1. Clone
git clone https://github.com/YOUR_USERNAME/scheme-saathi.git
cd scheme-saathi

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure environment
cp .env.example .env
# Edit .env and add:
#   TELEGRAM_BOT_TOKEN — from @BotFather
#   GROQ_API_KEY       — from console.groq.com
#   ADMIN_USER_IDS     — your Telegram numeric user ID (optional)

# 4. Start the bot
python telegram_bot.py
```

---

## Project structure

```
scheme-saathi/
├── agent.py                  # Conversation state machine
├── eligibility_engine.py     # Deterministic eligibility engine
├── telegram_bot.py           # Telegram interface + voice + TTS
├── activity_logger.py        # Usage tracking (JSONL)
├── data/
│   ├── schemes.json          # 19 schemes database
│   └── activity_log.jsonl    # Usage log (gitignored)
├── skills/
│   ├── discover.py           # Keyword-based scheme discovery
│   ├── documents.py          # Document guidance
│   └── eligibility.py        # (legacy, superseded by eligibility_engine.py)
├── tests/
│   ├── test_eligibility_engine.py   # 61 engine unit tests
│   └── test_agent_conversation.py  # 20 conversation-layer tests
├── build.md                  # Development log
├── learnings.md              # Architecture lessons
├── failures.md               # Real bugs and fixes
├── .env.example
└── requirements.txt
```

---

## Running tests

```bash
pip install pytest
python -m pytest tests/ -v
```

81 tests, all passing.

---

## Admin commands

Activity is logged to `data/activity_log.jsonl` (usage metadata only — no message content).

Telegram user IDs in `ADMIN_USER_IDS` can run:

- `/activity` — recent users and usage counts
- `/stats` — total events, unique users, event breakdown

---

## Target users

- Kirana / grocery store owners
- Tailors and clothing businesses
- Vegetable and fruit vendors
- Salon and beauty service providers
- Auto-rickshaw and taxi drivers
- Women entrepreneurs
- SC/ST/OBC/Minority business owners

Geographic focus: Telangana (scheme data is Telangana-specific; architecture is state-agnostic)

---

Improved for the **Razorpay Buildathon** — August 2026.

---

## License

MIT License — free to use, modify, and distribute.
