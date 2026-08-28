# failures.md — Mistakes and Failures

A running log of real mistakes, bugs, unexpected behavior, and failed approaches encountered during development.

**Rule:** Only record failures that actually happen. Do not invent failures.  
**Note:** Entries marked *(not yet verified)* are structural problems identified from reading the code, not confirmed by running it.

---

### Failure: Eligibility logic duplicated and untestable

**What happened:**  
`skills/eligibility.py` has a `check_eligibility()` function, but `agent.py` never calls it. Instead, `agent.py` re-implements all the same eligibility conditions inline inside the `handle_message` state machine. The two copies of the logic are not kept in sync.

**Why it happened:**  
During the hackathon, the state machine needed to filter schemes before showing them to the user. It was faster to write the conditions again inline than to refactor `skills/eligibility.py` to fit the filtering use case. Speed over structure.

**What we did:**  
*(not yet fixed as of 2026-08-26)*  
Plan: Extract a single `eligibility_engine.py` that is the only place eligibility rules live. Both the conversation layer and any future interface call it. Write unit tests directly against it.

**Result:**  
*(not yet verified)* Currently two separate copies of eligibility logic exist and can drift.

**What we learned:**  
Duplicating decision logic is a silent failure — it doesn't crash, it just becomes wrong gradually. The eligibility engine needs to be a hard boundary: one module, one set of rules, no duplicates anywhere.

---

### Failure: Multi-field input silently discarded

**What happened:**  
The state machine processes one field per step. If a user types "నేను 32 సంవత్సరాల మహిళను, GST లేదు" when the bot is on step 0 (gender), it extracts only gender and discards age and GST. The user is then asked for age and GST again as separate questions — information they already gave.

**Why it happened:**  
The state machine was designed around a fixed question sequence. There is no parsing layer — each state reads the raw message and looks for exactly one value. Anything extra in the message is ignored.

**What we did:**  
*(not yet fixed as of 2026-08-26)*  
Plan: Build a natural-language profile extractor (LLM-backed) that reads the entire message and returns a partial profile `{age, gender, gst, ...}`. The conversation layer then asks only for fields that are still missing.

**Result:**  
*(not yet verified)* Currently any extra information a user volunteers in one message is thrown away silently.

**What we learned:**  
A form-style question sequence is not a conversation. Real users give context in natural language, not one field at a time. The right model is: LLM listens and extracts everything it can, deterministic code asks only for what's missing.

---

### Failure: Scheme data has no source or verification date

**What happened:**  
Every entry in `data/schemes.json` has amounts, eligibility criteria, and documents — but no `official_source` URL and no `last_verified_date`. There is no way to tell a user where the information came from or whether it is still current.

**Why it happened:**  
The scheme data was built during a 24-hour hackathon. Getting the data in was the priority; provenance was not tracked.

**What we did:**  
*(not yet fixed as of 2026-08-26)*  
Plan: Add `official_source` and `last_verified_date` fields to every scheme entry. Update `audit_schemes.py` to flag any scheme missing these fields as an error, not a warning.

**Result:**  
*(not yet verified)* Currently the bot presents financial information (loan amounts, interest rates, eligibility rules) with no indication of when it was verified or from where.

**What we learned:**  
For a product that influences real financial decisions, unverified data is a trust failure, not just a technical debt. Scheme rules change — government portals get updated, amounts shift, eligibility criteria are amended. Without a verification date, we have no way to know if what we're telling users is still true.

---

### Failure: Indian number formatting rejected

**What happened:**  
Entering `1,50,000` for annual income (kalyana_lakshmi scheme-specific question) produced an invalid input error. The bot responded: "చెల్లని ఇన్పుట్. దయచేసి సంఖ్యలో టైప్ చేయండి."

**Why it happened:**  
`agent.py` uses `int(message.strip())` directly. Python's `int()` cannot parse comma-formatted numbers. Indian number formatting (1,50,000) is standard for the target demographic — the bot was built without accounting for it.

**What we did:**  
Not fixed yet. Confirmed by running the actual parse: `int("1,50,000")` raises `ValueError`. Confirmed the fix is `int(message.strip().replace(",", ""))` — `"1,50,000".replace(",","")` → `"150000"` → `150000`. One line change.

**Result:**  
Pending. Any user who types income in Indian format is stuck in a loop — the error message gives no hint that commas are the problem.

**What we learned:**  
User-facing financial inputs need to accept normal Indian number formatting. Any `int()` parse on a rupee amount should strip commas first. This applies to `annual_income` and `monthly_units` in `scheme_specific_question` state.

---

### Failure: Individual filter shows unscreened schemes as matched

**What happened:**  
A female SC user (age 25, white ration card yes, bank yes) is shown 6 schemes including `rythu_bharosa` (requires land ownership) and `kalyana_lakshmi` (requires annual income ≤ ₹2,00,000). Neither of these constraints is checked by the individual filter — they are only checked *after* the user picks the scheme. The list presents these as matching schemes when they have not been screened.

**Why it happened:**  
The individual filter checks: gender, age, caste, white_ration_card. `rythu_bharosa` stores its land requirement as `"land_ownership": "required"` (a string, not a boolean field the filter recognises). `kalyana_lakshmi` stores income as `"max_annual_income": 200000` — a field the filter does not check at all. The scheme-specific checks only happen in `check_final_eligibility`, which runs after selection.

**What we did:**  
Not fixed yet. Confirmed by running the individual filter: `rythu_bharosa` and `kalyana_lakshmi` both appear in the matched list for a profile that hasn't been screened for their key constraints.

**Result:**  
Pending. Users are shown an inflated list that includes schemes they may not qualify for. They only discover the problem after picking the scheme and answering additional questions.

**What we learned:**  
The two-stage design (filter → then scheme-specific checks) creates a misleading intermediate state. A user who sees 6 "matched" schemes may feel confident, then get rejected on 2 of them after answering more questions. Either the filter needs to be smarter, or the UI needs to make clear that the list is preliminary — not confirmed eligibility.

### F6 — Transient httpx.ConnectTimeout on first Telegram response (2026-08-28)

**What happened:**
During the first live smoke test after the eligibility-engine migration, the bot started successfully and began polling. When a `/start` message was sent from a real Telegram client, the bot's first attempt to send the reply timed out with `httpx.ConnectTimeout` while communicating with `api.telegram.org:443`.

**What we verified:**
- TCP connectivity to `api.telegram.org:443` was verified successfully — the network path was reachable
- The failure was on the outbound API call from the bot, not on inbound polling
- Retrying the bot succeeded — the `/start` interaction completed normally on the next attempt
- No source-code change was required to resolve it

**Root cause:**
Not established. The timeout was transient. Possible contributing factors include: transient network latency, Telegram API response delay, or httpx connection pool cold-start. We did not investigate further because a retry resolved it.

**Status:** Resolved by retry. No code change. Monitoring for recurrence.

**What we learned:**
See L19 — startup health and external API health are independent. A single transient timeout on first contact is not sufficient reason to diagnose a code problem. The correct response is: verify connectivity, retry, and only investigate further if the failure is reproducible.

<!-- New failures go here as they are discovered -->
