#! /usr/bin/env python3

import os
import sys
import logging
import asyncio
from typing import Any
from langchain_core.tools import tool
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_openai import ChatOpenAI
from langchain.agents import create_agent
from langchain.agents.middleware import wrap_tool_call
from langchain_core.messages import ToolMessage
from dotenv import load_dotenv
from datetime import datetime

SYSTEM_PROMPT = """You are an interactive agent that can interact with the Jenkins server."""

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')


@tool("get_date", description="Get the current date")
def get_date() -> str:
    """Get the current date"""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


@wrap_tool_call
async def handle_tool_errors(request, handler):
    """Handle tool execution errors with custom messages."""
    try:
        return await handler(request)
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


class JenkinsInteractiveAgent:
    def __init__(
        self,
        tools: list,
        llm_base_url: str,
        llm_api_key: str,
        llm_model: str,
        llm_temperature: float
    ):
        logging.info(
            f"Initializing Jenkins Interactive Agent with "
            f"LLM Base URL: {llm_base_url}, LLM Model: {llm_model}, LLM Temperature: {llm_temperature}"
        )

        # Store LLM config
        self.llm_base_url = llm_base_url
        self.llm_api_key = llm_api_key
        self.llm_model = llm_model
        self.llm_temperature = llm_temperature
        self.jenkins_tools = tools

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
        self.agent = create_agent( 
            self.llm, 
            tools=[get_date] + self.jenkins_tools,
            system_prompt=SYSTEM_PROMPT,
            middleware=[handle_tool_errors]
        )

    def get_agent(self):
        """Get the underlying agent instance"""
        return self.agent


async def get_jenkins_tools(
    jenkins_url: str,
    jenkins_user: str,
    jenkins_password: str,
    jenkins_server_path: str
):
    """Get Jenkins tools from MCP client"""
    logging.info("Initializing Jenkins MCP client")
    
    jenkins_client = MultiServerMCPClient(
        {
            "jenkins": {
                "command": "uv",
                "args": [
                    "--directory",
                    jenkins_server_path,
                    "run",
                    "main.py",
                    f"--jenkins-url={jenkins_url}",
                    f"--jenkins-user={jenkins_user}",
                    f"--jenkins-password={jenkins_password}"
                ],
                "transport": "stdio",
            },
        }
    )
    
    return await jenkins_client.get_tools()


def build_agent():
    """Build and initialize the Jenkins agent"""
    load_dotenv()
    
    # Create event loop and get tools
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    jenkins_tools = loop.run_until_complete(
        get_jenkins_tools(
            jenkins_url=os.getenv("JENKINS_URL"),
            jenkins_user=os.getenv("JENKINS_USER"),
            jenkins_password=os.getenv("JENKINS_PASSWORD"),
            jenkins_server_path=os.getenv("JENKINS_SERVER_PATH")
        )
    )

    logging.info(f"Jenkins tools: {[tool.name for tool in jenkins_tools]}")
    
    jenkins_agent = JenkinsInteractiveAgent(
        tools=jenkins_tools,
        llm_base_url=os.getenv("LLM_BASE_URL"),
        llm_api_key=os.getenv("LLM_API_KEY"),
        llm_model=os.getenv("LLM_MODEL"),
        llm_temperature=float(os.getenv("LLM_TEMPERATURE", "0.7"))
    )
    
    return jenkins_agent.get_agent()


# For LangGraph: create the agent at module level
agent = build_agent()


if __name__ == "__main__":
    print("Agent initialized successfully")
    print(f"Agent: {agent}")