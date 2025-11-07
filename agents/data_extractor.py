"""
DataExtractorAgent - Uses multiple tools to search different DB, tables, and data storages
"""
from typing import Dict, List, Optional, Any
import logging
import time
import json
import asyncio
import os
import re
from datetime import datetime
from adapters.llm_provider import LLMProvider
from config.settings import DATA_EXTRACTOR_PROMPT_TEMPLATE, DATA_EXTRACTOR_CONFIG
from tools.tool_factory import ToolFactory
from tools.base_tool import QueryType, ToolResult


class DataExtractorAgent:
    """Smart agent that parses queries and uses tools to extract data from multiple sources"""
    
    def __init__(self, llm_provider: Optional[LLMProvider] = None):
        """
        Initialize DataExtractorAgent

        Args:
            llm_provider: LLM provider instance (injected dependency)
                         If None, will be created from config
        """
        self.template = DATA_EXTRACTOR_PROMPT_TEMPLATE

        # logger initialization kept lightweight to avoid overriding app-level config
        self._logger = logging.getLogger(__name__)
        if not self._logger.handlers and not logging.getLogger().handlers:
            logging.basicConfig(
                level=logging.INFO,
                format='%(asctime)s %(levelname)s [%(name)s] %(message)s'
            )

        # Set LLM provider (injected or created from config)
        self.llm_provider = llm_provider
        if self.llm_provider is None:
            from adapters.provider_factory import LLMProviderFactory
            self.llm_provider = LLMProviderFactory.create(DATA_EXTRACTOR_CONFIG)

        self._logger.debug(f"DataExtractorAgent initialized with provider: {self.llm_provider}")

        # Validate configuration for email tool
        self._validate_email_tool_config()

    def _validate_email_tool_config(self):
        """
        Validate that email tool dependencies are properly configured

        Checks for:
        - DYNAMODB_TABLE environment variable
        - AWS credentials (if needed)
        """
        import os

        # Check DynamoDB table name - now required
        dynamodb_table = os.getenv("DYNAMODB_TABLE")
        if not dynamodb_table:
            raise ValueError(
                "DYNAMODB_TABLE environment variable is required. "
                "Set DYNAMODB_TABLE in .env or environment."
            )

        # Check AWS region - now required
        aws_region = os.getenv("AWS_REGION")
        if not aws_region:
            raise ValueError(
                "AWS_REGION environment variable is required. "
                "Set AWS_REGION in .env or environment."
            )

        self._logger.debug("Email tool configuration validated")

    async def extract(self, optimized_query: str, workspace_id: str, user_id: str, context_messages: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
        """
        Main entry point to extract data based on optimized query

        Args:
            optimized_query: Optimized query string from QueryOptimizerAgent
            workspace_id: Workspace identifier for data isolation
            user_id: User identifier for access control
            context_messages: Previous conversation messages for context (optional)

        Returns:
            Dictionary with extracted data grouped by tool:
            {
                "companies": [...],
                "people": [...],
                "emails": [...],
                "interactions": [...],
                "groups": [...],
                "workspace": {...},
                "_reasoning_traces": [...],  # NEW: Execution reasoning
                "_confidence_scores": {...},  # NEW: Confidence per tool
                "_validation": {...}          # NEW: Validation results
            }
        """
        self._logger.info("Starting data extraction")
        self._logger.debug(f"Optimized query: {optimized_query}")
        self._logger.debug(f"Workspace: {workspace_id}, User: {user_id}")
        if context_messages:
            self._logger.debug(f"Using {len(context_messages)} context messages for reference resolution")

        start_time = time.time()

        # NEW: Initialize reasoning traces
        self.reasoning_traces = []

        try:
            # Step 1: Parse optimized query using LLM (with context for reference resolution)
            parsed_query = self._parse_optimized_query(optimized_query, context_messages)
            self._logger.debug(f"Parsed query: {parsed_query}")

            # NEW: Log parsing decision
            self.reasoning_traces.append({
                "step": "parse_query",
                "timestamp": datetime.now().isoformat(),
                "decision": f"Planned {len(parsed_query.get('tool_calls', []))} tool call(s)",
                "tools_planned": [tc.get("tool") for tc in parsed_query.get("tool_calls", [])],
                "execution_plan": parsed_query.get("execution_plan", "No plan provided")
            })

            # Step 2: Execute tool calls
            tool_results = await self._execute_tool_calls(parsed_query, workspace_id, user_id)

            # Step 3: Aggregate results in tool-grouped structure
            extracted_data = self._aggregate_results(tool_results)

            # NEW: Step 4: Score confidence for each tool result
            confidence_scores = self._score_tool_results(tool_results)

            # NEW: Step 5: Validate results
            validation_result = self._validate_results(optimized_query, extracted_data, confidence_scores)

            elapsed_ms = int((time.time() - start_time) * 1000)
            self._logger.info(f"Data extraction completed in {elapsed_ms} ms")
            self._logger.info(f"Overall confidence: {validation_result.get('overall_confidence', 0.0):.2f}")
            self._logger.debug(f"Extracted data keys: {list(extracted_data.keys())}")

            # NEW: Add metadata to response
            extracted_data["_reasoning_traces"] = self.reasoning_traces
            extracted_data["_confidence_scores"] = confidence_scores
            extracted_data["_validation"] = validation_result
            extracted_data["_execution_time_ms"] = elapsed_ms

            return extracted_data

        except Exception as e:
            self._logger.exception(f"Error in data extraction: {e}")
            # Return empty structure on error
            return self._get_empty_result_structure()
    
    def _parse_optimized_query(self, optimized_query: str, context_messages: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
        """
        Use LLM to parse optimized query into structured tool calls
        
        Args:
            optimized_query: Optimized query string
            context_messages: Previous conversation messages for context (optional)
            
        Returns:
            Dictionary with parsed tool calls
        """
        self._logger.info("Parsing optimized query with LLM")
        
        # Build context string if available
        context_str = ""
        if context_messages and len(context_messages) > 0:
            context_lines = ["Previous conversation context:"]
            for msg in context_messages[-5:]:  # Last 5 messages for context
                role = msg.get("role", "UNKNOWN")
                content = msg.get("content", "")
                context_lines.append(f"{role}: {content}")
            context_str = "\n".join(context_lines)
            self._logger.debug(f"Using {len(context_messages)} context messages for reference resolution")
        
        # Format prompt template with optimized_query and context
        if context_str:
            # Add context to the prompt - format the template first, then append context
            base_prompt = self.template.format(optimized_query=optimized_query)
            prompt = f"{base_prompt}\n\nCONVERSATION CONTEXT:\n{context_str}\n\nIMPORTANT: If the query contains references like 'the first one', 'that company', 'the second one', etc., use the context above to resolve what they refer to. For example, if previous messages mention companies, 'the first one' refers to the first company from the previous results. Extract the specific name, ID, or identifier from the context and use it in your tool calls."
        else:
            prompt = self.template.format(optimized_query=optimized_query)
        
        self._logger.debug(f"Prompt prepared (length={len(prompt)})")
        
        # Prepare messages for LLM
        messages = [
            {"role": "system", "content": "You are a DataExtractorAgent that parses queries and returns structured JSON tool calls."},
            {"role": "user", "content": prompt}
        ]
        
        try:
            call_start = time.time()
            llm_response = self.llm_provider.chat(messages, temperature=0.1)
            call_elapsed_ms = int((time.time() - call_start) * 1000)
            self._logger.info(f"LLM parsing completed in {call_elapsed_ms} ms")
            self._logger.debug(f"LLM response: {llm_response}")
            
            # Parse JSON response
            # LLM might return JSON wrapped in code blocks or with extra text
            json_text = self._extract_json_from_response(llm_response)
            parsed = json.loads(json_text)
            
            # Validate structure
            if "tool_calls" not in parsed:
                raise ValueError("LLM response missing 'tool_calls' field")
            
            self._logger.info(f"Parsed {len(parsed['tool_calls'])} tool call(s)")
            return parsed
            
        except json.JSONDecodeError as e:
            self._logger.error(f"Failed to parse LLM JSON response: {e}")
            self._logger.debug(f"Raw response: {llm_response}")
            raise ValueError(f"Invalid JSON response from LLM: {e}")
        except Exception as exc:
            self._logger.exception(f"LLM parsing failed: {exc}")
            raise
    
    def _extract_json_from_response(self, response: str) -> str:
        """
        Extract JSON from LLM response (might be wrapped in code blocks)
        
        Args:
            response: Raw LLM response
            
        Returns:
            Extracted JSON string
        """
        response = response.strip()
        
        # Remove markdown code blocks if present
        if response.startswith("```"):
            # Find the first newline after ```
            start_idx = response.find("\n") + 1
            # Find the closing ```
            end_idx = response.rfind("```")
            if end_idx > start_idx:
                response = response[start_idx:end_idx].strip()
        
        # Remove leading/trailing whitespace and newlines
        response = response.strip()
        
        # If response doesn't start with {, try to find the JSON object
        if not response.startswith("{"):
            start_idx = response.find("{")
            if start_idx >= 0:
                response = response[start_idx:]
        
        return response
    
    async def _execute_tool_calls(self, parsed_query: Dict[str, Any], workspace_id: str, user_id: str) -> List[Dict[str, Any]]:
        """
        Execute all tool calls from parsed query

        Args:
            parsed_query: Parsed query with tool_calls
            workspace_id: Workspace identifier
            user_id: User identifier

        Returns:
            List of tool execution results with metadata
        """
        tool_calls = parsed_query.get("tool_calls", [])

        if not tool_calls:
            self._logger.warning("No tool calls in parsed query")
            return []

        self._logger.info(f"Executing {len(tool_calls)} tool call(s)")

        # Execute tools asynchronously
        results = await self._execute_tools_async(tool_calls, workspace_id, user_id)

        return results
    
    def _normalize_parameters(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Normalize parameter values to match database schema expectations

        Examples:
        - Convert 'private' → 'PRIVATE' for PrivacyLevel enum
        - Convert 'public' → 'PUBLIC' for PrivacyLevel enum

        Args:
            params: Parameter dictionary

        Returns:
            Normalized parameter dictionary
        """
        if not params:
            return params

        normalized = params.copy()

        # Normalize privacy_level to uppercase (PrivacyLevel enum: PRIVATE, PUBLIC)
        if 'privacy_level' in normalized and isinstance(normalized['privacy_level'], str):
            normalized['privacy_level'] = normalized['privacy_level'].upper()
            self._logger.debug(f"Normalized privacy_level to: {normalized['privacy_level']}")

        return normalized

    def _resolve_parameters(
        self,
        params: Dict[str, Any],
        previous_results: List[Dict[str, Any]],
        tool_index: int
    ) -> Optional[Dict[str, Any]]:
        """
        Resolve parameter placeholders using results from previous tool calls

        Placeholder format: <field_name_from_previous_call>
        Examples:
        - <company_id_from_previous_call>
        - <person_id_from_previous_call>
        - <id_from_previous_call>

        Args:
            params: Parameter dictionary that may contain placeholders
            previous_results: List of previous tool execution results
            tool_index: Current tool index (for context in logging)

        Returns:
            Resolved parameter dictionary with placeholders replaced by actual values
            Returns None if critical required parameters (person_id, company_id, etc.) failed to resolve
        """
        if not params or not previous_results:
            return params

        resolved_params = {}
        has_placeholders = False
        failed_critical_params = []

        # Define critical parameters that if missing should cause the tool call to be skipped
        critical_params = ['person_id', 'company_id', 'message_id', 'interaction_id', 'group_id']

        for key, value in params.items():
            # Check if value is a placeholder string
            if isinstance(value, str) and value.startswith('<') and value.endswith('>'):
                has_placeholders = True
                placeholder = value[1:-1]  # Remove < and >

                # Extract the actual value from previous results
                extracted_value = self._extract_value_from_results(
                    placeholder,
                    previous_results
                )

                if extracted_value is not None:
                    resolved_params[key] = extracted_value
                    self._logger.debug(
                        f"Tool {tool_index}: Resolved placeholder '{value}' -> '{extracted_value}' for param '{key}'"
                    )
                else:
                    # Could not resolve - log warning
                    self._logger.warning(
                        f"Tool {tool_index}: Could not resolve placeholder '{value}' for param '{key}'. "
                        f"Checked {len(previous_results)} previous result(s)."
                    )

                    # Check if this is a critical parameter
                    if key in critical_params:
                        failed_critical_params.append(key)
                        self._logger.error(
                            f"Tool {tool_index}: Critical parameter '{key}' failed to resolve. "
                            "This tool call should be skipped."
                        )

                    # Don't include unresolved parameters
                    continue
            else:
                # Not a placeholder, keep as-is
                resolved_params[key] = value

        # If any critical parameters failed to resolve, return None to signal failure
        if failed_critical_params:
            self._logger.warning(
                f"Tool {tool_index}: Skipping tool call due to unresolved critical parameters: {failed_critical_params}"
            )
            return None

        if has_placeholders:
            self._logger.info(
                f"Tool {tool_index}: Resolved parameters with values from previous tool calls"
            )

        return resolved_params

    def _extract_value_from_results(
        self,
        placeholder: str,
        previous_results: List[Dict[str, Any]]
    ) -> Optional[str]:
        """
        Extract value from previous tool results based on placeholder pattern

        Extraction strategies (in order of priority):
        1. Direct field match in result data (e.g., "company_id", "person_id")
        2. Extract ID from first item in results list
        3. Extract from nested data structures

        Args:
            placeholder: Placeholder string (without < >)
                        e.g., "company_id_from_previous_call", "person_id_from_previous_call"
            previous_results: List of previous tool results

        Returns:
            Extracted value or None if not found
        """
        # Parse placeholder to extract field name
        # Format: <field_name_from_previous_call>
        # Extract: field_name
        match = re.match(r'^(.+?)_from_previous_call$', placeholder)
        if match:
            field_name = match.group(1)
        else:
            # Fallback: use entire placeholder as field name
            field_name = placeholder

        # Search through previous results (most recent first)
        for result_dict in reversed(previous_results):
            result = result_dict.get('result')

            if not result or not hasattr(result, 'data') or not result.data:
                continue

            tool_data = result.data

            # Strategy 1: Direct field match in result data
            if isinstance(tool_data, dict) and field_name in tool_data:
                value = tool_data[field_name]
                if value:
                    return str(value)

            # Strategy 2: Check in list results (companies, people, etc.)
            if isinstance(tool_data, dict):
                # Check common list fields: companies, people, interactions, etc.
                for list_key in ['companies', 'people', 'interactions', 'groups']:
                    if list_key in tool_data and isinstance(tool_data[list_key], list):
                        items = tool_data[list_key]
                        if items and len(items) > 0:
                            first_item = items[0]
                            if isinstance(first_item, dict):
                                # Try to find field_name or 'id' in first item
                                if field_name in first_item:
                                    value = first_item[field_name]
                                    if value:
                                        return str(value)
                                elif 'id' in first_item and field_name.endswith('_id'):
                                    # e.g., looking for "company_id" but found "id"
                                    value = first_item['id']
                                    if value:
                                        return str(value)

            # Strategy 3: Single result object (GET_BY_ID operations)
            if isinstance(tool_data, dict) and 'id' in tool_data and field_name.endswith('_id'):
                value = tool_data['id']
                if value:
                    return str(value)

        return None

    async def _execute_tools_async(self, tool_calls: List[Dict], workspace_id: str, user_id: str) -> List[Dict[str, Any]]:
        """
        Execute tools sequentially with parameter resolution support

        This method now supports dependent tool calls where later tools can reference
        results from earlier tools using placeholder syntax like:
        - <company_id_from_previous_call>
        - <person_id_from_previous_call>

        Args:
            tool_calls: List of tool call specifications
            workspace_id: Workspace identifier
            user_id: User identifier

        Returns:
            List of tool execution results
        """
        results = []

        for tool_index, tool_call in enumerate(tool_calls):
            tool_name = tool_call.get("tool")
            query_type_str = tool_call.get("query_type", "search")
            params = tool_call.get("params", {})

            if not tool_name:
                self._logger.warning(f"Skipping tool call with no tool name: {tool_call}")
                continue

            try:
                # Resolve parameters using previous results (for dependent tool calls)
                resolved_params = self._resolve_parameters(params, results, tool_index)

                # Check if parameter resolution failed (None means critical params failed)
                if resolved_params is None:
                    # Critical parameters failed to resolve
                    self._logger.error(
                        f"Tool {tool_index} ({tool_name}): Critical required parameters could not be resolved. "
                        f"This likely means a previous tool call (e.g., company/person search) returned no results. "
                        f"Skipping this tool call."
                    )
                    results.append({
                        "tool": tool_name,
                        "query_type": query_type_str,
                        "result": None,
                        "success": False,
                        "error": "Required parameters (person_id, company_id, etc.) could not be resolved from previous tool results. The dependent entity may not exist in the system."
                    })
                    continue

                # Also check if all params are empty (edge case)
                if not resolved_params and params:
                    # All parameters were placeholders and none could be resolved
                    self._logger.error(
                        f"Tool {tool_index} ({tool_name}): All parameters are unresolved placeholders. "
                        f"Skipping this tool call."
                    )
                    results.append({
                        "tool": tool_name,
                        "query_type": query_type_str,
                        "result": None,
                        "success": False,
                        "error": "Could not resolve any parameter placeholders from previous tool results"
                    })
                    continue

                # Convert string query_type to enum
                query_type = QueryType(query_type_str.lower())

                # Normalize parameters (fix enum cases, etc.)
                normalized_params = self._normalize_parameters(resolved_params)

                # Execute tool with resolved and normalized parameters
                result = await self._execute_single_tool(
                    tool_name=tool_name,
                    query_type=query_type,
                    params=normalized_params,  # Use normalized parameters
                    workspace_id=workspace_id,
                    user_id=user_id
                )

                # NEW: Log tool execution reasoning
                self.reasoning_traces.append({
                    "step": f"execute_{tool_name}",
                    "timestamp": datetime.now().isoformat(),
                    "tool": tool_name,
                    "query_type": query_type_str,
                    "params": {k: v for k, v in resolved_params.items() if k not in ['workspace_id', 'user_id']},
                    "success": result.success if hasattr(result, 'success') else False,
                    "result_count": self._count_results(result) if result else 0,
                    "error": result.error if hasattr(result, 'error') and result.error else None
                })

                results.append({
                    "tool": tool_name,
                    "query_type": query_type_str,
                    "result": result,
                    "success": result.success if hasattr(result, 'success') else False,
                    "error": result.error if hasattr(result, 'error') and result.error else None
                })
                
            except ValueError as e:
                self._logger.error(f"Invalid query_type '{query_type_str}': {e}")
                results.append({
                    "tool": tool_name,
                    "query_type": query_type_str,
                    "result": None,
                    "success": False,
                    "error": f"Invalid query_type: {e}"
                })
            except Exception as e:
                self._logger.exception(f"Error executing tool {tool_name}: {e}")
                results.append({
                    "tool": tool_name,
                    "query_type": query_type_str,
                    "result": None,
                    "success": False,
                    "error": str(e)
                })
        
        return results
    
    async def _execute_single_tool(
        self,
        tool_name: str,
        query_type: QueryType,
        params: Dict[str, Any],
        workspace_id: str,
        user_id: str
    ) -> ToolResult:
        """
        Execute a single tool operation with automatic pagination support

        Args:
            tool_name: Name of the tool to use
            query_type: Type of query operation
            params: Parameters for the tool operation
            workspace_id: Workspace identifier
            user_id: User identifier

        Returns:
            ToolResult from tool execution (merged if paginated)
        """
        self._logger.debug(f"Executing {tool_name}.{query_type.value} with params: {params}")

        try:
            # Check if this is a paginated query type (SEARCH, LIST)
            supports_pagination = query_type in [QueryType.SEARCH, QueryType.LIST]

            if supports_pagination:
                # Execute with pagination support
                return await self._execute_with_pagination(
                    tool_name, query_type, params, workspace_id, user_id
                )
            else:
                # Execute single call for GET_BY_ID, ANALYTICS, etc.
                tool = ToolFactory.create_tool(tool_name, workspace_id, user_id)
                result = await tool.execute(query_type, **params)
                self._logger.debug(f"Tool {tool_name} executed: success={result.success}")
                return result

        except Exception as e:
            self._logger.exception(f"Error executing tool {tool_name}: {e}")
            # Return error result
            return ToolResult(
                success=False,
                error=str(e),
                execution_time_ms=0,
                metadata={"tool": tool_name, "query_type": query_type.value}
            )

    async def _execute_with_pagination(
        self,
        tool_name: str,
        query_type: QueryType,
        params: Dict[str, Any],
        workspace_id: str,
        user_id: str,
        max_pages: int = 10
    ) -> ToolResult:
        """
        Execute tool with automatic pagination to fetch all results

        Args:
            tool_name: Name of the tool
            query_type: Query type (SEARCH or LIST)
            params: Query parameters
            workspace_id: Workspace identifier
            user_id: User identifier
            max_pages: Maximum number of pages to fetch (prevent infinite loops)

        Returns:
            Merged ToolResult with all paginated data
        """
        all_results = []
        next_token = params.get('next_token')
        has_more = True
        page_count = 0
        total_execution_time = 0

        self._logger.debug(f"Starting paginated execution for {tool_name}.{query_type.value}")

        while has_more and page_count < max_pages:
            # Update pagination token in params
            if next_token and page_count > 0:
                params['next_token'] = next_token

            # Create tool and execute
            tool = ToolFactory.create_tool(tool_name, workspace_id, user_id)
            result = await tool.execute(query_type, **params)

            total_execution_time += result.execution_time_ms if result.execution_time_ms else 0

            if not result.success:
                # If first page fails, return error
                if page_count == 0:
                    return result
                # If subsequent page fails, return what we have so far
                self._logger.warning(f"Page {page_count + 1} failed, returning {page_count} page(s)")
                break

            # Collect result
            all_results.append(result)
            page_count += 1

            # Check for more pages
            if result.data and isinstance(result.data, dict):
                has_more = result.data.get('has_more', False)
                next_token = result.data.get('next_token')

                if has_more and next_token:
                    self._logger.debug(f"Fetching page {page_count + 1} for {tool_name}")
                else:
                    has_more = False
            else:
                has_more = False

        if page_count >= max_pages and has_more:
            self._logger.warning(f"Reached max_pages limit ({max_pages}) for {tool_name}, more data available")

        self._logger.info(f"Fetched {page_count} page(s) for {tool_name}.{query_type.value}")

        # Merge all paginated results
        return self._merge_paginated_results(all_results, total_execution_time)

    def _merge_paginated_results(self, results: List[ToolResult], total_execution_time: int) -> ToolResult:
        """
        Merge multiple paginated ToolResults into a single result

        Args:
            results: List of ToolResult objects from pagination
            total_execution_time: Total execution time across all pages

        Returns:
            Single merged ToolResult
        """
        if not results:
            return ToolResult(
                success=False,
                error="No results to merge",
                execution_time_ms=0
            )

        if len(results) == 1:
            return results[0]

        # Start with first result's structure
        first_result = results[0]
        merged_data = first_result.data.copy() if first_result.data else {}

        # Identify the main data key (emails, companies, people, etc.)
        data_keys = ['emails', 'companies', 'people', 'interactions', 'groups']
        main_key = None
        for key in data_keys:
            if key in merged_data and isinstance(merged_data[key], list):
                main_key = key
                break

        if main_key:
            # Merge list data from all pages
            merged_list = []
            for result in results:
                if result.data and main_key in result.data:
                    page_data = result.data[main_key]
                    if isinstance(page_data, list):
                        merged_list.extend(page_data)

            merged_data[main_key] = merged_list

            # Update metadata
            merged_data['total_count'] = len(merged_list)
            merged_data['has_more'] = results[-1].data.get('has_more', False) if results[-1].data else False
            merged_data['next_token'] = results[-1].data.get('next_token') if results[-1].data else None
            merged_data['pages_fetched'] = len(results)

        return ToolResult(
            success=True,
            data=merged_data,
            execution_time_ms=total_execution_time,
            metadata={
                **first_result.metadata,
                'paginated': True,
                'pages_fetched': len(results)
            }
        )
    
    def _aggregate_results(self, tool_results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Aggregate results from multiple tools into tool-grouped structure
        
        Args:
            tool_results: List of tool execution results
            
        Returns:
            Dictionary with data grouped by tool:
            {
                "companies": [...],
                "people": [...],
                "emails": [...],
                "interactions": [...],
                "groups": [...],
                "workspace": {...}
            }
        """
        self._logger.info("Aggregating results from tools")
        
        # Initialize empty structure
        aggregated = {
            "companies": [],
            "people": [],
            "emails": [],
            "interactions": [],
            "groups": [],
            "workspace": None
        }

        # Initialize metadata storage for pagination info
        metadata = {}

        # Track which tools were used and any errors
        tools_used = []
        errors = []
        
        # Aggregate results by tool
        for tool_result in tool_results:
            tool_name = tool_result.get("tool")
            success = tool_result.get("success", False)
            error = tool_result.get("error")
            result = tool_result.get("result")
            
            tools_used.append(tool_name)
            
            if not success:
                if error:
                    errors.append({
                        "tool": tool_name,
                        "error": error
                    })
                self._logger.warning(f"Tool {tool_name} failed: {error}")
                continue
            
            # Extract data from ToolResult
            if result and hasattr(result, 'data') and result.data:
                tool_data = result.data
                
                # Map tool names to result keys
                if tool_name == "company":
                    # Handle different return structures from company tool
                    if isinstance(tool_data, dict) and "companies" in tool_data:
                        aggregated["companies"].extend(tool_data["companies"])
                        metadata["companies"] = self._extract_metadata(tool_data)
                    elif isinstance(tool_data, list):
                        aggregated["companies"].extend(tool_data)
                    elif isinstance(tool_data, dict):
                        # Single company result
                        aggregated["companies"].append(tool_data)
                elif tool_name == "people":
                    if isinstance(tool_data, dict) and "people" in tool_data:
                        aggregated["people"].extend(tool_data["people"])
                        metadata["people"] = self._extract_metadata(tool_data)
                    elif isinstance(tool_data, list):
                        aggregated["people"].extend(tool_data)
                    elif isinstance(tool_data, dict):
                        aggregated["people"].append(tool_data)
                elif tool_name == "email":
                    if isinstance(tool_data, dict) and "emails" in tool_data:
                        aggregated["emails"].extend(tool_data["emails"])
                        # Preserve pagination and metadata for emails
                        metadata["emails"] = self._extract_metadata(tool_data)
                    elif isinstance(tool_data, list):
                        aggregated["emails"].extend(tool_data)
                    elif isinstance(tool_data, dict):
                        aggregated["emails"].append(tool_data)
                elif tool_name == "interaction":
                    if isinstance(tool_data, dict) and "interactions" in tool_data:
                        aggregated["interactions"].extend(tool_data["interactions"])
                        metadata["interactions"] = self._extract_metadata(tool_data)
                    elif isinstance(tool_data, list):
                        aggregated["interactions"].extend(tool_data)
                    elif isinstance(tool_data, dict):
                        aggregated["interactions"].append(tool_data)
                elif tool_name == "group":
                    if isinstance(tool_data, dict) and "groups" in tool_data:
                        aggregated["groups"].extend(tool_data["groups"])
                        metadata["groups"] = self._extract_metadata(tool_data)
                    elif isinstance(tool_data, list):
                        aggregated["groups"].extend(tool_data)
                    elif isinstance(tool_data, dict):
                        aggregated["groups"].append(tool_data)
                elif tool_name == "workspace":
                    aggregated["workspace"] = tool_data
                
                self._logger.debug(f"Added data from {tool_name}: {len(str(tool_data))} chars")
            else:
                self._logger.debug(f"Tool {tool_name} returned no data")
        
        # Remove empty arrays to keep response clean
        # But keep them if they're explicitly requested
        final_result = {}
        for key, value in aggregated.items():
            if value or key == "workspace":  # Keep workspace even if None
                final_result[key] = value
        
        self._logger.info(f"Aggregated results: {len([k for k, v in final_result.items() if k != 'workspace' and v])} non-empty tool groups")

        # Add metadata if present
        if metadata:
            final_result["_metadata"] = metadata

        if errors:
            final_result["_errors"] = errors

        return final_result

    def _extract_metadata(self, tool_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract pagination and other metadata from tool response

        Args:
            tool_data: Tool response data dictionary

        Returns:
            Dictionary containing metadata fields
        """
        metadata = {}

        # Extract pagination fields
        pagination_fields = ['total_count', 'has_more', 'next_token', 'limit', 'pages_fetched']
        for field in pagination_fields:
            if field in tool_data:
                metadata[field] = tool_data[field]

        # Extract other common metadata fields
        other_fields = ['person_id', 'company_id', 'workspace_id']
        for field in other_fields:
            if field in tool_data:
                metadata[field] = tool_data[field]

        return metadata if metadata else None
    
    def _get_empty_result_structure(self) -> Dict[str, Any]:
        """Return empty result structure"""
        return {
            "companies": [],
            "people": [],
            "emails": [],
            "interactions": [],
            "groups": [],
            "workspace": None
        }

    def _count_results(self, tool_result: ToolResult) -> int:
        """
        Count number of items in tool result

        Args:
            tool_result: ToolResult object

        Returns:
            Count of items in result
        """
        if not tool_result.success or not tool_result.data:
            return 0

        data = tool_result.data

        # Check common list keys
        for key in ['companies', 'people', 'emails', 'interactions', 'groups']:
            if key in data and isinstance(data[key], list):
                return len(data[key])

        # Single object result
        if isinstance(data, dict) and 'id' in data:
            return 1

        # List result
        if isinstance(data, list):
            return len(data)

        return 0

    def _score_tool_results(self, tool_results: List[Dict[str, Any]]) -> Dict[str, float]:
        """
        Score confidence for each tool result

        Scoring criteria:
        - Tool success/failure
        - Result count (0 = low, 1-50 = high, >50 = medium)
        - Data quality

        Args:
            tool_results: List of tool execution results

        Returns:
            Dictionary mapping tool names to confidence scores (0.0-1.0)
        """
        scores = {}

        for tool_result in tool_results:
            tool_name = tool_result.get("tool")
            result = tool_result.get("result")
            success = tool_result.get("success", False)

            if not success or not result:
                scores[tool_name] = 0.1
                self._logger.debug(f"Tool {tool_name} scored 0.1 (failed)")
                continue

            # Start with base score
            score = 1.0

            # Factor 1: Success/failure
            if not result.success:
                score *= 0.1
                self._logger.debug(f"Tool {tool_name}: Failed execution")

            # Factor 2: Result count
            if result.success:
                count = self._count_results(result)

                if count == 0:
                    score *= 0.3
                    self._logger.debug(f"Tool {tool_name}: No results found")
                elif count > 100:
                    score *= 0.7  # Too many results might be too broad
                    self._logger.debug(f"Tool {tool_name}: Many results ({count}), might be too broad")
                elif count > 50:
                    score *= 0.85
                    self._logger.debug(f"Tool {tool_name}: Good number of results ({count})")
                else:
                    # 1-50 results is optimal
                    self._logger.debug(f"Tool {tool_name}: Optimal result count ({count})")

            # Factor 3: Error messages
            if result.error:
                score *= 0.2
                self._logger.debug(f"Tool {tool_name}: Has error: {result.error}")

            # Factor 4: Pagination (incomplete results)
            if isinstance(result.data, dict) and result.data.get("has_more"):
                score *= 0.9  # Slightly reduce confidence for paginated results

            scores[tool_name] = round(score, 2)

            # Log reasoning trace for this tool
            self.reasoning_traces.append({
                "step": f"score_{tool_name}",
                "timestamp": datetime.now().isoformat(),
                "tool": tool_name,
                "confidence_score": scores[tool_name],
                "result_count": self._count_results(result) if success else 0,
                "success": success
            })

        return scores

    def _validate_results(
        self,
        optimized_query: str,
        extracted_data: Dict[str, Any],
        confidence_scores: Dict[str, float]
    ) -> Dict[str, Any]:
        """
        Validate extracted results using heuristic checks

        Checks performed:
        1. Is data empty?
        2. Are there errors?
        3. Does data type match query intent?
        4. Are results ambiguous (too many)?

        Args:
            optimized_query: Original optimized query
            extracted_data: Extracted data dictionary
            confidence_scores: Confidence scores per tool

        Returns:
            Dictionary with validation results:
            {
                "is_valid": bool,
                "overall_confidence": float,
                "issues": List[Dict],
                "recommendations": List[str],
                "has_data": bool
            }
        """
        issues = []
        recommendations = []

        # Check 1: Is data empty?
        has_data = any(
            len(v) > 0 if isinstance(v, list) else v is not None
            for k, v in extracted_data.items()
            if not k.startswith("_")
        )

        if not has_data:
            issues.append({
                "severity": "ERROR",
                "type": "NO_DATA",
                "message": "No data was retrieved from any tool",
                "impact": "Cannot answer user query"
            })
            recommendations.append("Check if entities exist in database or refine search criteria")

        # Check 2: Are there errors?
        if extracted_data.get("_errors"):
            error_count = len(extracted_data["_errors"])
            issues.append({
                "severity": "WARNING",
                "type": "TOOL_ERRORS",
                "message": f"{error_count} tool(s) failed during execution",
                "details": extracted_data["_errors"]
            })
            recommendations.append("Review failed tools and retry with different parameters")

        # Check 3: Query type vs data type heuristic
        query_lower = optimized_query.lower()

        # Detect if query asks for count
        is_count_query = any(word in query_lower for word in ['how many', 'count', 'number of', 'total'])

        # Detect if we returned list data
        has_list_data = any(
            isinstance(v, list) and len(v) > 0
            for k, v in extracted_data.items()
            if not k.startswith("_")
        )

        if is_count_query and has_list_data and 'analytics' not in query_lower:
            issues.append({
                "severity": "WARNING",
                "type": "TYPE_MISMATCH",
                "message": "Query asks for count but returned list of items",
                "impact": "Response formatter should count the items"
            })
            recommendations.append("Consider using analytics tool for count queries")

        # Check 4: Too many results (ambiguous query)
        for key, value in extracted_data.items():
            if isinstance(value, list) and len(value) > 50:
                issues.append({
                    "severity": "WARNING",
                    "type": "TOO_MANY_RESULTS",
                    "message": f"Retrieved {len(value)} {key}, query might be too broad",
                    "impact": "User might be overwhelmed with results"
                })
                recommendations.append(f"Consider adding filters to narrow down {key} results")

        # Calculate overall confidence
        if confidence_scores:
            overall_confidence = sum(confidence_scores.values()) / len(confidence_scores)
        else:
            overall_confidence = 0.0

        # Adjust confidence based on issues
        error_issues = [i for i in issues if i["severity"] == "ERROR"]
        if error_issues:
            overall_confidence *= 0.3
        elif not has_data:
            overall_confidence = 0.2

        validation_result = {
            "is_valid": len(error_issues) == 0,
            "overall_confidence": round(overall_confidence, 2),
            "has_data": has_data,
            "issues": issues,
            "recommendations": recommendations,
            "total_issues": len(issues),
            "error_count": len(error_issues),
            "warning_count": len([i for i in issues if i["severity"] == "WARNING"])
        }

        # Log validation reasoning
        self.reasoning_traces.append({
            "step": "validate_results",
            "timestamp": datetime.now().isoformat(),
            "overall_confidence": validation_result["overall_confidence"],
            "is_valid": validation_result["is_valid"],
            "has_data": has_data,
            "issue_count": len(issues),
            "issues_summary": [f"{i['severity']}: {i['type']}" for i in issues]
        })

        self._logger.info(
            f"Validation complete: is_valid={validation_result['is_valid']}, "
            f"confidence={validation_result['overall_confidence']:.2f}, "
            f"issues={len(issues)}"
        )

        return validation_result
