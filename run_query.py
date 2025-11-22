import os
import json
import logging
import sys

# Add current directory to path
sys.path.append(os.getcwd())

from dotenv import load_dotenv
from src.nodes.query_processing_node import query_processing_node
from src.graph.state import GraphState

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

def main():
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
    print("=" * 50)
    print("AnalystAI Query Interface")
    print("=" * 50)
    print("Type 'exit' or 'quit' to stop.")

    while True:
        try:
            user_query = input("\nEnter your question: ").strip()
            if user_query.lower() in ['exit', 'quit']:
                print("Goodbye!")
                break

            if not user_query:
                continue

            print("\nProcessing query...")
            
            # Create state
            state: GraphState = {
                "user_query": user_query,
                "workspace_id": workspace_id,
                "query_builder_result": f"Current query: {user_query}",
                "execution_path": ["manual_input"],
                "metadata": {},
            }

            # Execute query processing node
            result = query_processing_node(state)

            # Parse and display result
            if result.get("query_processing_result"):
                try:
                    response_data = json.loads(result["query_processing_result"])
                    answer = response_data.get('answer', 'No answer provided.')
                    
                    print("\n" + "-" * 50)
                    print("Answer:")
                    print("-" * 50)
                    print(answer)
                    print("-" * 50)
                    
                    # Optional: Show tool usage
                    tool_calls = response_data.get('tool_calls', [])
                    if tool_calls:
                        print(f"\n(Debug: Used {len(tool_calls)} tool calls)")
                        
                except json.JSONDecodeError:
                    print("\nError: Failed to parse response JSON.")
                    print("Raw output:", result.get("query_processing_result"))
            else:
                print("\nError: No result returned from query processing.")
                if result.get("errors"):
                    print("Errors:", result.get("errors"))

        except KeyboardInterrupt:
            print("\nGoodbye!")
            break
        except Exception as e:
            logger.error(f"An error occurred: {e}")

if __name__ == "__main__":
    main()
