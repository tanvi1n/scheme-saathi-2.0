# scheme-saathi 🤝
> సాథి — Your trusted companion for government schemes

---

## 🎯 Problem

Small businesses in Telangana are leaving **crores of rupees on the table.**

50+ government schemes (PM Vishwakarma, Mudra Loan, PMEGP, WE-HUB) exist specifically for kirana owners, tailors, vegetable vendors, and salon workers — but most never apply because:

- 🌐 All information is in English on complex government portals
- 😕 They don't know which schemes they qualify for
- 📄 Document requirements are unclear and overwhelming
- 💸 Middlemen charge ₹5,000–₹50,000 to "help" — and often cheat them
- 📉 Result: They take private loans at 24–60% interest instead of 5–8% government loans

---

## ✅ Our Solution

**scheme-saathi** is a Telugu-first autonomous agent on Telegram that guides any small business owner from _"I don't know what I qualify for"_ to _"my application is submitted"_ — for free, without middlemen, without English.

### How it works

| Step | What happens |
|------|-------------|
| 1️⃣ Discovery | Owner types business type in Telugu → Agent shows matching schemes + total money available |
| 2️⃣ Eligibility | Agent asks 3–4 simple questions → "High chance of approval" or "You need these 2 documents first" |
| 3️⃣ Documents | Exact photo checklist + where to get each document (nearest MeeSeva, bank, DIC office) |
| 4️⃣ Application | Step-by-step guidance → Status tracking → Resubmission help if rejected |

---

## 💬 Example Conversation
```
User:   నేను టైలరింగ్ షాప్ నడుపుతున్నాను
Bot:    మీకు 3 పథకాలు అర్హత ఉన్నాయి (మొత్తం ₹3,50,000):
        1. PM Vishwakarma — ₹3,00,000
        2. Mudra Loan (Shishu) — ₹50,000
        3. TS-iPass Subsidy
        ఏది మరింత తెలుసుకోవాలి?

User:   1
Bot:    📄 PM Vishwakarma కోసం అవసరమైన documents:
        ✅ Aadhaar card
        ✅ Bank passbook మొదటి పేజీ photo
        ✅ Caste certificate (MeeSeva లో తీయవచ్చు)
        📍 Apply చేయడానికి: దగ్గర MeeSeva Center కి వెళ్ళండి — FREE
```

---

## 🛠️ Tech Stack

| Component | Technology |
|-----------|-----------|
| Agent Framework | [nanobot](https://github.com/HKUDS/nanobot) |
| Local LLM | gemma:2b via Ollama |
| Interface | Telegram Bot |
| Language | Python 3.10+ |
| Data | JSON (schemes database) |

> Runs fully locally — no cloud dependency, no data leaves your machine.

---

## 🚀 Quick Start
```bash
# 1. Clone the repo
git clone https://github.com/YOUR_USERNAME/scheme-saathi.git
cd scheme-saathi

# 2. Install dependencies
pip install -r requirements.txt

# 3. Install and start Ollama with gemma:2b
ollama pull gemma:2b
ollama serve

# 4. Configure your Telegram bot token
cp .env.example .env
nano .env  # Add your bot token

# 5. Start the agent
nanobot gateway
```

---

## 📁 Project Structure
```
scheme-saathi/
├── data/
│   └── schemes.json          # Telangana schemes database
├── skills/
│   ├── discover.py           # Scheme discovery logic
│   ├── eligibility.py        # Eligibility checker
│   ├── documents.py          # Document guidance
│   └── apply.py              # Application hand-holding
├── .nanobot/
│   └── config.json           # nanobot configuration
├── .env.example
├── requirements.txt
└── README.md
```

---

## 🎯 Target Users

- Kirana / grocery store owners
- Tailors and clothing businesses
- Vegetable and fruit vendors
- Salon and beauty service providers
- Women entrepreneurs
- SC/ST/Minority business owners

**Geographic focus:** Telangana (expandable to all Indian states)

---

## 📊 Impact

- Enable access to low-interest govt loans (saving 15–50% on interest)
- Help businesses get subsidies for machinery and upgrades
- Eliminate ₹5,000–₹50,000 middlemen fees
- Increase government scheme utilization in Telangana

---

## 👥 Team Dev3

- Mukthanand
- Tanvi
- Charishma
---

## 🏆 Hackathon

Built at **Aarna Autonomous Agents Hackathon**
📍 Mondee Tech, Madhapur, Hyderabad
📅 March 14–15, 2026

---

## 📄 License

MIT License — free to use, modify, and distribute.