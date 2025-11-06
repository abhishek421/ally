#!/usr/bin/env python3
"""
Performance Testing Script for Analyst AI
Runs queries from TEST_QUERIES.md and records response times
"""
import json
import time
import requests
import csv
from datetime import datetime
from typing import Dict, List, Tuple

# Configuration
API_URL = "http://localhost:8000/api/v1/query"
WORKSPACE_ID = "550e8400-e29b-41d4-a716-446655440000"
USER_ID = "8d0c1f2f-a71c-4009-9942-3d8d9ae48816"

# Test queries categorized by complexity
TEST_QUERIES = {
    "meta": [
        "how can you help me?",
        "hello",
        "what can you do?",
    ],
    "simple": [
        "Show me all companies",
        "Show me all people",
        "Find John",
        "Find Acme Corporation",
    ],
    "medium": [
        "Find companies with 'Tech' in the name",
        "Find people with last name Smith",
        "Show me all private companies",
        "Give me analytics about companies",
    ],
    "complex": [
        "How many companies, people, and interactions do I have?",
        "Show me all private companies and people",
        "What was created in the last 30 days?",
        "Show me John Doe and Acme Corporation",
    ]
}


def run_query(query: str) -> Tuple[bool, int, Dict]:
    """
    Run a single query and measure response time

    Returns:
        (success, response_time_ms, response_data)
    """
    headers = {
        "accept": "application/json",
        "X-Workspace-ID": WORKSPACE_ID,
        "X-User-ID": USER_ID,
        "Content-Type": "application/json"
    }

    payload = {"query": query}

    try:
        start_time = time.time()
        response = requests.post(API_URL, headers=headers, json=payload, timeout=120)
        elapsed_ms = int((time.time() - start_time) * 1000)

        if response.status_code == 200:
            data = response.json()
            return (True, elapsed_ms, data)
        else:
            return (False, elapsed_ms, {"error": f"HTTP {response.status_code}", "detail": response.text[:200]})

    except requests.exceptions.Timeout:
        return (False, 120000, {"error": "Request timeout after 120s"})
    except Exception as e:
        return (False, -1, {"error": str(e)})


def format_time(ms: int) -> str:
    """Format milliseconds to human-readable string"""
    if ms < 0:
        return "ERROR"
    elif ms < 1000:
        return f"{ms}ms"
    else:
        return f"{ms/1000:.2f}s"


def analyze_response(data: Dict) -> Dict:
    """Extract key metrics from response"""
    metrics = {
        "reported_time_ms": data.get("execution_time_ms", -1),
        "success": data.get("success", False),
    }

    # Check if orchestrator was used
    result = data.get("result", {})
    if "_orchestration" in result:
        orch = result["_orchestration"]
        metrics["orchestrator"] = True
        metrics["query_complexity"] = orch["query_analysis"].get("complexity", "unknown")
        metrics["strategy"] = orch["execution_plan"].get("strategy", "unknown")
        metrics["agents_count"] = len(orch.get("agents_executed", []))
    elif "metadata" in result and result["metadata"].get("fast_path"):
        metrics["orchestrator"] = False
        metrics["fast_path"] = True
    else:
        metrics["orchestrator"] = False

    # Extract entity counts from response data
    data_result = result.get("data", {}) if isinstance(result, dict) else {}
    entity_counts = {}

    for entity_type in ["companies", "people", "interactions", "emails", "groups", "workspaces"]:
        if entity_type in data_result:
            entity_data = data_result[entity_type]
            if isinstance(entity_data, list):
                entity_counts[entity_type] = len(entity_data)
            elif isinstance(entity_data, dict):
                entity_counts[entity_type] = 1

    metrics["entity_counts"] = entity_counts
    metrics["total_entities"] = sum(entity_counts.values())

    # Extract AI response text
    ai_response = result.get("response", "")
    if not ai_response and "clarification_question" in result:
        ai_response = result["clarification_question"]
    metrics["ai_response"] = ai_response[:200] if ai_response else ""  # First 200 chars

    return metrics


