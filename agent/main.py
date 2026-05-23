from google.adk.agents import Agent
from google.adk.tools.function_tool import FunctionTool

from agent.tools.health_check import (
    check_site_uptime,
    check_ssl_certificate,
    check_wordpress_specific,
    check_dns_resolution,
)
from agent.tools.analyzer import generate_health_report, format_report_for_display
from agent.tools.dynatrace_tools import check_dynatrace_config, create_dynatrace_mcp_toolset


def create_health_guardian_agent() -> Agent:
    """Create the WordPress Health Guardian agent with all tools."""

    tools = [
        FunctionTool(func=check_site_uptime),
        FunctionTool(func=check_ssl_certificate),
        FunctionTool(func=check_wordpress_specific),
        FunctionTool(func=check_dns_resolution),
        FunctionTool(func=generate_health_report),
        FunctionTool(func=format_report_for_display),
        FunctionTool(func=check_dynatrace_config),
    ]

    dynatrace_toolset = create_dynatrace_mcp_toolset()
    if dynatrace_toolset:
        tools.append(dynatrace_toolset)

    agent = Agent(
        name="wordpress_health_guardian",
        model="gemini-2.0-flash",
        instruction="""You are the WordPress Health Guardian, an AI agent that monitors and analyzes WordPress site health.

Your capabilities:
1. **Health Checks**: Check site uptime, SSL certificates, DNS resolution, and WordPress-specific endpoints
2. **Dynatrace Integration**: If Dynatrace is configured, use it for deeper observability (problems, vulnerabilities, performance metrics)
3. **Intelligent Analysis**: Analyze all collected data and provide actionable recommendations
4. **Reporting**: Generate comprehensive health reports in markdown format

When a user asks about a site:
1. First check basic health (uptime, SSL, DNS, WordPress endpoints)
2. If Dynatrace is available, also query Dynatrace for monitored entity data
3. Analyze the results and generate a structured report
4. Provide clear recommendations for any issues found

Always format responses clearly. Use the format_report_for_display tool to create well-structured reports.
""",
        tools=tools,
        description="WordPress site health monitoring and analysis agent",
    )

    return agent
