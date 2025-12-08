"""System messages for error handling and corrections."""

PREMATURE_ANSWER_SYSTEM_MESSAGE_TEMPLATE = """SYSTEM: You provided an answer that says you WILL do something ('{answer}'). This is incorrect. Do NOT answer until you HAVE done it. Execute the next step using a tool."""


def get_premature_answer_message(answer: str) -> str:
    """Generate premature answer system message.
    
    Args:
        answer: The premature answer text
        
    Returns:
        Formatted system message
    """
    return PREMATURE_ANSWER_SYSTEM_MESSAGE_TEMPLATE.format(answer=answer)


# For backward compatibility
PREMATURE_ANSWER_SYSTEM_MESSAGE = PREMATURE_ANSWER_SYSTEM_MESSAGE_TEMPLATE

