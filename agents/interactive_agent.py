#! /usr/bin/env python3
"""
RHOAI Ops Buddy - Supervisor Pattern Multi-Agent System

This agent uses the supervisor pattern from LangChain where specialized sub-agents
are wrapped as tools and coordinated by a supervisor.

Configuration is loaded from mcp_servers.json which defines:
- MCP server connections
- Sub-agent prompts and tool descriptions
- Human-in-the-loop approval settings

See: https://docs.langchain.com/oss/python/langchain/multi-agent/subagents-personal-assistant
"""

import os
import logging
import asyncio
from datetime import datetime
from typing import Dict, List, Any

from langchain_core.tools import tool
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_openai import ChatOpenAI
from langchain.agents import create_agent
from langchain.agents.middleware import HumanInTheLoopMiddleware
from langgraph.checkpoint.memory import InMemorySaver
from dotenv import load_dotenv

from helpers import (
    load_config,
    Config,
    handle_tool_errors,
    build_subagents_and_tools,
)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# =============================================================================
# Utility Tools
# =============================================================================

@tool("get_date", description="Get the current date and time")
def get_date() -> str:
    """Get the current date and time"""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


# =============================================================================
# MCP Tools Loading
# =============================================================================

async def load_mcp_tools(config: Config) -> Dict[str, List]:
    """
    Load all MCP tools from configured servers.
    
    Args:
        config: Configuration object with server definitions
        
    Returns:
        Dictionary mapping server_id to list of tools
    """
    logger.info("Loading MCP tools from configured servers...")
    
    # Get MCP client configuration
    mcp_config = config.get_mcp_client_config()
    
    for server_id, server_config in mcp_config.items():
        logger.info(f"  {server_id}: {server_config['url']} ({server_config['transport']})")
    
    # Create MCP client and get all tools
    mcp_client = MultiServerMCPClient(mcp_config)
    all_tools = await mcp_client.get_tools()
    
    # Group tools by server
    # The MCP adapter prefixes tool names with server name, so we can use that
    # to categorize. If not prefixed, we need to match by known patterns.
    tools_by_server: Dict[str, List] = {server_id: [] for server_id in config.servers}
    
    for mcp_tool in all_tools:
        tool_name = mcp_tool.name.lower()
        assigned = False
        
        # Log detailed tool info for debugging
        logger.info(f"  MCP Tool: {mcp_tool.name}")
        args_schema = getattr(mcp_tool, 'args_schema', None)
        if args_schema:
            # MCP tools may have dict schemas instead of Pydantic models
            if isinstance(args_schema, dict):
                props = args_schema.get('properties', {})
                logger.info(f"    Parameters (dict): {list(props.keys())}")
            elif hasattr(args_schema, 'model_json_schema'):
                try:
                    schema = args_schema.model_json_schema()
                    props = schema.get('properties', {})
                    logger.info(f"    Parameters (pydantic): {list(props.keys())}")
                except Exception as e:
                    logger.info(f"    Schema error: {e}")
            else:
                logger.info(f"    Schema type: {type(args_schema)}")
        elif hasattr(mcp_tool, 'args'):
            logger.info(f"    Args: {mcp_tool.args}")
        
        # Try to match tool to server by checking server-specific keywords
        for server_id in config.servers:
            # Check if tool name starts with server id (common MCP pattern)
            if tool_name.startswith(f"{server_id.replace('-', '_')}_"):
                tools_by_server[server_id].append(mcp_tool)
                assigned = True
                break
        
        # Fallback: use keyword matching for known tool patterns
        if not assigned:
            if any(kw in tool_name for kw in ['cluster', 'hive', 'owner']):
                tools_by_server["cluster-monitor"].append(mcp_tool)
                assigned = True
            elif any(kw in tool_name for kw in ['job', 'build', 'jenkins', 'test_matrix']):
                tools_by_server["jenkins"].append(mcp_tool)
                assigned = True
        
        # Last resort: assign to first server
        if not assigned:
            first_server = list(config.servers.keys())[0]
            tools_by_server[first_server].append(mcp_tool)
            logger.warning(f"Tool '{mcp_tool.name}' assigned to default server: {first_server}")
    
    for server_id, tools in tools_by_server.items():
        logger.info(f"  {server_id}: {[t.name for t in tools]}")
    
    return tools_by_server


# =============================================================================
# Supervisor Agent Builder
# =============================================================================

class SupervisorAgent:
    """
    RHOAI Operations Supervisor Agent
    
    Uses the supervisor pattern where specialized sub-agents are wrapped as tools
    and coordinated by a supervisor agent. Configuration is loaded from JSON.
    """
    
    def __init__(
        self,
        config: Config,
        tools_by_server: Dict[str, List],
        llm_base_url: str,
        llm_api_key: str,
        llm_model: str,
        llm_temperature: float
    ):
        self.config = config
        self.tools_by_server = tools_by_server
        self.llm_base_url = llm_base_url
        self.llm_api_key = llm_api_key
        self.llm_model = llm_model
        self.llm_temperature = llm_temperature
        
        logger.info(
            f"Initializing Supervisor Agent - "
            f"LLM: {llm_model} @ {llm_base_url}, Temperature: {llm_temperature}"
        )
        
        self._init_llm()
        self._init_agent()

    def _init_llm(self):
        """Initialize the LLM instance."""
        self.llm = ChatOpenAI(
            base_url=self.llm_base_url,
            api_key=self.llm_api_key,
            model=self.llm_model,
            temperature=self.llm_temperature
        )

    def _init_agent(self):
        """Initialize the supervisor agent with sub-agent tools."""
        # Build sub-agents and their tool wrappers
        subagent_tools = build_subagents_and_tools(
            self.llm,
            self.config.servers,
            self.tools_by_server
        )
        
        # Get tools that require human approval
        approval_tools = self.config.get_approval_tools()
        logger.info(f"Tools requiring approval: {list(approval_tools.keys())}")
        
        # Build middleware stack
        middleware = [handle_tool_errors]
        if approval_tools:
            middleware.append(HumanInTheLoopMiddleware(interrupt_on=approval_tools))
        
        # Create the supervisor agent
        logger.info("Creating Supervisor agent...")
        self.agent = create_agent(
            self.llm,
            tools=[get_date] + subagent_tools,
            system_prompt=self.config.supervisor_prompt,
            middleware=middleware,
            checkpointer=InMemorySaver()
        )

    def get_agent(self):
        """Get the underlying supervisor agent instance."""
        return self.agent


# =============================================================================
# Agent Builder
# =============================================================================

def build_agent():
    """Build and initialize the RHOAI Ops supervisor agent."""
    load_dotenv()
    
    # Load configuration from JSON
    config = load_config()
    
    # Create event loop and load MCP tools
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    tools_by_server = loop.run_until_complete(load_mcp_tools(config))
    
    # Create the supervisor agent
    supervisor = SupervisorAgent(
        config=config,
        tools_by_server=tools_by_server,
        llm_base_url=os.getenv("LLM_BASE_URL"),
        llm_api_key=os.getenv("LLM_API_KEY"),
        llm_model=os.getenv("LLM_MODEL"),
        llm_temperature=float(os.getenv("LLM_TEMPERATURE", "0.7"))
    )
    
    return supervisor.get_agent()


# =============================================================================
# LangGraph Entry Point
# =============================================================================

# For LangGraph: create the agent at module level
agent = build_agent()


if __name__ == "__main__":
    print("RHOAI Ops Buddy - Supervisor Agent initialized successfully")
    print(f"Agent: {agent}")
