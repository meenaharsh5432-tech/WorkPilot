# WorkPilot — Autonomous AI Task Worker

WorkPilot is a local prototype of an AI operations worker that accepts a natural-language request, chooses from a restricted set of tools, performs invoice-processing operations, checks the resulting database state, and requests human authorization when appropriate.

Built for the **CentrAlign AI Engineering Intern — Autonomous AI Task Worker** assignment. The focus is verifiable execution in a controlled, synthetic company environment—not a chatbot that merely describes what it would do.

## What it can do

- Interpret requests such as "Find the latest Acme invoice, save it, and verify the result."
- Search a local collection of sample invoices and extract structured fields.
- Validate and persist invoice records in SQLite while preventing duplicate invoice entries.
- Read saved records back and compare them with extracted information.
- Request a human decision before marking a payment as approved; approvals do **not** initiate actual payments.
- Track tasks, tool calls, outcomes, errors, and retry evidence.
- Retry a supported read-only operation (`get_invoice`) after certain database operational errors, with bounded attempts.
- Show task execution history, approvals, and evaluation metrics through a Streamlit dashboard.

## Architecture

```text
Natural-language request (Streamlit or FastAPI)
                    |
                    v
          FastAPI task endpoint
                    |
                    v
           LangChain agent + Groq
          (reasoning / tool choice)
                    |
                    v
       Controlled tool executor + logs
          /       |          \
         v        v           v
  Local files   SQLite     Approval gate
  (synthetic)  (records)   (human decision)
         \        |           /
          \       v          /
          Read-back verification
                    |
                    v
     Task status + evidence + dashboard
```

**Components**

| Component | Responsibility |
|---|---|
| `app/main.py` | FastAPI routes for tasks, steps, invoices, and approvals |
| `app/agent/reasoning.py` | LangChain/Groq agent orchestration and outcome verification |
| `app/agent/executor.py` | Allowed tool execution, bounded retry for safe reads, and execution-step logging |
| `app/tools/invoice_tools.py` | Invoice-file lookup and extraction |
| `app/tools/finance_tools.py` | Invoice persistence and retrieval |
| `app/tools/approval_tools.py` | Create human approval requests |
| `app/models.py`, `app/database.py` | SQLAlchemy models and SQLite storage |
| `frontend/dashboard.py` | Streamlit task runner, history, approval interface, and metrics |
| `tests/` | Automated regression tests |
| `benchmarks/benchmark_agent.py` | Controlled, real-model benchmark scenarios |

The LLM selects **permitted tools**; application code executes them and enforces business constraints. The model cannot authorize payments by itself.

## Technology

- Python
- FastAPI + Uvicorn
- LangChain and `langchain-groq`
- Groq API; configured model: `openai/gpt-oss-120b`
- SQLAlchemy + SQLite
- Streamlit + Requests
- Pytest

## Setup

### 1. Clone and enter the project

```powershell
git clone <YOUR_GITHUB_REPOSITORY_URL>
cd workpilot
```

Replace the URL with your published repository link.

### 2. Create a virtual environment

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

### 3. Install dependencies

If your repository includes `requirements.txt`:

```powershell
python -m pip install -r requirements.txt
```

Otherwise, create and review a dependency file before publishing. The principal packages used by the prototype are `fastapi`, `uvicorn`, `sqlalchemy`, `python-dotenv`, `langchain`, `langchain-groq`, `streamlit`, `requests`, and `pytest`. Use the versions validated in your environment.

### 4. Configure credentials

Create `.env` in the repository root:

```dotenv
GROQ_API_KEY=your_new_groq_api_key
WORKPILOT_MODEL=openai/gpt-oss-120b
WORKPILOT_APPROVAL_TOKEN=your_new_random_approval_token
```

Use your own **new** secrets. Never commit real credentials. The approval token is intended for a local prototype, not as a production authorization mechanism.

### 5. Start the API

From the repository root, in terminal 1:

```powershell
python -m uvicorn app.main:app --reload
```

Swagger documentation: http://127.0.0.1:8000/docs  
Health check: http://127.0.0.1:8000/health

The development API initializes its SQLite tables at startup.

### 6. Start the dashboard

In terminal 2, from the same root and virtual environment:

```powershell
python -m streamlit run frontend/dashboard.py
```

Dashboard: http://localhost:8501

The dashboard defaults to the API at `http://127.0.0.1:8000`. If supported by your checked-in dashboard version, set `WORKPILOT_API_URL` to override it.

## Quick demo

Use the synthetic invoice files included in `sample_invoices/`.

1. Start FastAPI and Streamlit.
2. Submit: **"Find the latest Acme invoice, extract its details, save it, and verify the stored record."**
3. Check the task summary and individual tool executions.
4. Submit: **"Find the latest Acme invoice, verify it, and request human approval for payment."**
5. Review the pending request under **Human Approval Center**; enter the approval token and approve or reject.
6. Inspect the updated task status and invoice approval state using the dashboard or API.

Expected behavior depends on the invoice files present and their contents. In this demo, an approval changes internal status only; no money is transferred.

