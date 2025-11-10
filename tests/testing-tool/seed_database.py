#!/usr/bin/env python3
"""
Database Seeding Script for AI Analyst CRM System
Generates realistic test data for testing the chatbot across multiple years (2023-2025)
"""

import os
import sys
from datetime import datetime, timedelta
import random
import uuid
from typing import List, Dict, Any
import psycopg2
from psycopg2.extras import execute_values
from faker import Faker

# Initialize Faker with seed for reproducibility
fake = Faker()
Faker.seed(42)
random.seed(42)

# Database connection string - set via environment variable
DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql://postgres:postgres@localhost:5433/softsync?schema=public')

# Configuration
NUM_WORKSPACES = 2
NUM_USERS_PER_WORKSPACE = 3
NUM_COMPANIES = 50
NUM_PEOPLE = 150
NUM_INTERACTIONS_PER_PERSON = 15
NUM_GROUPS = 10
NUM_DEALS = 30

# Date ranges
START_DATE = datetime(2023, 1, 1)
END_DATE = datetime(2025, 11, 9)

# Industry sectors for companies
INDUSTRIES = [
    'Technology', 'Healthcare', 'Finance', 'Retail', 'Manufacturing',
    'Education', 'Real Estate', 'Consulting', 'Media', 'Hospitality'
]

# Job titles
JOB_TITLES = [
    'CEO', 'CTO', 'CFO', 'VP of Sales', 'VP of Marketing', 'Sales Manager',
    'Marketing Manager', 'Product Manager', 'Engineering Manager', 'Account Executive',
    'Business Development Manager', 'Customer Success Manager', 'Director of Operations'
]

# Email types
EMAIL_PROVIDERS = ['gmail.com', 'outlook.com', 'yahoo.com', 'company.com']

# Interaction subjects
EMAIL_SUBJECTS = [
    'Follow-up on our meeting',
    'Proposal for Q{quarter} {year}',
    'Contract renewal discussion',
    'Product demo request',
    'Pricing inquiry',
    'Partnership opportunity',
    'Technical support needed',
    'Feature request',
    'Quarterly business review',
    'Invoice payment reminder'
]

MEETING_SUBJECTS = [
    'Discovery call',
    'Product demonstration',
    'Contract negotiation',
    'Quarterly review meeting',
    'Strategy planning session',
    'Technical implementation review'
]


