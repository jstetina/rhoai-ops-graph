"""
Middleware for agent tool execution.
"""

import logging
from langchain.agents.middleware import wrap_tool_call
from langchain_core.messages import ToolMessage

logger = logging.getLogger(__name__)


@wrap_tool_call
async def handle_tool_errors(request, handler):
    """
    Handle tool execution errors and normalize MCP tool results.
    
    This middleware:
    1. Catches and logs exceptions from tool calls
    2. Normalizes MCP response format (extracts text from content array)
    3. Returns user-friendly error messages to the model
    """
    try:
        result = await handler(request)
        
        # Normalize MCP tool results: convert array of content objects to simple string
        if isinstance(result.content, list) and len(result.content) > 0:
            # Extract text from MCP format: [{"type": "text", "text": "..."}]
            if isinstance(result.content[0], dict) and "text" in result.content[0]:
                result.content = result.content[0]["text"]
        
        return result
    except Exception as e:
        # Get tool name from request
        tool_name = request.tool_call.get("name", "unknown")
        error_msg = f"ERROR in tool '{tool_name}': {type(e).__name__}: {str(e)}"
        
        # Log the full error with stack trace
        logger.error(error_msg, exc_info=True)
        
        # Return a custom error message to the model
        return ToolMessage(
            content=error_msg,
            tool_call_id=request.tool_call["id"]
        )
