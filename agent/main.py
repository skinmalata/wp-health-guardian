import os
from functools import cached_property
from google.genai import Client, types
from google.adk.agents import Agent
from google.adk.models import Gemini
from google.adk.tools.function_tool import FunctionTool

from agent.tools.health_check import (
    check_site_uptime,
    check_ssl_certificate,
    check_wordpress_specific,
    check_dns_resolution,
)
from agent.tools.analyzer import generate_health_report, format_report_for_display
from agent.tools.dynatrace_tools import (
    check_dynatrace_config,
    create_dynatrace_mcp_toolset,
    query_dynatrace_problems,
    query_dynatrace_entities,
    query_dynatrace_davis_analysis,
    query_dynatrace_for_domain,
)
from agent.tools.gcp_setup import check_gcp_config


class VertexAIGemini(Gemini):
    """Gemini model that forces Vertex AI backend."""

    _location: str = "us-central1"

    @cached_property
    def api_client(self) -> Client:
        base_url, api_version = self._base_url_and_api_version
        kwargs_for_http_options: dict[str, str] = {
            "headers": self._tracking_headers(),
            "retry_options": self.retry_options,
            "base_url": base_url,
        }
        if api_version:
            kwargs_for_http_options["api_version"] = api_version

        return Client(
            vertexai=True,
            location=self._location,
            http_options=types.HttpOptions(**kwargs_for_http_options),
        )

    @cached_property
    def _live_api_client(self) -> Client:
        base_url, _ = self._base_url_and_api_version
        return Client(
            vertexai=True,
            location=self._location,
            http_options=types.HttpOptions(
                headers=self._tracking_headers(),
                api_version=self._live_api_version,
                base_url=base_url,
            ),
        )


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
        FunctionTool(func=query_dynatrace_problems),
        FunctionTool(func=query_dynatrace_entities),
        FunctionTool(func=query_dynatrace_davis_analysis),
        FunctionTool(func=query_dynatrace_for_domain),
        FunctionTool(func=check_gcp_config),
    ]

    dynatrace_toolset = create_dynatrace_mcp_toolset()
    if dynatrace_toolset:
        tools.append(dynatrace_toolset)

    from agent.tools.gcp_setup import get_backend_mode

    mode = get_backend_mode()
    if mode == "vertex_ai":
        model = VertexAIGemini(model="gemini-2.5-flash")
        model_name = "gemini-2.5-flash (Vertex AI)"
    elif mode == "gemini_api":
        model = "gemini-2.0-flash"
        model_name = "gemini-2.0-flash (Gemini API)"
    else:
        model = "gemini-2.0-flash"
        model_name = "gemini-2.0-flash"

    agent = Agent(
        name="wordpress_health_guardian",
        model=model,
        instruction=f"""You are the WordPress Health Guardian, an AI agent that monitors and analyzes WordPress site health. You are powered by {model_name}.

Your capabilities:
1. **Health Checks**: Check site uptime, SSL certificates, DNS resolution, and WordPress-specific endpoints
2. **Dynatrace Integration**: If Dynatrace is configured, use it for deeper observability — call `query_dynatrace_problems(status="OPEN")` to check for active problems, and `query_dynatrace_entities()` to see monitored entities. You can also use the `dynatrace_` MCP tools for lower-level queries.
3. **GCP Integration**: Store health check history in Firestore; use Vertex AI for model inference
4. **Intelligent Analysis**: Analyze all collected data and provide actionable recommendations
5. **Reporting**: Generate comprehensive health reports in markdown format

When a user asks about a site:
1. Call `check_dynatrace_config()` to see if Dynatrace is configured
2. Run all health checks (uptime, SSL, DNS, WordPress endpoints) and check GCP config
3. If Dynatrace is configured, ALWAYS call `query_dynatrace_problems(status="OPEN")` to check for active problems and `query_dynatrace_entities()` to list monitored entities. ALSO call `query_dynatrace_for_domain(domain=<url>)` to find Dynatrace data specific to this site
4. If Dynatrace MCP tools (prefixed with `dynatrace_`) are available, also use them for deeper queries
5. If problems are found, call `query_dynatrace_davis_analysis(problem_id=...)` for each problem to get Davis AI root cause analysis
6. Generate a structured report with `generate_health_report(url="...", uptime_data=<uptime_dict>, ssl_data=<ssl_dict>, wp_data=<wp_dict>, dynatrace_problems=<problems_dict>, dynatrace_entities=<entities_dict>, dynatrace_domain_data=<dynatrace_for_domain_dict>)`. Pass the raw dicts directly — do NOT stringify them.
7. Format the final output with `format_report_for_display()`

Always include Dynatrace domain-specific findings in the report when available. Provide clear recommendations for any issues found. When Dynatrace problems are detected for the specific domain, include the Davis AI root cause analysis in the report.
""",
        tools=tools,
        description="WordPress site health monitoring and analysis agent powered by Google Cloud and Dynatrace MCP",
    )

    return agent
