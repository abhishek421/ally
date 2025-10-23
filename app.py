import streamlit as st
import os
from dotenv import load_dotenv
from agents.chatbot import create_chatbot
from database.db_setup import get_db_manager
from database.sample_data import get_sample_data_generator
from config.db_config import DatabaseConfig
import json

# Load environment variables
load_dotenv()

# Page configuration
st.set_page_config(
    page_title="Multi-Agent Database Chatbot",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        color: #1f77b4;
        text-align: center;
        margin-bottom: 2rem;
    }
    .chat-message {
        padding: 1rem;
        border-radius: 0.5rem;
        margin-bottom: 1rem;
    }
    .user-message {
        background-color: #e3f2fd;
        border-left: 4px solid #2196f3;
    }
    .assistant-message {
        background-color: #f3e5f5;
        border-left: 4px solid #9c27b0;
    }
    .error-message {
        background-color: #ffebee;
        border-left: 4px solid #f44336;
    }
    .success-message {
        background-color: #e8f5e8;
        border-left: 4px solid #4caf50;
    }
    .sidebar-section {
        margin-bottom: 2rem;
    }
    .query-suggestion {
        background-color: #f5f5f5;
        padding: 0.5rem;
        border-radius: 0.25rem;
        margin: 0.25rem 0;
        cursor: pointer;
    }
    .query-suggestion:hover {
        background-color: #e0e0e0;
    }
