# tools/emails_tool.py
from tools.base_tool import BaseTool, QueryType, ToolResult
from database.dynamodb_client import dynamodb_client
from typing import Dict, List, Any, Optional
from pydantic import BaseModel
from datetime import datetime, timedelta
import boto3
from botocore.exceptions import ClientError


class EmailSearchParams(BaseModel):
    """Parameters for email search"""
    person_id: Optional[str] = None
    integration_id: Optional[str] = None
    from_email: Optional[str] = None
    to_email: Optional[str] = None
    subject: Optional[str] = None
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None
    direction: Optional[str] = None  # 'sent' or 'received'
    limit: int = 50


class EmailTool(BaseTool):
    """Tool for email operations using DynamoDB"""
    
    def __init__(self, workspace_id: str, user_id: str):
        super().__init__(workspace_id, user_id)
        self.table_name = 'EmailSync'
    
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
                limit = kwargs.get('limit', 50)
                result = await self._list_emails_by_person(person_id, limit)
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
                # Query by person ID using partition key
                pk = f"WORKSPACE#{self.workspace_id}#PERSON#{params.person_id}"
                
                query_params = {
                    'KeyConditionExpression': 'PK = :pk',
                    'ExpressionAttributeValues': {':pk': pk},
                    'ScanIndexForward': False,  # Most recent first
                    'Limit': params.limit
                }
                
                # Add filters if provided
                filter_expressions = []
                expression_values = {':pk': pk}
                
                if params.from_email:
                    filter_expressions.append('contains(fromEmail, :from_email)')
                    expression_values[':from_email'] = params.from_email
                
                if params.to_email:
                    filter_expressions.append('contains(toEmail, :to_email)')
                    expression_values[':to_email'] = params.to_email
                
                if params.subject:
                    filter_expressions.append('contains(subject, :subject)')
                    expression_values[':subject'] = params.subject
                
                if params.direction:
                    filter_expressions.append('direction = :direction')
                    expression_values[':direction'] = params.direction
                
                if params.date_from:
                    filter_expressions.append('emailDate >= :date_from')
                    expression_values[':date_from'] = params.date_from.isoformat()
                
                if params.date_to:
                    filter_expressions.append('emailDate <= :date_to')
                    expression_values[':date_to'] = params.date_to.isoformat()
                
                if filter_expressions:
                    query_params['FilterExpression'] = ' AND '.join(filter_expressions)
                    query_params['ExpressionAttributeValues'] = expression_values
                
                response = table.query(**query_params)
                emails = response.get('Items', [])
                
            elif params.integration_id:
                # Query by integration ID using GSI1
                query_params = {
                    'IndexName': 'GSI1',
                    'KeyConditionExpression': 'GSI1PK = :gsi1pk',
                    'ExpressionAttributeValues': {':gsi1pk': f"WORKSPACE#{self.workspace_id}#INTEGRATION#{params.integration_id}"},
                    'ScanIndexForward': False,
                    'Limit': params.limit
                }
                
                response = table.query(**query_params)
                emails = response.get('Items', [])
                
            else:
                # Scan operation (less efficient, use sparingly)
                scan_params = {
                    'FilterExpression': 'PK begins_with :pk_prefix',
                    'ExpressionAttributeValues': {':pk_prefix': f"WORKSPACE#{self.workspace_id}#"},
                    'Limit': params.limit
                }
                
                response = table.scan(**scan_params)
                emails = response.get('Items', [])
            
            return {
                "emails": emails,
                "total_count": len(emails),
                "has_more": len(emails) == params.limit,
                "limit": params.limit
            }
            
        except ClientError as e:
            self.logger.error(f"DynamoDB error searching emails: {e}")
            return {
                "emails": [],
                "total_count": 0,
                "has_more": False,
                "limit": params.limit
            }
        except Exception as e:
            self.logger.error(f"Error searching emails: {e}")
            return {
                "emails": [],
                "total_count": 0,
                "has_more": False,
                "limit": params.limit
            }
    
    async def _get_email_by_id(self, message_id: str) -> Dict[str, Any]:
        """Get specific email by message ID"""
        try:
            table = dynamodb_client.get_table(self.table_name)
            
            # Query by message ID using GSI1
            response = table.query(
                IndexName='GSI1',
                KeyConditionExpression='GSI1PK = :gsi1pk AND GSI1SK = :gsi1sk',
                ExpressionAttributeValues={
                    ':gsi1pk': f"WORKSPACE#{self.workspace_id}#MESSAGE#{message_id}",
                    ':gsi1sk': message_id
                }
            )
            
            items = response.get('Items', [])
            if items:
                return items[0]
            return {}
            
        except ClientError as e:
            self.logger.error(f"DynamoDB error getting email by ID {message_id}: {e}")
            return {}
        except Exception as e:
            self.logger.error(f"Error getting email by ID {message_id}: {e}")
            return {}
    
    async def _list_emails_by_person(self, person_id: str, limit: int) -> Dict[str, Any]:
        """List emails for a specific person"""
        try:
            table = dynamodb_client.get_table(self.table_name)
            
            pk = f"WORKSPACE#{self.workspace_id}#PERSON#{person_id}"
            
            response = table.query(
                KeyConditionExpression='PK = :pk',
                ExpressionAttributeValues={':pk': pk},
                ScanIndexForward=False,  # Most recent first
                Limit=limit
            )
            
            emails = response.get('Items', [])
            
            return {
                "emails": emails,
                "total_count": len(emails),
                "has_more": len(emails) == limit,
                "limit": limit,
                "person_id": person_id
            }
            
        except ClientError as e:
            self.logger.error(f"DynamoDB error listing emails for person {person_id}: {e}")
            return {
                "emails": [],
                "total_count": 0,
                "has_more": False,
                "limit": limit,
                "person_id": person_id
            }
        except Exception as e:
            self.logger.error(f"Error listing emails for person {person_id}: {e}")
            return {
                "emails": [],
                "total_count": 0,
                "has_more": False,
                "limit": limit,
                "person_id": person_id
            }
    
    async def _get_email_analytics(self) -> Dict[str, Any]:
        """Get email analytics and metrics"""
        try:
            table = dynamodb_client.get_table(self.table_name)
            
            # Scan for workspace emails (this is expensive, consider caching)
            response = table.scan(
                FilterExpression='PK begins_with :pk_prefix',
                ExpressionAttributeValues={':pk_prefix': f"WORKSPACE#{self.workspace_id}#"},
                Select='COUNT'
            )
            
            total_emails = response.get('Count', 0)
            
            # Get emails by direction
            sent_response = table.scan(
                FilterExpression='PK begins_with :pk_prefix AND direction = :direction',
                ExpressionAttributeValues={
                    ':pk_prefix': f"WORKSPACE#{self.workspace_id}#",
                    ':direction': 'sent'
                },
                Select='COUNT'
            )
            
            received_response = table.scan(
                FilterExpression='PK begins_with :pk_prefix AND direction = :direction',
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
