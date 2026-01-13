#! /usr/bin/env python3

import os
import logging
import asyncio
from langchain_core.tools import tool
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_openai import ChatOpenAI
from langchain.agents import create_agent
from langchain.agents.middleware import wrap_tool_call
from langchain.agents.middleware import HumanInTheLoopMiddleware
from langchain_core.messages import ToolMessage
from langgraph.checkpoint.memory import InMemorySaver
from dotenv import load_dotenv
from datetime import datetime


SYSTEM_PROMPT = """You are RHOAI Ops Buddy, an AI operations assistant for Red Hat OpenShift AI infrastructure.

Your capabilities include:

**Jenkins CI/CD Operations:**
- Query job status, build history, and configurations
- Start, stop, enable, or disable Jenkins jobs
- Fetch and analyze build logs to diagnose failures
- Monitor pipeline health and identify issues

**OpenShift Cluster Management:**
- List and monitor Hive-managed OpenShift clusters
- Check cluster provisioning status and health
- Query cluster details (platform, version, state)
- Test connectivity to cluster management infrastructure

**General Assistance:**
- Answer questions about RHOAI infrastructure and processes
- Help troubleshoot CI/CD and cluster issues
- Provide operational insights and recommendations

When performing destructive or state-changing actions (starting jobs, provisioning clusters, etc.), 
you will request human approval before proceeding. Be concise but thorough in your responses."""

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')


@tool("get_date", description="Get the current date")
def get_date() -> str:
    """Get the current date"""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


@wrap_tool_call
async def handle_tool_errors(request, handler):
    """Handle tool execution errors and normalize MCP tool results."""
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
        logging.error(error_msg, exc_info=True)
        
        # Return a custom error message to the model
        return ToolMessage(
            content=error_msg,
            tool_call_id=request.tool_call["id"]
        )


class RHOAIOpsAgent:
    """RHOAI Operations Agent - handles Jenkins CI/CD and cluster management operations."""
    
    def __init__(
        self,
        tools: list,
        llm_base_url: str,
        llm_api_key: str,
        llm_model: str,
        llm_temperature: float
    ):
        logging.info(
            f"Initializing RHOAI Ops Agent with "
            f"LLM Base URL: {llm_base_url}, LLM Model: {llm_model}, LLM Temperature: {llm_temperature}"
        )

        # Store LLM config
        self.llm_base_url = llm_base_url
        self.llm_api_key = llm_api_key
        self.llm_model = llm_model
        self.llm_temperature = llm_temperature
        self.tools = tools

        self._init_llm()
        self._init_agent()

    def _init_llm(self):
        self.llm = ChatOpenAI(
            base_url=self.llm_base_url,
            api_key=self.llm_api_key,
            model=self.llm_model,
            temperature=self.llm_temperature
        )

    def _init_agent(self):
        # Define which tools require human approval (action tools, not read-only)
        action_tools = {
            "start_job": {"allowed_decisions": ["approve", "reject", "edit"]},
            "enable_job": {"allowed_decisions": ["approve", "reject", "edit"]},
            "disable_job": {"allowed_decisions": ["approve", "reject", "edit"]},
            "stop_build": {"allowed_decisions": ["approve", "reject", "edit"]},
            "provision_cluster": {"allowed_decisions": ["approve", "reject", "edit"]},
            "run_test_matrix": {"allowed_decisions": ["approve", "reject", "edit"]},
        }
        
        self.agent = create_agent( 
            self.llm, 
            tools=[get_date] + self.tools,
            system_prompt=SYSTEM_PROMPT,
            middleware=[
                handle_tool_errors,  # Handles errors AND normalizes MCP results
                HumanInTheLoopMiddleware(interrupt_on=action_tools)
            ],
            checkpointer=InMemorySaver()
        )

    def get_agent(self):
        """Get the underlying agent instance"""
        return self.agent


async def get_mcp_tools():
    """Get all MCP tools from MCP servers running in separate containers."""
    logging.info("Initializing MCP client with all servers")
    
    servers = {}
    
    # Connect to Jenkins MCP server via streamable_http (standalone container)
    servers["jenkins"] = {
        "url": "http://jenkins-mcp:8000/mcp",
        "transport": "streamable_http"
    }
    logging.info("Jenkins MCP server configured (streamable_http to http://jenkins-mcp:8000/mcp)")
    
    # Connect to cluster monitor MCP server via streamable_http (standalone container)
    servers["cluster-monitor"] = {
        "url": "http://cluster-monitor:8000/mcp",
        "transport": "streamable_http"
    }
    logging.info("Cluster monitor server configured (streamable_http to http://cluster-monitor:8000/mcp)")
    
    # Create MCP client and get tools
    mcp_client = MultiServerMCPClient(servers)
    tools = await mcp_client.get_tools()
    return tools


def build_agent():
    """Build and initialize the RHOAI Ops agent."""
    load_dotenv()
    
    # Create event loop and get tools
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    all_tools = loop.run_until_complete(get_mcp_tools())

    logging.info(f"All tools loaded: {[tool.name for tool in all_tools]}")
    
    ops_agent = RHOAIOpsAgent(
        tools=all_tools,
        llm_base_url=os.getenv("LLM_BASE_URL"),
        llm_api_key=os.getenv("LLM_API_KEY"),
        llm_model=os.getenv("LLM_MODEL"),
        llm_temperature=float(os.getenv("LLM_TEMPERATURE", "0.7"))
    )
    
    return ops_agent.get_agent()


# For LangGraph: create the agent at module level
agent = build_agent()


if __name__ == "__main__":
    print("Agent initialized successfully")
    print(f"Agent: {agent}")