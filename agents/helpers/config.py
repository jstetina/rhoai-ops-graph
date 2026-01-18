"""
Configuration loading utilities for MCP servers and agents.
"""

import os
import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional
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
class ApprovalConfig:
    """Configuration for human-in-the-loop approval."""
    require_approval: bool = False
    allowed_decisions: list = field(default_factory=lambda: ["approve", "reject", "edit"])
    description: str = "Operation pending approval"


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
                require_approval=approval_data.get("require_approval", False),
                allowed_decisions=approval_data.get("allowed_decisions", ["approve", "reject", "edit"]),
                description=approval_data.get("description", "Operation pending approval"),
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
    
    def get_approval_tools(self) -> Dict[str, Dict[str, Any]]:
        """Get tools that require human approval for HumanInTheLoopMiddleware."""
        return {
            server.agent.tool_name: {
                "allowed_decisions": server.approval.allowed_decisions,
                "description": server.approval.description,
            }
            for server in self.servers.values()
            if server.approval.require_approval
        }


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
