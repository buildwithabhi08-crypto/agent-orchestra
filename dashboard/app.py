"""Streamlit dashboard for Agent Orchestra."""

from __future__ import annotations

import time

import requests
import streamlit as st

# Configuration
API_URL = "http://localhost:8000/api"

st.set_page_config(
    page_title="Agent Orchestra",
    page_icon="🎼",
    layout="wide",
    initial_sidebar_state="expanded",
)


def init_session_state():
    """Initialize session state variables."""
    if "current_task_id" not in st.session_state:
        st.session_state.current_task_id = None
    if "events" not in st.session_state:
        st.session_state.events = []


def sidebar():
    """Render the sidebar with agent info and task history."""
    with st.sidebar:
        st.title("Agent Orchestra")
        st.caption("Multi-Agent SaaS Builder")

        st.divider()

        # Agent status
        st.subheader("Agents")
        try:
            response = requests.get(f"{API_URL}/agents", timeout=5)
            if response.status_code == 200:
                agents = response.json().get("agents", [])
                for agent in agents:
                    role = agent["role"]
                    name = agent["name"]
                    model = "Gemini" if "Google" in agent.get("model", "") else "Kimi K2.5"
                    tools = agent.get("tools", [])

                    with st.expander(f"**{name}**"):
                        st.caption(f"Role: `{role}`")
                        st.caption(f"Model: `{model}`")
                        if tools:
                            st.caption(f"Tools: {', '.join(tools)}")
                        st.caption(f"Skills: {'Yes' if agent.get('has_skills') else 'No'}")
        except requests.exceptions.ConnectionError:
            st.warning("Backend not connected. Start the FastAPI server first.")

        st.divider()

        # Task history
        st.subheader("Task History")
        try:
            response = requests.get(f"{API_URL}/tasks", timeout=5)
            if response.status_code == 200:
                tasks_list = response.json().get("tasks", [])
                for task in reversed(tasks_list):
                    status_emoji = {
                        "pending": "⏳",
                        "planning": "📋",
                        "in_progress": "🔄",
                        "awaiting_approval": "⏸️",
                        "completed": "✅",
                        "failed": "❌",
                    }.get(task["status"], "❓")

                    if st.button(
                        f"{status_emoji} {task['description'][:40]}...",
                        key=f"task_{task['task_id']}",
                        use_container_width=True,
                    ):
                        st.session_state.current_task_id = task["task_id"]
                        st.rerun()
        except requests.exceptions.ConnectionError:
            pass


def render_task_input():
    """Render the task input section."""
    st.header("New Task")
    st.markdown(
        "Describe what you want to build, research, validate, or market. "
        "The orchestrator will break it down and assign it to the right agents."
    )

    with st.form("task_form"):
        task_description = st.text_area(
            "Task Description",
            height=150,
            placeholder=(
                "Example: I want to build a micro-SaaS that helps freelancers "
                "track their invoices and get paid faster. Research the market, "
                "validate the idea, build a prototype, and create a marketing plan."
            ),
        )

        col1, col2 = st.columns(2)
        with col1:
            target_audience = st.text_input(
                "Target Audience (optional)",
                placeholder="e.g., Freelancers, Small businesses",
            )
        with col2:
            budget = st.text_input(
                "Budget Range (optional)",
                placeholder="e.g., $0-100/month",
            )

        submitted = st.form_submit_button("Launch Agents", type="primary", use_container_width=True)

        if submitted and task_description:
            context = {}
            if target_audience:
                context["target_audience"] = target_audience
            if budget:
                context["budget"] = budget

            try:
                response = requests.post(
                    f"{API_URL}/tasks",
                    json={"description": task_description, "context": context},
                    timeout=10,
                )
                if response.status_code == 200:
                    task_data = response.json()
                    st.session_state.current_task_id = task_data["task_id"]
                    st.success(f"Task created! ID: {task_data['task_id']}")
                    st.rerun()
                else:
                    st.error(f"Error: {response.text}")
            except requests.exceptions.ConnectionError:
                st.error("Cannot connect to backend. Is the FastAPI server running?")


