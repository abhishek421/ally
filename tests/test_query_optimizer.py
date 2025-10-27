"""
Tests for QueryOptimizerAgent
"""
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from agents.query_optimizer import QueryOptimizerAgent


def test_email_query_with_person_info():
    """Test email query with structured person information"""
    agent = QueryOptimizerAgent()
    
    query = "what was the last mail from {id: 123, name: 'palen', email: 'palen.exe@gmail.com'}"
    result = agent.optimize(query)
    
    print("\n" + "="*60)
    print("Test 1: Email Query with Person Info")
    print("="*60)
    print(f"Input:  {query}")
    print(f"Output: {result}")
    
    # Assertions
    assert "fetch" in result.lower() or "email" in result.lower()
    assert "person" in result.lower()
    assert "123" in result or "palen" in result
    print("✓ Test passed")


def test_deal_query():
    """Test deal/company query"""
    agent = QueryOptimizerAgent()
    
    query = "With how many companies we have closed deal previous year?"
    result = agent.optimize(query)
    
    print("\n" + "="*60)
    print("Test 2: Deal Query")
    print("="*60)
    print(f"Input:  {query}")
    print(f"Output: {result}")
    
    # Assertions
    assert "deals" in result.lower() or "deal" in result.lower()
    assert "previous year" in result.lower() or "last year" in result.lower()
    print("✓ Test passed")


def test_simple_email_query():
    """Test simple email query"""
    agent = QueryOptimizerAgent()
    
    query = "what was the last email from john?"
    result = agent.optimize(query)
    
    print("\n" + "="*60)
    print("Test 3: Simple Email Query")
    print("="*60)
    print(f"Input:  {query}")
    print(f"Output: {result}")
    
    # Assertions
    assert "fetch" in result.lower() or "email" in result.lower()
    assert "john" in result or "last" in result.lower()
    print("✓ Test passed")


def test_generic_query():
    """Test generic company query"""
    agent = QueryOptimizerAgent()
    
    query = "Show me all companies in New York"
    result = agent.optimize(query)
    
    print("\n" + "="*60)
    print("Test 4: Generic Query")
    print("="*60)
    print(f"Input:  {query}")
    print(f"Output: {result}")
    
    # Assertions
    assert "company" in result.lower()
    print("✓ Test passed")


def test_person_info_extraction():
    """Test person information extraction"""
    agent = QueryOptimizerAgent()
    
    query = "Send mail to {id: 456, name: 'Alice', email: 'alice@example.com'}"
    result = agent._extract_person_info(query)
    
    print("\n" + "="*60)
    print("Test 5: Person Info Extraction")
    print("="*60)
    print(f"Input:  {query}")
    print(f"Extracted: {result}")
    
    # Assertions
    assert result is not None
    assert "456" in result or "Alice" in result
    print("✓ Test passed")


def run_all_tests():
    """Run all tests"""
    print("\n" + "#"*60)
    print("# QueryOptimizerAgent Tests")
    print("#"*60)
    
    try:
        test_email_query_with_person_info()
        test_deal_query()
        test_simple_email_query()
        test_generic_query()
        test_person_info_extraction()
        
        print("\n" + "="*60)
        print("✓ All tests passed!")
        print("="*60)
        
    except AssertionError as e:
        print(f"\n✗ Test failed: {e}")
    except Exception as e:
        print(f"\n✗ Error: {e}")


if __name__ == "__main__":
    run_all_tests()

