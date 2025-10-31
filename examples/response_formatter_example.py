"""
Example usage of ResponseFormatterAgent

This example demonstrates how the ResponseFormatterAgent formats extracted data
into a professional markdown response.
"""
import asyncio
import json
from agents.response_formatter import ResponseFormatterAgent


def example_basic_usage():
    """Example 1: Basic usage with sample data"""
    print("=" * 80)
    print("Example 1: Basic Usage")
    print("=" * 80)

    # Initialize the agent
    formatter = ResponseFormatterAgent()

    # Sample optimized query
    optimized_query = "The user is asking you to fetch and analyze all closed deals from Oct 2024 and return structured information"

    # Sample extracted data (as would come from DataExtractorAgent)
    extracted_data = {
        "companies": [
            {
                "id": "comp-1",
                "name": "Acme Corp",
                "industry": "Technology",
                "deal_value": 150000,
                "status": "closed",
                "close_date": "2024-10-15"
            },
            {
                "id": "comp-2",
                "name": "TechStart Inc",
                "industry": "SaaS",
                "deal_value": 85000,
                "status": "closed",
                "close_date": "2024-10-22"
            }
        ],
        "people": [
            {
                "id": "person-1",
                "name": "John Doe",
                "email": "john@acmecorp.com",
                "company": "Acme Corp",
                "role": "CEO"
            },
            {
                "id": "person-2",
                "name": "Jane Smith",
                "email": "jane@techstart.com",
                "company": "TechStart Inc",
                "role": "VP Sales"
            }
        ]
    }

    # Format the response
    result = formatter.format(optimized_query, extracted_data)

    # Display results
    print("\n--- Markdown Response ---")
    print(result["response"])
    print("\n--- Metadata ---")
    print(json.dumps(result["metadata"], indent=2))
    print("\n--- Data Summary ---")
    print(f"Companies: {len(result['data']['companies'])}")
    print(f"People: {len(result['data']['people'])}")


def example_with_empty_data():
    """Example 2: Handling empty/missing data"""
    print("\n" + "=" * 80)
    print("Example 2: Handling Empty Data")
    print("=" * 80)

    formatter = ResponseFormatterAgent()

    optimized_query = "The user is asking you to find all meetings scheduled for tomorrow"

    # Empty extracted data
    extracted_data = {
        "interactions": [],
        "people": []
    }

    result = formatter.format(optimized_query, extracted_data)

    print("\n--- Markdown Response ---")
    print(result["response"])
    print("\n--- Metadata ---")
    print(json.dumps(result["metadata"], indent=2))


def example_with_multiple_data_sources():
    """Example 3: Complex data from multiple sources"""
    print("\n" + "=" * 80)
    print("Example 3: Multiple Data Sources")
    print("=" * 80)

    formatter = ResponseFormatterAgent()

    optimized_query = "The user is asking you to analyze communication with Acme Corp in Oct 2024"

    extracted_data = {
        "companies": [
            {
                "id": "comp-1",
                "name": "Acme Corp",
                "industry": "Technology",
                "status": "active"
            }
        ],
        "people": [
            {
                "id": "p1",
                "name": "John Doe",
                "email": "john@acmecorp.com",
                "company": "Acme Corp"
            },
            {
                "id": "p2",
                "name": "Sarah Wilson",
                "email": "sarah@acmecorp.com",
                "company": "Acme Corp"
            }
        ],
        "interactions": [
            {
                "id": "int-1",
                "type": "email",
                "date": "2024-10-05",
                "subject": "Product Demo Request",
                "from": "john@acmecorp.com",
                "sentiment": "positive"
            },
            {
                "id": "int-2",
                "type": "meeting",
                "date": "2024-10-10",
                "subject": "Product Demo",
                "attendees": ["john@acmecorp.com", "sarah@acmecorp.com"],
                "duration_minutes": 60
            },
            {
                "id": "int-3",
                "type": "email",
                "date": "2024-10-15",
                "subject": "Follow-up and Proposal",
                "from": "sarah@acmecorp.com",
                "sentiment": "positive"
            }
        ],
        "emails": [
            {
                "id": "email-1",
                "subject": "Product Demo Request",
                "date": "2024-10-05",
                "from": "john@acmecorp.com"
            }
        ]
    }

    result = formatter.format(optimized_query, extracted_data)

    print("\n--- Markdown Response ---")
    print(result["response"])
    print("\n--- Metadata ---")
    print(json.dumps(result["metadata"], indent=2))
    print(f"\n--- Data Sources Count: {result['metadata']['data_sources_count']} ---")


if __name__ == "__main__":
    print("\n" + "=" * 80)
    print("ResponseFormatterAgent Examples")
    print("=" * 80)
    print("\nNOTE: These examples require proper LLM configuration in your .env file")
    print("Set RESPONSE_FORMATTER_PROVIDER and RESPONSE_FORMATTER_MODEL")
    print("=" * 80)

    try:
        # Run examples
        example_basic_usage()
        example_with_empty_data()
        example_with_multiple_data_sources()

        print("\n" + "=" * 80)
        print("All examples completed successfully!")
        print("=" * 80)

    except Exception as e:
        print(f"\n\nError running examples: {e}")
        print("\nMake sure you have:")
        print("1. Set up your .env file with LLM provider credentials")
        print("2. Installed all required dependencies")
        print("3. Configured RESPONSE_FORMATTER_PROVIDER and RESPONSE_FORMATTER_MODEL")
