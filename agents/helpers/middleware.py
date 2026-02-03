"""
Middleware for agent tool execution.
"""

import json
import logging
from langchain.agents.middleware import wrap_tool_call
from langchain_core.messages import ToolMessage
from langgraph.types import Interrupt

logger = logging.getLogger(__name__)

# Exception types that should propagate for human-in-the-loop approval
INTERRUPT_EXCEPTION_NAMES = {"GraphInterrupt", "NodeInterrupt", "Interrupt"}


def normalize_mcp_content(content):
    """
    Normalize MCP response content to a string suitable for LLM consumption.
    
    MCP returns content as: [{"type": "text", "text": "..."}, ...]
    This function handles various response shapes intelligently.
    """
    if not isinstance(content, list) or len(content) == 0:
        return content
    
    # Check if it's MCP format (list of dicts with "text" key)
    if not (isinstance(content[0], dict) and "text" in content[0]):
        # Not MCP format, try JSON serialization
        try:
            return json.dumps(content, indent=2)
        except (TypeError, ValueError):
            return str(content)
    
    # Extract text items from MCP format
    text_items = [item["text"] for item in content if isinstance(item, dict) and "text" in item]
    
    if len(text_items) == 0:
        return str(content)
    
    if len(text_items) == 1:
        # Single item - return as-is
        return text_items[0]
    
    # Multiple items - format as JSON array for structured data
    # This preserves the list structure for the LLM
    return json.dumps(text_items, indent=2)


@wrap_tool_call
async def handle_tool_errors(request, handler):
    """
    Handle tool execution errors and normalize MCP tool results.
    
    This middleware:
    1. Catches and logs exceptions from tool calls (except interrupt types)
    2. Normalizes MCP response format to LLM-friendly strings
    3. Returns user-friendly error messages to the model
    
    Interrupt exceptions are re-raised to allow human-in-the-loop
    approval flows to work correctly across sub-agents.
    """
    try:
        result = await handler(request)
        
        # Normalize MCP tool results
        if isinstance(result.content, list):
            result.content = normalize_mcp_content(result.content)
        
        return result
    except BaseException as e:
        # Let interrupt-related exceptions propagate for human-in-the-loop approval
        if type(e).__name__ in INTERRUPT_EXCEPTION_NAMES:
            raise
        
        # Also check if it's an Interrupt instance
        if isinstance(e, Interrupt):
            raise
        
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
