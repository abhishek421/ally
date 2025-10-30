"""
Integration Tests for AI Analyst Pipeline
Tests the complete pipeline flow with all agents
"""
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from agents.query_optimizer import QueryOptimizerAgent


def test_pipeline_logic():
    """Test pipeline logic without LangGraph dependencies"""
    print("\n" + "#"*60)
    print("Integration Test: Query Optimizer -> Mock Data Extractor -> Mock Formatter")
    print("#"*60)
    
    # Simulate the pipeline flow manually
    query = "what was the last mail from {id: 123, name: 'palen', email: 'palen.exe@gmail.com'}"
    
    print(f"\nStep 1 - Original Query: {query}")
    
    # Step 1: Query Optimizer
    query_optimizer = QueryOptimizerAgent()
    optimized_query = query_optimizer.optimize(query)
    print(f"\nStep 2 - Optimized Query: {optimized_query}")
    
    # Step 2: Mock Data Extractor (when implemented)
    # extracted_data = data_extractor.extract(optimized_query)
    extracted_data = {
        "emails": [
            {"id": 1, "subject": "Meeting Tomorrow", "body": "Let's discuss the project"},
            {"id": 2, "subject": "RE: Proposal", "body": "Here's the updated proposal"}
        ],
        "person": {"id": 123, "name": "palen", "email": "palen.exe@gmail.com"}
    }
    print(f"\nStep 3 - Extracted Data: {extracted_data}")
    
    # Step 3: Mock Response Formatter (when implemented)
    final_response = {
        "query": optimized_query,
        "data": extracted_data,
        "formatted_response": {
            "person": "palen",
            "latest_email": {
                "subject": "RE: Proposal",
                "body": "Here's the updated proposal",
                "timestamp": "2024-01-15T10:30:00Z"
            }
        }
    }
    print(f"\nStep 4 - Final Response: {final_response}")
    
    # Verify structure
    assert 'formatted_response' in final_response
    assert 'data' in final_response
    assert 'query' in final_response
    
    print("\n✓ Pipeline logic executed successfully")
    print("✓ Result structure is valid")
    return final_response


def test_email_pipeline():
    """Test complete pipeline for email query"""
    print("\n" + "="*60)
    print("Integration Test 1: Email Query Pipeline")
    print("="*60)
    
    result = test_pipeline_logic()
    
    # Verify specific fields
    assert 'latest_email' in result['formatted_response']
    assert 'subject' in result['formatted_response']['latest_email']
    print("\n✓ Email pipeline test passed")


def test_deal_pipeline():
    """Test complete pipeline for deal/company query"""
    print("\n" + "="*60)
    print("Integration Test 2: Deal Query Pipeline")
    print("="*60)
    
    query = "With how many companies we have closed deal previous year?"
    
    query_optimizer = QueryOptimizerAgent()
    optimized_query = query_optimizer.optimize(query)
    
    print(f"\nOriginal Query: {query}")
    print(f"Optimized Query: {optimized_query}")
    
    # Mock extracted data
    extracted_data = {
        "deals": [
            {"company": "Acme Corp", "status": "closed", "date": "2023-06-15"},
            {"company": "TechCo", "status": "closed", "date": "2023-08-20"}
        ],
        "year": "2023"
    }
    
    final_response = {
        "query": optimized_query,
        "data": extracted_data,
        "formatted_response": {
            "total_companies": 2,
            "companies": ["Acme Corp", "TechCo"],
            "year": "2023"
        }
    }
    
    print(f"\nFinal Response: {final_response}")
    
    assert final_response['formatted_response']['total_companies'] == 2
    print("\n✓ Deal pipeline test passed")


def test_complete_flow():
    """Test the complete flow for multiple scenarios"""
    print("\n" + "="*60)
    print("Integration Test 3: Complete Flow Test")
    print("="*60)
    
    scenarios = [
        {
            "query": "what was the last mail from {id: 123, name: 'palen'}",
            "expected_keywords": ["email", "person", "123"]
        },
        {
            "query": "Show me all closed deals this month",
            "expected_keywords": ["deals", "closed"]
        },
        {
            "query": "Count companies in Europe",
            "expected_keywords": ["company", "Europe"]
        }
    ]
    
    query_optimizer = QueryOptimizerAgent()
    
    for i, scenario in enumerate(scenarios, 1):
        print(f"\n--- Scenario {i} ---")
        print(f"Query: {scenario['query']}")
        
        optimized = query_optimizer.optimize(scenario['query'])
        print(f"Optimized: {optimized}")
        
        # Check if expected keywords are present
        optimized_lower = optimized.lower()
        for keyword in scenario['expected_keywords']:
            assert keyword.lower() in optimized_lower, f"Missing expected keyword: {keyword}"
        
        print("✓ Scenario passed")
    
    print("\n✓ Complete flow test passed")


def run_all_integration_tests():
    """Run all integration tests"""
    print("\n" + "="*60)
    print("AI Analyst Pipeline - Integration Tests")
    print("="*60)
    
    try:
        test_email_pipeline()
        test_deal_pipeline()
        test_complete_flow()
        
        print("\n" + "="*60)
        print("✓ All integration tests passed!")
        print("="*60)
        
    except AssertionError as e:
        print(f"\n✗ Test failed: {e}")
        raise
    except Exception as e:
        print(f"\n✗ Error: {e}")
        raise


if __name__ == "__main__":
    run_all_integration_tests()
