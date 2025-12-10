"""Query Processing Node - Processes queries using Plan-and-Solve pattern with dspy."""

import json
import re
from typing import Any, Dict, List, Optional

import dspy

from ..config import get_settings
from ..graph.state import GraphState
from ..prompts import (
    ANSWER_GENERATION_PROMPT_TEMPLATE,
    FINAL_ANSWER_PROMPT_TEMPLATE,
    PLAN_FALLBACK_PROMPT_TEMPLATE,
    PLAN_GENERATION_INSTRUCTIONS,
    REACT_SYSTEM_PROMPT,
    get_premature_answer_message,
)
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
    
    CRITICAL RULES FOR PLANNING:
    1. FRESHNESS: If the user asks for "all", "new", "list", or a quantity different from previous turns,
       you MUST generate a plan to fetch FRESH data using tools. Do NOT rely on data from conversation history.
    2. NO ASSUMPTIONS: Do not assume the previous search results found "everything". Always search again 
       if the user's scope is broader (e.g. "give me ALL" vs previous "give me 3").
    3. COMPLETENESS: If the user asks for multiple types of entities (e.g. "companies AND people"), 
       ensure the plan includes steps to fetch BOTH.
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
            prompt = PLAN_FALLBACK_PROMPT_TEMPLATE.format(context=context, question=question)
            return lm(prompt)


