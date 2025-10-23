from typing import List
from database.csv_processor import get_csv_processor


class SampleDataGenerator:
    """Legacy class - now redirects to CSV processor"""
    
    def __init__(self):
        self.csv_processor = get_csv_processor()
    
    def seed_database(self, companies_count: int = 50, people_count: int = 200) -> bool:
        """Legacy method - CSV upload is now handled through UI"""
        print("Sample data generation is no longer supported.")
        print("Please use the CSV upload functionality in the UI to upload your data.")
        return False
    
    def clear_sample_data(self) -> bool:
        """Clear all data from database"""
        return self.csv_processor.clear_all_data()
    
    def get_sample_queries(self) -> List[str]:
        """Get sample queries for testing the chatbot"""
        return [
            "What are the top 5 companies by subscription date?",
            "How many people are there in each country?",
            "Which companies are in Chile?",
            "What are the different job titles?",
            "Show me all people born after 1990",
            "Which company has the most recent subscription?",
            "What are the different cities in our database?",
            "Find all people with 'Manager' in their job title",
            "Which companies were subscribed after 2020?",
            "What is the total number of people in our database?",
            "Show me people who work at companies in specific countries",
            "What are the top 3 countries by number of companies?",
            "Find all people with specific job titles",
            "Which companies don't have a website?",
            "What is the distribution of people by sex?"
        ]
    
    # Add this method to database/sample_data.py or run this manually
def reset_and_recreate_tables():
    """Reset database and recreate tables"""
    from database.db_setup import get_db_manager
    
    db_manager = get_db_manager()
    if db_manager.connect():
        # Drop existing tables
        db_manager.drop_tables()
        # Recreate tables
        db_manager.create_tables()
        print("Tables recreated successfully")
        return True
    return False


# Global sample data generator instance
sample_data_generator = SampleDataGenerator()


def get_sample_data_generator() -> SampleDataGenerator:
    """Get the global sample data generator instance"""
    return sample_data_generator
