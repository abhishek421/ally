"""Streamlit UI for interacting with the AnalystAI LangGraph pipeline."""

from __future__ import annotations

import json
import uuid
from typing import Any, Dict

import streamlit as st

from src.config import get_settings
from src.graph.runner import invoke_graph
from src.graph.state import GraphState

settings = get_settings()

st.set_page_config(page_title="AnalystAI Chat", page_icon="🤖", layout="wide")
st.title("AnalystAI Chat")
st.caption("Queries flow through Query Builder ➜ Query Processing nodes.")


def _init_session_state() -> None:
    """Ensure Streamlit session state has required defaults."""
    if "conversation_id" not in st.session_state:
        st.session_state.conversation_id = settings.conversation_id or str(uuid.uuid4())
    if "workspace_id" not in st.session_state:
        st.session_state.workspace_id = settings.workspace_id or ""
    if "messages" not in st.session_state:
        st.session_state.messages: list[Dict[str, str]] = []
    if "last_result" not in st.session_state:
        st.session_state.last_result: Dict[str, Any] | None = None


def _parse_processing_result(result: Dict[str, Any]) -> Dict[str, Any]:
    """Extract answer, reasoning, and tool call details from node output."""
    payload = result.get("query_processing_result")
    if not payload:
        return {"answer": "No answer generated.", "reasoning_steps": [], "tool_calls": []}

    try:
        data = json.loads(payload)
    except json.JSONDecodeError:
        return {"answer": payload, "reasoning_steps": [], "tool_calls": []}

    return {
        "answer": data.get("answer", "No answer generated."),
        "reasoning_steps": data.get("reasoning_steps", []),
        "tool_calls": data.get("tool_calls", []),
        "metadata": data.get("metadata", {}),
    }


def _render_run_details(result: Dict[str, Any], parsed: Dict[str, Any]) -> None:
    """Display additional debugging details for the last graph run."""
    execution_path = result.get("execution_path", [])
    query_builder_output = result.get("query_builder_result")

    with st.expander("Run details", expanded=False):
        st.markdown("**Execution Path**")
        if execution_path:
            execution_text = " → ".join(str(step) for step in execution_path)
        else:
            execution_text = "No steps recorded."
        st.write(execution_text)

        if query_builder_output:
            st.markdown("**Enriched Query**")
            st.code(query_builder_output)

        reasoning_steps = parsed.get("reasoning_steps") or []
        if reasoning_steps:
            st.markdown("**Reasoning Steps**")
            for idx, step in enumerate(reasoning_steps, start=1):
                st.markdown(f"{idx}. {step}")

        tool_calls = parsed.get("tool_calls") or []
        if tool_calls:
            st.markdown("**Tool Calls**")
            for call in tool_calls:
                st.json(call)

        metadata = parsed.get("metadata") or {}
        if metadata:
            st.markdown("**Metadata**")
            st.json(metadata)


def _handle_user_query(prompt: str) -> None:
    """Process a single user query through the LangGraph application."""
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    if not st.session_state.workspace_id:
        warning = "Please provide a workspace ID in the sidebar before asking questions."
        st.session_state.messages.append({"role": "assistant", "content": warning})
        with st.chat_message("assistant"):
            st.warning(warning)
        return

    initial_state: GraphState = {
        "user_query": prompt,
        "conversation_id": st.session_state.conversation_id,
        "workspace_id": st.session_state.workspace_id,
        "execution_path": [],
        "metadata": {},
    }

    with st.chat_message("assistant"):
        placeholder = st.empty()
        try:
            with st.spinner("Running AnalystAI graph..."):
                result = invoke_graph(initial_state)
            parsed = _parse_processing_result(result)
            answer = parsed.get("answer", "No answer generated.")
            placeholder.markdown(answer)
            _render_run_details(result, parsed)
            st.session_state.messages.append({"role": "assistant", "content": answer})
            st.session_state.last_result = {"result": result, "parsed": parsed}
        except Exception as exc:  # noqa: BLE001
            error_message = f"Graph execution failed: {exc}"
            placeholder.error(error_message)
            st.session_state.messages.append({"role": "assistant", "content": error_message})
            st.session_state.last_result = None


def main() -> None:
    """Entry point for the Streamlit application."""
    _init_session_state()

    with st.sidebar:
        st.subheader("Session Controls")
        workspace_id = st.text_input("Workspace ID", value=st.session_state.workspace_id)
        if workspace_id != st.session_state.workspace_id:
            st.session_state.workspace_id = workspace_id

        if st.button("New Conversation", use_container_width=True):
            st.session_state.conversation_id = str(uuid.uuid4())
            st.session_state.messages = []
            st.session_state.last_result = None
            st.success("Conversation reset.")

    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    prompt = st.chat_input("Ask about your CRM data")
    if prompt:
        _handle_user_query(prompt)


if __name__ == "__main__":
    main()