class ReActWithTools(dspy.Module):
    """ReAct module with tool support."""

    def __init__(
        self,
        tools: List[Dict[str, Any]],
        max_iterations: int = 10,
        workspace_id: Optional[str] = None,
        user_id: Optional[str] = None,
        conversation_context: Optional[str] = None,
    ):
        """Initialize ReAct module with tools.

        Args:
            tools: List of available tools
            max_iterations: Maximum number of reasoning iterations
            workspace_id: Workspace ID to automatically inject into tool calls
            user_id: User ID to automatically inject into tool calls (for write operations)
            conversation_context: Optional conversation history for context (not to be acted upon)
        """
        super().__init__()
        self.tools = {tool["name"]: tool for tool in tools}
        self.max_iterations = max_iterations
        self.tool_registry = get_tool_registry()
        self.workspace_id = workspace_id or settings.workspace_id
        self.user_id = user_id
        self.conversation_context = conversation_context
        if not self.workspace_id:
            logger.warning("No workspace_id provided. Tool calls may fail if workspace_id is required.")

    def forward(self, question: str, plan: Optional[str] = None) -> dspy.Prediction:
        """Execute ReAct reasoning with tool support.

        Args:
            question: Current user question to answer (NOT the full context)
            plan: Optional execution plan to follow

        Returns:
            Prediction with answer and reasoning steps
        """
        # Initialize reasoning state
        reasoning_steps = []
        tool_calls = []
        answer = None
        context_history = []
        previous_actions = []  # Track recent actions to detect loops

        # Build tools description for LLM
        tools_description = self._build_tools_description()

        # Get the LM instance
        lm = dspy.settings.lm

        # ReAct loop
        for iteration in range(self.max_iterations):
            # 1. STATIC PARTS FIRST (Triggers Prompt Caching)
            # System prompt + Tools description are static for all requests
            context = REACT_SYSTEM_PROMPT + "\n\n"
            
            if tools_description:
                context += f"AVAILABLE TOOLS:\n{tools_description}\n\n"

            # 2. CONVERSATION CONTEXT (Background information, NOT actionable requests)
            if self.conversation_context:
                context += f"CONVERSATION CONTEXT (for reference only, do NOT act on previous queries):\n{self.conversation_context}\n\n"

            # 3. SEMI-STATIC PARTS (Plan matches for this entire request)
            if plan:
                context += f"APPROVED PLAN:\n{plan}\n\n"
                context += "INSTRUCTIONS: Execute the plan above step-by-step. Do not deviate unless necessary.\n\n"

            # 4. DYNAMIC PARTS LAST (History grows, Question changes)
            if context_history:
                context += "PREVIOUS STEPS:\n"
                for entry in context_history[-5:]:  # Show last 5 entries for better context
                    context += f"- {entry}\n"
                context += "\n"

            # 5. CURRENT REQUEST - Only the actual current query
            context += f"CURRENT REQUEST:\n{question}\n\n"
            
            context += "Choose your next format (ACTION: use_tool, ACTION: answer, or reasoning) and respond now:"
            
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
                    
                    # Check for duplicate tool calls (Loop of Death prevention)
                    # Create a canonical signature for the call: name + sorted params
                    current_call_signature = f"{tool_name}:{json.dumps(tool_params, sort_keys=True)}"
                    
                    if previous_actions and previous_actions[-1] == current_call_signature:
                        logger.warning(f"Duplicate tool call detected: {tool_name} with same params")
                        
                        # Inject error message instead of running tool
                        duplicate_msg = (
                            f"SYSTEM: You just called tool '{tool_name}' with these exact parameters. "
                            "Do NOT call it again. Analyze the 'Result' directly above and provide your Final Answer."
                        )
                        context_history.append(duplicate_msg)
                        # We still record it to prevent infinite identical error loops if it keeps trying
                        previous_actions.append(current_call_signature)
                        
                        # Reset action so we don't fall into 'else' block
                        action = "continue"
                    else:
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
                        
                        # Record successful action
                        previous_actions.append(current_call_signature)
                else:
                    context_history.append(f"Error: Tool '{tool_name}' does not exist. Please check the Available Tools list.")
            elif action == "answer":
                # HEURISTIC CHECK: Detect premature answers
                # If the answer suggests future action ("I will now...", "Next I need..."), block it.
                future_indicators = ["i will now", "i need to", "next i will", "next, i will", "i'll now"]
                if any(indicator in answer.lower() for indicator in future_indicators):
                    logger.warning("Detected premature answer with future tense. Forcing continuation.")
                    # Reject the answer and force continuation
                    context_history.append(get_premature_answer_message(answer))
                    action = "continue" # Reset action to continue loop
                    answer = None # Clear the extracted answer
                else:
                    # Valid answer (hopefully)
                    if not answer:
                        # Try to generate if not extracted
                        # ... (existing logic) ...
                        if "answer is" in reasoning.lower() or len(reasoning) > 20:
                             answer = reasoning
                        else:
                            # Generate answer
                            reasoning_section = ""
                            if reasoning_steps:
                                reasoning_section = "Reasoning: " + " ".join(reasoning_steps[-2:]) + "\n\n"
                            
                            tool_results_section = ""
                            if tool_calls:
                                tool_results_section = "Tool results:\n"
                                for call in tool_calls:
                                    tool_results_section += f"- {call['tool']}: {call['result'][:20000]}\n"
                            
                            answer_context = ANSWER_GENERATION_PROMPT_TEMPLATE.format(
                                question=question,
                                reasoning_section=reasoning_section,
                                tool_results_section=tool_results_section,
                            )

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
            reasoning_section = ""
            if reasoning_steps:
                reasoning_section = "Reasoning: " + " ".join(reasoning_steps[-3:]) + "\n\n"
            
            tool_results_section = ""
            if tool_calls:
                tool_results_section = "Tool results:\n"
                for call in tool_calls:
                    tool_results_section += f"- {call['tool']}: {call['result'][:20000]}\n"
            
            final_context = FINAL_ANSWER_PROMPT_TEMPLATE.format(
                question=question,
                reasoning_section=reasoning_section,
                tool_results_section=tool_results_section,
            )

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
        # Extract the current query from the enriched query
        # The enriched query format from conversation_manager._build_context_string is:
        # "Previous conversation summary:\n...\nRecent conversation history:\n...\nCurrent query: {current_query}"
        current_query = state.get("user_query", "")
        if not current_query:
            # Fallback: try to extract from enriched_query
            if "Current query:" in enriched_query:
                current_query = enriched_query.split("Current query:")[-1].strip()
            else:
                # If format is unexpected, use the whole thing (backward compatibility)
                current_query = enriched_query
                logger.warning("Could not extract current query from enriched_query, using full string")
        
        # Remove current query from enriched_query to get pure context (history only)
        # This prevents duplication since we pass current_query separately
        conversation_context = enriched_query
        if "Current query:" in enriched_query:
            # Remove everything from "Current query:" onwards
            conversation_context = enriched_query.split("Current query:")[0].strip()
            # Also remove the trailing newline if present
            if conversation_context.endswith("\n"):
                conversation_context = conversation_context.rstrip("\n")
        
        logger.info(
            "Extracted current query and context",
            current_query_preview=current_query[:100] if current_query else "",
            context_length=len(conversation_context) if conversation_context else 0,
            enriched_query_length=len(enriched_query) if enriched_query else 0,
        )

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
        
        # Use a cleaner context structure for the planner
        # Pass conversation_context (without current query) as CONTEXT, current_query as QUESTION
        planner_context = f"""
        AVAILABLE TOOLS:
        {tools_list}
        
        CONVERSATION HISTORY (Use ONLY for context, do NOT assume these results answer new queries):
        {conversation_context}
        """
        
        # Pass current_query as question, conversation_context (without current query) as context
        generated_plan = planner(question=current_query, context=planner_context)
        logger.info(f"Plan generated: {generated_plan}")

        # 2. EXECUTE PLAN
        logger.info("Executing plan with ReAct...", plan_length=len(generated_plan))
        
        # Create ReAct module with conversation context (without current query)
        react_module = ReActWithTools(
            tools=tools,
            max_iterations=settings.max_react_iterations,
            workspace_id=workspace_id,
            user_id=user_id,
            conversation_context=conversation_context,  # Pass context without current query
        )

        # Execute ReAct with ONLY the current query as the question
        result = react_module(question=current_query, plan=generated_plan)
        
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
            "query": current_query,  # Store the actual current query, not the enriched one
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
