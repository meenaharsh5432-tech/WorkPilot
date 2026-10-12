"""WorkPilot Streamlit dashboard (local development)."""

import json
import os
from collections import Counter

import requests
import streamlit as st

API_URL = os.getenv("WORKPILOT_API_URL", "http://127.0.0.1:8000").rstrip("/")

st.set_page_config(page_title="WorkPilot | AI Operations", page_icon="🤖", layout="wide")
st.markdown("""
<style>
.block-container {max-width: 1280px; padding-top: 2.5rem; padding-bottom: 3rem;}
[data-testid="stMetric"] {border: 1px solid #64748b40; border-radius: 12px; padding: 16px;}
[data-testid="stMetricValue"] {font-size: 1.7rem;}
.stButton > button, .stFormSubmitButton > button {border-radius: 8px;}
@media (max-width: 640px) {.block-container {padding: 1.2rem 1rem;}}
</style>
""", unsafe_allow_html=True)
with st.sidebar:
    st.title("WorkPilot")
    st.caption("AI operations workspace")
    page = st.radio("Workspace", ["Overview", "Approvals", "Task history", "Analytics"])
    st.divider()
    st.caption("Create tasks, review decisions, and inspect execution evidence.")
    st.button("Refresh data", use_container_width=True)

st.title(page)
st.caption({
    "Overview": "Give your agent a task and follow its progress.",
    "Approvals": "Review invoice details before authorizing a decision.",
    "Task history": "Inspect requests, results, and the steps behind each task.",
    "Analytics": "Track recorded task outcomes and tool reliability.",
}[page])
if flash := st.session_state.pop("notice", None):
    st.success(flash)


def api_request(method: str, endpoint: str, **kwargs):
    """Call the FastAPI backend and return (parsed_response, error_message)."""
    try:
        response = requests.request(
            method, f"{API_URL}{endpoint}", timeout=(5, 120 if method == "POST" else 10), **kwargs
        )
        response.raise_for_status()
        return response.json(), None
    except requests.exceptions.ConnectionError:
        return None, "Cannot connect to WorkPilot. Start the API and refresh this page."
    except requests.exceptions.Timeout:
        return None, "The request timed out. Refresh task history to check its status before trying again."
    except requests.exceptions.RequestException as exc:
        message = str(exc)
        if exc.response is not None:
            try:
                detail = exc.response.json().get("detail")
                if detail:
                    message = f"HTTP {exc.response.status_code}: {detail}"
            except (ValueError, AttributeError):
                pass
        return None, message
    except ValueError:
        return None, "The API did not return valid JSON."


def show_json_or_text(value):
    """Display stored tool JSON, or raw text for legacy/malformed records."""
    if value is None or value == "":
        st.caption("No data recorded.")
        return
    if isinstance(value, (dict, list, int, float, bool)):
        st.json(value)
        return
    try:
        st.json(json.loads(value))
    except (json.JSONDecodeError, TypeError, ValueError):
        st.code(str(value))


def display_steps(steps):
    """Render execution records in a reusable expandable timeline."""
    if not steps:
        st.info("No execution steps recorded for this task.")
        return
    for step in steps:
        status = step.get("status", "unknown")
        symbol = "✅" if status == "completed" else "❌" if status == "failed" else "⏳"
        with st.expander(
            f"{symbol} Step {step.get('step_number', '?')}: "
            f"{step.get('tool_name', 'unknown')} — {status}"
        ):
            st.markdown("**Tool input**")
            show_json_or_text(step.get("input_data"))
            st.markdown("**Tool output**")
            show_json_or_text(step.get("output_data"))
            if step.get("error_message"):
                st.error(step["error_message"])


tasks, task_error = api_request("GET", "/tasks")
if not task_error:
    statuses = Counter(task["status"] for task in tasks)
    total, completed, awaiting, failed = st.columns(4)
    total.metric("Total tasks", len(tasks))
    completed.metric("Completed", statuses.get("completed", 0))
    awaiting.metric("Awaiting approval", statuses.get("awaiting_approval", 0))
    failed.metric("Failed", statuses.get("failed", 0))
    st.write("")

