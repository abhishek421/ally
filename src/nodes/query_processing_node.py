"""Query Processing Node - Processes queries using Plan-and-Solve pattern with dspy."""

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
        # Configure dspy with the LM. 
        # We avoid enforcing a strict JSON adapter globally as it can be brittle.
        # ChatAdapter is usually more flexible.
        dspy.configure(lm=_dspy_lm) 
    return _dspy_lm


class GeneratePlan(dspy.Signature):
    """Generate a step-by-step plan to answer the user's request using available tools.
    
    Analyze the user's request and the available tools. Create a numbered list of steps 
    to solve the problem efficiently. Do not execute the tools, just plan the steps.
    The plan should be logical, efficient, and directly address the user's goal.
    """
    
    context = dspy.InputField(desc="Context including available tools and conversation history")
    question = dspy.InputField(desc="The user's question or request")
    plan = dspy.OutputField(desc="A clear, numbered list of steps to execute")


class Planner(dspy.Module):
    """Planning module that generates execution plans."""
    
    def __init__(self):
        super().__init__()
        # Use Predict instead of ChainOfThought to simplify output and avoid "reasoning" field parsing issues
        self.generate_plan = dspy.Predict(GeneratePlan)
    
    def forward(self, question: str, context: str) -> str:
        """Generate a plan for the given question and context.
        
        Args:
            question: User's question
            context: Context string with tools and history
            
        Returns:
            Generated plan string
        """
        try:
            response = self.generate_plan(context=context, question=question)
            return response.plan
        except Exception as e:
            logger.warning(f"Planner failed to generate structured plan: {e}. Fallback to simple generation.")
            # Fallback: direct prompt if DSPy signature fails
            lm = dspy.settings.lm
            prompt = f"""
            You are a planner.
            Context: {context}
            Question: {question}
            
            Create a numbered list of steps to solve this request using the available tools.
            PLAN:
            """
            return lm(prompt)


