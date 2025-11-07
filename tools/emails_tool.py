# tools/emails_tool.py
from tools.base_tool import BaseTool, QueryType, ToolResult
from database.dynamodb_client import dynamodb_client
from database.prisma_client import prisma_client
from typing import Dict, List, Any, Optional
from pydantic import BaseModel
from datetime import datetime
from botocore.exceptions import ClientError
import json
import base64
import os
import re
from enum import Enum


class PrivacyLevel(Enum):
    """Privacy levels for email visibility"""
    PRIVATE = "PRIVATE"
    SUBJECT_ONLY = "SUBJECT_ONLY"
    FULL_ACCESS = "FULL_ACCESS"


class EmailOrder(Enum):
    """Email ordering options"""
    LATEST = "latest"  # Most recent email (1st)
    SECOND_LATEST = "second_latest"  # 2nd most recent
    THIRD_LATEST = "third_latest"  # 3rd most recent
    FOURTH_LATEST = "fourth_latest"  # 4th most recent
    FIFTH_LATEST = "fifth_latest"  # 5th most recent
    OLDEST = "oldest"  # Oldest email (last)
    SECOND_OLDEST = "second_oldest"  # 2nd oldest
    THIRD_OLDEST = "third_oldest"  # 3rd oldest
    FOURTH_OLDEST = "fourth_oldest"  # 4th oldest
    FIFTH_OLDEST = "fifth_oldest"  # 5th oldest


class EmailSearchParams(BaseModel):
    """Parameters for email search"""
    person_id: Optional[str] = None
    person_name: Optional[str] = None
    company_id: Optional[str] = None
    company_name: Optional[str] = None
    from_email: Optional[str] = None
    to_email: Optional[str] = None
    subject: Optional[str] = None
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None
    direction: Optional[str] = None
    limit: int = 50
    next_token: Optional[str] = None
    order: Optional[str] = None  # e.g., "latest", "second_latest", "oldest"