if page == "Overview":
    # Create a task and run the agent
    st.subheader("Create a task")
    task_text = st.text_area(
        "What should WorkPilot do?",
        placeholder=(
            "Find the latest Acme invoice, extract its details, "
            "save it to the finance database, and verify it."
        ),
        height=110,
    )
    if st.button("🚀 Run Agent", type="primary"):
        if not task_text.strip():
            st.warning("Please enter a task description.")
        else:
            with st.spinner("Creating and executing task..."):
                created, error = api_request("POST", "/tasks", json={"user_request": task_text})
                if error:
                    st.error(f"Could not create task: {error}")
                else:
                    task_id = created["id"]
                    st.session_state.pop("latest_task", None)
                    st.session_state["latest_task_id"] = task_id
                    result, error = api_request("POST", f"/tasks/{task_id}/run")
                    if error:
                        st.error(f"Agent execution failed for task #{task_id}: {error}")
                    else:
                        st.session_state["latest_task"] = result


    # Latest result
    if "latest_task" in st.session_state:
        result = st.session_state["latest_task"]
        st.divider()
        st.subheader("Latest Task Result")
        col1, col2, col3 = st.columns(3)
        col1.metric("Task ID", result.get("task_id", "-"))
        col2.metric("Tool Executions", result.get("tools_executed", 0))
        col3.metric("Status at execution", result.get("status", "unknown"))
        st.caption("This is the response at execution time. See Task History Explorer for updated status after approval.")
        st.markdown("### Agent Response")
        st.markdown(str(result.get("summary") or "No summary available"))
        if result.get("requires_approval"):
            st.warning("Human approval is required before this task can finish.")
        if result.get("requires_user_input"):
            st.info("The agent needs additional information to continue.")
        if result.get("verification_details"):
            with st.expander("Verification Details"):
                st.json(result["verification_details"])


    # Latest execution timeline
    st.divider()
    st.subheader("Agent Execution Timeline")
    if "latest_task_id" in st.session_state:
        task_id = st.session_state["latest_task_id"]
        steps, error = api_request("GET", f"/tasks/{task_id}/steps")
        if error:
            st.error(f"Could not load execution history: {error}")
        else:
            display_steps(steps)
    else:
        st.info("Run a task to see its execution timeline.")


    # Recent tasks
    st.divider()
    st.subheader("Recent Tasks")
    if task_error:
        st.error(f"Could not load tasks: {task_error}")
    elif tasks:
        st.dataframe(
            [
                {
                    "Task ID": item["id"],
                    "Request": item["user_request"],
                    "Status": item["status"],
                    "Created": item["created_at"],
                }
                for item in tasks
            ],
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.info("No tasks created yet.")



elif page == "Approvals":
    # Human approval center
    st.divider()
    st.subheader("Human Approval Center")
    approvals, approval_error = api_request("GET", "/approvals")
    if approval_error:
        st.error(f"Could not load approvals: {approval_error}")
    else:
        pending = [a for a in approvals if a.get("status") == "pending"]
        if not pending:
            st.success("No pending approvals.")
        for approval in pending:
            approval_id = approval["approval_id"]
            invoice_id = approval["invoice_id"]
            with st.container(border=True):
                st.markdown(f"### Approval Request #{approval_id}")
                st.caption(f"Task #{approval['task_id']} · {approval['action']}")
                invoice, error = api_request("GET", f"/invoices/{invoice_id}")
                if error:
                    st.error(f"Could not load invoice: {error}")
                    continue
                left, right = st.columns(2)
                with left:
                    st.write(f"**Company:** {invoice['company']}")
                    st.write(f"**Invoice:** {invoice['invoice_number']}")
                    st.write(f"**Amount:** {invoice['amount']} {invoice['currency']}")
                with right:
                    st.write(f"**Invoice date:** {invoice['invoice_date']}")
                    st.write(f"**Due date:** {invoice['due_date']}")
                    st.write(f"**Payment approval status:** {invoice['payment_approval_status']}")
                with st.form(f"approval_form_{approval_id}"):
                    decision = st.radio(
                        "Decision", ["approved", "rejected"],
                        horizontal=True, key=f"decision_{approval_id}"
                    )
                    note = st.text_area("Review note", key=f"note_{approval_id}")
                    approval_token = st.text_input(
                        "Approval authorization token", type="password",
                        key=f"token_{approval_id}"
                    )
                    submitted = st.form_submit_button("Submit Decision")
                    if submitted:
                        if not approval_token.strip():
                            st.error("Approval token is required.")
                        else:
                            result, decision_error = api_request(
                                "POST",
                                f"/approvals/{approval_id}/decision",
                                headers={"x-approval-token": approval_token},
                                json={"decision": decision, "note": note},
                            )
                            if decision_error:
                                st.error(f"Could not record decision: {decision_error}")
                            else:
                                st.session_state["notice"] = f"Decision recorded: {result.get('approval_status', decision)}"
                                st.rerun()



elif page == "Task history":
    # Any-task explorer
    st.divider()
    st.subheader("Task History Explorer")
    if task_error:
        st.error(f"Could not load task history: {task_error}")
    elif not tasks:
        st.info("No tasks available.")
    else:
        task_lookup = {task["id"]: task for task in tasks}
        selected_task_id = st.selectbox(
            "Select a task to inspect",
            options=list(task_lookup),
            format_func=lambda tid: (
                f"Task #{tid} — {task_lookup[tid]['status']} — "
                f"{task_lookup[tid]['user_request'][:65]}"
            ),
            key="explorer_task_id",
        )
        selected_task = task_lookup[selected_task_id]
        st.markdown("### Task Information")
        c1, c2, c3 = st.columns(3)
        c1.metric("Task ID", selected_task["id"])
        c2.metric("Current Status", selected_task["status"])
        c3.metric("Created", str(selected_task.get("created_at", ""))[:10])
        st.markdown("**Original Request**")
        st.info(selected_task["user_request"])
        if selected_task.get("result"):
            st.markdown("### Final Stored Result")
            try:
                task_result = json.loads(selected_task["result"])
                if isinstance(task_result, dict) and task_result.get("summary"):
                    st.markdown(str(task_result["summary"]))
                with st.expander("Full Task Result"):
                    show_json_or_text(task_result)
            except (json.JSONDecodeError, TypeError, ValueError):
                st.code(str(selected_task["result"]))
        st.markdown("### Execution Steps")
        selected_steps, error = api_request("GET", f"/tasks/{selected_task_id}/steps")
        if error:
            st.error(f"Could not load steps: {error}")
        else:
            display_steps(selected_steps)



elif page == "Analytics":
    # ---------------------------------------
    # AGENT EVALUATION DASHBOARD
    # ---------------------------------------

    st.divider()
    st.subheader("Agent Evaluation Dashboard")

    evaluation_tasks, evaluation_error = tasks, task_error

    if evaluation_error:
        st.error(f"Could not load evaluation data: {evaluation_error}")

    elif not evaluation_tasks:
        st.info("No task data available for evaluation.")

    else:

        statuses = Counter(
            task["status"] for task in evaluation_tasks
        )

        total = len(evaluation_tasks)
        completed = statuses.get("completed", 0)
        failed = statuses.get("failed", 0)
        needs_input = statuses.get("needs_input", 0)
        awaiting = statuses.get("awaiting_approval", 0)

        col1, col2, col3, col4 = st.columns(4)

        col1.metric("Total Tasks", total)
        col2.metric("Completed", completed)
        col3.metric("Failed", failed)
        col4.metric("Needs Input", needs_input)

        st.markdown("### Task Status Distribution")

        status_data = [
            {"Status": status, "Count": count}
            for status, count in statuses.items()
        ]

        st.bar_chart(
            status_data,
            x="Status",
            y="Count"
        )

        st.markdown("### Completion Rate")

        completion_rate = (
            completed / total * 100
            if total else 0
        )

        st.progress(
            completed / total if total else 0
        )

        st.write(f"**{completion_rate:.1f}%** of recorded tasks are completed.")

        st.caption(
            "Completion rate is based on recorded task statuses. "
            "It is not a controlled measure of agent accuracy, "
            "because tasks may have different objectives and "
            "human approval outcomes."
        )

    # ---------------------------------------
    # TOOL EXECUTION METRICS
    # ---------------------------------------

    st.markdown("### Tool Execution Reliability")

    tool_statuses = Counter()
    tool_usage = Counter()

    failed_step_loads = 0
    for task in evaluation_tasks or []:
        steps, error = api_request(
            "GET",
            f"/tasks/{task['id']}/steps"
        )

        if error:
            failed_step_loads += 1
            continue
        if not steps:
            continue

        for step in steps:
            tool_usage[step["tool_name"]] += 1
            tool_statuses[step["status"]] += 1

    if failed_step_loads:
        st.warning(f"Metrics are incomplete: execution history could not be loaded for {failed_step_loads} task(s).")

    total_calls = sum(tool_statuses.values())
    successful_calls = tool_statuses.get("completed", 0)

    tool_success_rate = (
        successful_calls / total_calls * 100
        if total_calls else 0
    )

    c1, c2, c3 = st.columns(3)

    c1.metric("Total Tool Calls", total_calls)
    c2.metric("Successful Calls", successful_calls)
    c3.metric("Tool Success Rate", f"{tool_success_rate:.1f}%" if total_calls else "—")

    if tool_usage:
        st.markdown("### Tool Usage")

        usage_data = [
            {"Tool": name, "Calls": count}
            for name, count in tool_usage.most_common()
        ]

        st.bar_chart(
            usage_data,
            x="Tool",
            y="Calls"
        )
