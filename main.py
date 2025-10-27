"""
Main entry point for AI Analyst RAG Pipeline
"""
from graph.pipeline import AnalystRAGPipeline


def main():
    """Run the RAG pipeline with a user query"""
    
    # Create the pipeline
    pipeline = AnalystRAGPipeline()
    
    # Example query
    user_query = "With how many companies we have closed deal previous year?"
    
    print(f"Processing query: {user_query}\n")
    
    # Run the pipeline
    result = pipeline.run(user_query)
    
    # Display the result
    print("Pipeline Result:")
    print(result)


def interactive_mode():
    """Interactive mode for querying the pipeline"""
    
    # Create the pipeline
    pipeline = AnalystRAGPipeline()
    
    print("AI Analyst RAG Pipeline")
    print("Type 'exit' to quit\n")
    
    while True:
        # Get user input
        user_query = input("Enter your query: ").strip()
        
        if user_query.lower() == 'exit':
            print("Exiting...")
            break
        
        if not user_query:
            continue
        
        print(f"\nProcessing: {user_query}")
        
        try:
            # Run the pipeline
            result = pipeline.run(user_query)
            
            # Display the result
            print("\nResult:")
            print(result)
            print("\n" + "="*50 + "\n")
            
        except Exception as e:
            print(f"Error: {e}\n")


if __name__ == "__main__":
    # Choose mode:
    # For single query testing
    main()
    
    # For interactive mode (uncomment to use)
    # interactive_mode()

