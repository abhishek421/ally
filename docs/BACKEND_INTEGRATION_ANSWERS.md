# Analyst V2 - Backend Integration Answers

## Overview

This document provides answers to the frontend integration questions based on the current backend implementation. The backend is built with FastAPI and uses PostgreSQL (via Prisma), DynamoDB, and Redis for data storage and caching.

**Last Updated:** 2024-12-19  
**Backend Version:** 1.0.0  
**API Base Path:** `/api/v1` (current), `/api/v2` (planned for V2)

---

## 1. Authentication

### What authentication method should be used?

**Answer:** Bearer token authentication using JWT tokens from AWS Cognito.

**Current Status:**
- JWT authentication infrastructure is implemented (`api/auth/cognito.py`)
- Currently **disabled** for development/testing
- Expected to be **enabled** for production

### How should the token be passed?

**Answer:** Standard Bearer token format in the `Authorization` header:

```
Authorization: Bearer <token>
```

**Implementation Details:**
- The backend expects the token without the "Bearer " prefix (it strips it automatically)
- Format: `Bearer <jwt_token>`
- Token is verified using AWS Cognito JWKS (JSON Web Key Set)

**Current Development Mode:**
- Authentication is currently disabled
- Hence also use these headers along with token:
  - `X-Workspace-ID: <workspace_id>` (UUID format)
  - `X-User-ID: <user_id>` (UUID format)

### Do we need to handle token refresh?

**Answer:** Yes, token refresh should be handled on the frontend.

**Details:**
- Tokens have expiration times (standard JWT `exp` claim)
- Backend will return `401 Unauthorized` if token is expired
- Frontend should:
  1. Detect 401 responses
  2. Refresh the token using AWS Cognito refresh token
  3. Retry the original request with new token
- Backend does **not** handle refresh automatically

**Error Response for Expired Token:**
```json
{
  "success": false,
  "error": "Token has expired",
  "detail": "Token has expired",
  "code": "TOKEN_EXPIRED"
}
```

---

## 2. Base URL

### What is the base URL for the REST API?

**Answer:** Base URL is configurable via environment variable.

**Default:**
- Development: `http://localhost:8000`
- Production: Set via `ANALYST_AI_PORT` environment variable (default: 8000)

**API Versioning:**
- Current API: `/api/v1`
- V2 API (planned): `/api/v2`

**Full Base URL Examples:**
- Development: `http://localhost:8000/api/v2`
- Production: `https://api.yourdomain.com/api/v2`

### Is it different for development/staging/production?

**Answer:** Yes, different base URLs for different environments.

**Recommended Environment Variables:**
```typescript
// Development
NEXT_PUBLIC_ANALYT_BASE_URL=http://localhost:8000/api/v2

// Staging
NEXT_PUBLIC_ANALYT_BASE_URL=https://staging-api.yourdomain.com/api/v2

// Production
NEXT_PUBLIC_ANALYT_BASE_URL=https://api.yourdomain.com/api/v2
```

### Should we use environment variables? What are the variable names?

**Answer:** Yes, use environment variables. Recommended naming:

**Frontend Environment Variables:**
- `NEXT_PUBLIC_ANALYT_BASE_URL` (for Next.js)

---

## 3. Error Handling

### What HTTP status codes are used for different error types?

**Answer:** Standard HTTP status codes with consistent error response format.

**Status Codes:**

| Status Code | Use Case | Example |
|-------------|----------|---------|
| **200** | Success | Successful query processing |
| **400** | Bad Request | Invalid query format, missing required fields |
| **401** | Unauthorized | Missing/invalid token, expired token |
| **403** | Forbidden | Insufficient permissions (workspace/user access) |
| **404** | Not Found | Conversation not found, resource not found |
| **422** | Validation Error | Pydantic validation errors (invalid request body) |
| **500** | Internal Server Error | Unexpected server errors, processing failures |

**Additional Status Codes (may be used):**
- **429** - Rate limit exceeded (if rate limiting is implemented)
- **503** - Service Unavailable (database connection issues)

### Is the error response format consistent across all endpoints?

**Answer:** Yes, consistent error response format across all endpoints.

**Error Response Schema:**
```typescript
{
  success: false;                    // Always false for errors
  error: string;                     // Human-readable error message
  detail: string | object;           // Detailed error information
  code: string;                      // Error code for programmatic handling
  request_id?: string;               // Optional: Request ID for tracing
}
```

