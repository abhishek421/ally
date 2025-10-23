#!/usr/bin/env python3
"""
Setup script for Multi-Agent Database Chatbot
This script helps users set up the environment and initialize the database.
"""

import os
import sys
import subprocess
from pathlib import Path


def check_python_version():
    """Check if Python version is compatible"""
    if sys.version_info < (3, 8):
        print("❌ Python 3.8 or higher is required")
        sys.exit(1)
    print(f"✅ Python {sys.version.split()[0]} detected")


def install_dependencies():
    """Install required dependencies"""
    print("\n📦 Installing dependencies...")
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])
        print("✅ Dependencies installed successfully")
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to install dependencies: {e}")
        sys.exit(1)


def setup_environment():
    """Set up environment variables"""
    print("\n🔧 Setting up environment...")
    
    env_file = Path(".env")
    env_example = Path("env.example")
    
    if not env_file.exists():
        if env_example.exists():
            env_file.write_text(env_example.read_text())
            print("✅ Created .env file from template")
            print("⚠️  Please edit .env file with your actual configuration")
        else:
            print("❌ env.example file not found")
            sys.exit(1)
    else:
        print("✅ .env file already exists")


def check_postgresql():
    """Check if PostgreSQL is available"""
    print("\n🗄️  Checking PostgreSQL...")
    try:
        result = subprocess.run(["psql", "--version"], capture_output=True, text=True)
        if result.returncode == 0:
            print(f"✅ PostgreSQL detected: {result.stdout.strip()}")
        else:
            print("❌ PostgreSQL not found. Please install PostgreSQL")
            print("   Visit: https://www.postgresql.org/download/")
    except FileNotFoundError:
        print("❌ PostgreSQL not found. Please install PostgreSQL")
        print("   Visit: https://www.postgresql.org/download/")


def check_openai_key():
    """Check if OpenAI API key is configured"""
    print("\n🔑 Checking OpenAI API key...")
    
    from dotenv import load_dotenv
    load_dotenv()
    
OPENAI_API_KEY=REDACTED
openai_api_key="REDACTED"
        print("✅ OpenAI API key is configured")
    else:
        print("⚠️  OpenAI API key not configured")
OPENAI_API_KEY=REDACTED
        print("   Get your API key from: https://platform.openai.com/api-keys")


def initialize_database():
    """Initialize the database"""
    print("\n🗄️  Initializing database...")
    
    try:
        from database.db_setup import get_db_manager
        
        db_manager = get_db_manager()
        
        # Create database
        if db_manager.create_database():
            print("✅ Database created successfully")
        else:
            print("⚠️  Database creation failed or database already exists")
        
        # Connect and create tables
        if db_manager.connect():
            print("✅ Connected to database")
            if db_manager.create_tables():
                print("✅ Tables created successfully")
            else:
                print("❌ Failed to create tables")
        else:
            print("❌ Failed to connect to database")
            print("   Please check your database configuration in .env")
            
    except Exception as e:
        print(f"❌ Database initialization failed: {e}")
        print("   Please check your database configuration")


def main():
    """Main setup function"""
    print("🚀 Multi-Agent Database Chatbot Setup")
    print("=" * 50)
    
    # Check Python version
    check_python_version()
    
    # Install dependencies
    install_dependencies()
    
    # Setup environment
    setup_environment()
    
    # Check PostgreSQL
    check_postgresql()
    
    # Check OpenAI key
    check_openai_key()
    
    # Initialize database
    initialize_database()
    
    print("\n🎉 Setup completed!")
    print("\nNext steps:")
    print("1. Edit .env file with your actual configuration")
    print("2. Start the application: streamlit run app.py")
    print("3. Open http://localhost:8501 in your browser")
    print("4. Connect to database and load sample data")
    print("\nFor more information, see README.md")


if __name__ == "__main__":
    main()
