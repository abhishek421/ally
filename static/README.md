# Admin Panel - Quick Start Guide

## Accessing the Admin Panel

Once your application is running, access the admin panel at:

```
http://localhost:8000/admin
```

## Features

### 1. Tool Tester 🛠️

Test individual tools with custom parameters:

- **Select Tool**: Choose from Company, People, Email, Interaction, Group, or Workspace tools
- **Query Type**: Select the operation type (search, get_by_id, list, aggregate)
- **Workspace ID & User ID**: Required identifiers for context
- **Parameters**: Provide tool-specific parameters in JSON format

**Example Parameters:**

For **Search** operations:
```json
{
  "name": "John"
}
```

For **Get by ID** operations:
```json
{
  "id": "abc-123-def-456"
}
```

For **List** operations (Workspace):
```json
{}
```

For **Aggregate** operations (Company):
```json
{
  "status": "active"
}
```

### 2. Database Viewer 💾

Browse and inspect database records:

- **Select Table**: Choose which table to view
- **Workspace Filter**: Optionally filter by workspace ID
- **Limit**: Control how many records to display (1-100)

Available tables:
- Workspace
- Company
- People
- Interaction
- Group
- User
- Workspace Member

### 3. Statistics 📊

View database statistics and record counts:

- See total counts across all tables
- Optionally filter by workspace to see workspace-specific stats

## Common Use Cases

### Test Workspace Listing

1. Go to **Tool Tester**
2. Select Tool: **Workspace Tool**
3. Query Type: **list**
4. Enter your Workspace ID and User ID
5. Parameters: `{}`
6. Click **Run Test**

### View All Companies

1. Go to **Database Viewer**
2. Select Table: **Company**
3. Optionally enter Workspace ID to filter
4. Click **Refresh**

### Search for People by Name

1. Go to **Tool Tester**
2. Select Tool: **People Tool**
3. Query Type: **search**
4. Enter your Workspace ID and User ID
5. Parameters: `{"name": "John"}`
6. Click **Run Test**

### Check Database Stats

1. Go to **Statistics**
2. Optionally enter Workspace ID to filter
3. Click **Load Statistics**

## Tips

- The admin panel uses the same database as your main application
- All tool operations are executed in real-time
- JSON parameters must be valid JSON format
- Use browser DevTools (F12) to see network requests for debugging
- The panel auto-formats JSON responses for easy reading
