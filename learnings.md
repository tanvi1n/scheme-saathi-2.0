# learnings.md — What We Learnt

A running log of insights, design lessons, and things that changed how we think about the product.

---

## How to use this file

Add an entry whenever you learn something meaningful — about the architecture, the users, the LLM, the scheme data, or the build process. Even small insights are worth writing down. This file is evidence for the Razorpay "AI judgment" and "failure recovery" criteria.

---

## Learnings Log

### 2026-08-26 — Session 1: Reading the Codebase

**L1 — The eligibility logic is buried inside the state machine**

`agent.py` mixes conversation flow, eligibility checking, and scheme filtering all in one `handle_message` function. This makes it impossible to test eligibility independently, and it means the LLM and the deterministic rules are not cleanly separated.

*Implication:* We need to extract the eligibility rules into a standalone engine that takes a user profile + scheme and returns a structured result — independently of any conversation state.

---

**L2 — The LLM is used in two different ways, but only one is safe**

Currently the LLM is used for:
1. Free-text Q&A about schemes (grounded in `schemes.json` context) — *relatively safe*
2. Implicit scheme matching via the state machine's keyword logic — *deterministic, safe*

It is NOT used for eligibility decisions — the state machine already does that with `if` conditions. This is actually the right instinct, but it is not documented or explicitly designed — it happened by accident.

*Implication:* We should make this separation explicit and document it. The LLM's role needs to be clearly bounded.

---

**L3 — Profile gathering is fragile because it assumes a fixed order**

The current flow asks: gender → caste → age → GST → bank account, one at a time. If a user says "నా వయసు 32, నేను మహిళను" in one message, the bot will only extract gender (the current step) and throw away the age. This is a real UX failure.

*Implication:* A natural-language profile extractor that reads a whole message and pulls out all available fields at once would dramatically improve the experience.

---

**L4 — Scheme data has no provenance**

None of the schemes in `schemes.json` have an `official_source` URL or a `last_verified_date`. This means we cannot tell a user "this information was last verified on X date from Y source." For a government schemes bot, this is a trust and reliability issue.

*Implication:* Every scheme needs a source and a verification date before the submission.

---

**L5 — "Eligible" without explanation is not enough**

The current bot says "మీరు ఈ పథకానికి అర్హులు! ✅" with no explanation of why. A user who gets rejected by a government office has no way to understand what went wrong. An explainable result — showing which criteria passed and which failed — builds trust and is far more useful.

*Implication:* The eligibility engine should return reasons, not just a boolean.

---

**L6 — Voice normalization is already state-aware**

`telegram_bot.py` has a `normalize_voice_input()` function that reads the current conversation state and maps speech transcription errors to expected values. This is a good pattern — it shows we already understood that voice input needs context to be interpreted correctly.

*Implication:* This same principle (context-aware interpretation) should be applied to the natural-language profile extractor.

---

### 2026-08-26 — Session 2: Baseline Test Results

**L7 — The keyword map is the real bottleneck for business scheme discovery**

A tailor matches only 1 scheme (PM Vishwakarma) because the keyword map doesn't map "tailor" → "service providers" or "micro-enterprises". Mudra Shishu (targets "Service Providers") is almost certainly relevant for a tailor but never appears. The filter logic is correct — the data coverage is the problem.

*Implication:* Improving the keyword map will have more impact on scheme discovery than any logic change. This is a data problem, not a code problem.

---

**L8 — "Matched schemes" and "eligible schemes" are not the same thing — but the UI treats them as if they are**

The individual filter produces a list that includes schemes with unmet constraints that haven't been checked yet (`rythu_bharosa` needs land, `kalyana_lakshmi` needs income). The user sees this list as "schemes you qualify for" when it actually means "schemes we haven't ruled out yet." The real eligibility check for these schemes happens later — only if the user picks them.

*Implication:* The new engine needs to either: (a) do all checks upfront (requires collecting all data before showing the list), or (b) explicitly label the list as "potentially eligible — confirmation needed" rather than presenting it as a definitive match.

---

**L9 — Missing data and negative answers are treated identically — silently**

`check_final_eligibility` for `rythu_bharosa`: `user_profile.get("land_ownership_verified")` returns `None` (missing) or `False` (answered No) — both produce ineligibility with the same reason. There is no distinction between "we don't know yet" and "the user told us no."

For `kalyana_lakshmi` and `gruha_jyothi` it's the opposite — missing data defaults to 0, which passes the check. So the two bugs are asymmetric: land defaults to "no", income defaults to "₹0 (eligible)", electricity defaults to "0 units (eligible)."

*Implication:* The new engine must treat `None` (unknown) as a distinct state from `False` (no) and `0` (zero). Unknown should produce `NEEDS_VERIFICATION`, not a pass or fail.

---

**L10 — The one-line fix for Indian number formatting is `replace(",", "")` before `int()`**

Confirmed: `"1,50,000".replace(",", "")` → `"150000"` → `int()` → `150000`. This is the complete fix for M11. It should be applied to every numeric input the bot collects from users — age, income, electricity units.

### 2026-08-26 — Session 3: Eligibility Engine Implementation

**L11 — UNKNOWN as a first-class type prevents an entire class of silent bugs**

The old code had two asymmetric bugs: missing land → ineligible (silent fail), missing income → eligible (silent pass via default 0). Both came from the same root cause: no sentinel for "not yet collected." Making `UNKNOWN` a distinct object that cannot be used as a boolean forces every check to explicitly handle the missing-data case. The engine cannot accidentally treat absent data as false or zero.

---

**L12 — Eligibility logic independent of conversation state is trivially testable**

