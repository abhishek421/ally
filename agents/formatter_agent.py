from typing import Dict, Any
from langchain_core.messages import HumanMessage, SystemMessage
from agents.base_agent import BaseAgent, AgentState


class ResponseFormatterAgent(BaseAgent):
    """Agent responsible for formatting results into human-readable responses"""
    
    def __init__(self, llm):
        super().__init__(llm)
        self.system_prompt = """You are a response formatting agent. Your job is to format database query results into clear, human-readable responses.

Your tasks:
1. Take the raw query results and format them nicely
2. Provide context and explanations
3. Make the response conversational and helpful
4. Highlight key insights or patterns
5. Suggest follow-up questions if appropriate

Guidelines:
- Be conversational and friendly
- Explain what the data shows
- Format numbers and dates nicely
- Use bullet points or tables when appropriate
- Keep responses concise but informative
- If there are no results, explain why and suggest alternatives"""

    def run(self, state: AgentState) -> AgentState:
        """Format the query results into a human-readable response"""
        try:
            user_query = state["user_query"]
            query_result = state["query_result"]
            sql_query = state["sql_query"]
            
            messages = [
                SystemMessage(content=self.system_prompt),
                HumanMessage(content=f"""User Query: {user_query}
SQL Query Used: {sql_query}
Query Results: {query_result}

Format these results into a clear, helpful response for the user.""")
            ]
            
            response = self.llm.invoke(messages)
            final_response = response.content.strip()
            
            # Update state
            state["final_response"] = final_response
            self._log_message(state, "assistant", final_response)
            
            return state
            
        except Exception as e:
            self._set_error(state, f"Response formatting failed: {str(e)}")
            return state
