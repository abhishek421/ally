"""Query Processing Node - Processes queries using ReAct pattern with dspy."""

import json
import re
from typing import Any, Dict, List, Optional

import dspy

from ..config import get_settings
from ..graph.state import GraphState
from ..tools.registry import get_tool_registry
from ..utils.logger import get_logger
from ..utils.dspy_adapter import get_dspy_lm

logger = get_logger(__name__)
settings = get_settings()

# Global dspy LM instance
_dspy_lm = None


def _get_dspy_lm():
    """Get or create dspy language model instance.

    Returns:
        dspy language model instance
    """
    global _dspy_lm
    if _dspy_lm is None:
        _dspy_lm = get_dspy_lm(model_name=settings.query_processing_model)
        dspy.configure(lm=_dspy_lm)
    return _dspy_lm


class ReActWithTools(dspy.Module):
    """ReAct module with tool support."""

    def __init__(self, tools: List[Dict[str, Any]], max_iterations: int = 10, workspace_id: Optional[str] = None):
        """Initialize ReAct module with tools.

        Args:
            tools: List of available tools
            max_iterations: Maximum number of reasoning iterations
            workspace_id: Workspace ID to automatically inject into tool calls
        """
        super().__init__()
        self.tools = {tool["name"]: tool for tool in tools}
        self.max_iterations = max_iterations
        self.tool_registry = get_tool_registry()
        self.workspace_id = workspace_id or settings.workspace_id
        if not self.workspace_id:
            logger.warning("No workspace_id provided. Tool calls may fail if workspace_id is required.")

    def forward(self, question: str) -> dspy.Prediction:
        """Execute ReAct reasoning with tool support.

        Args:
            question: User question to answer

        Returns:
            Prediction with answer and reasoning steps
        """
        # Initialize reasoning state
        reasoning_steps = []
        tool_calls = []
        answer = None
        context_history = []

        # Build tools description for LLM
        tools_description = self._build_tools_description()

        # ReAct loop
        for iteration in range(self.max_iterations):
            # Build context
            context = f"Question: {question}\n\n"
            
            if tools_description:
                context += f"Available tools:\n{tools_description}\n\n"

            if context_history:
                context += "Previous context:\n"
                for entry in context_history[-3:]:  # Last 3 entries
                    context += f"- {entry}\n"
                context += "\n"

            # Reason about next action
            reason_signature = "context -> reasoning, action, tool_name, tool_params"
            reason_prompt = (
                f"{context}\n"
                "Think step by step about what to do next. "
                "If you need to use a tool, specify which tool and what parameters. "
                "If you have enough information, provide the final answer."
            )
            
            reasoning_pred = dspy.ChainOfThought(reason_signature)(context=reason_prompt)
            reasoning = reasoning_pred.reasoning
            action = getattr(reasoning_pred, "action", "").lower() if hasattr(reasoning_pred, "action") else ""
            tool_name = getattr(reasoning_pred, "tool_name", "").strip() if hasattr(reasoning_pred, "tool_name") else ""
            tool_params_str = getattr(reasoning_pred, "tool_params", "") if hasattr(reasoning_pred, "tool_params") else ""

            reasoning_steps.append(reasoning)
            logger.info(f"ReAct iteration {iteration + 1}", reasoning=reasoning[:200], action=action)

            # Check if we should call a tool
            if action == "use_tool" or tool_name:
                if not tool_name:
                    # Try to extract tool name from reasoning
                    for tool in self.tools.keys():
                        if tool.lower() in reasoning.lower():
                            tool_name = tool
                            break

                if tool_name and tool_name in self.tools:
                    # Extract and parse tool parameters
                    tool_params = self._extract_tool_params(tool_name, tool_params_str, reasoning)
                    
                    # Call tool
                    tool_result = self._call_tool(tool_name, tool_params)
                    tool_call_record = {
                        "tool": tool_name,
                        "params": tool_params,
                        "result": str(tool_result)[:500],  # Limit result length
                        "iteration": iteration + 1,
                    }
                    tool_calls.append(tool_call_record)
                    context_history.append(f"Tool {tool_name} called with params {tool_params}, result: {str(tool_result)[:100]}")
                    logger.info(f"Tool called: {tool_name}", params=tool_params, result_preview=str(tool_result)[:100])
                else:
                    context_history.append(f"Attempted to call unknown tool: {tool_name}")
            elif action == "answer" or "answer" in reasoning.lower()[-50:]:
                # Generate final answer
                answer_context = f"Question: {question}\n\n"
                if reasoning_steps:
                    answer_context += "Reasoning: " + " ".join(reasoning_steps[-2:]) + "\n\n"
                if tool_calls:
                    answer_context += "Tool results:\n"
                    for call in tool_calls:
                        answer_context += f"- {call['tool']}: {call['result'][:200]}\n"
                    answer_context += "\n"

                answer_signature = "context -> answer"
                answer_pred = dspy.ChainOfThought(answer_signature)(context=f"{answer_context}Provide a comprehensive answer:")
                answer = answer_pred.answer
                break
            else:
                # Continue reasoning
                context_history.append(reasoning[:100])

        # If no answer yet, generate one
        if not answer:
            final_context = f"Question: {question}\n\n"
            if reasoning_steps:
                final_context += "Reasoning: " + " ".join(reasoning_steps[-3:]) + "\n\n"
            if tool_calls:
                final_context += "Tool results:\n"
                for call in tool_calls:
                    final_context += f"- {call['tool']}: {call['result'][:200]}\n"
                final_context += "\n"

            answer_pred = dspy.ChainOfThought("context -> answer")(context=f"{final_context}Provide a comprehensive answer:")
            answer = answer_pred.answer

        return dspy.Prediction(
            answer=answer or "I couldn't generate a complete answer.",
            reasoning_steps=reasoning_steps,
            tool_calls=tool_calls,
        )

    def _build_tools_description(self) -> str:
        """Build tools description for LLM context.

        Returns:
            Formatted tools description
        """
        if not self.tools:
            return ""

        desc_lines = []
        for tool_name, tool_info in self.tools.items():
            desc = f"- {tool_name}: {tool_info['description']}"
            params = tool_info.get("parameters", {}).get("properties", {})
            if params:
                param_list = ", ".join([f"{name} ({info.get('type', 'string')})" for name, info in params.items()])
                desc += f" [Parameters: {param_list}]"
            desc_lines.append(desc)

        return "\n".join(desc_lines)

    def _extract_tool_params(self, tool_name: str, tool_params_str: str, reasoning: str) -> Dict[str, Any]:
        """Extract tool parameters from reasoning text.

        Args:
            tool_name: Name of tool
            tool_params_str: Explicit parameter string (if provided)
            reasoning: Reasoning text that may contain parameters

        Returns:
            Dictionary of parameters
        """
        tool_info = self.tools.get(tool_name, {})
        params_schema = tool_info.get("parameters", {}).get("properties", {})
        
        params = {}
        
        # Try to parse explicit params string
        if tool_params_str:
            # Simple JSON-like parsing
            try:
                # Try to extract JSON from string
                json_match = re.search(r'\{[^}]+\}', tool_params_str)
                if json_match:
                    params = json.loads(json_match.group())
            except:
                pass

        # If no params extracted, try to extract from reasoning
        if not params and params_schema:
            for param_name in params_schema.keys():
                # Look for param_name: value pattern
                pattern = rf"{param_name}['\"]?\s*[:=]\s*['\"]?([^,\s\)]+)"
                match = re.search(pattern, reasoning, re.IGNORECASE)
                if match:
                    params[param_name] = match.group(1).strip("'\" ")

        return params

    def _call_tool(self, tool_name: str, params: Dict[str, Any]) -> Any:
        """Call a tool by name.

        Args:
            tool_name: Name of tool to call
            params: Tool parameters

        Returns:
            Tool execution result
        """
        try:
            tool = self.tool_registry.get(tool_name)
            if not tool:
                return f"Error: Tool '{tool_name}' not found"

            # Automatically inject workspace_id if not provided and available
            if self.workspace_id and "workspace_id" not in params:
                params["workspace_id"] = self.workspace_id

            result = tool.execute(**params)
            return result
        except Exception as e:
            logger.error(f"Tool execution error: {tool_name}", error=str(e), params=params)
            return f"Error executing tool: {str(e)}"


