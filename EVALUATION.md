# WorkPilot — Agent Evaluation Report

## Objective

Evaluate whether WorkPilot can carry out natural-language invoice-processing requests through real tool execution, verify persisted outcomes, handle missing information and duplicate records, enforce human approval, and recover from a simulated transient tool failure.

## Evaluation setup

- **Agent:** LangChain-based agent using Groq (`openai/gpt-oss-120b` in the project's current configuration).
- **Backend and storage:** FastAPI, SQLAlchemy, and SQLite.
- **Tools:** Invoice search, field extraction, database save, database read-back, and human approval request.
- **Test data:** Synthetic, structured text invoices.
- **Isolation:** Each benchmark scenario uses a temporary SQLite database and a controlled invoice directory.
- **Execution:** Actual agent calls are made for each benchmark scenario; checks inspect database state, recorded tool calls, and agent outcome.
- **Command:** `python -m benchmarks.benchmark_agent`
- **Report output:** `benchmark_report.json`

## Results

The user-reported latest run completed **6 of 6 benchmark scenarios successfully (100% for this run)**.

| Scenario | Expected outcome | Reported result | Evidence checked |
| --- | --- | --- | --- |
| Normal invoice processing | `completed` | PASS | One invoice saved; record read back and verified |
| Case-insensitive company request | `completed` | PASS | Mixed-case company request handled; record verified |
| Duplicate invoice protection | `completed` | PASS | Existing invoice not duplicated |
| Unknown company | `needs_input` | PASS | No invoice fabricated or saved |
| Human approval gate | `awaiting_approval` | PASS | Invoice verified; pending approval exists; payment approval still `not_approved` |
| Transient database failure recovery | `completed` | PASS | First simulated invoice read fails, retry succeeds, retry evidence recorded, and task verified |

The benchmark pass rate describes **one reported run of six controlled scenarios**. It is not a claim of 100% reliability on arbitrary tasks.

## Independent unit and integration tests

The user also reported **23 passing automated tests** following the recovery-executor integration test. These tests cover the existing invoice/finance/approval components and recovery behavior.

Run the tests with:

```powershell
python -m pytest tests/ -v
```

## Recovery scenario: what it demonstrates

The sixth scenario deliberately raises a simulated SQLAlchemy `OperationalError` on the first `get_invoice` call. The bounded retry policy then makes a second read attempt. The benchmark checks both the final verified outcome and the retry event stored in the tool execution record.

This demonstrates **executor-managed recovery within a real agent task**. The LLM does not independently decide to retry this specific failure: the deterministic executor applies a narrowly scoped policy for the read-only `get_invoice` tool. The simulation does not prove recovery from an actual invalidated database connection or all forms of `OperationalError`.

No automatic retry is enabled for invoice-saving or approval actions, where repeated execution could have side effects.

## Safety and verification controls

- Invoice processing includes database read-back comparison rather than accepting a tool's claimed success alone.
- Duplicate processing is checked against the persisted invoice count.
- An unknown company results in a request for additional information, rather than a fabricated invoice.
- Approval requests are created only after invoice verification in the tested approval scenario.
- Creating a pending approval does **not** set `payment_approval_status` to `approved`.
- A human authorization decision is required before simulated payment approval state changes.
- WorkPilot **does not transfer money or execute a real payment**.

## Limitations

1. Only six benchmark scenarios were included, and the reported run was not repeated statistically.
2. LLM outputs, response times, and external API availability may vary across runs.
3. Inputs are structured synthetic text invoices; scanned PDFs, images, and email ingestion are not yet implemented.
4. Transient-failure injection is simulated and does not cover invalidated SQLAlchemy sessions or real network outages.
5. The narrow tool interface demonstrates invoice operations, not general desktop or browser control.
6. Execution is designed for a local prototype; production concerns such as queues, concurrency, authentication, rate limits, secrets management, and monitoring require additional work.

## How to reproduce

1. Create and activate the project virtual environment.
2. Install the project dependencies and set the required environment variables in an untracked `.env` file.
3. Run the deterministic tests:

   ```powershell
   python -m pytest tests/ -v
   ```

4. Run the Groq-powered benchmark from the repository root:

   ```powershell
   python -m benchmarks.benchmark_agent
   ```

5. Inspect `benchmark_report.json` and confirm scenario statuses, database checks, tool execution history, and recovery evidence.

**Security:** Use synthetic data, rotate any previously exposed credentials, and never commit `.env` or production secrets.

## Next improvements

- Repeat all scenarios over multiple runs and report per-scenario success frequency and latency distribution.
- Test malformed invoice fields, partial writes, timeouts, and persistent tool failures.
- Add rollback/session recreation for specific retryable connection failures.
- Extend document intake to PDFs and optionally email, with safe attachment handling.
- Add a queued background worker and stronger API authentication for multi-user deployments.

## Conclusion

WorkPilot passed the user's latest six-scenario benchmark run and 23 automated tests. The observed results support a functioning, bounded invoice-processing agent with verifiable database operations, human approval controls, and simulated transient-read recovery. The results should be interpreted within the controlled prototype environment and the limitations above.
