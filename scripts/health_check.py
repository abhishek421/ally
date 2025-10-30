#!/usr/bin/env python3
"""
Quick Health Check Script for AI Analyst RAG System
Run this script to verify your system setup before testing
"""
import asyncio
import sys
import os
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

def print_header(title):
    """Print a formatted header"""
    print("\n" + "="*60)
    print(f"  {title}")
    print("="*60)

def print_status(check, message, status="✅"):
    """Print a status message"""
    print(f"{status} {check}: {message}")

async def check_environment():
    """Check environment variables"""
    print_header("Environment Variables Check")
    
    required_vars = {
OPENAI_API_KEY=REDACTED
        'DATABASE_URL': 'PostgreSQL Database URL',
        'REDIS_HOST': 'Redis Host'
    }
    
    optional_vars = {
        'ANTHROPIC_API_KEY': 'Anthropic API Key',
        'GOOGLE_API_KEY': 'Google API Key',
        'GLOBAL_LLM_PROVIDER': 'Global LLM Provider',
        'GLOBAL_LLM_MODEL': 'Global LLM Model'
    }
    
    all_good = True
    
    # Check required variables
    for var, desc in required_vars.items():
        value = os.getenv(var)
        if value:
            masked = value[:10] + "..." if len(value) > 10 else value
            print_status(desc, f"Set ({masked})", "✅")
        else:
            print_status(desc, "NOT SET", "❌")
            all_good = False
    
    # Check optional variables
    print("\nOptional Variables:")
    for var, desc in optional_vars.items():
        value = os.getenv(var)
        if value:
            masked = value[:10] + "..." if len(value) > 10 else value
            print_status(desc, f"Set ({masked})", "✅")
        else:
            print_status(desc, "Not set (optional)", "⚠️")
    
    return all_good

async def check_database():
    """Check database connection"""
    print_header("Database Connection Check")
    
    try:
        from database.prisma_client import prisma_client
        
        await prisma_client.connect()
        client = await prisma_client.get_client()
        
        # Check GlobalLLMConfig table
        global_count = await client.globalllmconfig.count()
        print_status("GlobalLLMConfig Table", f"Found {global_count} record(s)", "✅")
        
        # Check AgentLLMConfig table
        agent_count = await client.agentllmconfig.count()
        print_status("AgentLLMConfig Table", f"Found {agent_count} record(s)", "✅")
        
        if global_count == 0:
            print("\n⚠️  Warning: No LLM configuration found in database.")
            print("   Run: python scripts/seed_llm_config.py")
        
        await prisma_client.disconnect()
        return True
        
    except Exception as e:
        print_status("Database Connection", f"Failed: {e}", "❌")
        return False

def check_redis():
    """Check Redis connection"""
    print_header("Redis Connection Check")
    
    try:
        from database.redis_client import redis_client
        
        redis_client.set("health_check", "ok")
        value = redis_client.get("health_check")
        
        if value == "ok":
            print_status("Redis Connection", "Connected successfully", "✅")
            return True
        else:
            print_status("Redis Connection", "Value mismatch", "❌")
            return False
            
    except Exception as e:
        print_status("Redis Connection", f"Failed: {e}", "❌")
        print("   Note: Redis is optional but recommended for caching")
        return False

async def check_llm_provider():
    """Check LLM provider configuration"""
    print_header("LLM Provider Configuration Check")
    
    try:
        from config.config_manager import get_config_manager
        
        config_manager = get_config_manager()
        await config_manager.initialize()
        
        agents = ['query_optimizer', 'data_extractor', 'response_formatter']
        
        for agent_name in agents:
            try:
                config = config_manager.get_agent_config_sync(agent_name)
                status = "✅" if config.api_key else "❌"
                api_status = "Set" if config.api_key else "NOT SET"
                
                print_status(
                    f"{agent_name.replace('_', ' ').title()}",
                    f"{config.provider}/{config.model} (source: {config.source})",
                    status
                )
                print_status(
                    f"  └─ API Key",
                    api_status,
                    "✅" if config.api_key else "❌"
                )
                
            except Exception as e:
                print_status(f"{agent_name}", f"Error: {e}", "❌")
        
        return True
        
    except Exception as e:
        print_status("LLM Configuration", f"Failed: {e}", "❌")
        return False

def check_dependencies():
    """Check if required Python packages are installed"""
    print_header("Dependencies Check")
    
    required_packages = [
        'langgraph',
        'openai',
        'anthropic',
        'google.generativeai',
        'prisma',
        'redis',
        'pydantic',
        'dotenv'
    ]
    
    all_installed = True
    
    for package in required_packages:
        try:
            if package == 'dotenv':
                __import__('dotenv')
            elif package == 'google.generativeai':
                __import__('google.generativeai')
            else:
                __import__(package)
            print_status(package, "Installed", "✅")
        except ImportError:
            print_status(package, "NOT INSTALLED", "❌")
            all_installed = False
    
    return all_installed

def check_project_structure():
    """Check if required files and directories exist"""
    print_header("Project Structure Check")
    
    required_files = [
        'main.py',
        'graph/pipeline.py',
        'agents/query_optimizer.py',
        'agents/data_extractor.py',
        'config/settings.py',
        'tools/company_tool.py',
        'tests/test_query_optimizer.py',
        'prisma/schema.prisma'
    ]
    
    all_exist = True
    
    for file_path in required_files:
        full_path = project_root / file_path
        if full_path.exists():
            print_status(file_path, "Exists", "✅")
        else:
            print_status(file_path, "NOT FOUND", "❌")
            all_exist = False
    
    return all_exist

async def main():
    """Run all health checks"""
    print("\n" + "="*60)
    print("  AI Analyst RAG System - Health Check")
    print("="*60)
    
    results = {}
    
    # Run checks
    results['project_structure'] = check_project_structure()
    results['dependencies'] = check_dependencies()
    results['environment'] = await check_environment()
    results['database'] = await check_database()
    results['redis'] = check_redis()
    results['llm_provider'] = await check_llm_provider()
    
    # Summary
    print_header("Summary")
    
    all_passed = True
    for check, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status}: {check.replace('_', ' ').title()}")
        if not passed:
            all_passed = False
    
    print("\n" + "="*60)
    if all_passed:
        print("✅ All checks passed! System is ready for testing.")
        print("\nNext steps:")
        print("  1. Run: python tests/test_query_optimizer.py")
        print("  2. Run: python tests/test_pipeline_integration.py")
        print("  3. Run: python main.py")
    else:
        print("❌ Some checks failed. Please fix the issues above.")
        print("\nRefer to docs/TESTING_GUIDE.md for detailed setup instructions.")
    print("="*60 + "\n")
    
    return 0 if all_passed else 1

if __name__ == "__main__":
    try:
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n\nHealth check interrupted by user.")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

