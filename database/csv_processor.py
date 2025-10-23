import pandas as pd
import io
from typing import List, Dict, Any, Optional
from datetime import datetime
from sqlalchemy import text
from database.db_setup import get_db_manager


class CSVProcessor:
    """Handles CSV file processing and data insertion"""
    
    def __init__(self):
        self.db_manager = get_db_manager()
    
    def process_companies_csv(self, csv_content: str) -> bool:
        """Process companies CSV data and insert into database"""
        try:
            # Read CSV from string content
            df = pd.read_csv(io.StringIO(csv_content))
            
            # Map CSV columns to database columns
            column_mapping = {
                'Customer Id': 'customer_id',
                'First Name': 'first_name',
                'Last Name': 'last_name',
                'Company': 'company',
                'City': 'city',
                'Country': 'country',
                'Phone 1': 'phone_1',
                'Phone 2': 'phone_2',
                'Email': 'email',
                'Subscription Date': 'subscription_date',
                'Website': 'website'
            }
            
            # Rename columns to match database schema
            df = df.rename(columns=column_mapping)
            
            # Remove the Index column if it exists
            if 'Index' in df.columns:
                df = df.drop('Index', axis=1)
            
            # Convert date columns
            if 'subscription_date' in df.columns:
                df['subscription_date'] = pd.to_datetime(df['subscription_date'], errors='coerce')
            
            # Prepare data for insertion
            companies_data = df.to_dict('records')
            
            # Insert data
            return self._insert_companies_data(companies_data)
            
        except Exception as e:
            print(f"Error processing companies CSV: {e}")
            return False
    
    def process_people_csv(self, csv_content: str) -> bool:
        """Process people CSV data and insert into database"""
        try:
            # Read CSV from string content
            df = pd.read_csv(io.StringIO(csv_content))
            
            # Map CSV columns to database columns
            column_mapping = {
                'User Id': 'user_id',
                'First Name': 'first_name',
                'Last Name': 'last_name',
                'Sex': 'sex',
                'Email': 'email',
                'Phone': 'phone',
                'Date of birth': 'date_of_birth',
                'Job Title': 'job_title'
            }
            
            # Rename columns to match database schema
            df = df.rename(columns=column_mapping)
            
            # Remove the Index column if it exists
            if 'Index' in df.columns:
                df = df.drop('Index', axis=1)
            
            # Convert date columns
            if 'date_of_birth' in df.columns:
                df['date_of_birth'] = pd.to_datetime(df['date_of_birth'], errors='coerce')
            
            # Prepare data for insertion
            people_data = df.to_dict('records')
            
            # Insert data
            return self._insert_people_data(people_data)
            
        except Exception as e:
            print(f"Error processing people CSV: {e}")
            return False
    
    def _insert_companies_data(self, companies_data: List[Dict[str, Any]]) -> bool:
        """Insert companies data into database"""
        try:
            if not self.db_manager.engine:
                print("No database engine available")
                return False
            
            if not companies_data:
                print("No companies data to insert")
                return False
            
            # Check if database has the correct schema
            try:
                # Try to query a new column to check if schema is updated
                test_result = self.db_manager.execute_query("SELECT customer_id FROM companies LIMIT 1")
            except Exception as schema_error:
                if "customer_id" in str(schema_error):
                    print("ERROR: Database schema is outdated. Please reset the database schema first.")
                    print("The database still has the old schema. Use 'Reset Database Schema' button in the UI.")
                    return False
                else:
                    # If companies table doesn't exist, that's also an issue
                    print("ERROR: Companies table doesn't exist. Please reset the database schema first.")
                    return False
            
            # Prepare insert statement - exclude 'id' as it's auto-generated
            columns = [col for col in companies_data[0].keys() if col != 'id']
            # Add required timestamp columns
            columns.extend(['created_at', 'updated_at'])
            placeholders = ", ".join([f":{col}" for col in columns])
            query = f"INSERT INTO companies ({', '.join(columns)}) VALUES ({placeholders})"
            
            with self.db_manager.engine.connect() as conn:
                for company in companies_data:
                    # Remove 'id' from company data if it exists and convert datetime to string
                    company_data = {}
                    for k, v in company.items():
                        if k != 'id':
                            if pd.isna(v):
                                company_data[k] = None
                            elif isinstance(v, datetime):
                                company_data[k] = v.isoformat()
                            elif isinstance(v, pd.Timestamp):
                                company_data[k] = v.isoformat()
                            else:
                                company_data[k] = v
                    
                    # Add required timestamp values
                    company_data['created_at'] = datetime.now().isoformat()
                    company_data['updated_at'] = datetime.now().isoformat()
                    
                    conn.execute(text(query), company_data)
                conn.commit()
            
            print(f"Successfully inserted {len(companies_data)} companies")
            return True
            
        except Exception as e:
            print(f"Error inserting companies data: {e}")
            return False
    
    def _insert_people_data(self, people_data: List[Dict[str, Any]]) -> bool:
        """Insert people data into database"""
        try:
            if not self.db_manager.engine:
                print("No database engine available")
                return False
            
            if not people_data:
                print("No people data to insert")
                return False
            
            # Check if database has the correct schema
            try:
                # Try to query a new column to check if schema is updated
                test_result = self.db_manager.execute_query("SELECT user_id FROM people LIMIT 1")
            except Exception as schema_error:
                if "user_id" in str(schema_error):
                    print("ERROR: Database schema is outdated. Please reset the database schema first.")
                    print("The database still has the old schema. Use 'Reset Database Schema' button in the UI.")
                    return False
                else:
                    # If people table doesn't exist, that's also an issue
                    print("ERROR: People table doesn't exist. Please reset the database schema first.")
                    return False
            
            # Prepare insert statement - exclude 'id' as it's auto-generated
            columns = [col for col in people_data[0].keys() if col != 'id']
            # Add required timestamp columns
            columns.extend(['created_at', 'updated_at'])
            placeholders = ", ".join([f":{col}" for col in columns])
            query = f"INSERT INTO people ({', '.join(columns)}) VALUES ({placeholders})"
            
            with self.db_manager.engine.connect() as conn:
                for person in people_data:
                    # Remove 'id' from person data if it exists and convert datetime to string
                    person_data = {}
                    for k, v in person.items():
                        if k != 'id':
                            if pd.isna(v):
                                person_data[k] = None
                            elif isinstance(v, datetime):
                                person_data[k] = v.isoformat()
                            elif isinstance(v, pd.Timestamp):
                                person_data[k] = v.isoformat()
                            else:
                                person_data[k] = v
                    
                    # Add required timestamp values
                    person_data['created_at'] = datetime.now().isoformat()
                    person_data['updated_at'] = datetime.now().isoformat()
                    
                    conn.execute(text(query), person_data)
                conn.commit()
            
            print(f"Successfully inserted {len(people_data)} people")
            return True
            
        except Exception as e:
            print(f"Error inserting people data: {e}")
            return False
    
    def clear_all_data(self) -> bool:
        """Clear all data from both tables"""
        try:
            if not self.db_manager.engine:
                return False
            
            with self.db_manager.engine.connect() as conn:
                # Clear people first (if there were foreign key constraints)
                conn.execute(text("DELETE FROM people"))
                conn.execute(text("DELETE FROM companies"))
                conn.commit()
            
            print("All data cleared successfully")
            return True
            
        except Exception as e:
            print(f"Error clearing data: {e}")
            return False
    
    def get_table_stats(self) -> Dict[str, int]:
        """Get row counts for both tables"""
        try:
            stats = {}
            
            if self.db_manager.engine:
                # Get companies count
                companies_count = self.db_manager.get_table_row_count("companies")
                stats["companies"] = companies_count if companies_count is not None else 0
                
                # Get people count
                people_count = self.db_manager.get_table_row_count("people")
                stats["people"] = people_count if people_count is not None else 0
            
            return stats
            
        except Exception as e:
            print(f"Error getting table stats: {e}")
            return {"companies": 0, "people": 0}


# Global CSV processor instance
csv_processor = CSVProcessor()


def get_csv_processor() -> CSVProcessor:
    """Get the global CSV processor instance"""
    return csv_processor