class DatabaseSeeder:
    def __init__(self, connection_string: str):
        self.conn = psycopg2.connect(connection_string)
        self.cursor = self.conn.cursor()
        self.data_cache = {
            'workspaces': [],
            'users': [],
            'companies': [],
            'people': [],
            'groups': [],
            'columns': [],
            'deals': []
        }
    
    def close(self):
        self.cursor.close()
        self.conn.close()
    
    def commit(self):
        self.conn.commit()
    
    def generate_uuid(self) -> str:
        return str(uuid.uuid4())
    
    def random_date(self, start: datetime, end: datetime) -> datetime:
        """Generate random datetime between start and end"""
        delta = end - start
        random_days = random.randint(0, delta.days)
        random_seconds = random.randint(0, 86400)
        return start + timedelta(days=random_days, seconds=random_seconds)
    
    def seed_workspaces(self):
        """Create test workspaces"""
        print("Creating workspaces...")
        workspaces = []
        
        for i in range(NUM_WORKSPACES):
            workspace_id = self.generate_uuid()
            workspace = {
                'id': workspace_id,
                'name': f'{fake.company()} Workspace',
                'createdAt': START_DATE,
                'updatedAt': datetime.now()
            }
            workspaces.append(workspace)
        
        query = """
            INSERT INTO workspace (id, name, "createdAt", "updatedAt")
            VALUES %s
        """
        values = [(w['id'], w['name'], w['createdAt'], w['updatedAt']) for w in workspaces]
        execute_values(self.cursor, query, values)
        
        self.data_cache['workspaces'] = workspaces
        print(f"Created {len(workspaces)} workspaces")
    
    def seed_users(self):
        """Create test users"""
        print("Creating users...")
        users = []
        
        for workspace in self.data_cache['workspaces']:
            for i in range(NUM_USERS_PER_WORKSPACE):
                user_id = self.generate_uuid()
                first_name = fake.first_name()
                last_name = fake.last_name()
                email = f"{first_name.lower()}.{last_name.lower()}@test.com"
                
                user = {
                    'id': user_id,
                    'email': email,
                    'firstName': first_name,
                    'lastName': last_name,
                    'cognitoSub': self.generate_uuid(),
                    'createdAt': START_DATE,
                    'updatedAt': datetime.now(),
                    'workspaceId': workspace['id']
                }
                users.append(user)
        
        # Insert users
        query = """
            INSERT INTO "user" (id, email, "firstName", "lastName", "cognitoSub", "createdAt", "updatedAt")
            VALUES %s
        """
        values = [(u['id'], u['email'], u['firstName'], u['lastName'], u['cognitoSub'], 
                   u['createdAt'], u['updatedAt']) for u in users]
        execute_values(self.cursor, query, values)
        
        # Insert workspace members
        print("Creating workspace members...")
        workspace_members = []
        for user in users:
            member = {
                'id': self.generate_uuid(),
                'userId': user['id'],
                'workspaceId': user['workspaceId'],
                'role': 'ADMIN' if users.index(user) % NUM_USERS_PER_WORKSPACE == 0 else 'MEMBER',
                'createdAt': START_DATE,
                'updatedAt': datetime.now()
            }
            workspace_members.append(member)
        
        query = """
            INSERT INTO "workspaceMember" (id, "userId", "workspaceId", role, "createdAt", "updatedAt")
            VALUES %s
        """
        values = [(m['id'], m['userId'], m['workspaceId'], m['role'], 
                   m['createdAt'], m['updatedAt']) for m in workspace_members]
        execute_values(self.cursor, query, values)
        
        self.data_cache['users'] = users
        print(f"Created {len(users)} users and workspace members")
    
    def seed_groups(self):
        """Create test groups"""
        print("Creating groups...")
        groups = []
        
        for workspace in self.data_cache['workspaces']:
            workspace_users = [u for u in self.data_cache['users'] if u['workspaceId'] == workspace['id']]
            creator = workspace_users[0]
            
            group_names = [
                'Enterprise Customers', 'SMB Leads', 'Partners', 'Hot Prospects',
                'Churned Accounts', 'Trial Users', 'VIP Clients', 'Cold Leads',
                'Marketing Qualified', 'Sales Qualified'
            ]
            
            for i, name in enumerate(group_names[:NUM_GROUPS // NUM_WORKSPACES]):
                group_id = self.generate_uuid()
                group = {
                    'id': group_id,
                    'name': name,
                    'workspaceId': workspace['id'],
                    'type': random.choice(['COMPANY', 'PEOPLE']),
                    'isPrivate': random.choice([True, False]),
                    'createdBy': creator['id'],
                    'createdAt': self.random_date(START_DATE, END_DATE),
                    'updatedAt': datetime.now(),
                    'isDeleted': False,
                    'isFavourite': i < 3,
                    'isCollapse': True,
                    'favouriteOrder': i if i < 3 else 0,
                    'privateOrder': 0,
                    'publicOrder': 0
                }
                groups.append(group)
        
        query = """
            INSERT INTO "group" (id, name, "workspaceId", type, "isPrivate", "createdBy", 
                                "createdAt", "updatedAt", "isDeleted", "isFavourite", 
                                "isCollapse", "favouriteOrder", "privateOrder", "publicOrder")
            VALUES %s
        """
        values = [(g['id'], g['name'], g['workspaceId'], g['type'], g['isPrivate'], 
                   g['createdBy'], g['createdAt'], g['updatedAt'], g['isDeleted'], 
                   g['isFavourite'], g['isCollapse'], g['favouriteOrder'], 
                   g['privateOrder'], g['publicOrder']) for g in groups]
        execute_values(self.cursor, query, values)
        
        self.data_cache['groups'] = groups
        print(f"Created {len(groups)} groups")
    
    def seed_companies(self):
        """Create test companies"""
        print("Creating companies...")
        companies = []
        
        for workspace in self.data_cache['workspaces']:
            workspace_users = [u for u in self.data_cache['users'] if u['workspaceId'] == workspace['id']]
            
            for i in range(NUM_COMPANIES // NUM_WORKSPACES):
                company_id = self.generate_uuid()
                created_at = self.random_date(START_DATE, END_DATE)
                
                company = {
                    'id': company_id,
                    'name': fake.company(),
                    'description': f"{random.choice(INDUSTRIES)} company specializing in {fake.bs()}",
                    'workspaceId': workspace['id'],
                    'createdBy': random.choice(workspace_users)['id'],
                    'privacyLevel': random.choice(['PRIVATE', 'PUBLIC']),
                    'createdAt': created_at,
                    'updatedAt': self.random_date(created_at, END_DATE)
                }
                companies.append(company)
        
        query = """
            INSERT INTO company (id, name, description, "workspaceId", "createdBy", 
                               "privacyLevel", "createdAt", "updatedAt")
            VALUES %s
        """
        values = [(c['id'], c['name'], c['description'], c['workspaceId'], 
                   c['createdBy'], c['privacyLevel'], c['createdAt'], c['updatedAt']) 
                  for c in companies]
        execute_values(self.cursor, query, values)
        
        self.data_cache['companies'] = companies
        print(f"Created {len(companies)} companies")
        
        # Add company addresses, phone numbers, emails, and URLs
        self.seed_company_contact_info()
    
    def seed_company_contact_info(self):
        """Add contact information for companies"""
        print("Adding company contact information...")
        
        # Addresses
        addresses = []
        for company in self.data_cache['companies']:
            address_id = self.generate_uuid()
            addresses.append({
                'id': address_id,
                'value': fake.address().replace('\n', ', '),
                'type': 'work',
                'isPrimary': True,
                'companyId': company['id'],
                'createdAt': company['createdAt'],
                'updatedAt': company['updatedAt']
            })
        
        query = """
            INSERT INTO address (id, value, type, "isPrimary", "companyId", "createdAt", "updatedAt")
            VALUES %s
        """
        values = [(a['id'], a['value'], a['type'], a['isPrimary'], a['companyId'], 
                   a['createdAt'], a['updatedAt']) for a in addresses]
        execute_values(self.cursor, query, values)
        
        # Phone numbers
        phone_numbers = []
        for company in self.data_cache['companies']:
            phone_id = self.generate_uuid()
            phone_numbers.append({
                'id': phone_id,
                'value': fake.phone_number(),
                'type': 'work',
                'isPrimary': True,
                'companyId': company['id'],
                'createdAt': company['createdAt'],
                'updatedAt': company['updatedAt']
            })
        
        query = """
            INSERT INTO "phoneNumber" (id, value, type, "isPrimary", "companyId", "createdAt", "updatedAt")
            VALUES %s
        """
        values = [(p['id'], p['value'], p['type'], p['isPrimary'], p['companyId'], 
                   p['createdAt'], p['updatedAt']) for p in phone_numbers]
        execute_values(self.cursor, query, values)
        
        # Emails
        emails = []
        for company in self.data_cache['companies']:
            email_id = self.generate_uuid()
            company_name = company['name'].lower().replace(' ', '').replace(',', '')[:20]
            emails.append({
                'id': email_id,
                'value': f"info@{company_name}.com",
                'type': 'work',
                'isPrimary': True,
                'verified': random.choice([True, False]),
                'companyId': company['id'],
                'createdAt': company['createdAt'],
                'updatedAt': company['updatedAt']
            })
        
        query = """
            INSERT INTO email (id, value, type, "isPrimary", verified, "companyId", "createdAt", "updatedAt")
            VALUES %s
        """
        values = [(e['id'], e['value'], e['type'], e['isPrimary'], e['verified'], 
                   e['companyId'], e['createdAt'], e['updatedAt']) for e in emails]
        execute_values(self.cursor, query, values)
        
        # URLs
        urls = []
        for company in self.data_cache['companies']:
            url_id = self.generate_uuid()
            company_name = company['name'].lower().replace(' ', '').replace(',', '')[:20]
            urls.append({
                'id': url_id,
                'label': 'Website',
                'value': f"https://www.{company_name}.com",
                'isPrimary': True,
                'companyId': company['id'],
                'createdAt': company['createdAt'],
                'updatedAt': company['updatedAt']
            })
        
        query = """
            INSERT INTO url (id, label, value, "isPrimary", "companyId", "createdAt", "updatedAt")
            VALUES %s
        """
        values = [(u['id'], u['label'], u['value'], u['isPrimary'], u['companyId'], 
                   u['createdAt'], u['updatedAt']) for u in urls]
        execute_values(self.cursor, query, values)
        
        print(f"Added contact info for {len(self.data_cache['companies'])} companies")
    
    def seed_people(self):
        """Create test people/contacts"""
        print("Creating people...")
        people = []
        
        for workspace in self.data_cache['workspaces']:
            workspace_users = [u for u in self.data_cache['users'] if u['workspaceId'] == workspace['id']]
            workspace_companies = [c for c in self.data_cache['companies'] if c['workspaceId'] == workspace['id']]
            
            for i in range(NUM_PEOPLE // NUM_WORKSPACES):
                person_id = self.generate_uuid()
                first_name = fake.first_name()
                last_name = fake.last_name()
                created_at = self.random_date(START_DATE, END_DATE)
                
                person = {
                    'id': person_id,
                    'firstName': first_name,
                    'lastName': last_name,
                    'jobTitle': random.choice(JOB_TITLES),
                    'description': fake.text(max_nb_chars=200),
                    'workspaceId': workspace['id'],
                    'createdBy': random.choice(workspace_users)['id'],
                    'privacyLevel': random.choice(['PRIVATE', 'PUBLIC']),
                    'createdAt': created_at,
                    'updatedAt': self.random_date(created_at, END_DATE),
                    'companyId': random.choice(workspace_companies)['id'] if random.random() > 0.2 else None
                }
                people.append(person)
        
        query = """
            INSERT INTO people (id, "firstName", "lastName", "jobTitle", description, 
                              "workspaceId", "createdBy", "privacyLevel", "createdAt", "updatedAt")
            VALUES %s
        """
        values = [(p['id'], p['firstName'], p['lastName'], p['jobTitle'], p['description'],
                   p['workspaceId'], p['createdBy'], p['privacyLevel'], p['createdAt'], 
                   p['updatedAt']) for p in people]
        execute_values(self.cursor, query, values)
        
        self.data_cache['people'] = people
        print(f"Created {len(people)} people")
        
        # Add people contact info and metadata
        self.seed_people_contact_info()
        self.seed_metadata()
    
    def seed_people_contact_info(self):
        """Add contact information for people"""
        print("Adding people contact information...")
        
        # Emails
        emails = []
        for person in self.data_cache['people']:
            # Primary email
            email_id = self.generate_uuid()
            emails.append({
                'id': email_id,
                'value': f"{person['firstName'].lower()}.{person['lastName'].lower()}@{random.choice(EMAIL_PROVIDERS)}",
                'type': 'work',
                'isPrimary': True,
                'verified': random.choice([True, False]),
                'personId': person['id'],
                'createdAt': person['createdAt'],
                'updatedAt': person['updatedAt']
            })
            
            # Some people have secondary emails
            if random.random() > 0.7:
                email_id2 = self.generate_uuid()
                emails.append({
                    'id': email_id2,
                    'value': f"{person['firstName'].lower()}{random.randint(1, 99)}@{random.choice(EMAIL_PROVIDERS)}",
                    'type': 'personal',
                    'isPrimary': False,
                    'verified': random.choice([True, False]),
                    'personId': person['id'],
                    'createdAt': person['createdAt'],
                    'updatedAt': person['updatedAt']
                })
        
        query = """
            INSERT INTO email (id, value, type, "isPrimary", verified, "personId", "createdAt", "updatedAt")
            VALUES %s
        """
        values = [(e['id'], e['value'], e['type'], e['isPrimary'], e['verified'], 
                   e['personId'], e['createdAt'], e['updatedAt']) for e in emails]
        execute_values(self.cursor, query, values)
        
        # Phone numbers
        phone_numbers = []
        for person in self.data_cache['people']:
            phone_id = self.generate_uuid()
            phone_numbers.append({
                'id': phone_id,
                'value': fake.phone_number(),
                'type': random.choice(['mobile', 'work', 'home']),
                'isPrimary': True,
                'personId': person['id'],
                'createdAt': person['createdAt'],
                'updatedAt': person['updatedAt']
            })
        
        query = """
            INSERT INTO "phoneNumber" (id, value, type, "isPrimary", "personId", "createdAt", "updatedAt")
            VALUES %s
        """
        values = [(p['id'], p['value'], p['type'], p['isPrimary'], p['personId'], 
                   p['createdAt'], p['updatedAt']) for p in phone_numbers]
        execute_values(self.cursor, query, values)
        
        # Addresses
        addresses = []
        for person in self.data_cache['people']:
            if random.random() > 0.5:  # 50% of people have addresses
                address_id = self.generate_uuid()
                addresses.append({
                    'id': address_id,
                    'value': fake.address().replace('\n', ', '),
                    'type': random.choice(['home', 'work']),
                    'isPrimary': True,
                    'personId': person['id'],
                    'createdAt': person['createdAt'],
                    'updatedAt': person['updatedAt']
                })
        
        if addresses:
            query = """
                INSERT INTO address (id, value, type, "isPrimary", "personId", "createdAt", "updatedAt")
                VALUES %s
            """
            values = [(a['id'], a['value'], a['type'], a['isPrimary'], a['personId'], 
                       a['createdAt'], a['updatedAt']) for a in addresses]
            execute_values(self.cursor, query, values)
        
        print(f"Added contact info for {len(self.data_cache['people'])} people")
    
    def seed_metadata(self):
        """Create metadata linking people to companies"""
        print("Creating people-company metadata...")
        metadata = []
        
        for person in self.data_cache['people']:
            if person['companyId']:
                metadata_id = self.generate_uuid()
                metadata.append({
                    'id': metadata_id,
                    'peopleId': person['id'],
                    'companyId': person['companyId'],
                    'isPeoplePrimary': True,
                    'isCompanyPrimary': random.choice([True, False]),
                    'createdAt': person['createdAt'],
                    'updatedAt': person['updatedAt']
                })
        
        if metadata:
            query = """
                INSERT INTO "metaData" (id, "peopleId", "companyId", "isPeoplePrimary", 
                                       "isCompanyPrimary", "createdAt", "updatedAt")
                VALUES %s
            """
            values = [(m['id'], m['peopleId'], m['companyId'], m['isPeoplePrimary'], 
                       m['isCompanyPrimary'], m['createdAt'], m['updatedAt']) for m in metadata]
            execute_values(self.cursor, query, values)
        
        print(f"Created {len(metadata)} metadata records")
    
    def seed_interactions(self):
        """Create test interactions (emails, meetings, calls, notes)"""
        print("Creating interactions...")
        interactions = []
        
        interaction_types = ['EMAIL', 'MEETING', 'CALL', 'NOTE']
        directions = ['INBOUND', 'OUTBOUND']
        
        for person in self.data_cache['people']:
            workspace_users = [u for u in self.data_cache['users'] 
                             if u['workspaceId'] == person['workspaceId']]
            
            # Generate interactions for this person
            num_interactions = random.randint(5, NUM_INTERACTIONS_PER_PERSON)
            
            for _ in range(num_interactions):
                interaction_id = self.generate_uuid()
                interaction_type = random.choice(interaction_types)
                interaction_date = self.random_date(person['createdAt'], END_DATE)
                
                # Generate appropriate subject and content
                if interaction_type == 'EMAIL':
                    quarter = (interaction_date.month - 1) // 3 + 1
                    subject = random.choice(EMAIL_SUBJECTS).format(
                        quarter=quarter, 
                        year=interaction_date.year
                    )
                    content = fake.text(max_nb_chars=500)
                elif interaction_type == 'MEETING':
                    subject = random.choice(MEETING_SUBJECTS)
                    content = fake.text(max_nb_chars=300)
                elif interaction_type == 'CALL':
                    subject = f"Phone call with {person['firstName']}"
                    content = fake.text(max_nb_chars=200)
                else:  # NOTE
                    subject = "Internal note"
                    content = fake.text(max_nb_chars=150)
                
                interaction = {
                    'id': interaction_id,
                    'type': interaction_type,
                    'direction': random.choice(directions),
                    'subject': subject,
                    'content': content,
                    'date': interaction_date,
                    'createdById': random.choice(workspace_users)['id'],
                    'peopleId': person['id'],
                    'companyId': person['companyId'],
                    'workspaceId': person['workspaceId'],
                    'createdAt': interaction_date,
                    'updatedAt': interaction_date,
                    'isDeleted': False
                }
                interactions.append(interaction)
        
        # Batch insert interactions
        batch_size = 1000
        for i in range(0, len(interactions), batch_size):
            batch = interactions[i:i + batch_size]
            query = """
                INSERT INTO interaction (id, type, direction, subject, content, date, 
                                       "createdById", "peopleId", "companyId", "workspaceId",
                                       "createdAt", "updatedAt", "isDeleted")
                VALUES %s
            """
            values = [(int_['id'], int_['type'], int_['direction'], int_['subject'], 
                       int_['content'], int_['date'], int_['createdById'], int_['peopleId'],
                       int_['companyId'], int_['workspaceId'], int_['createdAt'], 
                       int_['updatedAt'], int_['isDeleted']) for int_ in batch]
            execute_values(self.cursor, query, values)
            print(f"Inserted {min(i + batch_size, len(interactions))}/{len(interactions)} interactions")
        
        print(f"Created {len(interactions)} interactions")
    
    def seed_columns_and_deals(self):
        """Create custom columns and deals"""
        print("Creating columns and deals...")
        
        # Create deal columns for each company group
        company_groups = [g for g in self.data_cache['groups'] if g['type'] == 'COMPANY']
        
        columns = []
        for group in company_groups:
            # Pipeline column
            column_id = self.generate_uuid()
            column = {
                'id': column_id,
                'groupId': group['id'],
                'name': 'Sales Pipeline',
                'description': 'Track deal progress through sales stages',
                'dataType': 'SELECT',
                'type': 'DEAL',
                'isDefault': False,
                'isDeleted': False,
                'createdAt': group['createdAt'],
                'updatedAt': datetime.now(),
                'selectOptions': ['Lead', 'Qualified', 'Proposal', 'Negotiation', 'Closed Won', 'Closed Lost']
            }
            columns.append(column)
        
        if columns:
            query = """
                INSERT INTO column (id, "groupId", name, description, "dataType", type, 
                                  "isDefault", "isDeleted", "createdAt", "updatedAt", "selectOptions")
                VALUES %s
            """
            values = [(c['id'], c['groupId'], c['name'], c['description'], c['dataType'], 
                       c['type'], c['isDefault'], c['isDeleted'], c['createdAt'], 
                       c['updatedAt'], psycopg2.extras.Json(c['selectOptions'])) for c in columns]
            execute_values(self.cursor, query, values)
            
            self.data_cache['columns'] = columns
        
        # Create deals
        deals = []
        for column in columns:
            for i in range(NUM_DEALS // len(columns)):
                deal_id = self.generate_uuid()
                created_at = self.random_date(START_DATE, END_DATE)
                
                deal = {
                    'id': deal_id,
                    'name': f"Deal - {fake.company()} - ${random.randint(10, 500)}K",
                    'columnId': column['id'],
                    'createdAt': created_at,
                    'updatedAt': self.random_date(created_at, END_DATE),
                    'createdBy': random.choice([u['id'] for u in self.data_cache['users']])
                }
                deals.append(deal)
        
        if deals:
            query = """
                INSERT INTO deal (id, name, "columnId", "createdAt", "updatedAt", "createdBy")
                VALUES %s
            """
            values = [(d['id'], d['name'], d['columnId'], d['createdAt'], 
                       d['updatedAt'], d['createdBy']) for d in deals]
            execute_values(self.cursor, query, values)
            
            self.data_cache['deals'] = deals
            print(f"Created {len(columns)} columns and {len(deals)} deals")
    
    def seed_group_associations(self):
        """Associate companies and people with groups"""
        print("Creating group associations...")
        
        # Group companies
        group_companies = []
        company_groups = [g for g in self.data_cache['groups'] if g['type'] == 'COMPANY']
        
        for group in company_groups:
            workspace_companies = [c for c in self.data_cache['companies'] 
                                 if c['workspaceId'] == group['workspaceId']]
            # Add 5-15 companies to each group
            num_companies = min(random.randint(5, 15), len(workspace_companies))
            selected_companies = random.sample(workspace_companies, num_companies)
            
            for company in selected_companies:
                group_companies.append({
                    'groupId': group['id'],
                    'companyId': company['id'],
                    'addedBy': group['createdBy'],
                    'addedAt': self.random_date(max(group['createdAt'], company['createdAt']), END_DATE)
                })
        
        if group_companies:
            query = """
                INSERT INTO "groupCompany" ("groupId", "companyId", "addedBy", "addedAt")
                VALUES %s
            """
            values = [(gc['groupId'], gc['companyId'], gc['addedBy'], gc['addedAt']) 
                      for gc in group_companies]
            execute_values(self.cursor, query, values)
            print(f"Created {len(group_companies)} group-company associations")
        
        # Group people
        group_people = []
        people_groups = [g for g in self.data_cache['groups'] if g['type'] == 'PEOPLE']
        
        for group in people_groups:
            workspace_people = [p for p in self.data_cache['people'] 
                              if p['workspaceId'] == group['workspaceId']]
            # Add 10-30 people to each group
            num_people = min(random.randint(10, 30), len(workspace_people))
            selected_people = random.sample(workspace_people, num_people)
            
            for person in selected_people:
                group_people.append({
                    'groupId': group['id'],
                    'peopleId': person['id'],
                    'addedBy': group['createdBy'],
                    'addedAt': self.random_date(max(group['createdAt'], person['createdAt']), END_DATE)
                })
        
        if group_people:
            query = """
                INSERT INTO "groupPeople" ("groupId", "peopleId", "addedBy", "addedAt")
                VALUES %s
            """
            values = [(gp['groupId'], gp['peopleId'], gp['addedBy'], gp['addedAt']) 
                      for gp in group_people]
            execute_values(self.cursor, query, values)
            print(f"Created {len(group_people)} group-people associations")
    
    def seed_conversations(self):
        """Create AI conversation history"""
        print("Creating AI conversations...")
        
        conversations = []
        for workspace in self.data_cache['workspaces']:
            workspace_users = [u for u in self.data_cache['users'] 
                             if u['workspaceId'] == workspace['id']]
            
            # Create 10-15 conversations per workspace
            for _ in range(random.randint(10, 15)):
                conv_id = self.generate_uuid()
                created_at = self.random_date(START_DATE, END_DATE)
                
                conversation = {
                    'id': conv_id,
                    'workspaceId': workspace['id'],
                    'userId': random.choice(workspace_users)['id'],
                    'title': random.choice([
                        'Q4 Revenue Analysis',
                        'Top Performing Sales Reps',
                        'Pipeline Health Check',
                        'Customer Engagement Report',
                        'Monthly Activity Summary'
                    ]),
                    'createdAt': created_at,
                    'updatedAt': self.random_date(created_at, END_DATE)
                }
                conversations.append(conversation)
        
        if conversations:
            query = """
                INSERT INTO conversation (id, "workspaceId", "userId", title, "createdAt", "updatedAt")
                VALUES %s
            """
            values = [(c['id'], c['workspaceId'], c['userId'], c['title'], 
                       c['createdAt'], c['updatedAt']) for c in conversations]
            execute_values(self.cursor, query, values)
            print(f"Created {len(conversations)} conversations")
    
    def run(self):
        """Run all seeding operations"""
        try:
            print("Starting database seeding...")
            print(f"Date range: {START_DATE.date()} to {END_DATE.date()}")
            print("-" * 50)
            
            self.seed_workspaces()
            self.commit()
            
            self.seed_users()
            self.commit()
            
            self.seed_groups()
            self.commit()
            
            self.seed_companies()
            self.commit()
            
            self.seed_people()
            self.commit()
            
            self.seed_interactions()
            self.commit()
            
            self.seed_columns_and_deals()
            self.commit()
            
            self.seed_group_associations()
            self.commit()
            
            self.seed_conversations()
            self.commit()
            
            print("-" * 50)
            print("Database seeding completed successfully!")
            print("\nSummary:")
            print(f"  - Workspaces: {len(self.data_cache['workspaces'])}")
            print(f"  - Users: {len(self.data_cache['users'])}")
            print(f"  - Groups: {len(self.data_cache['groups'])}")
            print(f"  - Companies: {len(self.data_cache['companies'])}")
            print(f"  - People: {len(self.data_cache['people'])}")
            print(f"  - Columns: {len(self.data_cache['columns'])}")
            print(f"  - Deals: {len(self.data_cache['deals'])}")
            print(f"\nYou can now test the AI Analyst chatbot with queries like:")
            print("  - 'Show me all interactions from last month'")
            print("  - 'Who are the top 10 companies by interaction count?'")
            print("  - 'List all deals created in Q3 2024'")
            print("  - 'Show me people working at [company name]'")
            print("  - 'What's my sales pipeline looking like?'")
            
        except Exception as e:
            print(f"Error during seeding: {e}")
            self.conn.rollback()
            raise
        finally:
            self.close()


def main():
    """Main entry point"""
    if not DATABASE_URL or DATABASE_URL == 'postgresql://user:password@localhost:5432/dbname':
        print("Error: Please set the DATABASE_URL environment variable")
        print("Example: export DATABASE_URL='postgresql://user:pass@host:5432/dbname'")
        sys.exit(1)
    
    print(f"Connecting to database...")
    seeder = DatabaseSeeder(DATABASE_URL)
    seeder.run()


if __name__ == '__main__':
    main()