class ReActWithTools(dspy.Module):
    """ReAct module with tool support."""

    def __init__(
        self,
        tools: List[Dict[str, Any]],
        max_iterations: int = 10,
        workspace_id: Optional[str] = None,
        user_id: Optional[str] = None,
    ):
        """Initialize ReAct module with tools.

        Args:
            tools: List of available tools
            max_iterations: Maximum number of reasoning iterations
            workspace_id: Workspace ID to automatically inject into tool calls
            user_id: User ID to automatically inject into tool calls (for write operations)
        """
        super().__init__()
        self.tools = {tool["name"]: tool for tool in tools}
        self.max_iterations = max_iterations
        self.tool_registry = get_tool_registry()
        self.workspace_id = workspace_id or settings.workspace_id
        self.user_id = user_id
        if not self.workspace_id:
            logger.warning("No workspace_id provided. Tool calls may fail if workspace_id is required.")

    def forward(self, question: str, plan: Optional[str] = None) -> dspy.Prediction:
        """Execute ReAct reasoning with tool support.

        Args:
            question: User question or full context string to answer
            plan: Optional execution plan to follow

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

        # Get the LM instance
        lm = dspy.settings.lm

        # ReAct loop
        for iteration in range(self.max_iterations):
            # Build context
            context = f"Context & Request:\n{question}\n\n"
            
            if plan:
                context += f"APPROVED PLAN:\n{plan}\n\n"
                context += "INSTRUCTIONS: Execute the plan above step-by-step. Do not deviate unless necessary.\n\n"
            
            if tools_description:
                context += f"Available tools:\n{tools_description}\n\n"

            if context_history:
                context += "Previous steps:\n"
                for entry in context_history[-5:]:  # Show last 5 entries for better context
                    context += f"- {entry}\n"
                context += "\n"

            context += (
                "You are a friendly, alive, and direct business analyst AI. You have a personality. "
                "You are not just a tool; you are a partner in analysis. Be concise and direct. "
                "If the data is large, big messages are fine. If not, keep it brief. "
                "Avoid irrelevant long messages.\n\n"
                "IMPORTANT: You do NOT have direct access to data. You MUST use tools to retrieve information.\n"
                "If you cannot perform an action (like adding a person) because you lack the tool, "
                "say so directly. Do NOT suggest logging into the CRM or navigating to the website. "
                "I don't need that generic advice.\n\n"
                "CRITICAL - User-Friendly Responses:\n"
                "- NEVER include UUIDs, IDs, or technical identifiers in your responses to the user.\n"
                "- NEVER mention workspace_id, user_id, company_id, person_id, or any internal IDs.\n"
                "- Use names and descriptions instead of IDs (e.g., say 'Created company Entreship' NOT 'Created company with ID abc-123').\n"
                "- Keep responses natural and conversational, as if talking to a non-technical business user.\n"
                "- When referring to entities from previous messages, use their names, not IDs.\n"
                "- If tool results contain duplicate entities (same name, different ID), treat them as the same entity and only list unique names.\n\n"
                "When interpreting tool results, pay attention to metadata fields like 'total' or 'count' in the response. "
                "If the user's question asks for a 'total', 'count', or 'number of' items, and the tool returns a 'total' field, "
                "use this value as the answer. "
                "However, if the user asks to 'list', 'show', or 'find' items, use the 'results' list to provide the details.\n\n"
                "Format your final answer in clean, readable Markdown.\n\n"
                "You MUST respond in one of these formats:\n\n"
                "Format 1 - To use a tool (USE THIS to get information):\n"
                "ACTION: use_tool\n"
                "TOOL: <exact_tool_name>\n"
                "PARAMS: {\"param1\": \"value1\", \"param2\": \"value2\"}\n\n"
                "Format 2 - To provide final answer (ONLY after you have tool results):\n"
                "ACTION: answer\n"
                "ANSWER: <your comprehensive answer based on tool results>\n\n"
                "Format 3 - To continue reasoning (if you need to think more):\n"
                "Just explain your thoughts without ACTION keyword.\n\n"
                "If you need information, you MUST use a tool first. Choose one format and respond now:"
            )
            
            try:
                # Call LM directly to avoid JSON parsing issues
                response = lm(context)
                
                # Parse the response
                action = "continue"
                tool_name = ""
                tool_params_str = ""
                reasoning = response
                
                # Robust parsing logic
                lines = response.split("\n")
                for i, line in enumerate(lines):
                    line_stripped = line.strip()
                    line_upper = line_stripped.upper()
                    
                    # Check for ACTION
                    if line_upper.startswith("ACTION:"):
                        action_value = line_stripped.split(":", 1)[1].strip().lower()
                        
                        # More permissive action checking
                        if "use_tool" in action_value or "tool" in action_value or action_value in self.tools:
                            action = "use_tool"
                            # If the action value itself IS the tool name (e.g., "ACTION: search_companies")
                            if action_value in self.tools:
                                tool_name = action_value
                        elif "answer" in action_value:
                            action = "answer"
                    
                    # Check for TOOL (only if action is use_tool)
                    if line_upper.startswith("TOOL:") and action == "use_tool":
                        candidate_name = line_stripped.split(":", 1)[1].strip().strip("\"' ")
                        if candidate_name:
                            tool_name = candidate_name
                    
                    # Check for PARAMS (only if action is use_tool)
                    if line_upper.startswith("PARAMS:") and action == "use_tool":
                        # Extract params part
                        params_part = line_stripped.split(":", 1)[1].strip()
                        
                        # If it looks like it starts a JSON block, try to capture multi-line
                        if not params_part or params_part.startswith("{"):
                            # Accumulate lines until we find matching braces or end of block
                            buffer = params_part
                            # If it's a single line JSON, fine. If not, read ahead.
                            if not buffer.endswith("}"):
                                for j in range(i + 1, len(lines)):
                                    next_line = lines[j]
                                    buffer += "\n" + next_line
                                    # Crude check for end of JSON
                                    if next_line.strip().endswith("}"):
                                        break
                            tool_params_str = buffer
                        else:
                            tool_params_str = params_part

                    # Check for ANSWER
                    if line_upper.startswith("ANSWER:") and action == "answer":
                        answer = line_stripped.split(":", 1)[1].strip()
                        # Collect remaining lines
                        for j in range(i + 1, len(lines)):
                            answer += "\n" + lines[j]
                        break
                
            except Exception as e:
                logger.error(f"ReAct iteration {iteration + 1} failed", error=str(e))
                reasoning = f"Error in reasoning: {str(e)}"
                # Fallback: Don't force answer immediately, try to continue
                action = "continue" 
                tool_name = ""
                tool_params_str = ""

            reasoning_steps.append(reasoning)
            logger.info(f"ReAct iteration {iteration + 1}", reasoning=reasoning[:200], action=action)

            # Check if we should call a tool
            if action == "use_tool" and tool_name:
                if tool_name in self.tools:
                    # Extract and parse tool parameters
                    tool_params = self._extract_tool_params(tool_name, tool_params_str, reasoning)
                    
                    # Call tool
                    tool_result = self._call_tool(tool_name, tool_params)
                    tool_call_record = {
                        "tool": tool_name,
                        "params": tool_params,
                        "result": str(tool_result)[:20000],  # Limit result length
                        "iteration": iteration + 1,
                    }
                    tool_calls.append(tool_call_record)
                    
                    # Truncate result in history to save context
                    result_preview = str(tool_result)
                    if len(result_preview) > settings.tool_result_limit:
                        result_preview = result_preview[:settings.tool_result_limit] + "... (truncated)"
                    context_history.append(f"Tool {tool_name} called with params {tool_params}\nResult: {result_preview}")
                    
                    logger.info(f"Tool called: {tool_name}", params=tool_params, result_preview=str(tool_result)[:100])
                else:
                    context_history.append(f"Error: Tool '{tool_name}' does not exist. Please check the Available Tools list.")
            elif action == "answer":
                # If answer wasn't extracted from ANSWER: tag, try to generate one or use reasoning
                if not answer:
                    # Check if the reasoning itself looks like an answer
                    if "answer is" in reasoning.lower() or len(reasoning) > 20:
                         answer = reasoning
                    else:
                        # Generate answer
                        answer_context = f"Original Request:\n{question}\n\n"
                        if reasoning_steps:
                            answer_context += "Reasoning: " + " ".join(reasoning_steps[-2:]) + "\n\n"
                        if tool_calls:
                            answer_context += "Tool results:\n"
                            for call in tool_calls:
                                answer_context += f"- {call['tool']}: {call['result'][:20000]}\n"
                        answer_context += "\n"
                        answer_context += "Provide a comprehensive answer based on the above information."

                        try:
                            answer = lm(answer_context)
                        except Exception as e:
                            logger.error(f"Answer generation failed", error=str(e))
                            answer = "I encountered an error while generating the answer."
                break
            else:
                # Continue reasoning
                context_history.append(reasoning[:200])

        # If no answer yet, generate one
        if not answer:
            final_context = f"Original Request:\n{question}\n\n"
            if reasoning_steps:
                final_context += "Reasoning: " + " ".join(reasoning_steps[-3:]) + "\n\n"
            if tool_calls:
                final_context += "Tool results:\n"
                for call in tool_calls:
                    final_context += f"- {call['tool']}: {call['result'][:20000]}\n"
                final_context += "\n"
            final_context += "Provide a comprehensive answer based on the above information."

            try:
                answer = lm(final_context)
            except Exception as e:
                logger.error(f"Final answer generation failed", error=str(e))
                answer = "I couldn't generate a complete answer due to an error."

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
            try:
                # First, try direct JSON parse
                params = json.loads(tool_params_str)
            except json.JSONDecodeError:
                # If that fails, try to extract valid JSON substring
                try:
                    # Match anything starting with { and ending with }
                    # Use a more robust method for finding the matching brace
                    start_idx = tool_params_str.find('{')
                    if start_idx != -1:
                        # Simple counter for balanced braces
                        count = 0
                        end_idx = -1
                        for i, char in enumerate(tool_params_str[start_idx:], start_idx):
                            if char == '{':
                                count += 1
                            elif char == '}':
                                count -= 1
                                if count == 0:
                                    end_idx = i + 1
                                    break
                        
                        if end_idx != -1:
                            json_str = tool_params_str[start_idx:end_idx]
                            params = json.loads(json_str)
                except Exception:
                    pass

        # If no params extracted yet, try to extract from reasoning text (fallback)
        if not params and params_schema:
            for param_name in params_schema.keys():
                # Look for param_name: value pattern
                # Improved regex to handle quoted values better
                pattern = rf"{param_name}['\"]?\s*[:=]\s*['\"]?([^,\s\)]+)"
                match = re.search(pattern, reasoning, re.IGNORECASE)
                if match:
                    # Clean up the value
                    val = match.group(1).strip("'\" ,")
                    params[param_name] = val

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

            # Always inject/override workspace_id if available
            # This ensures correct workspace_id even if LLM provides a placeholder
            if self.workspace_id:
                params["workspace_id"] = self.workspace_id

            # Also inject user_id for write operations
            # This ensures correct user_id even if LLM provides a placeholder
            if self.user_id:
                params["user_id"] = self.user_id

            result = tool.execute(**params)
            return result
        except Exception as e:
            logger.error(f"Tool execution error: {tool_name}", error=str(e), params=params)
            return f"Error executing tool: {str(e)}"


def query_processing_node(state: GraphState) -> Dict[str, Any]:
    """Process query using Plan-and-Solve pattern with dspy.

    This node takes the enriched query from query_builder_node and processes it
    using a two-step approach:
    1. Planner: Generates a high-level execution plan
    2. Executor (ReAct): Executes the plan using tools

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

        # Get workspace_id from state (prefer state over settings)
        workspace_id = state.get("workspace_id")
        if not workspace_id:
            # Fallback to settings if not in state
            workspace_id = settings.workspace_id

        # Get user_id from state (needed for write operations)
        user_id = state.get("user_id")

        # 1. GENERATE PLAN
        logger.info("Generating execution plan...")
        
        planner = Planner()
        
        # Build simple tool list string for the planner (lighter context)
        tools_list = "\n".join([f"- {t['name']}: {t['description']}" for t in tools])
        planner_context = f"Available Tools:\n{tools_list}\n\nOriginal Query:\n{enriched_query}"
        
        generated_plan = planner(question=enriched_query, context=planner_context)
        logger.info(f"Plan generated: {generated_plan}")

        # 2. EXECUTE PLAN
        logger.info("Executing plan with ReAct...", plan_length=len(generated_plan))
        
        # Create ReAct module
        react_module = ReActWithTools(
            tools=tools,
            max_iterations=settings.max_react_iterations,
            workspace_id=workspace_id,
            user_id=user_id,
        )

        # Execute ReAct with the generated plan
        # Note: We pass the FULL enriched query and the plan
        result = react_module(question=enriched_query, plan=generated_plan)
        
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
            "query": enriched_query,
            "plan": generated_plan, # Return the plan in the response
            "metadata": {
                "iterations": len(reasoning_steps),
                "tools_used": [tc["tool"] for tc in tool_calls],
                "timestamp": None,
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
                "generated_plan": generated_plan,
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
