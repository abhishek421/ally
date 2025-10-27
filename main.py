"""
Main entry point for AI Analyst RAG Pipeline
"""
from graph.pipeline import AnalystRAGPipeline


def main():
    """Run the RAG pipeline with a user query"""
    
    # Create the pipeline
    pipeline = AnalystRAGPipeline()
    
    # Example queries to test
    example_queries = [
        "what was the last mail from {id: 123, name: 'palen', email: 'palen.exe@gmail.com'}",
        "With how many companies we have closed deal previous year?"
    ]
    
    for user_query in example_queries:
        print(f"\n{'='*60}")
        print(f"Original Query: {user_query}")
        print('='*60)
        
        # Run the pipeline
        result = pipeline.run(user_query)
        
        # Display the result
        print("\nPipeline Result:")
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

