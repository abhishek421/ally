"""
DataExtractorAgent - Uses multiple tools to search different DB, tables, and data storages
"""
from typing import Dict, List, Optional, Any
import logging
import time
import json
import asyncio
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
    
    async def extract(self, optimized_query: str, workspace_id: str, user_id: str) -> Dict[str, Any]:
        """
        Main entry point to extract data based on optimized query

        Args:
            optimized_query: Optimized query string from QueryOptimizerAgent
            workspace_id: Workspace identifier for data isolation
            user_id: User identifier for access control

        Returns:
            Dictionary with extracted data grouped by tool:
            {
                "companies": [...],
                "people": [...],
                "emails": [...],
                "interactions": [...],
                "groups": [...],
                "workspace": {...}
            }
        """
        self._logger.info("Starting data extraction")
        self._logger.debug(f"Optimized query: {optimized_query}")
        self._logger.debug(f"Workspace: {workspace_id}, User: {user_id}")

        start_time = time.time()

        try:
            # Step 1: Parse optimized query using LLM
            parsed_query = self._parse_optimized_query(optimized_query)
            self._logger.debug(f"Parsed query: {parsed_query}")

            # Step 2: Execute tool calls
            tool_results = await self._execute_tool_calls(parsed_query, workspace_id, user_id)

            # Step 3: Aggregate results in tool-grouped structure
            extracted_data = self._aggregate_results(tool_results)

            elapsed_ms = int((time.time() - start_time) * 1000)
            self._logger.info(f"Data extraction completed in {elapsed_ms} ms")
            self._logger.debug(f"Extracted data keys: {list(extracted_data.keys())}")

            return extracted_data

        except Exception as e:
            self._logger.exception(f"Error in data extraction: {e}")
            # Return empty structure on error
            return self._get_empty_result_structure()
    
    def _parse_optimized_query(self, optimized_query: str) -> Dict[str, Any]:
        """
        Use LLM to parse optimized query into structured tool calls
        
        Args:
            optimized_query: Optimized query string
            
        Returns:
            Dictionary with parsed tool calls
        """
        self._logger.info("Parsing optimized query with LLM")
        
        # Format prompt template with optimized_query
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
    
    async def _execute_tools_async(self, tool_calls: List[Dict], workspace_id: str, user_id: str) -> List[Dict[str, Any]]:
        """
        Execute tools asynchronously
        
        Args:
            tool_calls: List of tool call specifications
            workspace_id: Workspace identifier
            user_id: User identifier
            
        Returns:
            List of tool execution results
        """
        results = []
        
        for tool_call in tool_calls:
            tool_name = tool_call.get("tool")
            query_type_str = tool_call.get("query_type", "search")
            params = tool_call.get("params", {})
            
            if not tool_name:
                self._logger.warning(f"Skipping tool call with no tool name: {tool_call}")
                continue
            
            try:
                # Convert string query_type to enum
                query_type = QueryType(query_type_str.lower())
                
                # Execute tool
                result = await self._execute_single_tool(
                    tool_name=tool_name,
                    query_type=query_type,
                    params=params,
                    workspace_id=workspace_id,
                    user_id=user_id
                )
                
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
        Execute a single tool operation
        
        Args:
            tool_name: Name of the tool to use
            query_type: Type of query operation
            params: Parameters for the tool operation
            workspace_id: Workspace identifier
            user_id: User identifier
            
        Returns:
            ToolResult from tool execution
        """
        self._logger.debug(f"Executing {tool_name}.{query_type.value} with params: {params}")
        
        try:
            # Create tool instance
            tool = ToolFactory.create_tool(tool_name, workspace_id, user_id)
            
            # Execute tool operation
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
                    elif isinstance(tool_data, list):
                        aggregated["companies"].extend(tool_data)
                    elif isinstance(tool_data, dict):
                        # Single company result
                        aggregated["companies"].append(tool_data)
                elif tool_name == "people":
                    if isinstance(tool_data, dict) and "people" in tool_data:
                        aggregated["people"].extend(tool_data["people"])
                    elif isinstance(tool_data, list):
                        aggregated["people"].extend(tool_data)
                    elif isinstance(tool_data, dict):
                        aggregated["people"].append(tool_data)
                elif tool_name == "email":
                    if isinstance(tool_data, dict) and "emails" in tool_data:
                        aggregated["emails"].extend(tool_data["emails"])
                    elif isinstance(tool_data, list):
                        aggregated["emails"].extend(tool_data)
                    elif isinstance(tool_data, dict):
                        aggregated["emails"].append(tool_data)
                elif tool_name == "interaction":
                    if isinstance(tool_data, dict) and "interactions" in tool_data:
                        aggregated["interactions"].extend(tool_data["interactions"])
                    elif isinstance(tool_data, list):
                        aggregated["interactions"].extend(tool_data)
                    elif isinstance(tool_data, dict):
                        aggregated["interactions"].append(tool_data)
                elif tool_name == "group":
                    if isinstance(tool_data, dict) and "groups" in tool_data:
                        aggregated["groups"].extend(tool_data["groups"])
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
        
        if errors:
            final_result["_errors"] = errors
        
        return final_result
    
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
