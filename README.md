# Kapture Finance Collections Voicebot ("Maya") - Task 2 Submission

This project contains the complete source code, tool schemas, and setup guidelines for **Maya**, the outbound collections voicebot for **Kapture Finance**. 

---

## 1. Project Directory Structure
- **`HLD.md`**: Task 1 High-Level Design document containing architecture specifications, pipeline latency details, compliance, state-machine transitions, and observability guidelines.
- **`system_prompt.txt`**: The complete state-enforced Vapi system prompt.
- **`server.py`**: A FastAPI webhook server implementing endpoints for the voicebot tools and handling Vapi webhook formats.
- **`requirements.txt`**: List of Python requirements for running the webhook server locally.
- **`tools/`**: Folder containing the JSON definitions for the 5 Vapi custom tools:
  - `verify_customer.json`
  - `log_promise_to_pay.json`
  - `send_payment_link.json`
  - `escalate_to_agent.json`
  - `mark_disposition.json`
- **`architecture_diagram.mermaid`**: Source code of the architecture and state-machine flow diagrams.

---

## 2. Setup & Installation Instructions

### Prerequisites
- Python 3.10+ installed.
- A Vapi.ai account (free trial credits are sufficient).
- `ngrok` installed (to expose your local webhook server to the internet).

### Step 1: Install Dependencies
Navigate to this project directory in your terminal and install the requirements:
```bash
pip install -r requirements.txt
```

### Step 2: Start the Webhook Server
Run the FastAPI webhook server:
```bash
python server.py
```
The server will start running locally at `http://127.0.0.1:8000`. You can inspect the API endpoints in your browser at `http://127.0.0.1:8000/docs`.

### Step 3: Expose Server with ngrok
To allow Vapi to communicate with your local mock database, expose port `8000` using ngrok:
```bash
ngrok http 8000
```
This will output a public forwarding URL like: `https://abcd-12-34-56.ngrok-free.app`. Copy this forwarding URL.

### Step 4: Configure Tools on Vapi
1. Log in to the [Vapi Dashboard](https://dashboard.vapi.ai).
2. Go to **Tools** -> **Create Tool**.
3. Create the 5 tools one by one. Select the type as **Function** and paste the JSON schemas located in the `tools/` folder.
4. For each tool, set the **Server URL** to: `<your_ngrok_forwarding_url>/webhook` (e.g. `https://abcd-12-34-56.ngrok-free.app/webhook`).

### Step 5: Configure the Vapi Assistant
1. In Vapi, go to **Assistants** -> **Create Assistant**.
2. **Model**: Set to **GPT-4o-mini** (for low latency and excellent tool parsing). Set temperature to `0.1` (to prevent hallucinations and maintain strict state-machine flow).
3. **Transcriber**: Set to **Deepgram (Nova-2)**. Select Language as `en-IN` (Indian English) or `Multi-language` if testing bilingual switches.
4. **Voice**: Set to **Cartesia (Sonic-multilingual)** or **ElevenLabs (Neha - Indian Female)**.
5. **System Prompt**: Copy and paste the contents of `system_prompt.txt` as the assistant's System Prompt.
6. **First Message**: Set the initial message to: `"Hello, am I speaking with Rahul Sharma?"`
7. **Tools**: Assign the 5 created tools to this assistant.
8. Set the assistant's general **Server URL** (under Advanced settings) to `<your_ngrok_forwarding_url>/webhook`.

---

## 3. Design Choices & Voice AI Configuration

- **Orchestration Framework**: **Vapi.ai** was selected for its low-overhead streaming audio loop (telephony, speech-to-text, LLM context generation, and speech generation).
- **Deepgram Nova-2 (STT)**: Handles the Indian accent (`en-IN`) with high accuracy (low Word Error Rate). Its endpointing features prevent the bot from interrupting the customer too early or lagging behind.
- **GPT-4o-mini (LLM)**: Chosen over larger models (like GPT-4o or Sonnet) because of its significantly lower Time-To-First-Token (~250-300ms) and highly structured, reliable function calls.
- **Cartesia Sonic-multilingual (TTS)**: Offers ultra-low latency text-to-speech (~90ms generation speed). It allows clean bilingual shifting (English/Hindi) mid-call without voice quality degradation.
- **State-Enforced Prompt**: Using distinct Markdown states in the system prompt locks the bot's behavior. The LLM is strictly instructed **not** to share details of the loan/overdue EMI before calling the `verify_customer` tool and receiving a success payload.

---

## 4. Troubleshooting & Debugging Logs

### What Broke & How it Was Fixed:
1. **Tool Schema Discrepancy**: Vapi tool calls were failing with schema warnings when returning arrays. 
   - *Fix*: Structured the FastAPI webhook response to conform precisely to Vapi's multi-tool output syntax: `{"results": [{"toolCallId": "...", "result": { ... }}]}`.
2. **LLM Pre-emptively Disclosing Debt Details**: In initial prompt iterations, when the customer asked "Why are you calling?", the LLM would occasionally explain that the loan EMI of ₹8,499 was overdue, bypassing verification.
   - *Fix*: Added a strict **"Compliance Lock"** warning block at the top of the prompt and in State 0/1. The bot is restricted to stating: "It is regarding your personal loan account, but I require identity verification before discussing details."
3. **Relative Dates in PTP Logging**: The LLM would pass strings like `"this coming Friday"` instead of `"YYYY-MM-DD"`.
   - *Fix*: Added guidance in the system prompt for the bot to output ISO format dates and added a date parser fallback in the FastAPI backend logic to calculate relative offsets.

---

## 5. Future Enhancements
- **Dynamic Speech Rate / Tone Match**: Adjusting TTS speed based on customer response speed to improve connection and lower drop rates.
- **Direct SMS Gateway Integration**: Wire Twilio or MSG91 credentials directly inside environment variables (supported in `server.py`) to trigger automated WhatsApp payment links dynamically.
- **Voice Biometrics**: Use voiceprint analysis for frictionless, compliant authentication instead of Aadhaar confirmation.
