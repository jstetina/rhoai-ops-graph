"""
Sub-agent factories and tool wrappers for the supervisor pattern.
"""

import logging
from typing import List, Dict, Any, Callable, Optional
from langchain_core.tools import tool
from langchain.agents import create_agent
from langchain.agents.middleware import HumanInTheLoopMiddleware
from langchain_openai import ChatOpenAI

from helpers.config import MCPServerConfig
from helpers.middleware import handle_tool_errors

logger = logging.getLogger(__name__)


def build_interrupt_on_config(approval_tools: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    """
    Convert approval_tools config to HumanInTheLoopMiddleware interrupt_on format.
    
    Args:
        approval_tools: Dict mapping tool names to their approval config
                       e.g. {"start_job": {"allowed_decisions": ["approve", "reject"], "description": "..."}}
    
    Returns:
        Dict in interrupt_on format for HumanInTheLoopMiddleware
    """
    interrupt_on = {}
    for tool_name, config in approval_tools.items():
        interrupt_on[tool_name] = {
            "allowed_decisions": config.get("allowed_decisions", ["approve", "reject"]),
            "description": config.get("description", f"{tool_name} requires approval"),
        }
    return interrupt_on


def create_subagent(
    llm: ChatOpenAI,
    config: MCPServerConfig,
    tools: List,
    approval_tools: Optional[Dict[str, Dict[str, Any]]] = None
) -> Any:
    """
    Create a specialized sub-agent from configuration.
    
    Args:
        llm: The LLM instance to use
        config: Server configuration including agent prompt
        tools: List of MCP tools for this agent
        approval_tools: Optional dict of tools requiring approval
        
    Returns:
        The created agent instance
    """
    logger.info(f"Creating sub-agent: {config.agent.name} with {len(tools)} tools")
    
    # Log tool schemas for debugging
    for t in tools:
        tool_name = getattr(t, 'name', str(t))
        args_schema = getattr(t, 'args_schema', None)
        if args_schema:
            # MCP tools may have dict schemas instead of Pydantic models
            if isinstance(args_schema, dict):
                props = args_schema.get('properties', {})
                logger.info(f"  Tool '{tool_name}' params: {list(props.keys())}")
            elif hasattr(args_schema, 'model_fields'):
                logger.info(f"  Tool '{tool_name}' params: {list(args_schema.model_fields.keys())}")
            else:
                logger.info(f"  Tool '{tool_name}' schema type: {type(args_schema)}")
        else:
            logger.info(f"  Tool '{tool_name}' - no schema found")
    
    # Build middleware stack
    middleware = []
    
    # Add HumanInTheLoopMiddleware if there are tools requiring approval
    # See: https://docs.langchain.com/oss/python/langchain/human-in-the-loop
    if approval_tools:
        interrupt_on = build_interrupt_on_config(approval_tools)
        logger.info(f"  Tools requiring approval: {list(interrupt_on.keys())}")
        middleware.append(
            HumanInTheLoopMiddleware(
                interrupt_on=interrupt_on,
                description_prefix="Tool execution requires approval",
            )
        )
    
    middleware.append(handle_tool_errors)
    
    return create_agent(
        llm,
        tools=tools,
        system_prompt=config.agent.prompt,
        middleware=middleware,
    )


def create_subagent_tool(agent: Any, config: MCPServerConfig) -> Callable:
    """
    Create an async tool wrapper for a sub-agent that can be used by the supervisor.
    
    Args:
        agent: The sub-agent instance
        config: Server configuration with tool name and description
        
    Returns:
        An async tool function that delegates to the sub-agent
    """
    tool_name = config.agent.tool_name
    tool_description = config.agent.tool_description
    
    @tool(tool_name, description=tool_description)
    async def subagent_tool(request: str) -> str:
        """
        Delegate operation to the specialized sub-agent.
        
        Args:
            request: Natural language description of the operation needed
            
        Returns:
            The result from the sub-agent
        """
        result = await agent.ainvoke({
            "messages": [{"role": "user", "content": request}]
        })
        # Extract the final response
        return result["messages"][-1].content
    
    # Update the function name for better debugging
    subagent_tool.__name__ = tool_name
    
    logger.info(f"Created async tool wrapper: {tool_name}")
    
    return subagent_tool


def build_subagents_and_tools(
    llm: ChatOpenAI,
    server_configs: Dict[str, MCPServerConfig],
    tools_by_server: Dict[str, List],
    approval_tools_by_server: Optional[Dict[str, Dict[str, Dict[str, Any]]]] = None
) -> List[Callable]:
    """
    Build all sub-agents and their tool wrappers.
    
    Args:
        llm: The LLM instance to use
        server_configs: Dictionary of server configurations by server_id
        tools_by_server: Dictionary of MCP tools by server_id
        approval_tools_by_server: Optional dict mapping server_id to approval tools config
        
    Returns:
        List of tool functions for the supervisor to use
    """
    subagent_tools = []
    approval_tools_by_server = approval_tools_by_server or {}
    
    for server_id, config in server_configs.items():
        tools = tools_by_server.get(server_id, [])
        
        if not tools:
            logger.warning(f"No tools found for server: {server_id}")
            continue
        
        # Get approval tools for this server
        approval_tools = approval_tools_by_server.get(server_id, {})
        
        # Create the sub-agent with approval middleware if needed
        agent = create_subagent(llm, config, tools, approval_tools)
        
        # Create the tool wrapper
        tool_wrapper = create_subagent_tool(agent, config)
        subagent_tools.append(tool_wrapper)
    
    return subagent_tools
