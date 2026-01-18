"""
Helper modules for the RHOAI Ops Buddy agent system.

This package provides:
- config: Configuration loading from mcp_servers.json
- middleware: Tool execution middleware (error handling, MCP normalization)
- subagents: Sub-agent factories and tool wrappers for supervisor pattern
"""

from helpers.config import (
    Config,
    MCPServerConfig,
    AgentConfig,
    ConnectionConfig,
    ApprovalConfig,
    load_config,
)

from helpers.middleware import handle_tool_errors

from helpers.subagents import (
    create_subagent,
    create_subagent_tool,
    build_subagents_and_tools,
)

__all__ = [
    # Config
    "Config",
    "MCPServerConfig",
    "AgentConfig",
    "ConnectionConfig",
    "ApprovalConfig",
    "load_config",
    # Middleware
    "handle_tool_errors",
    # Subagents
    "create_subagent",
    "create_subagent_tool",
    "build_subagents_and_tools",
]
