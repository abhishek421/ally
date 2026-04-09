import asyncio
import sys
import os

sys.path.append("/app")
from src.config import get_settings
from src.agent.graph import get_agent
from src.tools.base import ToolContext
from langchain_core.messages import HumanMessage

async def main():
    ctx = ToolContext(
        workspace_id="81c54b70-60f0-43ab-b4ab-4a64d01917f2",
        user_id="test-user",
        auth_token="test-token",
        user_first_name="Ishaan"
    )
    agent = await get_agent(ctx, is_new_conversation=True)
    config = {"configurable": {"thread_id": "test-id-1234"}}
    
    print("Invoking agent...")
    async for chunk in agent.astream(
        {"messages": [HumanMessage(content="show me all the companies")]},
        config=config,
        stream_mode="updates"
    ):
        if "agent" in chunk:
            messages = chunk["agent"].get("messages", [])
            if messages:
                print("Agent message:", messages[-1].content)
                if hasattr(messages[-1], "tool_calls") and messages[-1].tool_calls:
                    print("Tool calls:", [tc.get("name") for tc in messages[-1].tool_calls])
        elif "tools" in chunk:
            print("Tool result ready")

if __name__ == "__main__":
    asyncio.run(main())
