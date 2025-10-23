#!/usr/bin/env python3
"""
Test script to verify LLM model configuration works correctly
Updated for multi-provider support
"""

import os
import sys
from dotenv import load_dotenv

# Add the project root to the path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def test_model_configuration():
    """Test that the model configuration works correctly"""
    print("Testing Multi-Provider LLM Configuration")
    print("=" * 50)
    
    # Load environment variables
    load_dotenv()
    
    # Test 1: Check if LLM_PROVIDER and LLM_MODEL_NAME are set
    provider = os.getenv("LLM_PROVIDER", "openai")
    model_name = os.getenv("LLM_MODEL_NAME", "gpt-3.5-turbo")
    print(f"✅ Provider from environment: {provider}")
    print(f"✅ Model name from environment: {model_name}")
    
    # Test 2: Test chatbot creation with current environment
    try:
        from agents.chatbot import create_chatbot
        
        print(f"\nTesting chatbot creation with provider: {provider}, model: {model_name}")
        chatbot = create_chatbot()
        print(f"✅ Chatbot created successfully")
        print(f"   Provider: {chatbot.provider_name}")
        print(f"   Model: {chatbot.llm.model}")
        
        # Verify the model matches what we expect
        if chatbot.llm.model == model_name:
            print("✅ Model configuration is working correctly!")
        else:
            print(f"❌ Model mismatch: expected {model_name}, got {chatbot.llm.model}")
            return False
            
    except Exception as e:
        print(f"❌ Error creating chatbot: {e}")
        return False
    
    # Test 3: Test with different provider configurations
    print(f"\nTesting with different provider configurations...")
    
    test_configs = [
OPENAI_API_KEY=REDACTED
OPENAI_API_KEY=REDACTED
        ("gemini", "gemini-pro", "GOOGLE_API_KEY"),
        ("claude", "claude-3-sonnet-20240229", "ANTHROPIC_API_KEY")
    ]
    
    success_count = 0
    
    for test_provider, test_model, api_key_env in test_configs:
        try:
            # Temporarily set the environment variables
            os.environ["LLM_PROVIDER"] = test_provider
            os.environ["LLM_MODEL_NAME"] = test_model
            os.environ[api_key_env] = "test-key"  # Mock key for testing
            
            # Create chatbot with new configuration
            chatbot = create_chatbot()
            
            if chatbot.llm.model == test_model and chatbot.provider_name.lower() == test_provider:
                print(f"✅ {test_provider.title()} {test_model}: Configuration successful")
                success_count += 1
            else:
                print(f"❌ {test_provider.title()} {test_model}: Configuration failed")
                
        except ImportError:
            print(f"⚠️  {test_provider.title()} {test_model}: Required package not installed")
        except Exception as e:
            print(f"❌ {test_provider.title()} {test_model}: Error - {e}")
    
    print(f"\n✅ Successfully tested {success_count}/{len(test_configs)} configurations")
    
    if success_count > 0:
        print(f"\n🎉 Multi-provider LLM configuration is working correctly!")
        return True
    else:
        print(f"\n❌ No configurations worked. Check your environment setup.")
        return False

if __name__ == "__main__":
    success = test_model_configuration()
    sys.exit(0 if success else 1)
