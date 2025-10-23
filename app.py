import streamlit as st
import os
from dotenv import load_dotenv
from agents.chatbot import create_chatbot
from database.db_setup import get_db_manager
from database.sample_data import get_sample_data_generator
from database.csv_processor import get_csv_processor
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
    """Load sample data into the database - Legacy method"""
    st.warning("Sample data generation is no longer supported. Please use CSV upload instead.")
    return False


def upload_csv_data(uploaded_file, table_type):
    """Upload CSV data to database"""
    try:
        csv_processor = get_csv_processor()
        
        # Read the uploaded file
        csv_content = uploaded_file.read().decode('utf-8')
        
        if table_type == "companies":
            success = csv_processor.process_companies_csv(csv_content)
        elif table_type == "people":
            success = csv_processor.process_people_csv(csv_content)
        else:
            st.error("Invalid table type")
            return False
        
        if success:
            st.success(f"✅ Successfully uploaded {table_type} data!")
            return True
        else:
            st.error(f"❌ Failed to upload {table_type} data")
            return False
            
    except Exception as e:
        st.error(f"Failed to upload CSV: {str(e)}")
        return False


def reset_database_schema():
    """Reset database schema to match the new CSV structure"""
    try:
        db_manager = get_db_manager()
        
        # Connect to database
        if not db_manager.connect():
            st.error("Failed to connect to database")
            return False
        
        # Drop existing tables
        if not db_manager.drop_tables():
            st.error("Failed to drop existing tables")
            return False
        
        # Create new tables with updated schema
        if not db_manager.create_tables():
            st.error("Failed to create new tables")
            return False
        
        return True
        
    except Exception as e:
        st.error(f"Failed to reset database schema: {str(e)}")
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
            
            # CSV Upload Section
            st.markdown("### CSV Data Upload")
            
            # Check if database needs schema reset
            try:
                db_manager = get_db_manager()
                if db_manager.check_table_exists("companies"):
                    # Check if new schema exists by trying to query new columns
                    result = db_manager.execute_query("SELECT customer_id FROM companies LIMIT 1")
                    if result is None:
                        st.warning("⚠️ **Database schema needs to be updated!** Click 'Reset Database Schema' below before uploading CSV files.")
            except:
                # If we can't query customer_id, it means old schema is still there
                st.warning("⚠️ **Database schema needs to be updated!** Click 'Reset Database Schema' below before uploading CSV files.")
            
            # Companies CSV Upload
            st.markdown("**Upload Companies CSV:**")
            companies_file = st.file_uploader(
                "Choose companies CSV file",
                type=['csv'],
                key="companies_csv",
                help="Upload CSV with columns: Customer Id, First Name, Last Name, Company, City, Country, Phone 1, Phone 2, Email, Subscription Date, Website"
            )
            
            if companies_file is not None:
                if st.button("Upload Companies Data", key="upload_companies"):
                    with st.spinner("Uploading companies data..."):
                        if upload_csv_data(companies_file, "companies"):
                            st.session_state.sample_data_loaded = True
            
            # People CSV Upload
            st.markdown("**Upload People CSV:**")
            people_file = st.file_uploader(
                "Choose people CSV file",
                type=['csv'],
                key="people_csv",
                help="Upload CSV with columns: User Id, First Name, Last Name, Sex, Email, Phone, Date of birth, Job Title"
            )
            
            if people_file is not None:
                if st.button("Upload People Data", key="upload_people"):
                    with st.spinner("Uploading people data..."):
                        if upload_csv_data(people_file, "people"):
                            st.session_state.sample_data_loaded = True
            
            # Database Management Buttons
            col1, col2 = st.columns(2)
            
            with col1:
                if st.button("Clear All Data", key="clear_data"):
                    with st.spinner("Clearing all data..."):
                        csv_processor = get_csv_processor()
                        if csv_processor.clear_all_data():
                            st.success("✅ All data cleared!")
                            st.session_state.sample_data_loaded = False
                        else:
                            st.error("❌ Failed to clear data")
            
            with col2:
                if st.button("Reset Database Schema", key="reset_schema"):
                    with st.spinner("Resetting database schema..."):
                        if reset_database_schema():
                            st.success("✅ Database schema reset successfully!")
                            st.session_state.sample_data_loaded = False
                        else:
                            st.error("❌ Failed to reset database schema")
            
            # Data Status
            try:
                csv_processor = get_csv_processor()
                stats = csv_processor.get_table_stats()
                st.info(f"**Data Status:** Companies: {stats['companies']}, People: {stats['people']}")
            except Exception as e:
                st.warning("Could not get data statistics")
        
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
                csv_processor = get_csv_processor()
                stats = csv_processor.get_table_stats()
                
                st.metric("Companies Table", f"{stats['companies']} rows")
                st.metric("People Table", f"{stats['people']} rows")
            except Exception as e:
                st.error(f"Failed to get statistics: {str(e)}")
        
        # Sample Queries Section
        st.markdown("### Sample Queries")
        st.markdown("Click on any query below to use it:")
        
        sample_queries = [
            "What are the top 5 companies by subscription date?",
            "How many people are there in each country?",
            "Which companies are in Chile?",
            "What are the different job titles?",
            "Show me all people born after 1990",
            "Which company has the most recent subscription?",
            "What are the different cities in our database?",
            "Find all people with 'Manager' in their job title",
            "Which companies were subscribed after 2020?",
            "What is the total number of people in our database?"
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