</style>
""", unsafe_allow_html=True)

# Initialize session state
if "messages" not in st.session_state:
    st.session_state.messages = []
if "chatbot" not in st.session_state:
    st.session_state.chatbot = None
if "db_connected" not in st.session_state:
    st.session_state.db_connected = False
if "sample_data_loaded" not in st.session_state:
    st.session_state.sample_data_loaded = False


def initialize_chatbot():
    """Initialize the chatbot"""
    try:
        if st.session_state.chatbot is None:
            st.session_state.chatbot = create_chatbot()
        return True
    except Exception as e:
        st.error(f"Failed to initialize chatbot: {str(e)}")
        return False


def connect_to_database():
    """Connect to the database"""
    try:
        db_manager = get_db_manager()
        if db_manager.connect():
            st.session_state.db_connected = True
            return True
        else:
            st.session_state.db_connected = False
            return False
    except Exception as e:
        st.error(f"Failed to connect to database: {str(e)}")
        st.session_state.db_connected = False
        return False


def load_sample_data():
    """Load sample data into the database"""
    try:
        sample_generator = get_sample_data_generator()
        if sample_generator.seed_database():
            st.session_state.sample_data_loaded = True
            return True
        else:
            return False
    except Exception as e:
        st.error(f"Failed to load sample data: {str(e)}")
        return False


def display_chat_message(role: str, content: str):
    """Display a chat message with appropriate styling"""
    if role == "user":
        st.markdown(f"""
        <div class="chat-message user-message">
            <strong>You:</strong><br>
            {content}
        </div>
        """, unsafe_allow_html=True)
    elif role == "assistant":
        st.markdown(f"""
        <div class="chat-message assistant-message">
            <strong>Assistant:</strong><br>
            {content}
        </div>
        """, unsafe_allow_html=True)
    elif role == "error":
        st.markdown(f"""
        <div class="chat-message error-message">
            <strong>Error:</strong><br>
            {content}
        </div>
        """, unsafe_allow_html=True)


def main():
    # Main header
    st.markdown('<h1 class="main-header">🤖 Multi-Agent Database Chatbot</h1>', unsafe_allow_html=True)
    
    # Sidebar for configuration
    with st.sidebar:
        st.markdown("## Configuration")
        
        # Database Connection Section
        st.markdown("### Database Connection")
        
        if st.button("Connect to Database", key="connect_db"):
            with st.spinner("Connecting to database..."):
                if connect_to_database():
                    st.success("✅ Database connected successfully!")
                else:
                    st.error("❌ Failed to connect to database")
        
        if st.session_state.db_connected:
            st.success("Database Status: Connected")
            
            # Sample Data Section
            st.markdown("### Sample Data")
            
            if st.button("Load Sample Data", key="load_sample"):
                with st.spinner("Loading sample data..."):
                    if load_sample_data():
                        st.success("✅ Sample data loaded successfully!")
                    else:
                        st.error("❌ Failed to load sample data")
            
            if st.button("Clear Sample Data", key="clear_sample"):
                with st.spinner("Clearing sample data..."):
                    sample_generator = get_sample_data_generator()
                    if sample_generator.clear_sample_data():
                        st.success("✅ Sample data cleared!")
                        st.session_state.sample_data_loaded = False
                    else:
                        st.error("❌ Failed to clear sample data")
            
            if st.session_state.sample_data_loaded:
                st.success("Sample Data: Loaded")
            else:
                st.warning("Sample Data: Not loaded")
        
        else:
            st.error("Database Status: Not connected")
        
        # Schema Information Section
        if st.session_state.db_connected:
            st.markdown("### Database Schema")
            
            if st.button("View Schema", key="view_schema"):
                try:
                    config = DatabaseConfig()
                    schema_info = config.get_all_schema_info()
                    st.json(schema_info)
                except Exception as e:
                    st.error(f"Failed to load schema: {str(e)}")
            
            # Database Statistics
            st.markdown("### Database Statistics")
            try:
                db_manager = get_db_manager()
                for table_name in ["companies", "people"]:
                    if db_manager.check_table_exists(table_name):
                        row_count = db_manager.get_table_row_count(table_name)
                        st.metric(f"{table_name.title()} Table", f"{row_count} rows")
            except Exception as e:
                st.error(f"Failed to get statistics: {str(e)}")
        
        # Sample Queries Section
        st.markdown("### Sample Queries")
        st.markdown("Click on any query below to use it:")
        
        sample_queries = [
            "What are the top 5 newly added companies?",
            "How many people work in the Engineering department?",
            "Which companies are in the Technology industry?",
            "What is the average salary by role?",
            "Show me all people hired in the last year",
            "Which company has the most employees?",
            "What are the different departments in our database?",
            "Find all people with 'Manager' in their role",
            "Which companies were founded after 2020?",
            "What is the total number of employees across all companies?"
        ]
        
        for query in sample_queries:
            if st.button(query, key=f"sample_{hash(query)}"):
                # Add the query directly to messages instead of setting user_input
                st.session_state.messages.append({
                    "role": "user",
                    "content": query
                })
                
                # Process the query immediately
                if initialize_chatbot():
                    with st.spinner("Processing your query..."):
                        try:
                            response = st.session_state.chatbot.chat(query)
                            st.session_state.messages.append({
                                "role": "assistant",
                                "content": response
                            })
                        except Exception as e:
                            error_msg = f"Error processing query: {str(e)}"
                            st.session_state.messages.append({
                                "role": "error",
                                "content": error_msg
                            })
                
                st.rerun()
    
    # Main chat interface
    col1, col2 = st.columns([3, 1])
    
    with col1:
        # Chat messages
        st.markdown("## Chat")
        
        # Display chat history
        for message in st.session_state.messages:
            display_chat_message(message["role"], message["content"])
        
        # Chat input
        user_input = st.text_input(
            "Ask a question about the database:",
            key="user_input",
            placeholder="e.g., What are the top 5 newly added companies?",
            disabled=not st.session_state.db_connected
        )
        
        if st.button("Send", disabled=not st.session_state.db_connected):
            if user_input:
                # Add user message to history
                st.session_state.messages.append({
                    "role": "user",
                    "content": user_input
                })
                
                # Process the query
                if initialize_chatbot():
                    with st.spinner("Processing your query..."):
                        try:
                            response = st.session_state.chatbot.chat(user_input)
                            
                            # Add assistant response to history
                            st.session_state.messages.append({
                                "role": "assistant",
                                "content": response
                            })
                            
                        except Exception as e:
                            error_msg = f"Error processing query: {str(e)}"
                            st.session_state.messages.append({
                                "role": "error",
                                "content": error_msg
                            })
                
                # Rerun to refresh the interface
                st.rerun()
    
    with col2:
        # Quick actions
        st.markdown("## Quick Actions")
        
        if st.button("Clear Chat", key="clear_chat"):
            st.session_state.messages = []
            st.rerun()
        
        if st.button("Reset Database", key="reset_db"):
            if st.session_state.db_connected:
                with st.spinner("Resetting database..."):
                    db_manager = get_db_manager()
                    if db_manager.reset_database():
                        st.success("✅ Database reset successfully!")
                        st.session_state.sample_data_loaded = False
                    else:
                        st.error("❌ Failed to reset database")
            else:
                st.error("Please connect to database first")
        
        # Environment Variables Check
        st.markdown("## Environment Check")
        
        # Check API keys based on provider
        provider = os.getenv("LLM_PROVIDER", "openai").lower()
        
        if provider in ['openai']:
OPENAI_API_KEY=REDACTED
            if api_key:
                st.success("✅ OpenAI API Key: Set")
            else:
                st.error("❌ OpenAI API Key: Not set")
        elif provider in ['gemini', 'google']:
            api_key = os.getenv("GOOGLE_API_KEY")
            if api_key:
                st.success("✅ Google API Key: Set")
            else:
                st.error("❌ Google API Key: Not set")
        elif provider in ['claude', 'anthropic']:
            api_key = os.getenv("ANTHROPIC_API_KEY")
            if api_key:
                st.success("✅ Anthropic API Key: Set")
            else:
                st.error("❌ Anthropic API Key: Not set")
        
        llm_provider = os.getenv("LLM_PROVIDER", "openai")
        llm_model = os.getenv("LLM_MODEL_NAME", "gpt-3.5-turbo")
        st.info(f"🤖 LLM Provider: {llm_provider.title()}")
        st.info(f"🧠 LLM Model: {llm_model}")
        
        db_host = os.getenv("DB_HOST")
        if db_host:
            st.info(f"Database Host: {db_host}")
        else:
            st.warning("Database Host: Not set")
    
    # Footer
    st.markdown("---")
    st.markdown("""
    <div style="text-align: center; color: #666; font-size: 0.8rem;">
        Multi-Agent Database Chatbot powered by LangGraph, Streamlit, and OpenAI
    </div>
    """, unsafe_allow_html=True)


if __name__ == "__main__":
    main()
