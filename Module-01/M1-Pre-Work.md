<!-- JHF-BRAND -->
<div align="center" style="padding:28px 20px; background:#ffffff; border:2px solid #e0e0e0; border-radius:12px;">
  <p style="margin:0 0 16px 0;">
    <img src="../assets/jhf-logo.png" alt="Jerusalem High-Tech Foundry (JHF)" height="54" style="vertical-align:middle; margin:0 22px;" />
    <img src="../assets/comcec-logo.png" alt="COMCEC - Cooperation for Development" height="72" style="vertical-align:middle; margin:0 22px;" />
  </p>
  <h1 style="color:#1a3c5e; margin:6px 0;">Agentic AI Bootcamp</h1>
  <h3 style="color:#0078d4; margin:4px 0; font-weight:600;">Module 1 &middot; Pre-Work &mdash; What Agentic AI Really Is</h3>
  <hr style="border:0; border-top:1px solid #0078d4; width:60%; margin:16px auto;" />
  <p style="font-size:14px; color:#555; margin:6px 0;">
    <strong>Lead Trainer</strong><br/>
    <a href="https://www.linkedin.com/in/alaaldin-ahmed-260266150" target="_blank">Alaaldin Ahmed</a>
  </p>
  <p style="font-size:12.5px; color:#777; margin:8px 0 0 0;">
    Organized by <strong>Jerusalem High-Tech Foundry (JHF)</strong> &nbsp;&middot;&nbsp; In partnership with <strong>COMCEC</strong>
  </p>
</div>

# Module 1 — Pre-Work
## What Agentic AI Really Is

> **Complete BEFORE the session.** Total time: **~25 minutes.**
> Two parts: (1) a required **setup check** — non-negotiable, or you'll lose lab time; (2) a short **primer** + 3 questions to arrive ready.
> No code to write yet. The goal is to walk in with a working environment and the right mental model.

---

## Part A — Setup Check (REQUIRED, ~15 min)

Do this on the machine you'll bring to class. If anything fails, message the instructor channel **before** the session.

1. **Python 3.11+**
   - Run: `python --version` → must show 3.11 or higher.

