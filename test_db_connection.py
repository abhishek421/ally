#!/usr/bin/env python3
"""
Test Database Connection
Run this script to test your PostgreSQL connection
"""

import os
from dotenv import load_dotenv
from database.db_setup import get_db_manager

def test_connection():
    print("Testing Database Connection")
    print("=" * 30)
    
    # Load environment variables
    load_dotenv()
    
    # Get configuration
    host = os.getenv("DB_HOST", "localhost")
    port = os.getenv("DB_PORT", "5432")
    database = os.getenv("DB_NAME", "chatbot_db")
    username = os.getenv("DB_USER", "postgres")
    password = os.getenv("DB_PASSWORD", "")
    
    print(f"Host: {host}")
    print(f"Port: {port}")
    print(f"Database: {database}")
    print(f"Username: {username}")
    print(f"Password: {'*' * len(password) if password else 'NOT SET'}")
    
    if not password or password == "your_password_here":
        print("\n[ERROR] Password not configured!")
        print("Please set DB_PASSWORD in your .env file")
        return False
    
    # Test connection
    print("\nTesting connection...")
    db_manager = get_db_manager()
    
    try:
        if db_manager.connect():
            print("[SUCCESS] Connected to PostgreSQL!")
            
            # Test database creation
            print("Creating database...")
            if db_manager.create_database():
                print("[SUCCESS] Database created/verified!")
            
            # Test table creation
            print("Creating tables...")
            if db_manager.create_tables():
                print("[SUCCESS] Tables created!")
            
            # Test query execution
            print("Testing query execution...")
            result = db_manager.execute_query("SELECT 1 as test")
            if result:
                print("[SUCCESS] Query execution works!")
                print(f"Test result: {result}")
            
            db_manager.disconnect()
            print("\n[SUCCESS] All tests passed! Your database is ready.")
            return True
            
        else:
            print("[ERROR] Failed to connect to database")
            print("Please check:")
            print("1. PostgreSQL service is running")
            print("2. Password is correct")
            print("3. Port 5432 is not blocked")
            return False
            
    except Exception as e:
        print(f"[ERROR] Connection failed: {e}")
        return False

if __name__ == "__main__":
    test_connection()