def init_csv(filename: str = "performance_results.csv"):
    """Initialize CSV file with headers"""
    with open(filename, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            "Timestamp",
            "Category",
            "Query",
            "Success",
            "Actual_Time_ms",
            "Reported_Time_ms",
            "Fast_Path",
            "Orchestrator",
            "Complexity",
            "Strategy",
            "Agents_Count",
            "Total_Entities",
            "Companies",
            "People",
            "Interactions",
            "Emails",
            "Groups",
            "AI_Response",
            "Error"
        ])
    print(f"📊 CSV file initialized: {filename}")


def append_to_csv(result: Dict, category: str, filename: str = "performance_results.csv"):
    """Append a single result to CSV file"""
    entity_counts = result.get("entity_counts", {})

    with open(filename, "a", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            datetime.now().isoformat(),
            category,
            result["query"],
            result["success"],
            result["actual_time_ms"],
            result["reported_time_ms"],
            result["fast_path"],
            result["orchestrator"],
            result["complexity"],
            result["strategy"],
            result["agents_count"],
            result.get("total_entities", 0),
            entity_counts.get("companies", 0),
            entity_counts.get("people", 0),
            entity_counts.get("interactions", 0),
            entity_counts.get("emails", 0),
            entity_counts.get("groups", 0),
            result.get("ai_response", ""),
            result.get("error", "")
        ])


def run_test_suite(csv_filename: str = "performance_results.csv") -> Dict:
    """
    Run all test queries and collect results

    Args:
        csv_filename: Name of CSV file to write live results

    Returns:
        Dictionary with test results
    """
    # Initialize CSV file
    init_csv(csv_filename)

    results = {
        "timestamp": datetime.now().isoformat(),
        "categories": {}
    }

    for category, queries in TEST_QUERIES.items():
        print(f"\n{'='*60}")
        print(f"Testing {category.upper()} queries ({len(queries)} queries)")
        print('='*60)

        category_results = []

        for i, query in enumerate(queries, 1):
            print(f"\n[{i}/{len(queries)}] Running: \"{query}\"")
            print("-" * 60)

            success, actual_time_ms, response_data = run_query(query)
            metrics = analyze_response(response_data)

            result = {
                "query": query,
                "success": success,
                "actual_time_ms": actual_time_ms,
                "reported_time_ms": metrics.get("reported_time_ms", -1),
                "fast_path": metrics.get("fast_path", False),
                "orchestrator": metrics.get("orchestrator", False),
                "complexity": metrics.get("query_complexity", "unknown"),
                "strategy": metrics.get("strategy", "unknown"),
                "agents_count": metrics.get("agents_count", 0),
                "total_entities": metrics.get("total_entities", 0),
                "entity_counts": metrics.get("entity_counts", {}),
                "ai_response": metrics.get("ai_response", ""),
                "error": response_data.get("error", "") if not success else ""
            }

            category_results.append(result)

            # Write to CSV immediately
            append_to_csv(result, category, csv_filename)

            # Print summary
            if success:
                print(f"✅ SUCCESS")
                print(f"   Actual time: {format_time(actual_time_ms)}")
                print(f"   Reported time: {format_time(metrics.get('reported_time_ms', -1))}")

                # Entity counts
                total_entities = metrics.get("total_entities", 0)
                if total_entities > 0:
                    entity_counts = metrics.get("entity_counts", {})
                    entities_str = ", ".join([f"{count} {entity}" for entity, count in entity_counts.items() if count > 0])
                    print(f"   📦 Data: {total_entities} entities ({entities_str})")

                # AI response preview
                ai_response = metrics.get("ai_response", "")
                if ai_response:
                    print(f"   💬 Response: {ai_response[:80]}...")

                if metrics.get("fast_path"):
                    print(f"   🚀 FAST PATH (instant response)")
                elif metrics.get("orchestrator"):
                    print(f"   🎯 Orchestrator: {metrics.get('query_complexity', 'unknown')} complexity")
                    print(f"   📊 Strategy: {metrics.get('strategy', 'unknown')}")
                    print(f"   🤖 Agents: {metrics.get('agents_count', 0)}")
            else:
                print(f"❌ FAILED")
                print(f"   Time: {format_time(actual_time_ms)}")
                print(f"   Error: {response_data.get('error', 'Unknown')}")

            # Flush to ensure CSV is written
            print(f"   💾 Written to {csv_filename}")

            # Small delay between requests
            time.sleep(0.5)

        results["categories"][category] = {
            "queries": category_results,
            "avg_time_ms": sum(r["actual_time_ms"] for r in category_results if r["success"]) / len([r for r in category_results if r["success"]]) if any(r["success"] for r in category_results) else 0,
            "success_rate": sum(1 for r in category_results if r["success"]) / len(category_results) * 100
        }

    return results