2. **Create your OpenRouter API key** — this bootcamp calls all LLMs through **[OpenRouter](https://openrouter.ai)** (one key, many models, OpenAI-compatible).
   1. Go to **https://openrouter.ai** and sign in (Google/GitHub/email).
   2. Open **https://openrouter.ai/keys** → **Create Key** → name it `agentic-bootcamp` → **Create** → **copy the key** (starts with `sk-or-...`). You won't see it again.
   3. Add a little credit: **https://openrouter.ai/credits** → add **$5–10** (pay-as-you-go; our default model `openai/gpt-4o-mini` is very cheap — the whole course costs ~$1–2). *Free models exist too; the instructor will confirm the class default.*

3. **Set the key as an environment variable** (never paste keys into code):
   - **PowerShell (Windows):**
     ```powershell
     $env:OPENROUTER_API_KEY="sk-or-...your key..."
     ```
     > This lasts for the current terminal only. To make it permanent, run once:
     > `setx OPENROUTER_API_KEY "sk-or-...your key..."` then **open a new terminal**.
   - **macOS/Linux (bash/zsh):**
     ```bash
     export OPENROUTER_API_KEY="sk-or-...your key..."
     ```
   - From **Module 2** on, you'll instead keep it in a git-ignored **`.env`** file (`OPENROUTER_API_KEY=sk-or-...`) loaded by `python-dotenv`. A ready-to-copy **`.env.example`** is in the repo root.

4. **Editor + GitHub Copilot Pro** — you'll use Copilot as a pair-programmer all bootcamp, so a **paid GitHub Copilot Pro** subscription is required.
   1. **Get a GitHub account** — sign in or sign up at **https://github.com**.
   2. **Check for free access first** — if you're a verified student or teacher, Copilot Pro is **free** via **[GitHub Education](https://github.com/education)** (apply with your academic email; approval can take a few days, so do this early).
   3. **Otherwise, subscribe to Copilot Pro** (~**$10/month** or **$100/year**, with a **30-day free trial** for eligible accounts):
      - Go to **https://github.com/settings/copilot** (or **https://github.com/features/copilot** → **Get Copilot Pro**).
      - Choose **Copilot Pro** → **Start free trial / Subscribe** → enter payment details → confirm.
   4. **Install the Copilot extension in your editor:**
      - **VS Code:** Extensions (`Ctrl+Shift+X`) → search **"GitHub Copilot"** → **Install** → sign in with your GitHub account when prompted.
      - **JetBrains / Visual Studio / Neovim:** install the official **GitHub Copilot** plugin from the IDE's marketplace, then sign in.
   5. **Verify it works:** open a `.py` file, type a comment like `# function that adds two numbers` and press Enter — you should see a grey inline suggestion. Accept with **Tab**.
   - ☑️ Done when you see live Copilot suggestions in your editor.

5. **Smoke test (the gate)** — prove the key works before class:
   ```bash
   pip install openai
   ```
   ```python
   # smoke_test.py
   import os
   from openai import OpenAI

   client = OpenAI(
       api_key=os.environ["OPENROUTER_API_KEY"],
       base_url="https://openrouter.ai/api/v1",
   )
   resp = client.chat.completions.create(
       model="openai/gpt-4o-mini",
       messages=[{"role": "user", "content": "Reply with the single word: ok"}],
   )
   print(resp.choices[0].message.content)
   ```
   - Run `python smoke_test.py` → you should see **`ok`**.
   - ✅ **You must see a model reply before class.** A dead key is the #1 reason people fall behind on Day 1.

> ☑️ **Done when:** `python --version` is 3.11+, `OPENROUTER_API_KEY` is set, Copilot is on, and `smoke_test.py` prints a reply.

---

## Part B — Primer (~10 min)

Read **§1–§2 of the M1 Learner Handout** (*The Agency Spectrum* and *The Agent Loop*). As you read, hold these ideas:

- An **agent** is defined by *who decides the next step* — the **model at runtime**, not the developer in advance.
- The loop is **Perceive → Reason → Act → Observe**, repeated until done.
- The model **decides**; your code **executes**. Always keep a **hard stop** (step/cost cap).

### Arrive ready to answer (jot a one-line answer each)
1. In your own words, what's the difference between a **workflow** and an **agent**?
2. Why must an agent loop **always** have a step or cost cap?
3. Think of one task from your own life/work that genuinely needs an agent — and one that absolutely does not.

> Bring your three answers. We'll open the session with them.

---

## Optional Stretch (only if curious)
- Skim the difference between "function calling / structured output" and free-text model responses — you'll use this in M3. No need to understand it deeply yet.

---

**Why this matters:** the session is ~70% hands-on. Doing this 25-minute prep means we start building immediately instead of fighting setup — and the concepts will already feel familiar.

---

<div align="center" style="padding:14px; border-top:2px solid #0078d4; margin-top:34px;">
  <p style="margin:0 0 8px 0;">
    <img src="../assets/jhf-logo.png" alt="JHF" height="28" style="vertical-align:middle; margin:0 14px; background:#ffffff; padding:6px 10px; border-radius:6px;" />
    <img src="../assets/comcec-logo.png" alt="COMCEC" height="40" style="vertical-align:middle; margin:0 14px; background:#ffffff; padding:6px 10px; border-radius:6px;" />
  </p>
  <p style="color:#888; font-size:13px; margin:0;">
    <strong>JHF Agentic AI Bootcamp</strong> &mdash; Module 1 Pre-Work<br/>
    Lead Trainer: <a href="https://www.linkedin.com/in/alaaldin-ahmed-260266150">Alaaldin Ahmed</a><br/>
    Organized by Jerusalem High-Tech Foundry (JHF) &middot; In partnership with COMCEC
  </p>
</div>

