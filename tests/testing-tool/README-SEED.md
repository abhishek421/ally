# Database Seeding Script for AI Analyst CRM

This script generates realistic test data for the AI Analyst chatbot system, spanning from 2023 to 2025.

## What Data Gets Created

The script generates:

- **2 Workspaces** - Different organizations
- **6 Users** (3 per workspace) - Team members with admin/member roles
- **10 Groups** - Collections of companies or people (e.g., "Enterprise Customers", "Hot Prospects")
- **50 Companies** - With full contact information (addresses, phone numbers, emails, URLs)
- **150 People** - Contacts with emails, phone numbers, job titles, linked to companies
- **~2,250 Interactions** - Emails, meetings, calls, and notes spread across 2023-2025
- **30 Deals** - Sales pipeline opportunities
- **Custom Columns** - Deal pipeline stages
- **Group Associations** - Companies and people organized into groups
- **AI Conversations** - Sample conversation history

## Installation

1. Install Python dependencies:
```bash
pip install -r requirements-seed.txt
```

## Usage

1. Set your PostgreSQL database URL:
```bash
export DATABASE_URL='postgresql://username:password@host:port/database'
```

Example:
```bash
export DATABASE_URL='postgresql://admin:mypassword@localhost:5432/analyst_db'
```

2. Run the seeding script:
```bash
python seed_database.py
```

The script will:
- Connect to your database
- Generate realistic data with proper relationships
- Insert data in batches for efficiency
- Show progress for each step
- Display a summary when complete

## Expected Output

```
Starting database seeding...
Date range: 2023-01-01 to 2025-11-09
--------------------------------------------------
Creating workspaces...
Created 2 workspaces
Creating users...
Creating workspace members...
Created 6 users and workspace members
Creating groups...
Created 10 groups
Creating companies...
Created 50 companies
Adding company contact information...
Added contact info for 50 companies
Creating people...
Created 150 people
Adding people contact information...
Added contact info for 150 people
Creating people-company metadata...
Created 120 metadata records
Creating interactions...
Inserted 1000/2250 interactions
Inserted 2000/2250 interactions
Inserted 2250/2250 interactions
Created 2250 interactions
Creating columns and deals...
Created 5 columns and 30 deals
Creating group associations...
Created 50 group-company associations
Created 150 group-people associations
Creating AI conversations...
Created 25 conversations
--------------------------------------------------
Database seeding completed successfully!

Summary:
  - Workspaces: 2
  - Users: 6
  - Groups: 10
  - Companies: 50
  - People: 150
  - Columns: 5
  - Deals: 30

You can now test the AI Analyst chatbot with queries like:
  - 'Show me all interactions from last month'
  - 'Who are the top 10 companies by interaction count?'
  - 'List all deals created in Q3 2024'
  - 'Show me people working at [company name]'
  - 'What's my sales pipeline looking like?'
```

## Sample Test Queries

Once the data is seeded, you can test the AI Analyst with queries like:

### Temporal Queries
- "Show me all interactions from last month"
- "What happened in Q3 2024?"
- "List companies created in 2023"
- "How many emails did we send in January 2025?"

### Aggregation Queries
- "Who are the top 10 companies by interaction count?"
- "Which sales rep has the most interactions?"
- "Show me the most active contacts"
- "What's the total value of all deals?"

### Filtering Queries
- "Show me all people working at [company name]"
- "List all VP-level contacts"
- "Find all deals in the negotiation stage"
- "Show me all inbound emails"

### Analytical Queries
- "What's my sales pipeline looking like?"
- "Show me deal conversion rates by stage"
- "Which groups have the most companies?"
- "Analyze interaction patterns over the last year"

## Data Characteristics

- **Date Range**: January 1, 2023 to November 9, 2025 (current date)
- **Realistic Names**: Uses Faker library for realistic company and person names
- **Proper Relationships**: 
  - People are linked to companies via metadata
  - Interactions are linked to both people and companies
  - Deals are organized in pipeline columns
  - Groups contain relevant companies and people
- **Contact Info**: All companies and people have emails, phone numbers, addresses
- **Temporal Distribution**: Data is randomly distributed across the date range
- **Privacy Levels**: Mix of private and public records
- **Interaction Types**: Emails, meetings, calls, and notes with realistic subjects

## Customization

You can modify the constants at the top of `seed_database.py` to adjust:

```python
NUM_WORKSPACES = 2
NUM_USERS_PER_WORKSPACE = 3
NUM_COMPANIES = 50
NUM_PEOPLE = 150
NUM_INTERACTIONS_PER_PERSON = 15
NUM_GROUPS = 10
NUM_DEALS = 30
```

## Troubleshooting

### "Error: Please set the DATABASE_URL environment variable"
Make sure you've exported the DATABASE_URL with your actual PostgreSQL connection string.

### Connection errors
Verify:
- Database server is running
- Credentials are correct
- Database exists
- Network connectivity (if remote database)

### Permission errors
Ensure your database user has INSERT permissions on all tables.

### Duplicate key errors
If you're re-running the script, you may need to clear existing data first or drop/recreate the database.

## Notes

- The script uses deterministic random seeds (42) for reproducibility
- UUIDs are generated using Python's uuid4 for uniqueness
- Data is committed in batches for better performance
- Foreign key relationships are respected during insertion order
- The script handles large datasets efficiently with batch inserts
