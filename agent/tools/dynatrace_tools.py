import os
import httpx
from urllib.parse import urlparse
from google.adk.tools.mcp_tool.mcp_toolset import McpToolset
from google.adk.tools.mcp_tool.mcp_session_manager import StdioConnectionParams
from mcp import StdioServerParameters


def create_dynatrace_mcp_toolset():
    """Create an McpToolset connected to the Dynatrace MCP server."""
    dt_env = os.environ.get("DT_ENVIRONMENT", "").strip()
    dt_token = os.environ.get("DT_PLATFORM_TOKEN", "").strip()
    if not dt_env or not dt_token:
        return None
    env = {
        "DT_ENVIRONMENT": dt_env,
        "DT_PLATFORM_TOKEN": dt_token,
    }
    server_params = StdioServerParameters(
        command="npx",
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


def _normalize_dt_url(raw: str) -> str:
    raw = raw.strip().rstrip("/")
    for prefix in ("https://", "http://"):
        if raw.startswith(prefix):
            raw = raw.removeprefix(prefix)
    if "apps.dynatrace.com" in raw:
        raw = raw.replace("apps.dynatrace.com", "live.dynatrace.com")
    if ".dynatrace.com" not in raw:
        raw = f"{raw}.live.dynatrace.com"
    return raw


def check_dynatrace_config() -> dict:
    """Check if Dynatrace environment variables are configured."""
    dt_env = os.environ.get("DT_ENVIRONMENT", "").strip()
    dt_token = os.environ.get("DT_PLATFORM_TOKEN", "").strip()
    configured = bool(dt_env and dt_token)
    display = ""
    if configured:
        base = _normalize_dt_url(dt_env)
        display = base[:30] + "..." if len(base) > 30 else base
    return {
        "configured": configured,
        "dt_environment": display or dt_env[:30],
        "message": "Dynatrace is configured and ready" if configured
        else "Dynatrace not configured. Set DT_ENVIRONMENT and DT_PLATFORM_TOKEN env vars.",
    }


def _get_dt_token() -> str:
    """Return the best available Dynatrace token: classic token preferred, fallback to platform token."""
    classic = os.environ.get("DT_CLASSIC_TOKEN", "").strip()
    if classic:
        return classic
    return os.environ.get("DT_PLATFORM_TOKEN", "").strip()


def query_dynatrace_problems(status: str = "OPEN") -> dict:
    """Query Dynatrace for active problems via the API.

    Args:
        status: Problem status filter - "OPEN", "CLOSED", or "ALL" (default: "OPEN")

    Returns:
        Dict with problems data or error message.
    """
    dt_env = os.environ.get("DT_ENVIRONMENT", "").strip()
    dt_token = _get_dt_token()
    if not dt_env or not dt_token:
        return {"configured": False, "error": "Dynatrace not configured"}
    try:
        base = _normalize_dt_url(dt_env)
        url = f"https://{base}/api/v2/problems"
        params = {"pageSize": 10, "status": status}
        headers = {"Authorization": f"Api-Token {dt_token}"}
        resp = httpx.get(url, params=params, headers=headers, timeout=15.0)
        if resp.status_code == 200:
            data = resp.json()
            problems = data.get("problems", [])
            return {
                "configured": True,
                "total_count": data.get("totalCount", len(problems)),
                "problems": [
                    {
                        "id": p.get("problemId"),
                        "title": p.get("title"),
                        "status": p.get("status"),
                        "severity": p.get("severityLevel"),
                        "impact": p.get("impactLevel"),
                        "start_time": p.get("startTime"),
                    }
                    for p in problems[:5]
                ],
            }
        return {
            "configured": True,
            "error": f"Dynatrace API returned {resp.status_code}: {resp.text[:200]}",
        }
    except Exception as e:
        return {"configured": True, "error": str(e)}


def query_dynatrace_entities(entity_type: str = None, limit: int = 10) -> dict:
    """Query Dynatrace for monitored entities via the API.

    Args:
        entity_type: Type filter (e.g. "HOST", "SERVICE", "APPLICATION"). None for all.
        limit: Max entities to return (default: 10)

    Returns:
        Dict with entities data or error message.
    """
    dt_env = os.environ.get("DT_ENVIRONMENT", "").strip()
    dt_token = _get_dt_token()
    if not dt_env or not dt_token:
        return {"configured": False, "error": "Dynatrace not configured"}
    try:
        base = _normalize_dt_url(dt_env)
        url = f"https://{base}/api/v2/entities"
        params = {"pageSize": limit}
        if entity_type:
            params["entitySelector"] = f"type(\"{entity_type}\")"
        else:
            params["entitySelector"] = "type(\"HOST\"),type(\"SERVICE\"),type(\"APPLICATION\")"
        headers = {"Authorization": f"Api-Token {dt_token}"}
        resp = httpx.get(url, params=params, headers=headers, timeout=15.0)
        if resp.status_code == 200:
            data = resp.json()
            entities = data.get("entities", [])
            return {
                "configured": True,
                "total_count": data.get("totalCount", len(entities)),
                "entities": [
                    {
                        "id": e.get("entityId"),
                        "name": e.get("displayName"),
                        "type": e.get("type"),
                        "health_state": "healthy",
                    }
                    for e in entities[:limit]
                ],
            }
        return {
            "configured": True,
            "error": f"Dynatrace API returned {resp.status_code}: {resp.text[:200]}",
        }
    except Exception as e:
        return {"configured": True, "error": str(e)}


def _extract_hostname(url_or_hostname: str) -> str:
    parsed = urlparse(url_or_hostname)
    hostname = parsed.hostname or url_or_hostname.split("/")[0]
    return hostname.strip()


def _search_entities_by_name(name_fragment: str, limit: int = 20) -> list:
    """Search Dynatrace entities whose name contains the given fragment."""
    dt_env = os.environ.get("DT_ENVIRONMENT", "").strip()
    dt_token = _get_dt_token()
    if not dt_env or not dt_token:
        return []
    try:
        base = _normalize_dt_url(dt_env)
        fragments = name_fragment.lower().split(".")
        selector = f"entityName(\"*{fragments[0]}*\")"
        url = f"https://{base}/api/v2/entities"
        params = {"pageSize": limit, "entitySelector": selector}
        headers = {"Authorization": f"Api-Token {dt_token}"}
        resp = httpx.get(url, params=params, headers=headers, timeout=15.0)
        if resp.status_code == 200:
            return resp.json().get("entities", [])
        return []
    except Exception:
        return []


def _get_entity_health_state(entity_id: str) -> str:
    """Get the health state of a Dynatrace entity."""
    dt_env = os.environ.get("DT_ENVIRONMENT", "").strip()
    dt_token = _get_dt_token()
    if not dt_env or not dt_token:
        return "unknown"
    try:
        base = _normalize_dt_url(dt_env)
        url = f"https://{base}/api/v2/entities/{entity_id}"
        headers = {"Authorization": f"Api-Token {dt_token}"}
        resp = httpx.get(url, headers=headers, timeout=10.0)
        if resp.status_code == 200:
            data = resp.json()
            return data.get("healthState", data.get("properties", {}).get("healthState", "unknown"))
        return "unknown"
    except Exception:
        return "unknown"


def query_dynatrace_for_domain(domain: str) -> dict:
    """Query Dynatrace for monitoring data related to a specific domain.

    Searches for entities whose name matches the domain, checks their health
    state, and finds any open problems affecting them. This correlates the
    domain being health-checked with Dynatrace observability data so the
    report can include Dynatrace-specific findings.

    Args:
        domain: URL or hostname of the site being checked (e.g. \"https://wordpress.org\")

    Returns:
        Dict with domain-related Dynatrace findings or error message.
    """
    dt_env = os.environ.get("DT_ENVIRONMENT", "").strip()
    dt_token = _get_dt_token()
    if not dt_env or not dt_token:
        return {"configured": False, "domain": domain, "error": "Dynatrace not configured"}

    try:
        hostname = _extract_hostname(domain)
        entities = _search_entities_by_name(hostname, limit=10)

        matched_entities = []
        entity_ids = []

        for ent in entities:
            name = ent.get("displayName", "").lower()
            eid = ent.get("entityId")
            if hostname in name or any(part in name for part in hostname.split(".") if len(part) > 3):
                health = _get_entity_health_state(eid) if eid else "unknown"
                matched_entities.append({
                    "id": eid,
                    "name": ent.get("displayName"),
                    "type": ent.get("type"),
                    "health_state": health,
                })
                if eid:
                    entity_ids.append(eid)

        related_problems = []
        if entity_ids:
            base = _normalize_dt_url(dt_env)
            selector = "(" + ",".join(f"entityId(\"{eid}\")" for eid in entity_ids[:5]) + ")"
            url = f"https://{base}/api/v2/problems"
            params = {"pageSize": 10, "status": "OPEN", "entitySelector": selector}
            headers = {"Authorization": f"Api-Token {dt_token}"}
            resp = httpx.get(url, params=params, headers=headers, timeout=15.0)
            if resp.status_code == 200:
                for p in resp.json().get("problems", []):
                    related_problems.append({
                        "id": p.get("problemId"),
                        "title": p.get("title"),
                        "severity": p.get("severityLevel"),
                        "impact": p.get("impactLevel"),
                        "status": p.get("status"),
                        "start_time": p.get("startTime"),
                    })

            for prob in related_problems[:3]:
                pid = prob.get("id")
                if pid:
                    try:
                        pu = f"https://{base}/api/v2/problems/{pid}"
                        pr = httpx.get(pu, headers=headers, timeout=10.0)
                        if pr.status_code == 200:
                            pd = pr.json()
                            evidence = pd.get("evidenceDetails", {}).get("details", [])
                            prob["root_cause"] = pd.get("rootCauseEntity", {}).get("entityId")
                            prob["evidence_count"] = len(evidence)
                    except Exception:
                        pass

        result = {
            "configured": True,
            "domain": hostname,
            "entities_found": len(matched_entities),
            "entities": matched_entities[:10],
            "problems_found": len(related_problems),
            "problems": related_problems[:5],
            "has_monitoring_data": len(matched_entities) > 0,
            "has_related_problems": len(related_problems) > 0,
        }

        if not matched_entities and not related_problems:
            result["enhancement"] = "none"
            result["message"] = "No Dynatrace monitoring data found for this domain"
        elif related_problems:
            result["enhancement"] = "problems"
            result["message"] = f"Dynatrace found {len(related_problems)} problem(s) affecting this domain"
        else:
            result["enhancement"] = "monitored"
            result["message"] = f"Dynatrace is monitoring {len(matched_entities)} entity(ies) related to this domain — no active problems"

        return result

    except Exception as e:
        return {"configured": True, "domain": domain, "error": str(e), "has_monitoring_data": False}


def query_dynatrace_davis_analysis(problem_id: str) -> dict:
    """Fetch Davis AI root cause analysis for a specific problem.

    Args:
        problem_id: The Dynatrace problem ID to analyze (e.g. "-1908432690963577333")

    Returns:
        Dict with Davis analysis including root cause, impact, severity, and evidence.
    """
    dt_env = os.environ.get("DT_ENVIRONMENT", "").strip()
    dt_token = _get_dt_token()
    if not dt_env or not dt_token:
        return {"configured": False, "error": "Dynatrace not configured"}
    try:
        base = _normalize_dt_url(dt_env)
        url = f"https://{base}/api/v2/problems/{problem_id}"
        headers = {"Authorization": f"Api-Token {dt_token}"}
        resp = httpx.get(url, headers=headers, timeout=15.0)
        if resp.status_code == 200:
            data = resp.json()
            evidence = data.get("evidenceDetails", {}).get("details", [])
            return {
                "configured": True,
                "problem_id": problem_id,
                "title": data.get("title"),
                "severity": data.get("severityLevel"),
                "impact": data.get("impactLevel"),
                "status": data.get("status"),
                "root_cause": data.get("rootCauseEntity", {}).get("entityId") if data.get("rootCauseEntity") else None,
                "affected_entities": [e.get("entityId") for e in (data.get("affectedEntities") or [])[:10]],
                "evidence_count": len(evidence),
                "evidence": [
                    {
                        "entity": e.get("entity", {}).get("name"),
                        "entity_id": e.get("entity", {}).get("id"),
                        "event_type": e.get("eventType"),
                    }
                    for e in evidence[:5]
                ],
                "start_time": data.get("startTime"),
                "end_time": data.get("endTime"),
            }
        return {
            "configured": True,
            "error": f"Dynatrace API returned {resp.status_code}: {resp.text[:200]}",
        }
    except Exception as e:
        return {"configured": True, "error": str(e)}
