"""Run the complete graph with query builder and query processing nodes."""
import os
import json
import logging
import sys

# Add current directory to path
sys.path.append(os.getcwd())

from dotenv import load_dotenv
from src.graph.builder import build_graph
from src.graph.state import GraphState

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)


def main():
    """Run the complete graph flow."""
    # Load environment variables
    load_dotenv()

    # Check for API keys
    api_key = (
OPENAI_API_KEY=REDACTED
        or os.getenv("GOOGLE_API_KEY")
        or os.getenv("ANTHROPIC_API_KEY")
    )
    if not api_key:
OPENAI_API_KEY=REDACTED
        return

    # Check for Workspace ID
    workspace_id = os.getenv("WORKSPACE_ID")
    if not workspace_id:
        print("Error: WORKSPACE_ID not set. Please set WORKSPACE_ID in your .env file.")
        return

    print(f"Using Workspace ID: {workspace_id}")
    print("=" * 80)
    print("AnalystAI - Complete Graph Flow")
    print("Query Builder → Query Processing")
    print("=" * 80)
    print("Type 'exit' or 'quit' to stop.\n")

    # Build the graph
    try:
        app = build_graph()
        print("✓ Graph built successfully\n")
    except Exception as e:
        print(f"Error building graph: {e}")
        return

    while True:
        try:
            user_query = input("Enter your question: ").strip()
            if user_query.lower() in ['exit', 'quit']:
                print("Goodbye!")
                break

            if not user_query:
                continue

            print("\nProcessing query through complete graph flow...")
            print("-" * 80)
            
            # Create initial state
            initial_state: GraphState = {
                "user_query": user_query,
                "workspace_id": workspace_id,
                "execution_path": [],
                "metadata": {},
            }

            # Execute the graph
            result = app.invoke(initial_state)

            # Display results
            print("\n" + "=" * 80)
            print("GRAPH EXECUTION COMPLETE")
            print("=" * 80)
            
            # Show execution path
            execution_path = result.get("execution_path", [])
            print(f"\nExecution Path: {' → '.join(execution_path)}")
            
            # Show query builder result
            if result.get("query_builder_result"):
                print("\n" + "-" * 80)
                print("Query Builder Output:")
                print("-" * 80)
                print(result["query_builder_result"])
            
            # Show query processing result
            if result.get("query_processing_result"):
                print("\n" + "-" * 80)
                print("Query Processing Output:")
                print("-" * 80)
                try:
                    response_data = json.loads(result["query_processing_result"])
                    answer = response_data.get('answer', 'No answer provided.')
                    print(f"\nAnswer:\n{answer}")
                    
                    # Show metadata
                    tool_calls = response_data.get('tool_calls', [])
                    if tool_calls:
                        print(f"\n(Used {len(tool_calls)} tool call(s))")
                        tools_used = list(set([tc.get('tool') for tc in tool_calls]))
                        print(f"Tools: {', '.join(tools_used)}")
                        
                except json.JSONDecodeError:
                    print("Error: Failed to parse response JSON.")
                    print("Raw output:", result.get("query_processing_result"))
            
            # Show any errors
            if result.get("errors"):
                print("\n" + "-" * 80)
                print("Errors:")
                print("-" * 80)
                for error in result.get("errors", []):
                    print(f"  • {error}")
            
            print("\n" + "=" * 80 + "\n")

        except KeyboardInterrupt:
            print("\nGoodbye!")
            break
        except Exception as e:
            logger.error(f"An error occurred: {e}", exc_info=True)
            print(f"\nError: {e}\n")


if __name__ == "__main__":
    main()
