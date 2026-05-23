import os
from google.adk.tools.mcp_tool.mcp_toolset import McpToolset
from google.adk.tools.mcp_tool.mcp_session_manager import StdioConnectionParams
from mcp import StdioServerParameters


def create_dynatrace_mcp_toolset():
    """Create an McpToolset connected to the Dynatrace MCP server."""
    dt_env = os.environ.get("DT_ENVIRONMENT", "")
    dt_token = os.environ.get("DT_PLATFORM_TOKEN", "")

    if not dt_env or not dt_token:
        return None

    env = {
        "DT_ENVIRONMENT": dt_env,
        "DT_PLATFORM_TOKEN": dt_token,
    }

    server_params = StdioServerParameters(
        command="npx.cmd",
        args=["-y", "@dynatrace-oss/dynatrace-mcp-server"],
        env=env,
    )

    connection_params = StdioConnectionParams(
        server_params=server_params,
        timeout=30.0,
    )

    return McpToolset(
        connection_params=connection_params,
        tool_name_prefix="dynatrace_",
    )


def check_dynatrace_config() -> dict:
    """Check if Dynatrace environment variables are configured."""
    dt_env = os.environ.get("DT_ENVIRONMENT", "")
    dt_token = os.environ.get("DT_PLATFORM_TOKEN", "")
    configured = bool(dt_env and dt_token)
    return {
        "configured": configured,
        "message": "Dynatrace MCP is configured and ready" if configured
        else "Dynatrace not configured. Set DT_ENVIRONMENT and DT_PLATFORM_TOKEN env vars.",
    }
