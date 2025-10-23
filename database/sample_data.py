import random
from datetime import datetime, timedelta
from typing import List, Dict, Any
from faker import Faker
from sqlalchemy import text  # Add this line
from database.db_setup import get_db_manager
# Add this import at the top of database/sample_data.py

fake = Faker()


class SampleDataGenerator:
    def __init__(self):
        self.db_manager = get_db_manager()
    
    def generate_companies_data(self, count: int = 50) -> List[Dict[str, Any]]:
        """Generate sample company data"""
        industries = [
            "Technology", "Healthcare", "Finance", "Manufacturing", "Retail",
            "Education", "Real Estate", "Transportation", "Energy", "Media",
            "Consulting", "Food & Beverage", "Automotive", "Telecommunications",
            "Pharmaceuticals", "Construction", "Entertainment", "Sports",
            "Agriculture", "Logistics"
        ]
        
        locations = [
            "New York", "San Francisco", "Los Angeles", "Chicago", "Boston",
            "Seattle", "Austin", "Denver", "Miami", "Atlanta", "Dallas",
            "Phoenix", "Philadelphia", "Detroit", "Minneapolis", "Portland",
            "Nashville", "Orlando", "Las Vegas", "San Diego"
        ]
        
        companies = []
        
        for i in range(count):
            founded_year = random.randint(1990, 2023)
            employee_count = random.randint(10, 10000)
            
            company = {
                "name": fake.company(),
                "industry": random.choice(industries),
                "location": random.choice(locations),
                "website": f"https://www.{fake.domain_name()}",
                "employee_count": employee_count,
                "founded_year": founded_year,
                "created_at": fake.date_time_between(start_date="-2y", end_date="now"),
                "updated_at": datetime.now()
            }
            companies.append(company)
        
        return companies
    
    def generate_people_data(self, companies_data: List[Dict[str, Any]], count: int = 200) -> List[Dict[str, Any]]:
        """Generate sample people data"""
        roles = [
            "CEO", "CTO", "CFO", "VP Engineering", "VP Sales", "VP Marketing",
            "Director of Product", "Director of Operations", "Senior Manager",
            "Manager", "Senior Developer", "Developer", "Senior Designer",
            "Designer", "Data Scientist", "DevOps Engineer", "QA Engineer",
            "Product Manager", "Project Manager", "Business Analyst",
            "Sales Manager", "Account Executive", "Marketing Manager",
            "Content Manager", "HR Manager", "Recruiter", "Financial Analyst",
            "Operations Manager", "Customer Success Manager", "Support Engineer"
        ]
        
        departments = [
            "Engineering", "Product", "Sales", "Marketing", "Operations",
            "Finance", "Human Resources", "Customer Success", "Support",
            "Business Development", "Legal", "Security", "Data Science",
            "Design", "Quality Assurance", "DevOps", "Research & Development"
        ]
        
        people = []
        
        for i in range(count):
            company = random.choice(companies_data)
            role = random.choice(roles)
            department = random.choice(departments)
            
            # Generate realistic salary based on role and company size
            base_salary = self._get_base_salary(role)
            company_multiplier = min(company["employee_count"] / 1000, 2.0)  # Cap at 2x
            salary = int(base_salary * (0.8 + random.random() * 0.4) * company_multiplier)
            
            # Generate hire date (within last 5 years)
            hire_date = fake.date_between(start_date="-5y", end_date="today")
            
            person = {
                "name": fake.name(),
                "email": fake.email(),
                "role": role,
                "department": department,
                "company_id": company["id"] if "id" in company else random.randint(1, len(companies_data)),
                "hire_date": hire_date,
                "salary": salary,
                "created_at": fake.date_time_between(start_date="-2y", end_date="now"),
                "updated_at": datetime.now()
            }
            people.append(person)
        
        return people
    
    def _get_base_salary(self, role: str) -> int:
        """Get base salary for a role"""
        salary_ranges = {
            "CEO": 300000, "CTO": 250000, "CFO": 200000,
            "VP Engineering": 180000, "VP Sales": 160000, "VP Marketing": 150000,
            "Director of Product": 140000, "Director of Operations": 130000,
            "Senior Manager": 120000, "Manager": 100000,
            "Senior Developer": 120000, "Developer": 80000,
            "Senior Designer": 100000, "Designer": 70000,
            "Data Scientist": 110000, "DevOps Engineer": 100000,
            "QA Engineer": 75000, "Product Manager": 110000,
            "Project Manager": 90000, "Business Analyst": 80000,
            "Sales Manager": 100000, "Account Executive": 70000,
            "Marketing Manager": 90000, "Content Manager": 65000,
            "HR Manager": 85000, "Recruiter": 60000,
            "Financial Analyst": 75000, "Operations Manager": 90000,
            "Customer Success Manager": 80000, "Support Engineer": 70000
        }
        
        return salary_ranges.get(role, 70000)
    
    def insert_companies_data(self, companies_data: List[Dict[str, Any]]) -> bool:
        """Insert companies data into database"""
        try:
            if not self.db_manager.engine:
                print("No database engine available")
                return False
            
            if not companies_data:
                print("No companies data to insert")
                return False
            
            # Prepare insert statement - exclude 'id' as it's auto-generated
            columns = [col for col in companies_data[0].keys() if col != 'id']
            placeholders = ", ".join([f":{col}" for col in columns])
            query = f"INSERT INTO companies ({', '.join(columns)}) VALUES ({placeholders})"
            
            with self.db_manager.engine.connect() as conn:
                for company in companies_data:
                    # Remove 'id' from company data if it exists and convert datetime to string
                    company_data = {}
                    for k, v in company.items():
                        if k != 'id':
                            if isinstance(v, datetime):
                                company_data[k] = v.isoformat()
                            else:
                                company_data[k] = v
                    
                    conn.execute(text(query), company_data)
                conn.commit()
            
            return True
            
        except Exception as e:
            print(f"Error inserting companies data: {e}")
            return False
    
    def insert_people_data(self, people_data: List[Dict[str, Any]]) -> bool:
        """Insert people data into database"""
        try:
            if not self.db_manager.engine:
                return False
            
            # Prepare insert statement
            columns = list(people_data[0].keys())
            placeholders = ", ".join([f":{col}" for col in columns])
            query = f"INSERT INTO people ({', '.join(columns)}) VALUES ({placeholders})"
            
            with self.db_manager.engine.connect() as conn:
                for person in people_data:
                    conn.execute(text(query), person)
                conn.commit()
            
            return True
            
        except Exception as e:
            print(f"Error inserting people data: {e}")
            return False
    
    def seed_database(self, companies_count: int = 50, people_count: int = 200) -> bool:
        """Seed the database with sample data"""
        print("Generating sample data...")
        
        # Ensure database connection
        if not self.db_manager.engine:
            if not self.db_manager.connect():
                print("Failed to connect to database")
                return False
        
        # Generate companies data
        companies_data = self.generate_companies_data(companies_count)
        
        # Insert companies and get their IDs
        if not self.insert_companies_data(companies_data):
            return False
        
        # Get company IDs from database
        companies_with_ids = self.db_manager.execute_query("SELECT id, name, employee_count FROM companies ORDER BY id")
        if not companies_with_ids:
            return False
        
        # Generate people data with correct company IDs
        people_data = self.generate_people_data(companies_with_ids, people_count)
        
        # Insert people data
        if not self.insert_people_data(people_data):
            return False
        
        print(f"Successfully seeded database with {len(companies_data)} companies and {len(people_data)} people")
        return True
    
    def clear_sample_data(self) -> bool:
        """Clear all sample data from database"""
        try:
            if not self.db_manager.engine:
                return False
            
            with self.db_manager.engine.connect() as conn:
                # Clear people first (due to foreign key constraint)
                conn.execute(text("DELETE FROM people"))
                conn.execute(text("DELETE FROM companies"))
                conn.commit()
            
            print("Sample data cleared successfully")
            return True
            
        except Exception as e:
            print(f"Error clearing sample data: {e}")
            return False
    
    def get_sample_queries(self) -> List[str]:
        """Get sample queries for testing the chatbot"""
        return [
            "What are the top 5 newly added companies?",
            "How many people work in the Engineering department?",
            "Which companies are in the Technology industry?",
            "What is the average salary by role?",
            "Show me all people hired in the last year",
            "Which company has the most employees?",
            "What are the different departments in our database?",
            "Find all people with 'Manager' in their role",
            "Which companies were founded after 2020?",
            "What is the total number of employees across all companies?",
            "Show me people who work at companies with more than 1000 employees",
            "What are the top 3 industries by number of companies?",
            "Find all people in the Sales department",
            "Which companies don't have a website?",
            "What is the average salary by department?"
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
