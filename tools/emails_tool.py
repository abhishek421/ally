# tools/emails_tool.py
from tools.base_tool import BaseTool, QueryType, ToolResult
from database.dynamodb_client import dynamodb_client
from database.prisma_client import prisma_client
from typing import Dict, List, Any, Optional
from pydantic import BaseModel
from datetime import datetime, timedelta
import boto3
from botocore.exceptions import ClientError
import json
import base64
import os
import re
from enum import Enum


class PrivacyLevel(Enum):
    """Privacy levels for email visibility"""
    PRIVATE = "PRIVATE"  # Only visible to creator
    SUBJECT_ONLY = "SUBJECT_ONLY"  # Show subject/metadata, hide body
    FULL_ACCESS = "FULL_ACCESS"  # Show everything


class EmailSearchParams(BaseModel):
    """Parameters for email search"""
    person_id: Optional[str] = None
    company_id: Optional[str] = None
    company_id: Optional[str] = None
    integration_id: Optional[str] = None
    from_email: Optional[str] = None
    to_email: Optional[str] = None
    subject: Optional[str] = None
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None
    direction: Optional[str] = None  # 'sent' or 'received'
    limit: int = 50
    next_token: Optional[str] = None
    next_token: Optional[str] = None


class EmailTool(BaseTool):
    """Tool for email operations using DynamoDB"""


    def __init__(self, workspace_id: str, user_id: str):
        super().__init__(workspace_id, user_id)
        # Get table name from environment variable as per documentation
        self.table_name = os.getenv("DYNAMODB_TABLE", "prod-softsync")

        # Get table name from environment variable as per documentation
        self.table_name = os.getenv("DYNAMODB_TABLE", "prod-softsync")

    def get_supported_operations(self) -> List[QueryType]:
        return [
            QueryType.SEARCH,
            QueryType.GET_BY_ID,
            QueryType.LIST,
            QueryType.ANALYTICS
        ]


    async def execute(self, query_type: QueryType, **kwargs) -> ToolResult:
        start_time = datetime.now()


        try:
            if query_type == QueryType.SEARCH:
                params = EmailSearchParams(**kwargs)
                result = await self._search_emails(params)
            elif query_type == QueryType.GET_BY_ID:
                message_id = kwargs.get('message_id')
                result = await self._get_email_by_id(message_id)
            elif query_type == QueryType.LIST:
                person_id = kwargs.get('person_id')
                company_id = kwargs.get('company_id')
                company_id = kwargs.get('company_id')
                limit = kwargs.get('limit', 50)
                next_token = kwargs.get('next_token')

                if person_id:
                    result = await self._list_emails_by_person(person_id, limit, next_token)
                elif company_id:
                    result = await self._list_emails_by_company(company_id, limit, next_token)
                else:
                    raise ValueError("Either person_id or company_id is required for LIST operation")
                next_token = kwargs.get('next_token')

                if person_id:
                    result = await self._list_emails_by_person(person_id, limit, next_token)
                elif company_id:
                    result = await self._list_emails_by_company(company_id, limit, next_token)
                else:
                    raise ValueError("Either person_id or company_id is required for LIST operation")
            elif query_type == QueryType.ANALYTICS:
                result = await self._get_email_analytics()
            else:
                raise ValueError(f"Unsupported operation: {query_type}")


            execution_time = int((datetime.now() - start_time).total_seconds() * 1000)
            self._log_operation(query_type.value, True, execution_time)


            return ToolResult(
                success=True,
                data=result,
                execution_time_ms=execution_time,
                metadata={"workspace_id": self.workspace_id, "user_id": self.user_id}
            )
        except Exception as e:
            execution_time = int((datetime.now() - start_time).total_seconds() * 1000)
            return await self._handle_error(e, query_type.value)


    async def _search_emails(self, params: EmailSearchParams) -> Dict[str, Any]:
        """Search emails using DynamoDB queries"""
        try:
            table = dynamodb_client.get_table(self.table_name)


            # Build query parameters based on search criteria
            if params.person_id:
                # Query by person ID using partition key (as per documentation)
                # Query by person ID using partition key (as per documentation)
                pk = f"WORKSPACE#{self.workspace_id}#PERSON#{params.person_id}"


                query_params = {
                    'KeyConditionExpression': 'PK = :pk',
                    'ExpressionAttributeValues': {':pk': pk},
                    'ScanIndexForward': False,  # Most recent first
                    'Limit': min(params.limit, 100)  # Cap at 100 for performance
                }

                # Add filters if provided
                filter_expressions = []
                expression_values = {':pk': pk}


                if params.from_email:
                    filter_expressions.append('contains(#from, :from_email)')
                    filter_expressions.append('contains(#from, :from_email)')
                    expression_values[':from_email'] = params.from_email
                    if 'ExpressionAttributeNames' not in query_params:
                        query_params['ExpressionAttributeNames'] = {}
                    query_params['ExpressionAttributeNames']['#from'] = 'from'

                    if 'ExpressionAttributeNames' not in query_params:
                        query_params['ExpressionAttributeNames'] = {}
                    query_params['ExpressionAttributeNames']['#from'] = 'from'

                if params.to_email:
                    filter_expressions.append('contains(#to, :to_email)')
                    filter_expressions.append('contains(#to, :to_email)')
                    expression_values[':to_email'] = params.to_email
                    if 'ExpressionAttributeNames' not in query_params:
                        query_params['ExpressionAttributeNames'] = {}
                    query_params['ExpressionAttributeNames']['#to'] = 'to'

                    if 'ExpressionAttributeNames' not in query_params:
                        query_params['ExpressionAttributeNames'] = {}
                    query_params['ExpressionAttributeNames']['#to'] = 'to'

                if params.subject:
                    filter_expressions.append('contains(subject, :subject)')
                    expression_values[':subject'] = params.subject


                if params.direction:
                    filter_expressions.append('direction = :direction')
                    expression_values[':direction'] = params.direction


                if params.date_from:
                    filter_expressions.append('#date >= :date_from')
                    filter_expressions.append('#date >= :date_from')
                    expression_values[':date_from'] = params.date_from.isoformat()
                    if 'ExpressionAttributeNames' not in query_params:
                        query_params['ExpressionAttributeNames'] = {}
                    query_params['ExpressionAttributeNames']['#date'] = 'date'

                    if 'ExpressionAttributeNames' not in query_params:
                        query_params['ExpressionAttributeNames'] = {}
                    query_params['ExpressionAttributeNames']['#date'] = 'date'

                if params.date_to:
                    filter_expressions.append('#date <= :date_to')
                    filter_expressions.append('#date <= :date_to')
                    expression_values[':date_to'] = params.date_to.isoformat()
                    if 'ExpressionAttributeNames' not in query_params:
                        query_params['ExpressionAttributeNames'] = {}
                    query_params['ExpressionAttributeNames']['#date'] = 'date'

                    if 'ExpressionAttributeNames' not in query_params:
                        query_params['ExpressionAttributeNames'] = {}
                    query_params['ExpressionAttributeNames']['#date'] = 'date'

                if filter_expressions:
                    query_params['FilterExpression'] = ' AND '.join(filter_expressions)
                    query_params['ExpressionAttributeValues'] = expression_values

                # Handle pagination token
                if params.next_token:
                    try:
                        decoded_token = base64.b64decode(params.next_token).decode('utf-8')
                        exclusive_start_key = json.loads(decoded_token)
                        query_params['ExclusiveStartKey'] = exclusive_start_key
                    except Exception as e:
                        self.logger.error(f"Invalid pagination token: {e}")


                # Handle pagination token
                if params.next_token:
                    try:
                        decoded_token = base64.b64decode(params.next_token).decode('utf-8')
                        exclusive_start_key = json.loads(decoded_token)
                        query_params['ExclusiveStartKey'] = exclusive_start_key
                    except Exception as e:
                        self.logger.error(f"Invalid pagination token: {e}")

                response = table.query(**query_params)
                emails = response.get('Items', [])

            elif params.company_id:
                # Query by company ID using partition key (as per documentation)
                pk = f"WORKSPACE#{self.workspace_id}#COMPANY#{params.company_id}"


            elif params.company_id:
                # Query by company ID using partition key (as per documentation)
                pk = f"WORKSPACE#{self.workspace_id}#COMPANY#{params.company_id}"

                query_params = {
                    'KeyConditionExpression': 'PK = :pk',
                    'ExpressionAttributeValues': {':pk': pk},
                    'KeyConditionExpression': 'PK = :pk',
                    'ExpressionAttributeValues': {':pk': pk},
                    'ScanIndexForward': False,
                }

                # Handle pagination token
                if params.next_token:
                    try:
                        decoded_token = base64.b64decode(params.next_token).decode('utf-8')
                        exclusive_start_key = json.loads(decoded_token)
                        query_params['ExclusiveStartKey'] = exclusive_start_key
                    except Exception as e:
                        self.logger.error(f"Invalid pagination token: {e}")


                # Handle pagination token
                if params.next_token:
                    try:
                        decoded_token = base64.b64decode(params.next_token).decode('utf-8')
                        exclusive_start_key = json.loads(decoded_token)
                        query_params['ExclusiveStartKey'] = exclusive_start_key
                    except Exception as e:
                        self.logger.error(f"Invalid pagination token: {e}")

                response = table.query(**query_params)
                emails = response.get('Items', [])


            else:
                # Scan operation (less efficient, use sparingly)
                scan_params = {
                    'FilterExpression': 'begins_with(PK, :pk_prefix)',
                    'FilterExpression': 'begins_with(PK, :pk_prefix)',
                    'ExpressionAttributeValues': {':pk_prefix': f"WORKSPACE#{self.workspace_id}#"}, 
                }

                # Handle pagination token
                if params.next_token:
                    try:
                        decoded_token = base64.b64decode(params.next_token).decode('utf-8')
                        exclusive_start_key = json.loads(decoded_token)
                        scan_params['ExclusiveStartKey'] = exclusive_start_key
                    except Exception as e:
                        self.logger.error(f"Invalid pagination token: {e}")


                # Handle pagination token
                if params.next_token:
                    try:
                        decoded_token = base64.b64decode(params.next_token).decode('utf-8')
                        exclusive_start_key = json.loads(decoded_token)
                        scan_params['ExclusiveStartKey'] = exclusive_start_key
                    except Exception as e:
                        self.logger.error(f"Invalid pagination token: {e}")

                response = table.scan(**scan_params)
                emails = response.get('Items', [])

            # Get pagination token if more results exist
            last_evaluated_key = response.get('LastEvaluatedKey')
            next_token_encoded = None
            if last_evaluated_key:
                # Encode LastEvaluatedKey as base64 for next request
                token_json = json.dumps(last_evaluated_key)
                next_token_encoded = base64.b64encode(token_json.encode('utf-8')).decode('utf-8')

            # Map DynamoDB items to email data structure
            mapped_emails = [self._map_dynamo_item_to_email(item) for item in emails]

            # Apply privacy filtering
            filtered_emails = await self._apply_privacy_filtering(mapped_emails)

            return {
                "emails": filtered_emails,
                "total_count": len(filtered_emails),
                "has_more": last_evaluated_key is not None,
                "next_token": next_token_encoded,
                "limit": params.limit,
                "privacy_filtered": len(mapped_emails) - len(filtered_emails)
            }


        except ClientError as e:
            self.logger.error(f"DynamoDB error searching emails: {e}")
            return {
                "emails": [],
                "total_count": 0,
                "has_more": False,
                "next_token": None,
                "next_token": None,
                "limit": params.limit
            }
        except Exception as e:
            self.logger.error(f"Error searching emails: {e}")
            return {
                "emails": [],
                "total_count": 0,
                "has_more": False,
                "next_token": None,
                "next_token": None,
                "limit": params.limit
            }


    async def _get_email_by_id(self, message_id: str) -> Dict[str, Any]:
        """Get specific email by message ID using GSI1"""
        """Get specific email by message ID using GSI1"""
        try:
            table = dynamodb_client.get_table(self.table_name)

            # Query by message ID using GSI1 (as per documentation)
            gsi1pk = f"WORKSPACE#{self.workspace_id}#EMAIL#{message_id}"


            # Query by message ID using GSI1 (as per documentation)
            gsi1pk = f"WORKSPACE#{self.workspace_id}#EMAIL#{message_id}"

            response = table.query(
                IndexName='GSI1',
                KeyConditionExpression='GSI1PK = :gsi1pk',
                ExpressionAttributeValues={':gsi1pk': gsi1pk},
                KeyConditionExpression='GSI1PK = :gsi1pk',
                ExpressionAttributeValues={':gsi1pk': gsi1pk}
                )


            items = response.get('Items', [])
            if items:
                return self._map_dynamo_item_to_email(items[0])
                return self._map_dynamo_item_to_email(items[0])
            return {}


        except ClientError as e:
            self.logger.error(f"DynamoDB error getting email by ID {message_id}: {e}")
            return {}
        except Exception as e:
            self.logger.error(f"Error getting email by ID {message_id}: {e}")
            return {}

    async def _list_emails_by_person(
        self,
        person_id: str,
        limit: int,
        next_token: Optional[str] = None
    ) -> Dict[str, Any]:
        """List emails for a specific person"""
        try:
            table = dynamodb_client.get_table(self.table_name)

            # Use PERSON partition key as per documentation

            # Use PERSON partition key as per documentation
            pk = f"WORKSPACE#{self.workspace_id}#PERSON#{person_id}"

            query_params = {
                'KeyConditionExpression': 'PK = :pk',
                'ExpressionAttributeValues': {':pk': pk},
                'ScanIndexForward': False,  # Most recent first
                'Limit': min(limit, 100)
            }

            # Handle pagination token
            if next_token:
                try:
                    decoded_token = base64.b64decode(next_token).decode('utf-8')
                    exclusive_start_key = json.loads(decoded_token)
                    query_params['ExclusiveStartKey'] = exclusive_start_key
                except Exception as e:
                    self.logger.error(f"Invalid pagination token: {e}")

            response = table.query(**query_params)

            query_params = {
                'KeyConditionExpression': 'PK = :pk',
                'ExpressionAttributeValues': {':pk': pk},
                'ScanIndexForward': False,  # Most recent first
                'Limit': min(limit, 100)
            }

            # Handle pagination token
            if next_token:
                try:
                    decoded_token = base64.b64decode(next_token).decode('utf-8')
                    exclusive_start_key = json.loads(decoded_token)
                    query_params['ExclusiveStartKey'] = exclusive_start_key
                except Exception as e:
                    self.logger.error(f"Invalid pagination token: {e}")

            response = table.query(**query_params)
            emails = response.get('Items', [])

            # Get pagination token
            last_evaluated_key = response.get('LastEvaluatedKey')
            next_token_encoded = None
            if last_evaluated_key:
                token_json = json.dumps(last_evaluated_key)
                next_token_encoded = base64.b64encode(token_json.encode('utf-8')).decode('utf-8')

            # Map items
            mapped_emails = [self._map_dynamo_item_to_email(item) for item in emails]

            # Apply privacy filtering
            filtered_emails = await self._apply_privacy_filtering(mapped_emails)

            return {
                "emails": filtered_emails,
                "total_count": len(filtered_emails),
                "has_more": last_evaluated_key is not None,
                "next_token": next_token_encoded,
                "limit": limit,
                "person_id": person_id,
                "privacy_filtered": len(mapped_emails) - len(filtered_emails)
            }


        except ClientError as e:
            self.logger.error(f"DynamoDB error listing emails for person {person_id}: {e}")
            return {
                "emails": [],
                "total_count": 0,
                "has_more": False,
                "next_token": None,
                "next_token": None,
                "limit": limit,
                "person_id": person_id
            }
        except Exception as e:
            self.logger.error(f"Error listing emails for person {person_id}: {e}")
            return {
                "emails": [],
                "total_count": 0,
                "has_more": False,
                "next_token": None,
                "next_token": None,
                "limit": limit,
                "person_id": person_id
            }

    async def _list_emails_by_company(
        self,
        company_id: str,
        limit: int,
        next_token: Optional[str] = None
    ) -> Dict[str, Any]:
        """List emails for a specific company"""
        try:
            table = dynamodb_client.get_table(self.table_name)

            # Use COMPANY partition key as per documentation
            pk = f"WORKSPACE#{self.workspace_id}#COMPANY#{company_id}"

            query_params = {
                'KeyConditionExpression': 'PK = :pk',
                'ExpressionAttributeValues': {':pk': pk},
                'ScanIndexForward': False,  # Most recent first
                'Limit': min(limit, 100)
            }

            # Handle pagination token
            if next_token:
                try:
                    decoded_token = base64.b64decode(next_token).decode('utf-8')
                    exclusive_start_key = json.loads(decoded_token)
                    query_params['ExclusiveStartKey'] = exclusive_start_key
                except Exception as e:
                    self.logger.error(f"Invalid pagination token: {e}")

            response = table.query(**query_params)
            emails = response.get('Items', [])

            # Get pagination token
            last_evaluated_key = response.get('LastEvaluatedKey')
            next_token_encoded = None
            if last_evaluated_key:
                token_json = json.dumps(last_evaluated_key)
                next_token_encoded = base64.b64encode(token_json.encode('utf-8')).decode('utf-8')

            # Map items
            mapped_emails = [self._map_dynamo_item_to_email(item) for item in emails]

            # Apply privacy filtering
            filtered_emails = await self._apply_privacy_filtering(mapped_emails)

            return {
                "emails": filtered_emails,
                "total_count": len(filtered_emails),
                "has_more": last_evaluated_key is not None,
                "next_token": next_token_encoded,
                "limit": limit,
                "company_id": company_id,
                "privacy_filtered": len(mapped_emails) - len(filtered_emails)
            }

        except ClientError as e:
            self.logger.error(f"DynamoDB error listing emails for company {company_id}: {e}")
            return {
                "emails": [],
                "total_count": 0,
                "has_more": False,
                "next_token": None,
                "limit": limit,
                "company_id": company_id
            }
        except Exception as e:
            self.logger.error(f"Error listing emails for company {company_id}: {e}")
            return {
                "emails": [],
                "total_count": 0,
                "has_more": False,
                "next_token": None,
                "limit": limit,
                "company_id": company_id
            }

    async def _get_email_analytics(self) -> Dict[str, Any]:
        """Get email analytics and metrics"""
        try:
            table = dynamodb_client.get_table(self.table_name)


            # Scan for workspace emails (this is expensive, consider caching)
            response = table.scan(
                FilterExpression='begins_with(PK, :pk_prefix)',
                FilterExpression='begins_with(PK, :pk_prefix)',
                ExpressionAttributeValues={':pk_prefix': f"WORKSPACE#{self.workspace_id}#"},
                Select='COUNT'
            )


            total_emails = response.get('Count', 0)


            # Get emails by direction
            sent_response = table.scan(
                FilterExpression='begins_with(PK, :pk_prefix) AND direction = :direction',
                FilterExpression='begins_with(PK, :pk_prefix) AND direction = :direction',
                ExpressionAttributeValues={
                    ':pk_prefix': f"WORKSPACE#{self.workspace_id}#",
                    ':direction': 'sent'
                },
                Select='COUNT'
            )


            received_response = table.scan(
                FilterExpression='begins_with(PK, :pk_prefix) AND direction = :direction',
                FilterExpression='begins_with(PK, :pk_prefix) AND direction = :direction',
                ExpressionAttributeValues={
                    ':pk_prefix': f"WORKSPACE#{self.workspace_id}#",
                    ':direction': 'received'
                },
                Select='COUNT'
            )


            return {
                "total_emails": total_emails,
                "by_direction": {
                    "sent": sent_response.get('Count', 0),
                    "received": received_response.get('Count', 0)
                },
                "workspace_id": self.workspace_id
            }


        except ClientError as e:
            self.logger.error(f"DynamoDB error getting email analytics: {e}")
            return {
                "total_emails": 0,
                "by_direction": {"sent": 0, "received": 0},
                "workspace_id": self.workspace_id
            }
        except Exception as e:
            self.logger.error(f"Error getting email analytics: {e}")
            return {
                "total_emails": 0,
                "by_direction": {"sent": 0, "received": 0},
                "workspace_id": self.workspace_id
            }

    def _map_dynamo_item_to_email(self, item: Dict[str, Any]) -> Dict[str, Any]:
        """
        Convert DynamoDB item to email data structure.
        Handles both EMAIL_SYNC and MANUAL_EVENT sources.
        """
        source = item.get('source', 'EMAIL_SYNC')

        # Handle manual interaction events
        if source == 'MANUAL_EVENT':
            return {
                'messageId': item.get('interactionId'),
                'subject': item.get('eventName'),
                'from': '',
                'to': [],
                'direction': item.get('direction', 'received'),
                'body': item.get('description'),
                'htmlBody': None,
                'date': self._parse_datetime(item.get('dateTime')),
                'threadId': None,
                'participants': [],
                'workspaceId': item.get('workspaceId'),
                'userId': item.get('createdById'),
                'processed': item.get('processed', True),
                'createdAt': self._parse_datetime(item.get('createdAt')),
                'updatedAt': self._parse_datetime(item.get('updatedAt')),
                'deleted': item.get('isDeleted', False),
                'labels': [],
                'source': 'MANUAL_EVENT',
                'interactionType': item.get('interactionType'),
                'eventName': item.get('eventName'),
                'description': item.get('description'),
                'dateTime': self._parse_datetime(item.get('dateTime')),
                'duration': item.get('duration'),
                'personId': item.get('personId'),
                'companyId': item.get('companyId'),
                'createdById': item.get('createdById')
            }

        # Handle synced email messages
        raw_html = item.get('htmlBody')
        raw_body = item.get('body')

        # Derive text preview from HTML or use body
        body_text = self._derive_text_preview(raw_html, raw_body)

        # Handle 'to' field - ensure it's a list
        to_field = item.get('to', [])
        if not isinstance(to_field, list):
            to_field = [to_field] if to_field else []

        return {
            'messageId': item.get('messageId'),
            'subject': item.get('subject'),
            'from': item.get('from', ''),
            'to': to_field,
            'direction': item.get('direction', 'received'),
            'body': body_text,
            'htmlBody': raw_html,
            'date': self._parse_datetime(item.get('date')),
            'threadId': item.get('threadId'),
            'participants': item.get('participants', []),
            'workspaceId': item.get('workspaceId'),
            'userId': item.get('userId'),
            'processed': item.get('processed', False),
            'createdAt': self._parse_datetime(item.get('createdAt')),
            'updatedAt': self._parse_datetime(item.get('updatedAt')),
            'deleted': item.get('deleted', False),
            'labels': item.get('labels', []),
            'source': 'EMAIL_SYNC'
        }

    def _derive_text_preview(self, html: Optional[str], fallback: Optional[str]) -> Optional[str]:
        """
        Extract text preview from HTML or use fallback text.
        Clamps to 16KB to avoid size limits.
        """
        source = ''
        if html:
            # Strip HTML tags
            source = re.sub(r'<script[\s\S]*?>[\s\S]*?</script>', '', html, flags=re.IGNORECASE)
            source = re.sub(r'<style[\s\S]*?>[\s\S]*?</style>', '', source, flags=re.IGNORECASE)
            source = re.sub(r'<[^>]+>', '', source)
            source = source.replace('&nbsp;', ' ').replace('&amp;', '&').strip()
        elif fallback:
            source = fallback.strip()

        if not source:
            return None

        # Clamp to 16KB
        MAX_PREVIEW_BYTES = 16000
        if len(source.encode('utf-8')) <= MAX_PREVIEW_BYTES:
            return source

        # Truncate if too large
        end = len(source)
        while len(source[:end].encode('utf-8')) > MAX_PREVIEW_BYTES and end > 0:
            end = int(end * 0.8)

        return source[:end]

    def _parse_datetime(self, dt_str: Optional[str]) -> Optional[datetime]:
        """Parse datetime string from DynamoDB, handling various formats"""
        if not dt_str:
            return None

        try:
            # Handle ISO format with 'Z' timezone
            if isinstance(dt_str, str):
                return datetime.fromisoformat(dt_str.replace('Z', '+00:00'))
            elif isinstance(dt_str, datetime):
                return dt_str
            return None
        except (ValueError, AttributeError):
            self.logger.warning(f"Could not parse datetime: {dt_str}")
            return None

    async def _apply_privacy_filtering(
        self,
        emails: List[Dict[str, Any]],
        user_privacy_levels: Optional[Dict[str, str]] = None
    ) -> List[Dict[str, Any]]:
        """
        Filter emails based on privacy settings

        Privacy Levels:
        - PRIVATE: Only visible to creator (filter out for non-owners)
        - SUBJECT_ONLY: Show subject and metadata, hide body
        - FULL_ACCESS: Show everything

        Args:
            emails: List of email dictionaries
            user_privacy_levels: Dictionary mapping user_id -> privacy_level
                                If None, will attempt to fetch from database

        Returns:
            Filtered list of emails with privacy rules applied
        """
        if not emails:
            return emails

        # If no privacy levels provided, fetch from database
        if user_privacy_levels is None:
            # Extract unique user IDs from emails
            user_ids = set()
            for email in emails:
                user_id = email.get('userId') or email.get('createdById')
                if user_id:
                    user_ids.add(user_id)
            
            if user_ids:
                user_privacy_levels = await self._get_user_privacy_levels(
                    list(user_ids), 
                    self.workspace_id
                )
            else:
                user_privacy_levels = {}

        filtered = []

        for email in emails:
            email_user_id = email.get('userId') or email.get('createdById')
            is_own = email_user_id == self.user_id

            # Owner always sees their own emails in full
            if is_own:
                email['_privacyLevel'] = user_privacy_levels.get(email_user_id, PrivacyLevel.PRIVATE.value)
                filtered.append(email)
                continue

            # Get privacy level for email owner
            owner_privacy = user_privacy_levels.get(email_user_id, PrivacyLevel.PRIVATE.value)

            # Apply privacy rules
            if owner_privacy == PrivacyLevel.PRIVATE.value:
                # Hide completely from non-owners
                continue
            elif owner_privacy == PrivacyLevel.SUBJECT_ONLY.value:
                # Show subject and metadata, hide body
                email['body'] = None
                email['htmlBody'] = None
                email['_privacyLevel'] = owner_privacy
                filtered.append(email)
            elif owner_privacy == PrivacyLevel.FULL_ACCESS.value:
                # Show everything
                email['_privacyLevel'] = owner_privacy
                filtered.append(email)
            else:
                # Unknown privacy level, default to private
                self.logger.warning(f"Unknown privacy level '{owner_privacy}' for user {email_user_id}, treating as PRIVATE")
                continue

        return filtered

    async def _get_user_privacy_levels(
        self, 
        user_ids: List[str], 
        workspace_id: str
    ) -> Dict[str, str]:
        """
        Fetch user privacy levels from PostgreSQL emailIntegration table.

        Args:
            user_ids: List of user UUIDs to fetch privacy levels for
            workspace_id: Workspace UUID

        Returns:
            Dictionary mapping user_id -> privacy_level string
            (PRIVATE, SUBJECT_ONLY, or FULL_ACCESS)

        Notes:
            - Table: emailIntegration (lowercase)
            - Default privacy level: PRIVATE (if user has no active integration)
            - Only returns privacy levels for active integrations (isActive = true)
        """
        if not user_ids:
            return {}

        try:
            client = await prisma_client.get_client()

            # Query emailIntegration table for active integrations
            integrations = await client.emailintegration.find_many(
                where={
                    'userId': {'in': user_ids},
                    'workspaceId': workspace_id,
                    'isActive': True
                },
                select={
                    'userId': True,
                    'privacyLevel': True
                }
            )

            # Map user_id -> privacy_level
            privacy_levels = {}
            for integration in integrations:
                # Convert InteractionPrivacy enum to string
                privacy_level = integration.privacyLevel.value
                privacy_levels[integration.userId] = privacy_level

            # Set default PRIVATE for users without active integrations
            for user_id in user_ids:
                if user_id not in privacy_levels:
                    privacy_levels[user_id] = PrivacyLevel.PRIVATE.value

            self.logger.debug(
                f"Privacy filtering: Fetched privacy levels for {len(privacy_levels)} users "
                f"from emailIntegration table (workspace: {workspace_id})"
            )

            return privacy_levels

        except Exception as e:
            self.logger.error(
                f"Error fetching user privacy levels from PostgreSQL: {e}. "
                "Falling back to default PRIVATE for all users."
            )
            # On error, default to PRIVATE for all users (more restrictive)
            return {user_id: PrivacyLevel.PRIVATE.value for user_id in user_ids}
