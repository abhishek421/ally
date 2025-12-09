import streamlit as st
import requests
import uuid
import json

# Page configuration
st.set_page_config(page_title="Analyst AI", page_icon="🤖")

# Constants
API_URL = "http://localhost:8000/api/v1/chat"

# Hardcoded IDs from logs for demonstration
USER_ID = "5a587336-4fca-4759-8261-501ca8814647"
WORKSPACE_ID = "efa82c4d-3e6d-4c72-a512-cdcdc0ee1099"

st.title("🤖 Analyst AI Chat")
st.caption("Ask questions about your CRM data")

# Initialize session state
if "messages" not in st.session_state:
    st.session_state.messages = []

# We start with no conversation_id (new chat assumption)
# However, we store it once received to maintain context for the session
if "conversation_id" not in st.session_state:
    st.session_state.conversation_id = None

# Sidebar for debug info
with st.sidebar:
    st.header("Debug Info")
    st.text_input("User ID", value=USER_ID, disabled=True)
    st.text_input("Workspace ID", value=WORKSPACE_ID, disabled=True)
    st.text_input("Conversation ID", value=str(st.session_state.conversation_id), disabled=True)
    
    if st.button("Start New Chat"):
        st.session_state.messages = []
        st.session_state.conversation_id = None
        st.rerun()

# Display chat messages from history
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        # Display tool calls if present in metadata (optional enhancement)
        if "tool_calls" in message and message["tool_calls"]:
            with st.expander("View Tool Calls"):
                st.json(message["tool_calls"])

# Accept user input
if prompt := st.chat_input("What would you like to know?"):
    # Add user message to chat history
    st.session_state.messages.append({"role": "user", "content": prompt})
    
    # Display user message immediately
    with st.chat_message("user"):
        st.markdown(prompt)

    # Display assistant response placeholder
    with st.chat_message("assistant"):
        # UI elements for streaming
        status_container = st.status("Thinking...", expanded=True)
        message_placeholder = st.empty()
        
        full_answer = ""
        tool_calls = []
        
        try:
            # Prepare payload
            payload = {
                "query": prompt,
                "user_id": USER_ID,
                "workspace_id": WORKSPACE_ID,
                "conversation_id": st.session_state.conversation_id
            }
            
            # Stream request
            with requests.post(f"{API_URL}/stream", json=payload, stream=True) as response:
                if response.status_code != 200:
                    st.error(f"Error: {response.status_code} - {response.text}")
                    status_container.update(label="Error", state="error")
                else:
                    for line in response.iter_lines():
                        if line:
                            line_text = line.decode('utf-8')
                            if line_text.startswith("data: "):
                                data_str = line_text[6:]
                                try:
                                    chunk = json.loads(data_str)
                                    chunk_type = chunk.get("type")
                                    content = chunk.get("content", "")
                                    
                                    if chunk_type == "reasoning":
                                        status_container.write(f"💭 {content}")
                                    elif chunk_type == "tool_call":
                                        status_container.write(f"🛠️ {content}")
                                        if chunk.get("data"):
                                            tool_calls.append(chunk["data"])
                                    elif chunk_type == "token":
                                        full_answer += content
                                        message_placeholder.markdown(full_answer + "▌")
                                    elif chunk_type == "done":
                                        st.session_state.conversation_id = chunk.get("data", {}).get("conversation_id")
                                    elif chunk_type == "error":
                                        st.error(content)
                                        status_container.update(label="Error occurred", state="error")
                                        
                                except json.JSONDecodeError:
                                    pass
            
            # Finalize
            status_container.update(label="Finished thinking", state="complete", expanded=False)
            message_placeholder.markdown(full_answer)
            
            # Add assistant message to history
            st.session_state.messages.append({
                "role": "assistant", 
                "content": full_answer,
                "tool_calls": tool_calls
            })
            
        except requests.exceptions.ConnectionError:
            error_msg = "❌ **Error:** Could not connect to API server. Is it running on localhost:8000?"
            message_placeholder.markdown(error_msg)
            status_container.update(label="Connection Error", state="error")
            st.session_state.messages.append({"role": "assistant", "content": error_msg})
            
        except Exception as e:
            error_msg = f"❌ **Error:** {str(e)}"
            message_placeholder.markdown(error_msg)
            status_container.update(label="Error", state="error")
            st.session_state.messages.append({"role": "assistant", "content": error_msg})
