## Inspiration

I manage several WordPress sites. Every time a site goes down or slows to a crawl, I find out from a user — never before. There are monitoring tools out there, but they just beep at you. They don't tell you *what* broke, *why* it broke, or *how* to fix it.

I wanted an agent that doesn't just watch — it understands. Something that combines observability data with AI reasoning to give me a plain-English diagnosis and a fix. The Google Cloud Rapid Agent Hackathon was the perfect opportunity to build it.

## What I Learned

Building this agent taught me:

- **ADK architecture** — Google's Agent Development Kit is elegant. Tools are just Python functions, and the agent orchestrates them automatically based on the task.
- **MCP protocol** — The Dynatrace MCP server exposes observability data through a standardized interface. Connecting it to an ADK agent via `McpToolset` was surprisingly clean.
- **Gemini as a reasoning engine** — The real magic is in the prompt. Gemini takes raw health data and transforms it into structured reports with actionable recommendations. It doesn't just report problems — it prioritizes them.
- **Health check engineering** — SSL expiry parsing, DNS resolution edge cases, WordPress endpoint fingerprinting — each check has its own quirks.

## How I Built It

The agent has three layers:

1. **Health check tools** — Pure Python functions using `httpx` and `ssl` to probe sites. Each function is a standalone capability the agent can call.
2. **Dynatrace MCP** — An `McpToolset` connector that gives the agent access to Dynatrace's observability platform — problems, vulnerabilities, DQL queries, and entity discovery.
3. **Analysis engine** — A structured report builder that scores health (0-100), categorizes findings, and generates prioritized recommendations.

All wrapped in a FastAPI server with a clean web UI, deployed to Cloud Run.

## Challenges

The biggest challenge was getting the ADK + MCP integration right. The ADK's `McpToolset` expects specific connection parameters, and the Dynatrace MCP server requires environment variables for authentication. Getting the tool names to play nicely with the agent's function-calling pipeline took some trial and error.

Another challenge: making the health scoring fair. A slow response shouldn't count as much as a downed server. I iterated on the scoring algorithm until the report felt intuitive — a score of 85 means "mostly healthy, here's a minor thing to look at", while 40 means "fix this now".
