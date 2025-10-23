#!/usr/bin/env python3
"""
Test Runner for Multi-Agent Database Chatbot
Runs all test suites and provides comprehensive test results
"""

import os
import sys
import subprocess
import time
from pathlib import Path

def run_test(test_file: str, test_name: str) -> tuple[bool, str]:
    """Run a single test file and return results"""
    print(f"\n{'='*60}")
    print(f"Running {test_name}")
    print(f"{'='*60}")
    
    try:
        # Run the test
        result = subprocess.run(
            [sys.executable, test_file],
            capture_output=True,
            text=True,
            timeout=60  # 60 second timeout
        )
        
        # Print output
        if result.stdout:
            print(result.stdout)
        if result.stderr:
            print(f"STDERR: {result.stderr}")
        
        success = result.returncode == 0
        return success, result.stdout
        
    except subprocess.TimeoutExpired:
        print(f"❌ Test timed out after 60 seconds")
        return False, "Timeout"
    except Exception as e:
        print(f"❌ Error running test: {e}")
        return False, str(e)

def check_environment():
    """Check if environment is properly set up"""
    print("Environment Check")
    print("=" * 30)
    
    # Check if .env file exists
    env_file = Path(".env")
    if env_file.exists():
        print("✅ .env file found")
    else:
        print("⚠️  .env file not found - using env.example")
        if Path("env.example").exists():
            print("✅ env.example file found")
        else:
            print("❌ No environment configuration found")
            return False
    
    # Check Python version
    python_version = sys.version_info
    print(f"✅ Python version: {python_version.major}.{python_version.minor}.{python_version.micro}")
    
    if python_version < (3, 8):
        print("❌ Python 3.8+ required")
        return False
    
    return True

def main():
    """Run all tests"""
    print("Multi-Agent Database Chatbot - Test Suite")
    print("=" * 60)
    print(f"Test started at: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Check environment
    if not check_environment():
        print("\n❌ Environment check failed. Please fix issues before running tests.")
        return False
    
    # Define test files
    tests_dir = Path("tests")
    test_files = [
        ("test_db_connection.py", "Database Connection Tests"),
        ("test_model_config.py", "LLM Model Configuration Tests"),
        ("test_multi_provider.py", "Multi-Provider LLM Support Tests")
    ]
    
    # Run tests
    results = []
    total_tests = len(test_files)
    
    for test_file, test_name in test_files:
        test_path = tests_dir / test_file
        
        if not test_path.exists():
            print(f"\n❌ Test file not found: {test_path}")
            results.append((test_name, False, "File not found"))
            continue
        
        success, output = run_test(str(test_path), test_name)
        results.append((test_name, success, output))
    
    # Print summary
    print(f"\n{'='*60}")
    print("TEST SUMMARY")
    print(f"{'='*60}")
    
    passed = 0
    failed = 0
    
    for test_name, success, output in results:
        status = "✅ PASSED" if success else "❌ FAILED"
        print(f"{status} - {test_name}")
        
        if success:
            passed += 1
        else:
            failed += 1
    
    print(f"\nResults: {passed}/{total_tests} tests passed")
    
    if failed == 0:
        print("\n🎉 All tests passed! Your chatbot system is ready to use.")
        return True
    else:
        print(f"\n⚠️  {failed} test(s) failed. Check the output above for details.")
        return False

def run_specific_test(test_name: str):
    """Run a specific test by name"""
    tests_dir = Path("tests")
    
    test_mapping = {
        "db": ("test_db_connection.py", "Database Connection Tests"),
        "model": ("test_model_config.py", "LLM Model Configuration Tests"),
        "provider": ("test_multi_provider.py", "Multi-Provider LLM Support Tests"),
        "database": ("test_db_connection.py", "Database Connection Tests"),
        "config": ("test_model_config.py", "LLM Model Configuration Tests"),
        "multi": ("test_multi_provider.py", "Multi-Provider LLM Support Tests")
    }
    
    if test_name.lower() not in test_mapping:
        print(f"Unknown test: {test_name}")
        print(f"Available tests: {', '.join(test_mapping.keys())}")
        return False
    
    test_file, test_display_name = test_mapping[test_name.lower()]
    test_path = tests_dir / test_file
    
    if not test_path.exists():
        print(f"Test file not found: {test_path}")
        return False
    
    print(f"Running {test_display_name}")
    success, output = run_test(str(test_path), test_display_name)
    
    if success:
        print(f"\n✅ {test_display_name} passed!")
    else:
        print(f"\n❌ {test_display_name} failed!")
    
    return success

if __name__ == "__main__":
    if len(sys.argv) > 1:
        # Run specific test
        test_name = sys.argv[1]
        success = run_specific_test(test_name)
        sys.exit(0 if success else 1)
    else:
        # Run all tests
        success = main()
        sys.exit(0 if success else 1)