def query_processing_node(state: GraphState) -> Dict[str, Any]:
    """Process query using ReAct pattern with dspy.

    This node takes the enriched query from query_builder_node and processes it
    using ReAct (Reasoning + Acting) pattern with tool support.

    Args:
        state: Current graph state containing query_builder_result

    Returns:
        Dictionary with query_processing_result and metadata
    """
    logger.info("Query Processing Node: Starting processing")

    # Get enriched query from query_builder_node
    enriched_query = state.get("query_builder_result")
    if not enriched_query:
        logger.warning("No query_builder_result found in state")
        enriched_query = state.get("user_query", "")

    if not enriched_query:
        logger.error("No query to process")
        return {
            "query_processing_result": "",
            "query_processing_metadata": {"error": "No query to process"},
            "execution_path": state.get("execution_path", []) + ["query_processing_node"],
            "errors": (state.get("errors", []) or []) + ["No query to process"],
        }

    try:
        # Initialize dspy
        lm = _get_dspy_lm()

        # Get available tools
        tool_registry = get_tool_registry()
        tools = tool_registry.get_tool_descriptions() if settings.enable_tools else []

        # Get workspace_id from state or settings
        workspace_id = state.get("workspace_id") or settings.workspace_id

        # Create ReAct module
        react_module = ReActWithTools(
            tools=tools,
            max_iterations=settings.max_react_iterations,
            workspace_id=workspace_id,
        )

        # Process query
        logger.info("Starting ReAct processing", query_length=len(enriched_query), tools_count=len(tools))

        # Extract the actual question from enriched query (remove context)
        # The enriched query has format: "Previous conversation summary: ... Recent conversation history: ... Current query: ..."
        # We want just the current query part
        if "Current query:" in enriched_query:
            question = enriched_query.split("Current query:")[-1].strip()
        else:
            question = enriched_query

        # Execute ReAct with streaming support
        # For now, we'll collect streaming output but return final result
        # Streaming can be implemented via callbacks or async generators in future
        result = react_module(question=question)
        
        # Note: Full streaming support would require async/callback mechanism
        # For now, we collect all results and return as JSON

        # Extract answer and metadata
        answer = result.answer if hasattr(result, "answer") else str(result)
        reasoning_steps = result.reasoning_steps if hasattr(result, "reasoning_steps") else []
        tool_calls = result.tool_calls if hasattr(result, "tool_calls") else []

        # Log tool calls
        if tool_calls:
            logger.info(f"Tool calls made: {len(tool_calls)}", tool_calls=tool_calls)

        # Create JSON response
        response_data = {
            "answer": answer,
            "reasoning_steps": reasoning_steps,
            "tool_calls": tool_calls,
            "query": question,
            "metadata": {
                "iterations": len(reasoning_steps),
                "tools_used": [tc["tool"] for tc in tool_calls],
                "timestamp": None,  # Will be set by caller if needed
            },
        }

        logger.info(
            "Query Processing Node: Processing complete",
            answer_length=len(answer),
            reasoning_steps_count=len(reasoning_steps),
            tool_calls_count=len(tool_calls),
        )

        # Update execution path
        execution_path = state.get("execution_path", [])
        execution_path = execution_path + ["query_processing_node"] if execution_path else ["query_processing_node"]

        return {
            "query_processing_result": json.dumps(response_data, indent=2),
            "query_processing_metadata": {
                "reasoning_steps_count": len(reasoning_steps),
                "tool_calls_count": len(tool_calls),
                "tools_used": [tc["tool"] for tc in tool_calls],
            },
            "tool_calls": tool_calls,
            "execution_path": execution_path,
            "metadata": {
                **state.get("metadata", {}),
                "query_processing_completed": True,
            },
        }

    except Exception as e:
        logger.error("Query processing failed", error=str(e), exc_info=True)
        return {
            "query_processing_result": json.dumps({"error": str(e), "answer": ""}),
            "query_processing_metadata": {"error": str(e)},
            "execution_path": state.get("execution_path", []) + ["query_processing_node"],
            "errors": (state.get("errors", []) or []) + [f"Query processing error: {str(e)}"],
        }