The entire test suite (61 tests) requires zero mocking — no Telegram, no sessions, no LLM, no file reads (except the real-scheme regression tests which just load JSON). A test is three lines: build a `UserProfile`, call `check_scheme_eligibility`, assert the status. This was impossible with the old `agent.py` approach where eligibility lived inside a state machine function.

---

**L13 — Special requirements in data, not code, means new schemes need no code changes**

The old `check_final_eligibility` hardcoded three scheme IDs. Adding a fourth scheme with a special rule would require editing Python. The new engine reads `special_requirements` from the scheme dict generically — adding a new scheme's special rule is a JSON data change, not a code change. This is the right direction for a data-driven system.

---

**L14 — `failed` takes priority over `unknown` in status determination**

If a user hard-fails one criterion (e.g. wrong gender) but also has unknown fields, the overall status is `LIKELY_NOT_ELIGIBLE`, not `NEEDS_VERIFICATION`. There is no point collecting more information when a hard rule has already failed. This priority ordering was a deliberate design choice and is verified by `test_failed_takes_priority_over_unknown`.

### 2026-08-27 — Session 4: agent.py Migration

**L15 — Separating decision logic from conversation state makes both simpler**

The old `agent.py` had eligibility rules interleaved with state transitions. Extracting the engine made two things happen: the engine became trivially testable (pure function, no session), and the conversation layer became simpler (just collect inputs, call engine, render output). Neither layer needed to know about the internals of the other. This is the practical payoff of the architecture we designed.

---

**L16 — `collecting_missing_field` is more general than `scheme_specific_question`**

The old state had three hardcoded `if scheme["id"] == ...` branches. The new state has none — it reads `result.missing_fields` from the engine and looks up the question to ask from a dict. Adding a new scheme with a special requirement now requires: (1) add the field to `schemes.json` `special_requirements`, (2) add the question text to `_MISSING_FIELD_QUESTIONS` in `agent.py`. No logic change needed.

---

**L17 — The LLM trigger word list is an ordering hazard**

The `question_words` check runs before all other routing, including the documents shortcut. Any word in that list that appears in a user message — even as a substring — routes to the LLM. The word "documents" contains "document" which is in the list. This means typing "documents" as a command always hits the LLM, not the shortcut. The fix in tests was to use "పత్రాలు" instead. The underlying issue (LLM trigger is checked too early and too broadly) should be addressed separately.

### 2026-08-28 — Session 5: Telegram Smoke Test

**L18 — Automated tests validate application logic, but not external service integration**

81 unit and conversation-layer tests pass reliably. They test everything the engine and state machine do in isolation. They cannot test whether the Telegram API responds within the configured timeout, whether the network path to `api.telegram.org` is stable, or whether the bot's polling connection is healthy. A green test suite is a necessary condition for a working bot — not a sufficient one. Real integration testing against the live Telegram API is a separate step and must be done before any demo.

---

**L19 — A successful startup does not guarantee successful external API communication**

The bot process started cleanly, all imports resolved, and the Telegram polling loop initialised without error. The first outbound API call still timed out. These are two independent things: process health and network/API health. In a demo context, both need to be verified separately. The sequence is: (1) run tests, (2) start bot, (3) send a real message and confirm a real reply.

### 2026-08-28 — Session 6: Normalized Discovery Model

**L20 — Literal keyword matching is a data problem that compounds over time**

The old discovery model worked by substring-matching a user's occupation string against `target_business_types` values in `schemes.json`. For "tailor" this returned exactly one scheme — PM Vishwakarma — because only that scheme used the words "tailor" or "tailors" in its target types. Mudra Shishu targets "Service Providers, Micro-Units, Small Shops, Street Vendors" — all relevant to a tailor, but not textually connected to the word "tailor."

Fixing this with keyword expansion would require maintaining an ever-growing, English-biased synonym table. The table would need to cover every scheme's phrasing, every user's phrasing, and every combination. This doesn't scale.

*The right fix is a layer of abstraction:* assign schemes to normalized categories, assign occupations to normalized categories, and match on the categories — not the words.

---

**L21 — A controlled vocabulary makes the system auditable and constraints testable**

Once there is a controlled vocabulary (10 categories: `service`, `retail`, `artisan`, `micro_enterprise`, `manufacturing`, `transport`, `agriculture`, `startup`, `women_led`, `vendor`), every assignment can be validated automatically. Tests check that:

- Every business scheme has `normalized_categories`
- Every category used is from the allowed set
- Every occupation maps only to allowed categories

Without a controlled vocabulary, the category field would grow arbitrarily and become another unmaintainable synonym table. The constraint is what makes the abstraction work.

---

**L22 — Discovery and eligibility are separate responsibilities with different failure modes**

Discovery failure: a scheme that should appear as a candidate is missing from the list. The user never considers it. This is a silent miss — no error, just a missed opportunity.

Eligibility failure: a scheme is shown as eligible when the user doesn't actually qualify. This is a wrong answer — potentially misleading.

These have different acceptable error rates. Discovery can be inclusive (show more candidates; let the engine filter) without harm. Eligibility must be precise. Mixing the two responsibilities into one function means tuning one always risks breaking the other. The separation is the architecture.

---

**L23 — The legacy keyword fallback is the right default for the transition period**

11 canonical occupations are now in `occupation_to_categories`. There are many more occupations users might describe. Rather than crashing or returning nothing for unrecognised occupations, the new `get_candidate_schemes` function falls back to the old keyword model. This preserves existing behavior for everything not yet mapped, and makes the upgrade path incremental. The next step is LLM-based occupation classification that normalises free-text occupation descriptions (e.g. "నేను టైలరింగ్ చేస్తున్నాను") to canonical keys ("tailor") — that step is deferred, but the architecture is ready for it.

<!-- Add new entries below as work progresses -->