## API overview

| Method | Endpoint | Purpose |
|---|---|---|
| `GET` | `/health` | Health check |
| `POST` | `/tasks` | Create a natural-language task |
| `GET` | `/tasks` | List tasks |
| `GET` | `/tasks/{task_id}` | Fetch a task |
| `POST` | `/tasks/{task_id}/run` | Execute a pending task |
| `GET` | `/tasks/{task_id}/steps` | Inspect tool execution history |
| `GET` | `/invoices/{invoice_id}` | View stored invoice details |
| `GET` | `/approvals` | List approval requests |
| `POST` | `/approvals/{approval_id}/decision` | Approve/reject (requires `x-approval-token` header) |

Example using PowerShell:

```powershell
$task = Invoke-RestMethod -Method Post `
  -Uri http://127.0.0.1:8000/tasks `
  -ContentType 'application/json' `
  -Body '{"user_request":"Find the latest Acme invoice, save it and verify it."}'

Invoke-RestMethod -Method Post `
  -Uri "http://127.0.0.1:8000/tasks/$($task.id)/run"
```

## Testing and evaluation

Run the Python tests:

```powershell
python -m pytest tests/ -v
```

**Latest user-reported result:** 23 tests passed.

Run the real-agent benchmark:

```powershell
python -m benchmarks.benchmark_agent
```

**Latest user-reported result:** 6 of 6 controlled benchmark scenarios passed in a single run:

1. Normal invoice processing
2. Case-insensitive company request
3. Duplicate invoice protection
4. Unknown-company handling
5. Human approval gate
6. Transient database read failure and recovery

The benchmark uses temporary SQLite databases and sample invoice files. Its simulated read failure exercises the actual agent and executor, but retries are implemented by the **executor**, not independently planned by the language model. The benchmark writes `benchmark_report.json` in the working directory.

Six passes in one run do **not** establish universal reliability or a statistically significant success rate. LLM outputs and API latency may vary.

## Engineering decisions

- **Bounded autonomy:** The agent may select from an allowlist of tools, not arbitrary Python commands or financial operations.
- **Deterministic persistence:** Invoice saving, validation, and approval-state changes are implemented in application code.
- **Read-back verification:** Database state is checked independently of the model's natural-language claims.
- **Idempotency:** The invoice store avoids creating duplicates for the same company/invoice identity.
- **Human-in-the-loop:** Approval is a separate protected API action; the model can request, but not grant, authorization.
- **Auditability:** Tool inputs, outputs, errors, and recovery evidence are kept as execution steps.
- **Safe scoped recovery:** Retries are restricted to the supported read-only `get_invoice` operation; writes and approvals are not blindly retried.
- **Isolated benchmarking:** Benchmark tasks run in disposable local databases, separate from the development database.

## Current limitations

- Invoice ingestion is limited to the configured local **structured text** samples. General PDF/image OCR and email ingestion are not part of this prototype.
- Tasks are currently initiated by the user, rather than by a background inbox watcher or scheduler.
- The task execution endpoint performs synchronous work and is not yet a production task queue.
- SQLite and the current run endpoint have not been hardened for high-concurrency use.
- The retry demo simulates a temporary read error; it does not prove recovery from every type of broken SQLAlchemy connection or invalidated transaction.
- The approval token is a shared local-development secret, not a multi-user authentication/authorization system.
- The benchmark is small, synthetic, and has not been repeated enough to estimate statistical reliability.
- The system does not make real payments or interact with a production finance platform.

## Future improvements

1. Invoice intake from uploaded PDFs/images or a **sandbox** email integration, with validation and deduplication.
2. A durable job queue and background worker for automatic intake and concurrent task processing.
3. More detailed retry classification, per-attempt persistent logs, and session/connection recovery.
4. Role-based access control and per-user approvals.
5. More general document/task tools, repeated benchmarks, adversarial input tests, and prompt-injection defenses.

## Security and responsible use

Use synthetic company data and mock systems. Do **not** connect third-party systems without authorization. Never commit `.env`, database files, secrets, or credentials. Rotate any credentials previously shared in messages, screenshots, logs, or commits.

Suggested `.gitignore` entries:

```gitignore
.env
.venv/
__pycache__/
.pytest_cache/
*.pyc
*.db
*.db-journal
```

Review `benchmark_report.json` before committing it. It may include prompts, tool outputs, and error details.

## Submission checklist

- [ ] Push runnable source code to a GitHub repository.
- [ ] Include a tested `requirements.txt` and a sanitized `.env.example`.
- [ ] Verify setup commands on a clean environment.
- [ ] Attach architecture/design notes and an evaluation report.
- [ ] Record a short demo of successful execution, an approval request, and injected-failure recovery.
- [ ] Document assumptions, limitations, technologies, and next steps.
- [ ] Confirm the submission deadline and link from the original hiring communication.

## Project status

**Prototype implemented and locally tested.** WorkPilot demonstrates bounded agent tool use, invoice processing, database verification, human approvals, and a narrowly scoped retry/recovery path. It is an engineering demonstration, not a production financial system.