def print_summary(results: Dict):
    """Print summary of test results"""
    print("\n" + "="*60)
    print("PERFORMANCE TEST SUMMARY")
    print("="*60)
    print(f"Test Date: {results['timestamp']}")
    print()

    # Table header
    print(f"{'Category':<15} {'Queries':<10} {'Success':<12} {'Avg Time':<15} {'Notes':<20}")
    print("-" * 72)

    for category, data in results["categories"].items():
        queries_count = len(data["queries"])
        success_rate = data["success_rate"]
        avg_time = format_time(int(data["avg_time_ms"]))

        # Check for fast-path queries
        fast_path_count = sum(1 for q in data["queries"] if q.get("fast_path"))
        notes = f"{fast_path_count} fast-path" if fast_path_count > 0 else ""

        print(f"{category:<15} {queries_count:<10} {success_rate:>5.1f}%    {avg_time:<15} {notes:<20}")

    print("-" * 72)

    # Overall stats
    all_queries = [q for cat in results["categories"].values() for q in cat["queries"]]
    total_queries = len(all_queries)
    total_success = sum(1 for q in all_queries if q["success"])
    overall_avg = sum(q["actual_time_ms"] for q in all_queries if q["success"]) / total_success if total_success > 0 else 0

    print(f"{'TOTAL':<15} {total_queries:<10} {total_success/total_queries*100:>5.1f}%    {format_time(int(overall_avg)):<15}")
    print()

    # Performance breakdown
    print("\nPERFORMANCE BREAKDOWN:")
    print("-" * 40)

    fast_path_queries = [q for q in all_queries if q.get("fast_path")]
    orchestrated_queries = [q for q in all_queries if q.get("orchestrator")]

    if fast_path_queries:
        avg_fast = sum(q["actual_time_ms"] for q in fast_path_queries) / len(fast_path_queries)
        print(f"Fast-path queries: {len(fast_path_queries)} ({format_time(int(avg_fast))} avg)")

    if orchestrated_queries:
        avg_orch = sum(q["actual_time_ms"] for q in orchestrated_queries if q["success"]) / len([q for q in orchestrated_queries if q["success"]])
        print(f"Orchestrated queries: {len(orchestrated_queries)} ({format_time(int(avg_orch))} avg)")

        # By complexity
        by_complexity = {}
        for q in orchestrated_queries:
            complexity = q.get("complexity", "unknown")
            if complexity not in by_complexity:
                by_complexity[complexity] = []
            by_complexity[complexity].append(q["actual_time_ms"])

        print("\nBy Complexity:")
        for complexity, times in by_complexity.items():
            avg = sum(times) / len(times)
            print(f"  {complexity}: {len(times)} queries, {format_time(int(avg))} avg")


def save_results(results: Dict, filename: str = "performance_results.json"):
    """Save results to JSON file"""
    with open(filename, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\n✅ Results saved to {filename}")


if __name__ == "__main__":
    print("🚀 Starting Analyst AI Performance Test Suite")
    print(f"API URL: {API_URL}")
    print(f"Workspace: {WORKSPACE_ID}")
    print(f"User: {USER_ID}")
    print()

    # CSV filename with timestamp
    csv_filename = f"performance_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    json_filename = f"performance_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

    print(f"📊 Live results will be written to: {csv_filename}")
    print(f"📄 Final JSON results will be saved to: {json_filename}")
    print()

    # Run tests
    results = run_test_suite(csv_filename)

    # Print summary
    print_summary(results)

    # Save JSON results
    save_results(results, json_filename)

    print(f"\n✅ Performance test complete!")
    print(f"📊 CSV results: {csv_filename}")
    print(f"📄 JSON results: {json_filename}")
