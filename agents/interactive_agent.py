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

async def load_mcp_tools(config: Config) -> tuple[Dict[str, List], List[MultiServerMCPClient]]:
    """
    Load MCP tools from each configured server individually.
    
    Creates a separate MultiServerMCPClient for each server to ensure we know
    exactly which tools belong to which server while maintaining persistent
    connections for tool execution.
    
    Args:
        config: Configuration object with server definitions
        
    Returns:
        Tuple of (tools_by_server dict, list of MCP clients to keep alive)
    """
    logger.info("Loading MCP tools from configured servers...")
    
    tools_by_server: Dict[str, List] = {}
    clients: List[MultiServerMCPClient] = []
    
    for server_id, server_config in config.servers.items():
        url = server_config.connection.url
        transport = server_config.connection.transport
        logger.info(f"  Connecting to {server_id}: {url} ({transport})")
        
        try:
            # Create a single-server client for this server
            single_server_config = {
                server_id: {"url": url, "transport": transport}
            }
            client = MultiServerMCPClient(single_server_config)
            tools = await client.get_tools()
            
            tools_by_server[server_id] = tools
            clients.append(client)
            logger.info(f"  {server_id}: loaded {len(tools)} tools - {[t.name for t in tools]}")
        except Exception as e:
            logger.error(f"  {server_id}: failed to load tools - {e}")
            tools_by_server[server_id] = []
    
    return tools_by_server, clients


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
        # Build approval tools config per server
        approval_tools_by_server = {
            server_id: self.config.get_approval_tools_for_server(server_id)
            for server_id in self.config.servers
        }
        
        # Log tools requiring approval
        all_approval_tools = self.config.get_all_approval_tools()
        if all_approval_tools:
            logger.info(f"Tools requiring approval: {list(all_approval_tools.keys())}")
        
        # Build sub-agents and their tool wrappers with per-tool approval
        subagent_tools = build_subagents_and_tools(
            self.llm,
            self.config.servers,
            self.tools_by_server,
            approval_tools_by_server
        )
        
        # Create the supervisor agent
        logger.info("Creating Supervisor agent...")
        self.agent = create_agent(
            self.llm,
            tools=[get_date] + subagent_tools,
            system_prompt=self.config.supervisor_prompt,
            middleware=[handle_tool_errors],
            checkpointer=InMemorySaver()
        )

    def get_agent(self):
        """Get the underlying supervisor agent instance."""
        return self.agent


# =============================================================================
# Agent Builder
# =============================================================================

# Global list to keep MCP clients alive for the lifetime of the agent
_mcp_clients: List[MultiServerMCPClient] = []


def build_agent():
    """Build and initialize the RHOAI Ops supervisor agent."""
    global _mcp_clients
    load_dotenv()
    
    # Load configuration from JSON
    config = load_config()
    
    # Create event loop and load MCP tools
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    tools_by_server, clients = loop.run_until_complete(load_mcp_tools(config))
    
    # Keep clients alive globally
    _mcp_clients = clients
    
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
