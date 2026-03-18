# 🤖 AutoFix DevOps Agent

> **"We built an autonomous AI DevOps engineer that detects CI/CD failures, analyzes logs with structured reasoning, generates fixes, and creates merge requests — transforming CI/CD from reactive debugging to self-healing automation."**

[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/)
[![Flask](https://img.shields.io/badge/flask-2.3%2B-green.svg)](https://flask.palletsprojects.com/)
[![OpenAI](https://img.shields.io/badge/OpenAI-GPT--4o--mini-orange.svg)](https://openai.com/)

---

## 🚀 What is AutoFix?

AutoFix is an **autonomous AI DevOps engineer** (Software 3.0 agent) that:

| Traditional Approach ❌ | AutoFix Approach ✅ |
|------------------------|-------------------|
| Ask AI what's wrong | AI detects → fixes → acts automatically |
| Manually read logs | Smart log extraction (last 50 lines only) |
| Manually create branch + PR | Automated branch + Merge Request |
| Reactive debugging | Self-healing CI/CD automation |

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     AutoFix Agent                           │
│                                                             │
│  ┌──────────────┐   ┌──────────────┐   ┌───────────────┐  │
│  │  🔹 Trigger  │   │ 🧠 AI Brain  │   │ 🔹 Action     │  │
│  │    Layer     │──▶│              │──▶│    Layer      │  │
│  │              │   │ • Log parse  │   │               │  │
│  │ • Webhook    │   │ • Root cause │   │ • New branch  │  │
│  │ • Filter     │   │ • Fix gen    │   │ • Commit fix  │  │
│  │   (only      │   │ • Confidence │   │ • Open MR     │  │
│  │  script_fail)│   │   score      │   │               │  │
│  └──────────────┘   └──────────────┘   └───────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

### 🔹 1. Trigger Layer (`agent/trigger.py`)
- Listens to GitLab pipeline/job webhooks
- **Only processes `script_failure`** — ignores infrastructure/runner issues
- Extracts failure context (project, job, branch, commit)

### 🧠 2. Agent Brain (`agent/brain.py`)
- Uses **structured XML-style prompts** for higher accuracy
- Performs log parsing, root cause analysis, and code fix generation
- Assigns a **confidence score** (High/Medium + percentage)

### 🔹 3. Smart Log Processor (`agent/log_processor.py`)
- Extracts only the **last 50–100 lines** of CI logs
- Strips ANSI codes and CI section markers
- Improves speed ⚡, accuracy 🎯, and reduces cost 💰

### 🔹 4. Action Layer (`agent/action.py`)
- Creates a new fix branch automatically
- Commits the AI-generated fix
- Opens a Merge Request with rich description

---

## 🔄 Full Flow

```
Push bad code
   ↓
Pipeline fails
   ↓
Trigger fires (GitLab webhook → POST /webhook)
   ↓
Agent filters: only script_failure events proceed
   ↓
Fetch CI job logs (last 50 lines extracted)
   ↓
AI analyses root cause (structured XML prompt)
   ↓
Generate fix + confidence score (High/Medium + %)
   ↓
Commit fix to new branch (autofix/<branch>-<job>-<timestamp>)
   ↓
Create Merge Request → human reviews → merges
```

---

## ⚡ Quick Start

### 1. Clone & Install

```bash
git clone https://github.com/Tanmaykumar5423/autofix_devops.git
cd autofix_devops
pip install -r requirements.txt
```

### 2. Configure Environment

```bash
cp .env.example .env
# Edit .env with your credentials:
#   OPENAI_API_KEY=sk-...
#   GITLAB_URL=https://gitlab.com
#   GITLAB_TOKEN=glpat-...
#   GITLAB_PROJECT_ID=12345
#   WEBHOOK_SECRET=your_secret   # optional
```

### 3. Run the Agent

```bash
python app.py
# Agent listening on http://0.0.0.0:5000
```

### 4. Configure GitLab Webhook

In your GitLab project → Settings → Webhooks:
- **URL**: `http://your-server:5000/webhook`
- **Secret token**: value from `WEBHOOK_SECRET`
- **Trigger**: ✅ Job events, ✅ Pipeline events

---

## 📡 API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/webhook` | `POST` | GitLab CI/CD webhook receiver |
| `/health` | `GET` | Health check |

### Example Response (Fix Created)

```json
{
  "status": "fixed",
  "merge_request_url": "https://gitlab.com/org/project/-/merge_requests/42",
  "confidence": "High",
  "confidence_percentage": 92,
  "root_cause": "Missing dependency in requirements.txt"
}
```

---

## 📊 Confidence Score

The agent assigns a confidence score to every generated fix:

| Score | Meaning |
|-------|---------|
| 🟢 **High** (80–99%) | Clear, unambiguous error — fix is reliable |
| 🟡 **Medium** (50–79%) | Error detected but fix may need human review |

---

## 🔐 Security Model

- ✅ **Agent writes ONLY to new branches** — never to `main` or protected branches
- ✅ **Human review required** — all fixes go through Merge Request review
- ✅ **Webhook signature verification** — optional HMAC-SHA256 secret validation
- ✅ **Minimal GitLab token scope** — only developer-level access needed

---

## 🧪 Running Tests

```bash
pytest tests/ -v
```

---

## 📁 Project Structure

```
autofix_devops/
├── app.py                  # Flask webhook server (entry point)
├── agent/
│   ├── trigger.py          # Trigger layer — filter pipeline failures
│   ├── brain.py            # AI brain — analysis + fix generation
│   ├── log_processor.py    # Smart log processing (last 50 lines)
│   └── action.py           # Action layer — git ops + MR creation
├── tests/
│   ├── test_trigger.py
│   ├── test_brain.py
│   └── test_log_processor.py
├── requirements.txt
├── .env.example
└── README.md
```

---

## 🧠 Key Innovation: Smart Log Processing

Instead of sending thousands of log lines to the AI model (slow, expensive, inaccurate):

```python
# Only the last 50 lines — focused on the actual error
log_snippet = process_log(raw_log, tail_lines=50)
```

This approach:
- ⚡ **3-5× faster** AI response time
- 🎯 **Higher accuracy** — error is always at the end of CI logs
- 💰 **Lower cost** — fewer tokens consumed

---

*Built for the Software 3.0 era — autonomous agents that detect, reason, and act.*
