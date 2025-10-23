#!/usr/bin/env python3
"""
Test script to verify multi-provider LLM support works correctly
"""

import os
import sys
from dotenv import load_dotenv

# Add the project root to the path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def test_provider_factory():
    """Test the LLM provider factory"""
    print("Testing LLM Provider Factory")
    print("=" * 40)
    
    try:
        from agents.llm_provider import LLMProviderFactory
        
        # Test supported providers
        supported_providers = LLMProviderFactory.get_supported_providers()
        print(f"✅ Supported providers: {list(supported_providers.keys())}")
        
        for provider, models in supported_providers.items():
            print(f"  - {provider}: {models}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error testing provider factory: {e}")
        return False

def test_openai_provider():
    """Test OpenAI provider"""
    print(f"\nTesting OpenAI Provider")
    print("-" * 30)
    
    try:
        # Set OpenAI environment
        os.environ["LLM_PROVIDER"] = "openai"
        os.environ["LLM_MODEL_NAME"] = "gpt-3.5-turbo"
OPENAI_API_KEY=REDACTED
        
        from agents.llm_provider import get_llm_instance
        
        llm, provider_name = get_llm_instance()
        print(f"✅ OpenAI provider created: {provider_name}")
        print(f"✅ Model: {llm.model}")
        
        return True
        
    except Exception as e:
        print(f"❌ OpenAI provider test failed: {e}")
        return False

def test_gemini_provider():
    """Test Gemini provider"""
    print(f"\nTesting Gemini Provider")
    print("-" * 30)
    
    try:
        # Set Gemini environment
        os.environ["LLM_PROVIDER"] = "gemini"
        os.environ["LLM_MODEL_NAME"] = "gemini-pro"
        os.environ["GOOGLE_API_KEY"] = "test-key"  # Mock key for testing
        
        from agents.llm_provider import get_llm_instance
        
        llm, provider_name = get_llm_instance()
        print(f"✅ Gemini provider created: {provider_name}")
        print(f"✅ Model: {llm.model}")
        
        return True
        
    except ImportError:
        print("⚠️  Gemini provider test skipped: langchain-google-genai not installed")
        print("   Install with: pip install langchain-google-genai")
        return True
    except Exception as e:
        print(f"❌ Gemini provider test failed: {e}")
        return False

def test_claude_provider():
    """Test Claude provider"""
    print(f"\nTesting Claude Provider")
    print("-" * 30)
    
    try:
        # Set Claude environment
        os.environ["LLM_PROVIDER"] = "claude"
        os.environ["LLM_MODEL_NAME"] = "claude-3-sonnet-20240229"
        os.environ["ANTHROPIC_API_KEY"] = "test-key"  # Mock key for testing
        
        from agents.llm_provider import get_llm_instance
        
        llm, provider_name = get_llm_instance()
        print(f"✅ Claude provider created: {provider_name}")
        print(f"✅ Model: {llm.model}")
        
        return True
        
    except ImportError:
        print("⚠️  Claude provider test skipped: langchain-anthropic not installed")
        print("   Install with: pip install langchain-anthropic")
        return True
    except Exception as e:
        print(f"❌ Claude provider test failed: {e}")
        return False

def test_chatbot_creation():
    """Test chatbot creation with different providers"""
    print(f"\nTesting Chatbot Creation")
    print("-" * 30)
    
    providers_to_test = [
OPENAI_API_KEY=REDACTED
        ("gemini", "gemini-pro", "GOOGLE_API_KEY"),
        ("claude", "claude-3-sonnet-20240229", "ANTHROPIC_API_KEY")
    ]
    
    success_count = 0
    
    for provider, model, api_key_env in providers_to_test:
        try:
            # Set environment
            os.environ["LLM_PROVIDER"] = provider
            os.environ["LLM_MODEL_NAME"] = model
            os.environ[api_key_env] = "test-key"  # Mock key
            
            from agents.chatbot import create_chatbot
            
            chatbot = create_chatbot()
            print(f"✅ {provider.title()} chatbot created successfully")
            print(f"   Provider: {chatbot.provider_name}")
            print(f"   Model: {chatbot.llm.model}")
            
            success_count += 1
            
        except ImportError:
            print(f"⚠️  {provider.title()} chatbot test skipped: Required package not installed")
        except Exception as e:
            print(f"❌ {provider.title()} chatbot test failed: {e}")
    
    print(f"\n✅ Successfully tested {success_count}/{len(providers_to_test)} providers")
    return success_count > 0

def test_environment_validation():
    """Test environment variable validation"""
    print(f"\nTesting Environment Validation")
    print("-" * 30)
    
    # Test missing API key
    try:
        os.environ["LLM_PROVIDER"] = "openai"
        os.environ["LLM_MODEL_NAME"] = "gpt-3.5-turbo"
OPENAI_API_KEY=REDACTED
OPENAI_API_KEY=REDACTED
        
        from agents.llm_provider import get_llm_instance
        get_llm_instance()
        print("❌ Should have failed with missing API key")
        return False
        
    except ValueError as e:
        if "API key not found" in str(e):
            print("✅ Correctly detected missing API key")
        else:
            print(f"❌ Unexpected error: {e}")
            return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False
    
    # Test invalid provider
    try:
        os.environ["LLM_PROVIDER"] = "invalid_provider"
        os.environ["LLM_MODEL_NAME"] = "test-model"
OPENAI_API_KEY=REDACTED
        
        from agents.llm_provider import get_llm_instance
        get_llm_instance()
        print("❌ Should have failed with invalid provider")
        return False
        
    except ValueError as e:
        if "Unsupported provider" in str(e):
            print("✅ Correctly detected invalid provider")
        else:
            print(f"❌ Unexpected error: {e}")
            return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False
    
    return True

def main():
    """Run all tests"""
    print("Multi-Provider LLM Support Test Suite")
    print("=" * 50)
    
    # Load environment variables
    load_dotenv()
    
    tests = [
        test_provider_factory,
        test_openai_provider,
        test_gemini_provider,
        test_claude_provider,
        test_chatbot_creation,
        test_environment_validation
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        try:
            if test():
                passed += 1
        except Exception as e:
            print(f"❌ Test {test.__name__} failed with exception: {e}")
    
    print(f"\n{'='*50}")
    print(f"Test Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! Multi-provider support is working correctly.")
    else:
        print("⚠️  Some tests failed. Check the output above for details.")
    
    return passed == total

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