def render_task_progress(task_id: str):
    """Render the progress view for an active task."""
    try:
        response = requests.get(f"{API_URL}/tasks/{task_id}", timeout=5)
        if response.status_code != 200:
            st.error("Task not found")
            return

        task_data = response.json()
    except requests.exceptions.ConnectionError:
        st.error("Cannot connect to backend")
        return

    # Header
    st.header(f"Task: {task_data.get('description', task_id)[:80]}")

    # Status bar
    status = task_data.get("status", "unknown")
    phase = task_data.get("current_phase", "")

    col1, col2, col3 = st.columns(3)
    with col1:
        status_colors = {
            "pending": "🟡",
            "planning": "🔵",
            "in_progress": "🟢",
            "awaiting_approval": "🟠",
            "completed": "✅",
            "failed": "🔴",
        }
        st.metric("Status", f"{status_colors.get(status, '❓')} {status.replace('_', ' ').title()}")
    with col2:
        st.metric("Phase", phase.replace("_", " ").title() if phase else "N/A")
    with col3:
        plan = task_data.get("plan")
        if plan and hasattr(plan, "subtasks"):
            completed = sum(1 for st_item in plan.subtasks if st_item.get("status") == "completed")
            st.metric("Progress", f"{completed}/{len(plan.subtasks)} tasks")

    st.divider()

    # Approval section
    if status == "awaiting_approval":
        st.warning("The orchestrator is waiting for your approval to proceed.")

        with st.form("approval_form"):
            feedback = st.text_area("Feedback (optional)", placeholder="Any changes or directions?")
            col1, col2 = st.columns(2)
            with col1:
                approve = st.form_submit_button("Approve & Continue", type="primary")
            with col2:
                reject = st.form_submit_button("Request Changes")

            if approve:
                requests.post(
                    f"{API_URL}/tasks/{task_id}/approve",
                    json={"approved": True, "feedback": feedback},
                    timeout=10,
                )
                st.rerun()
            elif reject:
                requests.post(
                    f"{API_URL}/tasks/{task_id}/approve",
                    json={"approved": False, "feedback": feedback},
                    timeout=10,
                )
                st.rerun()

    # Results tabs
    tab1, tab2, tab3 = st.tabs(["Agent Activity", "Results", "Final Output"])

    with tab1:
        events = task_data.get("events", [])
        if events:
            for event in events:
                agent = event.get("agent", "system")
                content = event.get("content", "")
                event_type = event.get("event_type", "")

                icon_map = {
                    "phase_start": "🚀",
                    "plan_created": "📋",
                    "agent_start": "🤖",
                    "agent_complete": "✅",
                    "agent_error": "❌",
                    "checkpoint": "⏸️",
                    "approval": "👤",
                    "task_complete": "🎉",
                    "error": "⚠️",
                }
                icon = icon_map.get(event_type, "📝")

                st.markdown(f"{icon} **[{agent}]** {content}")
        else:
            st.info("Waiting for agent activity...")

    with tab2:
        results = task_data.get("results", {})
        if results:
            for result_key, result_value in results.items():
                with st.expander(f"Result: {result_key}", expanded=False):
                    st.markdown(result_value)
        else:
            st.info("No results yet...")

    with tab3:
        final_output = task_data.get("final_output", "")
        if final_output:
            st.markdown(final_output)
        else:
            st.info("Final output will appear here when all agents complete their work.")

    # Auto-refresh for active tasks
    if status in ("pending", "planning", "in_progress"):
        time.sleep(3)
        st.rerun()


def main():
    """Main Streamlit app."""
    init_session_state()
    sidebar()

    if st.session_state.current_task_id:
        render_task_progress(st.session_state.current_task_id)

        if st.button("← New Task"):
            st.session_state.current_task_id = None
            st.rerun()
    else:
        render_task_input()


if __name__ == "__main__":
    main()
