"""ReAct executor with tool support for query processing."""

import json
import re
from typing import Any, Dict, List, Optional

import dspy

from ...config import get_settings
from ...prompts import (
    ANSWER_GENERATION_PROMPT_TEMPLATE,
    FINAL_ANSWER_PROMPT_TEMPLATE,
    REACT_SYSTEM_PROMPT,
    get_premature_answer_message,
)
from ...tools.registry import get_tool_registry
from ...utils.logger import get_logger

logger = get_logger(__name__)
settings = get_settings()


class ReActWithTools(dspy.Module):
    """ReAct module with tool support."""

    def __init__(
        self,
        tools: List[Dict[str, Any]],
        max_iterations: int = 10,
        workspace_id: Optional[str] = None,
        user_id: Optional[str] = None,
    ):
        """Initialize ReAct module with tools."""
        super().__init__()
        self.tools = {tool["name"]: tool for tool in tools}
        self.max_iterations = max_iterations
        self.tool_registry = get_tool_registry()
        self.workspace_id = workspace_id or settings.workspace_id
        self.user_id = user_id
        if not self.workspace_id:
            logger.warning("No workspace_id provided. Tool calls may fail if workspace_id is required.")

    def decide_next_step(
        self, 
        question: str, 
        plan: Optional[str] = None, 
        context_history: List[str] = None,
        previous_actions: List[str] = None
    ) -> Dict[str, Any]:
        """Decide the next action to take based on the current context."""
        context_history = context_history or []
        previous_actions = previous_actions or []
        
        tools_description = self._build_tools_description()
        lm = dspy.settings.lm

        context = REACT_SYSTEM_PROMPT + "\n\n"

        if tools_description:
            context += f"AVAILABLE TOOLS:\n{tools_description}\n\n"

        if plan:
            context += f"APPROVED PLAN:\n{plan}\n\n"
            context += "INSTRUCTIONS: Execute the plan above step-by-step. Do not deviate unless necessary.\n\n"

        if context_history:
            context += "PREVIOUS STEPS:\n"
            for entry in context_history[-5:]:
                context += f"- {entry}\n"
            context += "\n"

        context += f"CURRENT REQUEST:\n{question}\n\n"
        context += "Choose your next format (ACTION: use_tool, ACTION: answer, or reasoning) and respond now:"

        try:
            response = lm(context)
            action = "continue"
            tool_name = ""
            tool_params_str = ""
            reasoning = response

            lines = response.split("\n")
            for i, line in enumerate(lines):
                line_stripped = line.strip()
                line_upper = line_stripped.upper()

                if line_upper.startswith("ACTION:"):
                    action_value = line_stripped.split(":", 1)[1].strip().lower()
                    if "use_tool" in action_value or "tool" in action_value or action_value in self.tools:
                        action = "use_tool"
                        if action_value in self.tools:
                            tool_name = action_value
                    elif "answer" in action_value:
                        action = "answer"

                if line_upper.startswith("TOOL:") and action == "use_tool":
                    candidate_name = line_stripped.split(":", 1)[1].strip().strip("\"' ")
                    if candidate_name:
                        tool_name = candidate_name

                if line_upper.startswith("PARAMS:") and action == "use_tool":
                    params_part = line_stripped.split(":", 1)[1].strip()
                    if not params_part or params_part.startswith("{"):
                        buffer = params_part
                        if not buffer.endswith("}"):
                            for j in range(i + 1, len(lines)):
                                next_line = lines[j]
                                buffer += "\n" + next_line
                                if next_line.strip().endswith("}"):
                                    break
                        tool_params_str = buffer
                    else:
                        tool_params_str = params_part

                if line_upper.startswith("ANSWER:") and action == "answer":
                    answer = line_stripped.split(":", 1)[1].strip()
                    for j in range(i + 1, len(lines)):
                        answer += "\n" + lines[j]
                    break
            
            tool_params = {}
            if action == "use_tool" and tool_name:
                 tool_params = self._extract_tool_params(tool_name, tool_params_str, reasoning)

            return {
                "action": action,
                "tool_name": tool_name,
                "tool_params": tool_params,
                "reasoning": reasoning,
                "answer": answer
            }

        except Exception as exc:  # pragma: no cover - defensive logging
            logger.error("ReAct decision failed", error=str(exc))
            return {
                "action": "continue",
                "reasoning": f"Error in reasoning: {str(exc)}",
                "tool_name": "",
                "tool_params": {},
                "answer": None
            }

    def execute_tool(self, tool_name: str, params: Dict[str, Any]) -> Any:
        """Execute a tool and return the result."""
        return self._call_tool(tool_name, params)
    
    def generate_final_answer(self, question: str, reasoning_steps: List[str], tool_calls: List[Dict[str, Any]]) -> str:
        """Generate final answer if not provided by ReAct loop."""
        lm = dspy.settings.lm
        
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
            return lm(final_context)
        except Exception as exc:  # pragma: no cover
            logger.error("Final answer generation failed", error=str(exc))
            return "I couldn't generate a complete answer due to an error."

    def forward(self, question: str, plan: Optional[str] = None) -> dspy.Prediction:
        """Execute ReAct reasoning with tool support."""
        # Backward compatibility wrapper around new methods
        reasoning_steps: List[str] = []
        tool_calls: List[Dict[str, Any]] = []
        context_history: List[str] = []
        previous_actions: List[str] = []
        answer = None

        for iteration in range(self.max_iterations):
            step_result = self.decide_next_step(
                question, 
                plan, 
                context_history, 
                previous_actions
            )
            
            action = step_result["action"]
            reasoning = step_result["reasoning"]
            tool_name = step_result["tool_name"]
            tool_params = step_result["tool_params"]
            current_answer = step_result["answer"]
            
            reasoning_steps.append(reasoning)
            logger.info("ReAct iteration %s", iteration + 1, reasoning=reasoning[:200], action=action)
            
            if action == "use_tool" and tool_name:
                if tool_name in self.tools:
                    current_call_signature = f"{tool_name}:{json.dumps(tool_params, sort_keys=True)}"
                    
                    if previous_actions and previous_actions[-1] == current_call_signature:
                        duplicate_msg = (
                            f"SYSTEM: You just called tool '{tool_name}' with these exact parameters. "
                            "Do NOT call it again. Analyze the 'Result' directly above and provide your Final Answer."
                        )
                        context_history.append(duplicate_msg)
                        previous_actions.append(current_call_signature)
                        continue
                    
                    tool_result = self.execute_tool(tool_name, tool_params)
                    
                    tool_call_record = {
                        "tool": tool_name,
                        "params": tool_params,
                        "result": str(tool_result)[:20000],
                        "iteration": iteration + 1,
                    }
                    tool_calls.append(tool_call_record)
                    
                    result_preview = str(tool_result)
                    if len(result_preview) > settings.tool_result_limit:
                        result_preview = result_preview[:settings.tool_result_limit] + "... (truncated)"
                    context_history.append(f"Tool {tool_name} called with params {tool_params}\nResult: {result_preview}")
                    
                    previous_actions.append(current_call_signature)
                else:
                    context_history.append(f"Error: Tool '{tool_name}' does not exist.")
            
            elif action == "answer":
                if current_answer:
                    # Heuristic check
                    future_indicators = ["i will now", "i need to", "next i will"]
                    if any(indicator in current_answer.lower() for indicator in future_indicators):
                        context_history.append(get_premature_answer_message(current_answer))
                    else:
                        answer = current_answer
                        break
            else:
                 context_history.append(reasoning[:200])

        if not answer:
            answer = self.generate_final_answer(question, reasoning_steps, tool_calls)

        return dspy.Prediction(
            answer=answer,
            reasoning_steps=reasoning_steps,
            tool_calls=tool_calls,
        )

    def _build_tools_description(self) -> str:
        """Build tools description for LLM context."""
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
        """Extract tool parameters from reasoning text."""
        tool_info = self.tools.get(tool_name, {})
        params_schema = tool_info.get("parameters", {}).get("properties", {})

        params: Dict[str, Any] = {}

        if tool_params_str:
            try:
                params = json.loads(tool_params_str)
            except json.JSONDecodeError:
                try:
                    start_idx = tool_params_str.find("{")
                    if start_idx != -1:
                        count = 0
                        end_idx = -1
                        for i, char in enumerate(tool_params_str[start_idx:], start_idx):
                            if char == "{":
                                count += 1
                            elif char == "}":
                                count -= 1
                                if count == 0:
                                    end_idx = i + 1
                                    break
                        if end_idx != -1:
                            json_str = tool_params_str[start_idx:end_idx]
                            params = json.loads(json_str)
                except Exception:
                    pass

        if not params and params_schema:
            for param_name in params_schema.keys():
                pattern = rf"{param_name}['\"]?\s*[:=]\s*['\"]?([^,\s\)]+)"
                match = re.search(pattern, reasoning, re.IGNORECASE)
                if match:
                    val = match.group(1).strip("'\" ,")
                    params[param_name] = val

        return params

    def _call_tool(self, tool_name: str, params: Dict[str, Any]) -> Any:
        """Call a tool by name."""
        try:
            tool = self.tool_registry.get(tool_name)
            if not tool:
                return f"Error: Tool '{tool_name}' not found"

            if self.workspace_id:
                params["workspace_id"] = self.workspace_id

            if self.user_id:
                params["user_id"] = self.user_id

            result = tool.execute(**params)
            return result
        except Exception as exc:  # pragma: no cover
            logger.error("Tool execution error: %s", tool_name, error=str(exc), params=params)
            return f"Error executing tool: {str(exc)}"
