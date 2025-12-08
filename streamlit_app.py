import streamlit as st
import requests
import uuid
import json

# Page configuration
st.set_page_config(page_title="Analyst AI", page_icon="🤖")

# Constants
API_URL = "http://localhost:8000/api/v1/chat"

# Hardcoded IDs from logs for demonstration
USER_ID = "6edf9760-c26e-4a4c-b641-1a23381f9268"
WORKSPACE_ID = "550e8400-e29b-41d4-a716-446655440000"

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
        message_placeholder = st.empty()
        message_placeholder.markdown("Thinking...")
        
        try:
            # Prepare payload
            payload = {
                "query": prompt,
                "user_id": USER_ID,
                "workspace_id": WORKSPACE_ID,
                "conversation_id": st.session_state.conversation_id
            }
            
            # Make API call
            with st.spinner("Processing request..."):
                response = requests.post(API_URL, json=payload)
                response.raise_for_status()
                data = response.json()
            
            # Extract data
            answer = data.get("answer", "No answer provided.")
            conversation_id = data.get("conversation_id")
            tool_calls = data.get("tool_calls", [])
            
            # Update conversation ID in session state
            st.session_state.conversation_id = conversation_id
            
            # Display answer
            message_placeholder.markdown(answer)
            
            # Display tool calls if any
            if tool_calls:
                with st.expander("View Tool Calls"):
                    st.json(tool_calls)
            
            # Add assistant message to history
            st.session_state.messages.append({
                "role": "assistant", 
                "content": answer,
                "tool_calls": tool_calls
            })
            
        except requests.exceptions.ConnectionError:
            error_msg = "❌ **Error:** Could not connect to API server. Is it running on localhost:8000?"
            message_placeholder.markdown(error_msg)
            st.session_state.messages.append({"role": "assistant", "content": error_msg})
            
        except Exception as e:
            error_msg = f"❌ **Error:** {str(e)}"
            message_placeholder.markdown(error_msg)
            st.session_state.messages.append({"role": "assistant", "content": error_msg})