class EmailTool(BaseTool):
    """Tool for email operations using DynamoDB"""

    def __init__(self, workspace_id: str, user_id: str):
        super().__init__(workspace_id, user_id)
        self.table_name = os.getenv("DYNAMODB_TABLE", "prod-softsync")

    def get_supported_operations(self) -> List[QueryType]:
        return [
            QueryType.SEARCH,
            QueryType.GET_BY_ID,
            QueryType.LIST,
            QueryType.ANALYTICS,
            QueryType.GET_LATEST,
            QueryType.GET_BY_THREAD
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
                result = await self._list_emails(**kwargs)
            elif query_type == QueryType.ANALYTICS:
                result = await self._get_email_analytics()
            elif query_type == QueryType.GET_LATEST:
                result = await self._get_latest_email(**kwargs)
            elif query_type == QueryType.GET_BY_THREAD:
                thread_id = kwargs.get('thread_id')
                person_id = kwargs.get('person_id')
                person_name = kwargs.get('person_name')
                result = await self._get_email_by_thread(thread_id, person_id, person_name)
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

    # =============================================================================
    # CORE EMAIL LISTING FUNCTIONS (following pseudo code structure)
    # =============================================================================

    async def _list_emails(self, **kwargs) -> Dict[str, Any]:
        """
        Main entry point for listing emails.
        Supports: company_id, company_name, person_id, person_name, direction
        Also supports order parameter: latest, second_latest, oldest, etc.
        """
        company_id = kwargs.get('company_id')
        company_name = kwargs.get('company_name')
        person_id = kwargs.get('person_id')
        person_name = kwargs.get('person_name')
        limit = kwargs.get('limit', 50)
        next_token = kwargs.get('next_token')
        order = kwargs.get('order')  # e.g., "latest", "second_latest", "oldest"
        direction = kwargs.get('direction')  # e.g., "sent", "received"

        # Route to appropriate list function
        if company_id:
            result = await self._list_emails_by_company_id(company_id, limit, next_token, direction)
        elif company_name:
            result = await self._list_emails_by_company_name(company_name, limit, next_token, direction)
        elif person_id:
            result = await self._list_emails_by_person_id(person_id, limit, next_token, direction)
        elif person_name:
            result = await self._list_emails_by_person_name(person_name, limit, next_token, direction)
        else:
            error_msg = (
                "Either company_id, company_name, person_id, or person_name is required. "
                "Examples: "
                "- LIST with company_name='Acme Corp' "
                "- LIST with company_id='123e4567-e89b-12d3-a456-426614174000' "
                "- LIST with person_name='John Doe' "
                "- LIST with person_id='123e4567-e89b-12d3-a456-426614174000' "
                "- LIST with company_name='Acme Corp', order='latest' "
                "- LIST with person_name='John Doe', order='second_latest', direction='sent'"
            )
            raise ValueError(error_msg)

        # Apply order filtering if specified
        if order:
            result = self._apply_email_order(result, order)

        return result

    async def _list_emails_by_company_name(
        self,
        company_name: str,
        limit: int = 50,
        next_token: Optional[str] = None,
        direction: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        List emails from a company by name.
        Implements the pseudo code: list_emails_from_company(company_name, workspace_id)
        """
        try:
            # Step 1: Find company by name
            company = await self._find_company_by_name(company_name)

            if not company:
                self.logger.warning(f"Company not found: {company_name}")
                return {
                    "emails": [],
                    "total_count": 0,
                    "has_more": False,
                    "next_token": None,
                    "limit": limit,
                    "company_name": company_name,
                    "error": f"Company '{company_name}' not found in workspace"
                }

            company_id = company.id

            # Step 2: Get all emails for the company (paginated)
            all_emails = []
            current_token = next_token

            while True:
                result = await self._get_company_emails(
                    company_id=company_id,
                    limit=limit,
                    next_token=current_token,
                    direction=direction
                )

                all_emails.extend(result['items'])
                current_token = result['next_token']

                # If no more pages or we've hit the limit, break
                if not current_token or len(all_emails) >= limit:
                    break

            # Apply privacy filtering
            filtered_emails = await self._apply_privacy_filtering(all_emails)

            return {
                "emails": filtered_emails[:limit],  # Respect limit
                "total_count": len(filtered_emails),
                "has_more": current_token is not None,
                "next_token": current_token,
                "limit": limit,
                "company_id": company_id,
                "company_name": company_name,
                "privacy_filtered": len(all_emails) - len(filtered_emails)
            }

        except Exception as e:
            self.logger.error(f"Error listing emails by company name '{company_name}': {e}")
            return {
                "emails": [],
                "total_count": 0,
                "has_more": False,
                "next_token": None,
                "limit": limit,
                "company_name": company_name,
                "error": str(e)
            }

    async def _list_emails_by_company_id(
        self,
        company_id: str,
        limit: int = 50,
        next_token: Optional[str] = None,
        direction: Optional[str] = None
    ) -> Dict[str, Any]:
        """List emails from a company by ID"""
        try:
            result = await self._get_company_emails(company_id, limit, next_token, direction)

            # Apply privacy filtering
            filtered_emails = await self._apply_privacy_filtering(result['items'])

            return {
                "emails": filtered_emails,
                "total_count": len(filtered_emails),
                "has_more": result['has_more'],
                "next_token": result['next_token'],
                "limit": limit,
                "company_id": company_id,
                "privacy_filtered": len(result['items']) - len(filtered_emails)
            }

        except Exception as e:
            self.logger.error(f"Error listing emails by company ID '{company_id}': {e}")
            return {
                "emails": [],
                "total_count": 0,
                "has_more": False,
                "next_token": None,
                "limit": limit,
                "company_id": company_id,
                "error": str(e)
            }

    async def _list_emails_by_person_name(
        self,
        person_name: str,
        limit: int = 50,
        next_token: Optional[str] = None,
        direction: Optional[str] = None
    ) -> Dict[str, Any]:
        """List emails from a person by name"""
        try:
            # Find person by name
            person = await self._find_person_by_name(person_name)

            if not person:
                self.logger.warning(f"Person not found: {person_name}")
                return {
                    "emails": [],
                    "total_count": 0,
                    "has_more": False,
                    "next_token": None,
                    "limit": limit,
                    "person_name": person_name,
                    "error": f"Person '{person_name}' not found in workspace"
                }

            person_id = person.id

            # Get emails for person
            result = await self._get_person_emails(person_id, limit, next_token, direction)

            # Apply privacy filtering
            filtered_emails = await self._apply_privacy_filtering(result['items'])

            return {
                "emails": filtered_emails,
                "total_count": len(filtered_emails),
                "has_more": result['has_more'],
                "next_token": result['next_token'],
                "limit": limit,
                "person_id": person_id,
                "person_name": person_name,
                "privacy_filtered": len(result['items']) - len(filtered_emails)
            }

        except Exception as e:
            self.logger.error(f"Error listing emails by person name '{person_name}': {e}")
            return {
                "emails": [],
                "total_count": 0,
                "has_more": False,
                "next_token": None,
                "limit": limit,
                "person_name": person_name,
                "error": str(e)
            }

    async def _list_emails_by_person_id(
        self,
        person_id: str,
        limit: int = 50,
        next_token: Optional[str] = None,
        direction: Optional[str] = None
    ) -> Dict[str, Any]:
        """List emails from a person by ID"""
        try:
            result = await self._get_person_emails(person_id, limit, next_token, direction)

            # Apply privacy filtering
            filtered_emails = await self._apply_privacy_filtering(result['items'])

            return {
                "emails": filtered_emails,
                "total_count": len(filtered_emails),
                "has_more": result['has_more'],
                "next_token": result['next_token'],
                "limit": limit,
                "person_id": person_id,
                "privacy_filtered": len(result['items']) - len(filtered_emails)
            }

        except Exception as e:
            self.logger.error(f"Error listing emails by person ID '{person_id}': {e}")
            return {
                "emails": [],
                "total_count": 0,
                "has_more": False,
                "next_token": None,
                "limit": limit,
                "person_id": person_id,
                "error": str(e)
            }

    # =============================================================================
    # HELPER FUNCTIONS (implementing pseudo code)
    # =============================================================================

    async def _find_company_by_name(self, company_name: str):
        """
        Find company by name (case-insensitive).
        Implements: find_company_by_name(company_name, workspace_id)
        """
        try:
            client = await prisma_client.get_client()

            company = await client.company.find_first(
                where={
                    'name': {
                        'equals': company_name,
                        'mode': 'insensitive'
                    },
                    'workspaceId': self.workspace_id
                }
            )

            return company

        except Exception as e:
            self.logger.error(f"Error finding company by name '{company_name}': {e}")
            return None

    async def _find_person_by_name(self, person_name: str):
        """
        Find person by name (case-insensitive)
        Searches by firstName, lastName, or full name combination
        """
        try:
            client = await prisma_client.get_client()

            # Try to split name into first and last
            name_parts = person_name.strip().split(None, 1)  # Split on first whitespace

            # Build search conditions
            search_conditions = []

            if len(name_parts) == 2:
                # Has both first and last name
                first_name, last_name = name_parts
                # Try exact match on both
                search_conditions.append({
                    'AND': [
                        {'firstName': {'equals': first_name, 'mode': 'insensitive'}},
                        {'lastName': {'equals': last_name, 'mode': 'insensitive'}}
                    ]
                })
                # Try contains match on both
                search_conditions.append({
                    'AND': [
                        {'firstName': {'contains': first_name, 'mode': 'insensitive'}},
                        {'lastName': {'contains': last_name, 'mode': 'insensitive'}}
                    ]
                })

            # Also search by either firstName or lastName containing the full query
            search_conditions.append({'firstName': {'contains': person_name, 'mode': 'insensitive'}})
            search_conditions.append({'lastName': {'contains': person_name, 'mode': 'insensitive'}})

            person = await client.people.find_first(
                where={
                    'OR': search_conditions,
                    'workspaceId': self.workspace_id
                }
            )

            return person

        except Exception as e:
            self.logger.error(f"Error finding person by name '{person_name}': {e}")
            return None

    async def _get_company_emails(
        self,
        company_id: str,
        limit: int = 50,
        next_token: Optional[str] = None,
        direction: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get emails for a company from DynamoDB.
        Implements: get_company_emails(company_id, workspace_id, limit, next_token)
        Supports optional direction filter: 'sent' or 'received'
        """
        try:
            table = dynamodb_client.get_table(self.table_name)

            # Build DynamoDB partition key
            partition_key = f"WORKSPACE#{self.workspace_id}#COMPANY#{company_id}"

            # Build query parameters
            query_params = {
                'KeyConditionExpression': 'PK = :pk',
                'ExpressionAttributeValues': {':pk': partition_key},
                'ScanIndexForward': False,  # Sort descending (newest first)
                'Limit': min(limit, 100)
            }

            # Add direction filter if provided
            if direction:
                query_params['FilterExpression'] = 'direction = :direction'
                query_params['ExpressionAttributeValues'][':direction'] = direction

            # Add pagination token if provided
            if next_token:
                try:
                    decoded_key = base64.b64decode(next_token).decode('utf-8')
                    query_params['ExclusiveStartKey'] = json.loads(decoded_key)
                except Exception as e:
                    self.logger.error(f"Invalid pagination token: {e}")

            # Execute DynamoDB query
            response = table.query(**query_params)

            # Extract email items
            items = response.get('Items', [])

            # Remove DynamoDB internal keys from each item
            emails = []
            for item in items:
                clean_item = self._remove_dynamo_keys(item)
                mapped_email = self._map_dynamo_item_to_email(clean_item)
                emails.append(mapped_email)

            # Encode pagination token for next page
            next_token_value = None
            if response.get('LastEvaluatedKey'):
                token_json = json.dumps(response['LastEvaluatedKey'])
                next_token_value = base64.b64encode(token_json.encode('utf-8')).decode('utf-8')

            return {
                'items': emails,
                'next_token': next_token_value,
                'has_more': next_token_value is not None
            }

        except ClientError as e:
            self.logger.error(f"DynamoDB error getting company emails: {e}")
            return {'items': [], 'next_token': None, 'has_more': False}
        except Exception as e:
            self.logger.error(f"Error getting company emails: {e}")
            return {'items': [], 'next_token': None, 'has_more': False}

    async def _get_person_emails(
        self,
        person_id: str,
        limit: int = 50,
        next_token: Optional[str] = None,
        direction: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get emails for a person from DynamoDB
        Supports optional direction filter: 'sent' or 'received'
        """
        try:
            table = dynamodb_client.get_table(self.table_name)

            # Build DynamoDB partition key
            partition_key = f"WORKSPACE#{self.workspace_id}#PERSON#{person_id}"

            # Build query parameters
            query_params = {
                'KeyConditionExpression': 'PK = :pk',
                'ExpressionAttributeValues': {':pk': partition_key},
                'ScanIndexForward': False,  # Sort descending (newest first)
                'Limit': min(limit, 100)
            }

            # Add direction filter if provided
            if direction:
                query_params['FilterExpression'] = 'direction = :direction'
                query_params['ExpressionAttributeValues'][':direction'] = direction

            # Add pagination token if provided
            if next_token:
                try:
                    decoded_key = base64.b64decode(next_token).decode('utf-8')
                    query_params['ExclusiveStartKey'] = json.loads(decoded_key)
                except Exception as e:
                    self.logger.error(f"Invalid pagination token: {e}")

            # Execute DynamoDB query
            response = table.query(**query_params)

            # Extract email items
            items = response.get('Items', [])

            # Remove DynamoDB internal keys from each item
            emails = []
            for item in items:
                clean_item = self._remove_dynamo_keys(item)
                mapped_email = self._map_dynamo_item_to_email(clean_item)
                emails.append(mapped_email)

            # Encode pagination token for next page
            next_token_value = None
            if response.get('LastEvaluatedKey'):
                token_json = json.dumps(response['LastEvaluatedKey'])
                next_token_value = base64.b64encode(token_json.encode('utf-8')).decode('utf-8')

            return {
                'items': emails,
                'next_token': next_token_value,
                'has_more': next_token_value is not None
            }

        except ClientError as e:
            self.logger.error(f"DynamoDB error getting person emails: {e}")
            return {'items': [], 'next_token': None, 'has_more': False}
        except Exception as e:
            self.logger.error(f"Error getting person emails: {e}")
            return {'items': [], 'next_token': None, 'has_more': False}

    def _remove_dynamo_keys(self, item: Dict[str, Any]) -> Dict[str, Any]:
        """
        Remove DynamoDB internal keys from an item.
        Removes: PK, SK, GSI1PK, GSI1SK
        """
        keys_to_remove = ['PK', 'SK', 'GSI1PK', 'GSI1SK']
        return {k: v for k, v in item.items() if k not in keys_to_remove}

    def _apply_email_order(self, result: Dict[str, Any], order: str) -> Dict[str, Any]:
        """
        Apply email ordering to filter specific emails by position.

        Examples:
        - "latest" returns the most recent email (1st)
        - "second_latest" returns the 2nd most recent email
        - "oldest" returns the oldest email (last)
        - "second_oldest" returns the 2nd oldest email

        Args:
            result: Result dictionary containing 'emails' list
            order: Order string (e.g., "latest", "second_latest", "oldest")

        Returns:
            Modified result with single email or empty list
        """
        emails = result.get('emails', [])

        if not emails:
            return result

        # Map order strings to indices
        order_mapping = {
            EmailOrder.LATEST.value: 0,
            EmailOrder.SECOND_LATEST.value: 1,
            EmailOrder.THIRD_LATEST.value: 2,
            EmailOrder.FOURTH_LATEST.value: 3,
            EmailOrder.FIFTH_LATEST.value: 4,
            EmailOrder.OLDEST.value: -1,
            EmailOrder.SECOND_OLDEST.value: -2,
            EmailOrder.THIRD_OLDEST.value: -3,
            EmailOrder.FOURTH_OLDEST.value: -4,
            EmailOrder.FIFTH_OLDEST.value: -5,
        }

        # Support numeric indices as well (e.g., "1" for latest, "2" for second latest)
        if order.isdigit():
            index = int(order) - 1  # Convert 1-based to 0-based
            if 0 <= index < len(emails):
                selected_email = emails[index]
                result['emails'] = [selected_email]
                result['total_count'] = 1
                result['selected_order'] = f"position_{order}"
            else:
                result['emails'] = []
                result['total_count'] = 0
                result['error'] = f"Email at position {order} not found. Total emails: {len(emails)}"
            return result

        # Handle string-based ordering
        if order not in order_mapping:
            result['error'] = (
                f"Invalid order '{order}'. Valid options: "
                f"latest, second_latest, third_latest, fourth_latest, fifth_latest, "
                f"oldest, second_oldest, third_oldest, fourth_oldest, fifth_oldest, "
                f"or numeric position (e.g., '1', '2', '3')"
            )
            return result

        index = order_mapping[order]

        # Check if index is within bounds
        try:
            selected_email = emails[index]
            result['emails'] = [selected_email]
            result['total_count'] = 1
            result['selected_order'] = order
        except IndexError:
            result['emails'] = []
            result['total_count'] = 0
            result['error'] = (
                f"Email '{order}' not found. "
                f"Total emails available: {len(emails)}. "
                f"Requested position: {index if index >= 0 else len(emails) + index + 1}"
            )

        return result

    # =============================================================================
    # SEARCH OPERATION
    # =============================================================================

    async def _search_emails(self, params: EmailSearchParams) -> Dict[str, Any]:
        """
        Search emails with advanced filters.
        Can search by person/company name or ID with additional filters.
        Supports order parameter to get specific emails (latest, second_latest, oldest, etc.)
        """
        try:
            # If searching by name, resolve to ID first
            if params.company_name and not params.company_id:
                company = await self._find_company_by_name(params.company_name)
                if company:
                    params.company_id = company.id
                else:
                    return {
                        "emails": [],
                        "total_count": 0,
                        "has_more": False,
                        "next_token": None,
                        "error": f"Company '{params.company_name}' not found"
                    }

            if params.person_name and not params.person_id:
                person = await self._find_person_by_name(params.person_name)
                if person:
                    params.person_id = person.id
                else:
                    return {
                        "emails": [],
                        "total_count": 0,
                        "has_more": False,
                        "next_token": None,
                        "error": f"Person '{params.person_name}' not found"
                    }

            # Now perform the search with resolved IDs
            table = dynamodb_client.get_table(self.table_name)

            if params.person_id:
                pk = f"WORKSPACE#{self.workspace_id}#PERSON#{params.person_id}"
            elif params.company_id:
                pk = f"WORKSPACE#{self.workspace_id}#COMPANY#{params.company_id}"
            else:
                # No specific entity, return error
                return {
                    "emails": [],
                    "total_count": 0,
                    "has_more": False,
                    "next_token": None,
                    "error": "Either person or company identifier is required for search"
                }

            query_params = {
                'KeyConditionExpression': 'PK = :pk',
                'ExpressionAttributeValues': {':pk': pk},
                'ScanIndexForward': False,
                'Limit': min(params.limit, 100)
            }

            # Build filter expressions for additional search criteria
            filter_expressions = []
            expression_values = {':pk': pk}
            expression_names = {}

            if params.from_email:
                filter_expressions.append('contains(#from, :from_email)')
                expression_values[':from_email'] = params.from_email
                expression_names['#from'] = 'from'

            if params.to_email:
                filter_expressions.append('contains(#to, :to_email)')
                expression_values[':to_email'] = params.to_email
                expression_names['#to'] = 'to'

            if params.subject:
                filter_expressions.append('contains(subject, :subject)')
                expression_values[':subject'] = params.subject

            if params.direction:
                filter_expressions.append('direction = :direction')
                expression_values[':direction'] = params.direction

            if params.date_from:
                filter_expressions.append('#date >= :date_from')
                expression_values[':date_from'] = params.date_from.isoformat()
                expression_names['#date'] = 'date'

            if params.date_to:
                filter_expressions.append('#date <= :date_to')
                expression_values[':date_to'] = params.date_to.isoformat()
                expression_names['#date'] = 'date'

            if filter_expressions:
                query_params['FilterExpression'] = ' AND '.join(filter_expressions)
                query_params['ExpressionAttributeValues'] = expression_values
                if expression_names:
                    query_params['ExpressionAttributeNames'] = expression_names

            # Handle pagination
            if params.next_token:
                try:
                    decoded_token = base64.b64decode(params.next_token).decode('utf-8')
                    query_params['ExclusiveStartKey'] = json.loads(decoded_token)
                except Exception as e:
                    self.logger.error(f"Invalid pagination token: {e}")

            response = table.query(**query_params)
            items = response.get('Items', [])

            # Clean and map items
            emails = []
            for item in items:
                clean_item = self._remove_dynamo_keys(item)
                mapped_email = self._map_dynamo_item_to_email(clean_item)
                emails.append(mapped_email)

            # Apply privacy filtering
            filtered_emails = await self._apply_privacy_filtering(emails)

            # Pagination
            last_evaluated_key = response.get('LastEvaluatedKey')
            next_token_encoded = None
            if last_evaluated_key:
                token_json = json.dumps(last_evaluated_key)
                next_token_encoded = base64.b64encode(token_json.encode('utf-8')).decode('utf-8')

            result = {
                "emails": filtered_emails,
                "total_count": len(filtered_emails),
                "has_more": last_evaluated_key is not None,
                "next_token": next_token_encoded,
                "limit": params.limit,
                "privacy_filtered": len(emails) - len(filtered_emails)
            }

            # Apply order filtering if specified
            if params.order:
                result = self._apply_email_order(result, params.order)

            return result

        except Exception as e:
            self.logger.error(f"Error searching emails: {e}")
            return {
                "emails": [],
                "total_count": 0,
                "has_more": False,
                "next_token": None,
                "error": str(e)
            }

    # =============================================================================
    # GET BY ID OPERATION
    # =============================================================================

    async def _get_email_by_id(self, message_id: str) -> Dict[str, Any]:
        """
        Get specific email by message ID using GSI1.
        Implements Scenario 2 from pseudo code: Retrieve Email by Message ID
        """
        try:
            if not message_id:
                return {"error": "Message ID is required"}

            table = dynamodb_client.get_table(self.table_name)

            # Query by message ID using GSI1
            gsi1pk = f"WORKSPACE#{self.workspace_id}#EMAIL#{message_id}"

            response = table.query(
                IndexName='GSI1',
                KeyConditionExpression='GSI1PK = :gsi1pk',
                ExpressionAttributeValues={':gsi1pk': gsi1pk}
            )

            items = response.get('Items', [])
            if items:
                clean_item = self._remove_dynamo_keys(items[0])
                email = self._map_dynamo_item_to_email(clean_item)

                # Apply privacy filtering
                filtered = await self._apply_privacy_filtering([email])
                if filtered:
                    return filtered[0]
                else:
                    return {"error": "Email not accessible due to privacy settings"}

            return {"error": f"Email with message ID '{message_id}' not found"}

        except ClientError as e:
            self.logger.error(f"DynamoDB error getting email by ID {message_id}: {e}")
            return {"error": f"Database error: {str(e)}"}
        except Exception as e:
            self.logger.error(f"Error getting email by ID {message_id}: {e}")
            return {"error": str(e)}

    # =============================================================================
    # GET LATEST EMAIL OPERATION
    # =============================================================================

    async def _get_latest_email(self, **kwargs) -> Dict[str, Any]:
        """
        Get the most recent email for a person or company.
        Implements Scenario 4 from pseudo code: Retrieve Most Recent Email for Person

        Supports:
        - person_id or person_name
        - company_id or company_name
        - direction (optional): 'sent' or 'received'
        """
        try:
            person_id = kwargs.get('person_id')
            person_name = kwargs.get('person_name')
            company_id = kwargs.get('company_id')
            company_name = kwargs.get('company_name')
            direction = kwargs.get('direction')

            # Resolve person by name if needed
            if person_name and not person_id:
                person = await self._find_person_by_name(person_name)
                if person:
                    person_id = person.id
                else:
                    return {"error": f"Person '{person_name}' not found"}

            # Resolve company by name if needed
            if company_name and not company_id:
                company = await self._find_company_by_name(company_name)
                if company:
                    company_id = company.id
                else:
                    return {"error": f"Company '{company_name}' not found"}

            # Build partition key
            if person_id:
                pk = f"WORKSPACE#{self.workspace_id}#PERSON#{person_id}"
                entity_type = "person"
                entity_id = person_id
            elif company_id:
                pk = f"WORKSPACE#{self.workspace_id}#COMPANY#{company_id}"
                entity_type = "company"
                entity_id = company_id
            else:
                return {
                    "error": "Either person_id, person_name, company_id, or company_name is required"
                }

            table = dynamodb_client.get_table(self.table_name)

            query_params = {
                'KeyConditionExpression': 'PK = :pk',
                'ExpressionAttributeValues': {':pk': pk},
                'ScanIndexForward': False,  # Most recent first
                'Limit': 1
            }

            # Add direction filter if specified
            if direction:
                query_params['FilterExpression'] = 'direction = :direction'
                query_params['ExpressionAttributeValues'][':direction'] = direction

            response = table.query(**query_params)
            items = response.get('Items', [])

            if not items:
                return {
                    "error": f"No emails found for {entity_type}",
                    f"{entity_type}_id": entity_id
                }

            # Clean, map, and apply privacy
            clean_item = self._remove_dynamo_keys(items[0])
            email = self._map_dynamo_item_to_email(clean_item)

            filtered = await self._apply_privacy_filtering([email])

            if filtered:
                return {
                    "email": filtered[0],
                    f"{entity_type}_id": entity_id,
                    "direction_filter": direction
                }
            else:
                return {
                    "error": "Latest email not accessible due to privacy settings",
                    f"{entity_type}_id": entity_id
                }

        except Exception as e:
            self.logger.error(f"Error getting latest email: {e}")
            return {"error": str(e)}

    # =============================================================================
    # GET EMAIL BY THREAD OPERATION
    # =============================================================================

    async def _get_email_by_thread(
        self,
        thread_id: str,
        person_id: Optional[str] = None,
        person_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get the latest email in a thread for a person.
        Implements Scenario 5 from pseudo code: Retrieve Email by Thread ID

        Args:
            thread_id: The thread ID to search for
            person_id: Optional person ID
            person_name: Optional person name (will be resolved to ID)
        """
        try:
            if not thread_id:
                return {"error": "Thread ID is required"}

            # Resolve person by name if needed
            if person_name and not person_id:
                person = await self._find_person_by_name(person_name)
                if person:
                    person_id = person.id
                else:
                    return {"error": f"Person '{person_name}' not found"}

            if not person_id:
                return {"error": "Either person_id or person_name is required"}

            table = dynamodb_client.get_table(self.table_name)

            # Build partition key for person
            pk = f"WORKSPACE#{self.workspace_id}#PERSON#{person_id}"

            query_params = {
                'KeyConditionExpression': 'PK = :pk',
                'FilterExpression': 'threadId = :threadId',
                'ExpressionAttributeValues': {
                    ':pk': pk,
                    ':threadId': thread_id
                },
                'ScanIndexForward': False,  # Most recent first
                'Limit': 1
            }

            response = table.query(**query_params)
            items = response.get('Items', [])

            if not items:
                return {
                    "error": f"No email found in thread '{thread_id}' for person",
                    "thread_id": thread_id,
                    "person_id": person_id
                }

            # Clean, map, and apply privacy
            clean_item = self._remove_dynamo_keys(items[0])
            email = self._map_dynamo_item_to_email(clean_item)

            filtered = await self._apply_privacy_filtering([email])

            if filtered:
                return {
                    "email": filtered[0],
                    "thread_id": thread_id,
                    "person_id": person_id
                }
            else:
                return {
                    "error": "Email in thread not accessible due to privacy settings",
                    "thread_id": thread_id,
                    "person_id": person_id
                }

        except Exception as e:
            self.logger.error(f"Error getting email by thread: {e}")
            return {"error": str(e)}

    # =============================================================================
    # ANALYTICS OPERATION
    # =============================================================================

    async def _get_email_analytics(self) -> Dict[str, Any]:
        """Get email analytics and metrics"""
        try:
            table = dynamodb_client.get_table(self.table_name)

            # Scan for workspace emails (expensive, consider caching)
            response = table.scan(
                FilterExpression='begins_with(PK, :pk_prefix)',
                ExpressionAttributeValues={':pk_prefix': f"WORKSPACE#{self.workspace_id}#"},
                Select='COUNT'
            )

            total_emails = response.get('Count', 0)

            # Get emails by direction
            sent_response = table.scan(
                FilterExpression='begins_with(PK, :pk_prefix) AND direction = :direction',
                ExpressionAttributeValues={
                    ':pk_prefix': f"WORKSPACE#{self.workspace_id}#",
                    ':direction': 'sent'
                },
                Select='COUNT'
            )

            received_response = table.scan(
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

    # =============================================================================
    # DATA MAPPING AND TRANSFORMATION
    # =============================================================================

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

    # =============================================================================
    # PRIVACY FILTERING
    # =============================================================================

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
        """
        if not emails:
            return emails

        # If no privacy levels provided, fetch from database
        if user_privacy_levels is None:
            user_ids = set()
            for email in emails:
                user_id = email.get('userId') or email.get('createdById')
                if user_id:
                    user_ids.add(user_id)

            if user_ids:
                user_privacy_levels = await self._get_user_privacy_levels(list(user_ids))
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

    async def _get_user_privacy_levels(self, user_ids: List[str]) -> Dict[str, str]:
        """
        Fetch user privacy levels from PostgreSQL emailIntegration table.
        Returns dictionary mapping user_id -> privacy_level string
        """
        if not user_ids:
            return {}

        try:
            client = await prisma_client.get_client()

            # Query emailIntegration table for active integrations
            integrations = await client.emailintegration.find_many(
                where={
                    'userId': {'in': user_ids},
                    'workspaceId': self.workspace_id,
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
                privacy_level = integration.privacyLevel.value
                privacy_levels[integration.userId] = privacy_level

            # Set default PRIVATE for users without active integrations
            for user_id in user_ids:
                if user_id not in privacy_levels:
                    privacy_levels[user_id] = PrivacyLevel.PRIVATE.value

            return privacy_levels

        except Exception as e:
            self.logger.error(f"Error fetching user privacy levels: {e}")
            # On error, default to PRIVATE for all users
            return {user_id: PrivacyLevel.PRIVATE.value for user_id in user_ids}
