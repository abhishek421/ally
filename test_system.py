#!/usr/bin/env python3
"""
Test script for Multi-Agent Database Chatbot
This script tests the basic functionality of the system.
"""

import os
import sys
from dotenv import load_dotenv


def test_imports():
    """Test if all required modules can be imported"""
    print("Testing imports...")
    
    try:
        from config.db_config import DatabaseConfig
        print("DatabaseConfig imported successfully")
        
        from database.db_setup import get_db_manager
        print("DatabaseManager imported successfully")
        
        from database.sample_data import get_sample_data_generator
        print("SampleDataGenerator imported successfully")
        
        from tools.database_tools import get_database_tools
        print("[OK] Database tools imported successfully")
        
        from tools.schema_tools import get_schema_tools
        print("[OK] Schema tools imported successfully")
        
        from agents.chatbot import create_chatbot
        print("[OK] MultiAgentChatbot imported successfully")
        
        return True
        
    except ImportError as e:
        print(f"[ERROR] Import error: {e}")
        return False


def test_configuration():
    """Test configuration loading"""
    print("\n[TEST] Testing configuration...")
    
    try:
        from config.db_config import DatabaseConfig
        
        config = DatabaseConfig()
        schema_info = config.get_all_schema_info()
        
        if "tables" in schema_info:
            print(f"[OK] Schema loaded successfully with {len(schema_info['tables'])} tables")
            for table_name in schema_info["tables"]:
                print(f"   - {table_name}")
        else:
            print("[ERROR] Schema loading failed")
            return False
            
        return True
        
    except Exception as e:
        print(f"[ERROR] Configuration test failed: {e}")
        return False


def test_database_connection():
    """Test database connection"""
    print("\n[TEST] Testing database connection...")
    
    try:
        from database.db_setup import get_db_manager
        
        db_manager = get_db_manager()
        
        if db_manager.connect():
            print("[OK] Database connection successful")
            
            # Test table creation
            if db_manager.create_tables():
                print("[OK] Tables created successfully")
            else:
                print("[WARNING]  Table creation failed (may already exist)")
            
            # Test query execution
            result = db_manager.execute_query("SELECT 1 as test")
            if result:
                print("[OK] Query execution successful")
            else:
                print("[ERROR] Query execution failed")
            
            db_manager.disconnect()
            return True
            
        else:
            print("[ERROR] Database connection failed")
            print("   Please check your database configuration in .env")
            return False
            
    except Exception as e:
        print(f"[ERROR] Database test failed: {e}")
        return False


def test_sample_data():
    """Test sample data generation"""
    print("\n[TEST] Testing sample data generation...")
    
    try:
        from database.sample_data import get_sample_data_generator
        
        sample_generator = get_sample_data_generator()
        
        # Test company data generation
        companies = sample_generator.generate_companies_data(5)
        if len(companies) == 5:
            print("[OK] Company data generation successful")
        else:
            print("[ERROR] Company data generation failed")
            return False
        
        # Test people data generation
        people = sample_generator.generate_people_data(companies, 10)
        if len(people) == 10:
            print("[OK] People data generation successful")
        else:
            print("[ERROR] People data generation failed")
            return False
        
        # Test sample queries
        queries = sample_generator.get_sample_queries()
        if len(queries) > 0:
            print(f"[OK] Sample queries generated ({len(queries)} queries)")
        else:
            print("[ERROR] Sample queries generation failed")
            return False
        
        return True
        
    except Exception as e:
        print(f"[ERROR] Sample data test failed: {e}")
        return False


def test_tools():
    """Test tool functionality"""
    print("\n[TEST] Testing tools...")
    
    try:
        from tools.database_tools import get_database_tools
        from tools.schema_tools import get_schema_tools
        
        # Test database tools
        db_tools = get_database_tools()
        if len(db_tools) > 0:
            print(f"[OK] Database tools loaded ({len(db_tools)} tools)")
        else:
            print("[ERROR] No database tools found")
            return False
        
        # Test schema tools
        schema_tools = get_schema_tools()
        if len(schema_tools) > 0:
            print(f"[OK] Schema tools loaded ({len(schema_tools)} tools)")
        else:
            print("[ERROR] No schema tools found")
            return False
        
        return True
        
    except Exception as e:
        print(f"[ERROR] Tools test failed: {e}")
        return False


def test_chatbot():
    """Test chatbot initialization"""
    print("\n[TEST] Testing chatbot initialization...")
    
    try:
        # Check if OpenAI API key is set
        load_dotenv()
OPENAI_API_KEY=REDACTED
        
openai_api_key="REDACTED"
            print("[WARNING]  OpenAI API key not configured - skipping chatbot test")
            return True
        
        from agents.chatbot import create_chatbot
        
        chatbot = create_chatbot()
        print("[OK] Chatbot initialized successfully")
        
        return True
        
    except Exception as e:
        print(f"[ERROR] Chatbot test failed: {e}")
        return False


def main():
    """Main test function"""
    print("Multi-Agent Database Chatbot Test Suite")
    print("=" * 50)
    
    tests = [
        ("Imports", test_imports),
        ("Configuration", test_configuration),
        ("Database Connection", test_database_connection),
        ("Sample Data", test_sample_data),
        ("Tools", test_tools),
        ("Chatbot", test_chatbot)
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        try:
            if test_func():
                passed += 1
        except Exception as e:
            print(f"[ERROR] {test_name} test crashed: {e}")
    
    print(f"\n[STATS] Test Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("[SUCCESS] All tests passed! The system is ready to use.")
        print("\nNext steps:")
        print("1. Run: streamlit run app.py")
        print("2. Open http://localhost:8501")
        print("3. Connect to database and load sample data")
    else:
        print("[WARNING]  Some tests failed. Please check the errors above.")
        print("Make sure you have:")
        print("- PostgreSQL running and configured")
        print("- OpenAI API key set in .env")
        print("- All dependencies installed")


if __name__ == "__main__":
    main()