**Example Error Responses:**

**400 Bad Request:**
```json
{
  "success": false,
  "error": "Validation error",
  "detail": [
    {
      "loc": ["body", "query"],
      "msg": "field required",
      "type": "value_error.missing"
    }
  ],
  "code": "VALIDATION_ERROR"
}
```

**401 Unauthorized:**
```json
{
  "success": false,
  "error": "Invalid token",
  "detail": "Token verification failed: Token has expired",
  "code": "TOKEN_EXPIRED"
}
```

**500 Internal Server Error:**
```json
{
  "success": false,
  "error": "Query processing failed",
  "detail": "Database connection timeout",
  "code": "QUERY_PROCESSING_ERROR",
  "request_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

---

## 4. Rate Limiting

### Are there rate limits on the endpoints?

**Answer:** Rate limiting is **not currently implemented** but should be added for production.

**Current Status:**
- No rate limiting enforced
- Recommended for production deployment

**Future Implementation (Recommended):**
- Rate limiting per user/IP
- Different limits for different endpoints
- Headers to communicate rate limit status:
  - `X-RateLimit-Limit`: Maximum requests allowed
  - `X-RateLimit-Remaining`: Remaining requests in window
  - `X-RateLimit-Reset`: Timestamp when limit resets

**If Rate Limiting is Implemented:**
- **429 Too Many Requests** status code
- Error response will include retry-after information

---

## 5. CORS & Headers

### Are there any CORS requirements?

**Answer:** CORS is currently configured to allow all origins (development mode).

**Current Configuration:**
```python
CORSMiddleware(
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

**Production Recommendation:**
- Restrict to specific frontend origins
- Example: `allow_origins=["https://app.yourdomain.com", "https://staging.yourdomain.com"]`

**CORS Headers:**
- Backend will automatically include appropriate CORS headers
- Preflight requests (OPTIONS) are handled automatically

### Any required headers beyond Authorization?

**Answer:** Yes, workspace and user context headers (till the time jwt authentication is disabled).

**Required Headers (till authentication is disabled):**
```
Authorization: Bearer <token>
X-Workspace-ID: <workspace_uuid>
X-User-ID: <user_uuid>
Content-Type: application/json
```

**Required Headers (when authentication is enabled):**
```
Authorization: Bearer <token>
X-Workspace-ID: <workspace_uuid>
Content-Type: application/json
```
(user_id will be extracted from token claims)

### Any custom headers needed?

**Answer:** No custom headers required beyond standard ones.

**Optional Headers:**
- `X-Request-ID`: For request tracing (if you want to provide your own request ID)

---

## 6. Pagination

### For conversations list, what pagination strategy is used?

**Answer:** Offset-based pagination (to be implemented).

**Recommended Implementation:**
- Query parameters: `limit` (default: 20, max: 100) and `offset` (default: 0)
- Response includes: `total` (optional) and `hasMore` (optional)

**Example Request:**
```
GET /api/v2/analyst/conversations?limit=20&offset=0
```

**Example Response:**
```json
{
  "conversations": [...],
  "total": 150,
  "hasMore": true
}
```

### For messages within a conversation, what pagination strategy is used?

**Answer:** Offset-based pagination with message-specific parameters.

**Recommended Implementation:**
- Query parameters:
  - `messageLimit` (default: 50, max: 200)
  - `messageOffset` (default: 0)
- Messages are ordered by `timestamp` (newest first)

**Example Request:**
```
GET /api/v2/analyst/conversations/{conversationId}?messageLimit=50&messageOffset=0
```

### How should we handle large result sets?

**Answer:** Use pagination with reasonable limits.

**Best Practices:**
1. **Default Limits:**
   - Conversations list: 20 per page
   - Messages: 50 per page
2. **Maximum Limits:**
   - Conversations: 100 per page
   - Messages: 200 per page
3. **Client-Side Handling:**
   - Implement infinite scroll or "Load More" buttons
   - Cache paginated results
   - Show loading states during pagination

---

## 7. WebSocket/Streaming

### Will responses be streamed?

**Answer:** **No, streaming is not currently implemented.**

**Current Implementation:**
- Responses are returned as complete JSON objects
- No Server-Sent Events (SSE)
- No WebSocket support
- No streaming responses

**Future Consideration:**
- Streaming may be added for long-running queries
- If implemented, would likely use Server-Sent Events (SSE)
- Format would be: `text/event-stream` with incremental updates

**For Now:**
- Assume non-streaming responses
- Handle loading states on the frontend
- Consider timeout handling for long-running queries (recommended: 30-60 seconds)

---

## 8. Model Selection

### What are the available model options?

**Answer:** Three LLM providers with multiple models each. But there is no way for Frontend to configure it.

**Available Providers & Models:**

#### OpenAI
- `gpt-4` - GPT-4 (recommended for complex queries)
- `gpt-4-turbo` - GPT-4 Turbo (faster, cost-effective)
- `gpt-3.5-turbo` - GPT-3.5 Turbo (fastest, most cost-effective)

#### Anthropic
- `claude-3-opus-20240229` - Claude Opus (most capable)
- `claude-3-sonnet-20240229` - Claude Sonnet (balanced)
- `claude-3-haiku-20240307` - Claude Haiku (fastest)

#### Google Gemini
- `gemini-pro` - Gemini Pro
- `gemini-ultra` - Gemini Ultra (when available)

**Model Selection in Request:**
```typescript
{
  model?: string;  // Optional: e.g., "gpt-4", "claude-3-opus-20240229"
}
```

**Default Behavior:**
- If not specified, uses default model from configuration
- Default is configured per agent (query_optimizer, data_extractor, response_formatter)

### Are there any model-specific requirements or limitations? 

**Answer:** Yes, some considerations. But there is no way for Frontend to configure it.

**Model-Specific Considerations:**
1. **Token Limits:**
   - GPT-4: ~8,192 tokens
   - Claude Opus: ~200,000 tokens
   - Gemini Pro: ~32,768 tokens
2. **Response Time:**
   - GPT-3.5 Turbo: Fastest (~1-2 seconds)
   - GPT-4: Slower (~3-5 seconds)
   - Claude Opus: Slowest (~5-10 seconds)
3. **Cost:**
   - GPT-3.5 Turbo: Cheapest
   - GPT-4: Most expensive
   - Claude models: Mid-range

**Recommendations:**
- Use `gpt-3.5-turbo` for simple queries
- Use `gpt-4` for complex analytical queries
- Use `claude-3-opus` for nuanced reasoning

### Do different models have different response formats?

**Answer:** No, all models return the same response format. But there is no way for Frontend to configure it.

**Unified Response Format:**
- All models are abstracted through a unified interface
- Response format is consistent regardless of provider
- Formatting is handled by the ResponseFormatterAgent

---

## 9. Context & Sources

### What data sources are available?

**Answer:** Six primary data sources accessible through tools.

**Available Data Sources:**

1. **Company** (`company`)
   - Company records, domains, deals
   - Operations: Search, GetById, List, Analytics

2. **People** (`people`)
   - Contact records, job titles, emails
   - Operations: Search, GetById, List, Analytics

3. **Email** (`email`)
   - Email synchronization data (stored in DynamoDB)
   - Operations: Search, GetById, List, Analytics
   - Filters: person_id, integration_id, date ranges, direction (sent/received)

4. **Interaction** (`interaction`)
   - CRM interactions (calls, meetings, notes)
   - Operations: Search, GetById, List, Analytics
   - Types: call, meeting, note

5. **Group** (`group`)
   - Contact groups, segments, lists
   - Operations: Search, GetById, List, Analytics

6. **Workspace** (`workspace`)
   - Workspace configuration and settings
   - Operations: GetById, List

**Source Specification in Request:**
```typescript
{
  context?: {
    sources?: string[];  // e.g., ["email", "company", "people"]
  }
}
```

### How should sources be specified in the request?

**Answer:** In query only. Query will include inline entity targets.

**Example:**
```json
{
  "query": "Show me emails for {id:"abc",name:"John",entityType:"people"}",
}
```

**If Not Specified:**
- Backend will automatically determine which sources to use based on query analysis
- DataExtractorAgent uses LLM to select appropriate tools/sources

### Can multiple sources be used simultaneously?

**Answer:** Yes, multiple sources can be queried in parallel.

**Implementation:**
- Backend automatically orchestrates multiple tool calls
- Sources are queried in parallel for performance
- Results are aggregated and formatted together

**Example Query:**
```json
{
  "query": "Show me emails from {id:"abc",name:"John",entityType:"people"} of {id:"xyz",name:"Acme Corp",entityType:"company"}",
}
```

---

## 10. Note Creation

### How should note creation be handled?

**Answer:** Note creation is not implemented currently.

### What fields are required for note creation?

**Answer:** Note creation is not implemented currently.

### What is the response format for created notes?

**Answer:** Note creation is not implemented currently.

---

## 11. Conversation Management

### Can conversations be deleted?

**Answer:** Delete functionality is **not yet implemented** but should be added.

**Recommended Endpoint:**
```
DELETE /api/v2/analyst/conversations/:conversationId
```

**Expected Response:**
- **204 No Content** on success
- **404 Not Found** if conversation doesn't exist
- **403 Forbidden** if user doesn't have permission

### Can conversation titles be updated?

**Answer:** Update functionality is **not yet implemented** but should be added.

**Recommended Endpoint:**
```
PATCH /api/v2/analyst/conversations/:conversationId
```

**Request Body:**
```json
{
  "title": "Updated conversation title"
}
```

**Expected Response:**
```json
{
  "id": "uuid",
  "title": "Updated conversation title",
  "updatedAt": "2024-01-15T10:30:00Z"
}
```

### Are there any conversation metadata fields we should know about?

**Answer:** NO

---

## 12. Testing

### Are there test/staging endpoints available?

**Answer:** Test endpoints are available via local development server.

**Development Setup:**
- Local server: `http://localhost:8000`
- Health check: `http://localhost:8000/health`
- API docs: `http://localhost:8000/docs` (Swagger UI)

**Staging/Production:**
- Staging URL: To be configured by DevOps team
- Production URL: To be configured by DevOps team

### Do you have Postman/Insomnia collections or OpenAPI/Swagger documentation?

**Answer:** Yes, OpenAPI/Swagger documentation is automatically generated.

**Available Documentation:**
- **Swagger UI:** `http://localhost:8000/docs`
- **ReDoc:** `http://localhost:8000/redoc`
- **OpenAPI JSON:** `http://localhost:8000/openapi.json`

**Features:**
- Interactive API testing
- Request/response schema documentation
- Example requests and responses
- Authentication testing (when enabled)

**Postman Collection:**
- Can be generated from OpenAPI JSON
- Use `http://localhost:8000/openapi.json` to import into Postman

### What are the test credentials (if any)?

**Answer:** Test credentials depend on authentication setup.

**Current Development Mode:**
- Authentication is disabled
- Use any valid UUIDs for `X-Workspace-ID` and `X-User-ID` headers
- Example:
  ```
  X-Workspace-ID: 550e8400-e29b-41d4-a716-446655440000
  X-User-ID: 550e8400-e29b-41d4-a716-446655440001
  ```

**Production Mode (when authentication is enabled):**
- Use AWS Cognito test user credentials
- Obtain JWT tokens from Cognito
- Test users should be created in Cognito User Pool

---

## Additional Information

### Endpoint Implementation Status

**Current V1 Endpoints (Implemented):**
- ✅ `POST /api/v1/query` - Process query
- ✅ `GET /health` - Health check
- ✅ `GET /ready` - Readiness check
- ✅ `GET /admin` - Admin panel

**V2 Endpoints (To Be Implemented):**
- ⏳ `POST /api/v2/analyst/query` - Query/Chat endpoint
- ⏳ `GET /api/v2/analyst/conversations` - List conversations
- ⏳ `GET /api/v2/analyst/conversations/:id` - Get conversation
- ⏳ `PATCH /api/v2/analyst/conversations/:id` - Update conversation
- ⏳ `DELETE /api/v2/analyst/conversations/:id` - Delete conversation
- ⏳ `POST /api/v2/notes` - Create note
- ⏳ `GET /api/v2/notes/:id` - Get note
- ⏳ `PATCH /api/v2/notes/:id` - Update note
- ⏳ `DELETE /api/v2/notes/:id` - Delete note

### Timestamp Format

**All timestamps are in ISO 8601 format:**
- Format: `YYYY-MM-DDTHH:mm:ssZ`
- Example: `2024-01-15T10:30:00Z`
- Timezone: UTC

### ID Format

**All IDs are UUIDs (v4):**
- Format: `xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx`
- Example: `550e8400-e29b-41d4-a716-446655440000`

---

## Contact

For questions or clarifications, please contact the backend team or refer to:
- API Documentation: `http://localhost:8000/docs`
- Codebase: `/api/v1/` directory
- Database Schema: `/prisma/schema.prisma`

---

**Document Status:** Ready for Review  
**Last Updated:** 2024-12-19

