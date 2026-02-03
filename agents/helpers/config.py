"""
Configuration loading utilities for MCP servers and agents.
"""

import os
import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# Default config path - top level of rhoai-ops-graph project
DEFAULT_CONFIG_PATH = Path(__file__).parent.parent.parent / "mcp_servers.json"


@dataclass
class AgentConfig:
    """Configuration for a sub-agent."""
    name: str
    tool_name: str
    tool_description: str
    prompt: str


@dataclass
class ConnectionConfig:
    """Configuration for MCP server connection."""
    url: str
    transport: str


@dataclass
class ToolApprovalConfig:
    """Configuration for per-tool human-in-the-loop approval."""
    allowed_decisions: list = field(default_factory=lambda: ["approve", "reject", "edit"])
    description: str = "Operation pending approval"


@dataclass
class ApprovalConfig:
    """Configuration for human-in-the-loop approval with per-tool granularity."""
    tools: Dict[str, ToolApprovalConfig] = field(default_factory=dict)


@dataclass
class MCPServerConfig:
    """Configuration for an MCP server and its associated agent."""
    server_id: str
    connection: ConnectionConfig
    agent: AgentConfig
    approval: ApprovalConfig
    
    @classmethod
    def from_dict(cls, server_id: str, data: Dict[str, Any]) -> "MCPServerConfig":
        """Create MCPServerConfig from dictionary."""
        connection_data = data.get("connection", {})
        agent_data = data.get("agent", {})
        approval_data = data.get("approval", {})
        
        # Parse per-tool approval settings
        tools_approval = {}
        tools_data = approval_data.get("tools", {})
        for tool_name, tool_config in tools_data.items():
            tools_approval[tool_name] = ToolApprovalConfig(
                allowed_decisions=tool_config.get("allowed_decisions", ["approve", "reject", "edit"]),
                description=tool_config.get("description", f"{tool_name} pending approval"),
            )
        
        return cls(
            server_id=server_id,
            connection=ConnectionConfig(
                url=connection_data.get("url", ""),
                transport=connection_data.get("transport", "streamable_http"),
            ),
            agent=AgentConfig(
                name=agent_data.get("name", server_id),
                tool_name=agent_data.get("tool_name", f"{server_id}_operations"),
                tool_description=agent_data.get("tool_description", f"Operations for {server_id}"),
                prompt=agent_data.get("prompt", f"You are a specialist for {server_id} operations."),
            ),
            approval=ApprovalConfig(
                tools=tools_approval,
            ),
        )


@dataclass
class Config:
    """Complete configuration for the agent system."""
    supervisor_prompt: str
    servers: Dict[str, MCPServerConfig]
    
    def get_mcp_client_config(self) -> Dict[str, Dict[str, str]]:
        """Get configuration dict for MultiServerMCPClient."""
        return {
            server_id: {
                "url": server.connection.url,
                "transport": server.connection.transport,
            }
            for server_id, server in self.servers.items()
        }
    
    def get_approval_tools_for_server(self, server_id: str) -> Dict[str, Dict[str, Any]]:
        """
        Get tools that require human approval for a specific server.
        
        Args:
            server_id: The server ID to get approval tools for
            
        Returns:
            Dictionary mapping tool names to their approval config for HumanInTheLoopMiddleware
        """
        server = self.servers.get(server_id)
        if not server:
            return {}
        
        return {
            tool_name: {
                "allowed_decisions": tool_config.allowed_decisions,
                "description": tool_config.description,
            }
            for tool_name, tool_config in server.approval.tools.items()
        }
    
    def get_all_approval_tools(self) -> Dict[str, Dict[str, Any]]:
        """
        Get all tools across all servers that require human approval.
        
        Returns:
            Dictionary mapping tool names to their approval config
        """
        all_tools = {}
        for server_id in self.servers:
            all_tools.update(self.get_approval_tools_for_server(server_id))
        return all_tools


def load_config(config_path: Optional[Path] = None) -> Config:
    """
    Load configuration from JSON file.
    
    Args:
        config_path: Path to configuration file. Uses MCP_CONFIG_PATH env var
                     or defaults to mcp_servers.json in the project root.
        
    Returns:
        Config object with all server and agent configurations.
    """
    # Priority: argument > env var > default
    if config_path:
        path = Path(config_path)
    else:
        env_path = os.getenv("MCP_CONFIG_PATH")
        if env_path:
            path = Path(env_path)
            logger.info(f"Using MCP_CONFIG_PATH from environment: {path}")
        else:
            path = DEFAULT_CONFIG_PATH
            logger.info(f"Using default config path: {path}")
    
    logger.info(f"Loading configuration from {path}")
    
    if not path.exists():
        raise FileNotFoundError(
            f"Configuration file not found: {path}\n"
            f"Set MCP_CONFIG_PATH environment variable or copy mcp_servers.template.json to mcp_servers.json"
        )
    
    with open(path, "r") as f:
        data = json.load(f)
    
    # Parse supervisor config
    supervisor_data = data.get("supervisor", {})
    supervisor_prompt = supervisor_data.get("prompt", "You are an operations assistant.")
    
    # Parse server configs
    servers = {}
    for server_id, server_data in data.get("servers", {}).items():
        servers[server_id] = MCPServerConfig.from_dict(server_id, server_data)
        logger.info(f"  Loaded server config: {server_id} -> {servers[server_id].connection.url}")
    
    return Config(
        supervisor_prompt=supervisor_prompt,
        servers=servers,
    )
