import json
import datetime


def _safe_parse(data):
    if not isinstance(data, str):
        return data
    try:
        return json.loads(data)
    except (json.JSONDecodeError, TypeError):
        pass
    try:
        import ast
        parsed = ast.literal_eval(data)
        if isinstance(parsed, dict):
            return parsed
        return {}
    except (ValueError, SyntaxError, MemoryError, ImportError):
        pass
    return {}


def generate_health_report(
    url: str,
    uptime_data: dict,
    ssl_data: dict,
    wp_data: dict,
    dynatrace_data: dict = None,
    dynatrace_problems: dict = None,
    dynatrace_entities: dict = None,
    dynatrace_domain_data: dict = None,
) -> dict:
    """Generate a structured health report from all collected data.

    Pass the raw dict results from check_site_uptime(), check_ssl_certificate(),
    check_wordpress_specific(), query_dynatrace_problems(), query_dynatrace_entities()
    directly as arguments. Do NOT stringify them.
    Pass query_dynatrace_for_domain() result as dynatrace_domain_data for
    Dynatrace-enhanced analysis specific to the checked domain.
    Returns a report dictionary with findings, recommendations, and severity.
    """
    report = {
        "site_url": url,
        "timestamp": datetime.datetime.now().isoformat(),
        "summary": {
            "status": "unknown",
            "score": 0,
            "issues_found": 0,
        },
        "checks": [],
        "recommendations": [],
        "dynatrace_enhanced": False,
    }

    up = _safe_parse(uptime_data)
    ssl = _safe_parse(ssl_data)
    wp = _safe_parse(wp_data)

    score = 100
    issues = 0

    if up.get("is_up"):
        report["checks"].append({
            "category": "Uptime",
            "status": "pass",
            "detail": f"Site is up (HTTP {up.get('status_code')}, {up.get('response_time_seconds')}s)",
        })
        if up.get("response_time_seconds", 0) > 3:
            score -= 10
            report["recommendations"].append(
                "Slow response time detected. Consider enabling caching, using a CDN, or upgrading hosting."
            )
        if up.get("response_time_seconds", 0) > 5:
            score -= 10
    else:
        score -= 30
        issues += 1
        report["checks"].append({
            "category": "Uptime",
            "status": "fail",
            "detail": up.get("error", "Site is unreachable"),
        })
        report["recommendations"].append("Site is down! Check web server, hosting, or DNS configuration.")

    if ssl.get("is_valid"):
        report["checks"].append({
            "category": "SSL Certificate",
            "status": "pass",
            "detail": f"Valid for {ssl.get('days_remaining')} more days",
        })
        if ssl.get("is_expiring_soon"):
            score -= 15
            issues += 1
            report["recommendations"].append(
                f"SSL certificate expires in {ssl.get('days_remaining')} days. Renew now to avoid disruption."
            )
    else:
        score -= 25
        issues += 1
        report["checks"].append({
            "category": "SSL Certificate",
            "status": "fail",
            "detail": ssl.get("error", "SSL check failed"),
        })
        report["recommendations"].append("SSL certificate issue detected. Verify certificate installation.")

    if isinstance(wp, dict):
        login = wp.get("Login Page", {})
        rest = wp.get("REST API", {})
        health = wp.get("Health Check", {})

        if login.get("status_code") == 200:
            report["checks"].append({
                "category": "WordPress Login",
                "status": "pass",
                "detail": "wp-admin is accessible",
            })
        elif login.get("status_code") == 302:
            report["checks"].append({
                "category": "WordPress Login",
                "status": "info",
                "detail": "wp-admin redirects (likely to login page)",
            })
        else:
            score -= 10
            issues += 1
            report["checks"].append({
                "category": "WordPress Login",
                "status": "warn",
                "detail": f"wp-admin returned {login.get('status_code')}",
            })

        if rest.get("status_code") == 200:
            report["checks"].append({
                "category": "REST API",
                "status": "pass",
                "detail": "WordPress REST API is accessible",
            })
        else:
            score -= 10
            issues += 1
            report["recommendations"].append("WordPress REST API is not accessible. Check permalinks and .htaccess.")

    if dynatrace_data:
        dt = dynatrace_data
        report["checks"].append({
            "category": "Dynatrace Observability",
            "status": "info",
            "detail": f"Dynatrace data available: {json.dumps(dt)[:200]}",
        })

    if dynatrace_problems:
        probs = dynatrace_problems
        if probs.get("configured") and not probs.get("error") and probs.get("total_count", 0) > 0:
            for p in probs.get("problems", []):
                severity = p.get("severity", "unknown")
                status = "fail" if severity in ("CRITICAL", "ERROR") else "warn"
                report["checks"].append({
                    "category": "Dynatrace Problem",
                    "status": status,
                    "detail": f"{p.get('title', 'Unknown')} ({severity})",
                })
                issues += 1
                score -= 10
                report["recommendations"].append(
                    f"Fix Dynatrace problem: {p.get('title', 'Unknown')}"
                )
        elif probs.get("configured") and not probs.get("error"):
            report["checks"].append({
                "category": "Dynatrace Problems",
                "status": "pass",
                "detail": "No active problems found",
            })
        elif probs.get("configured") and probs.get("error"):
            detail = probs.get("error", "API unavailable")
            if "403" in detail:
                detail = "Dynatrace MCP available (direct API requires classic token)"
            report["checks"].append({
                "category": "Dynatrace Problems",
                "status": "info",
                "detail": detail,
            })
        else:
            report["checks"].append({
                "category": "Dynatrace",
                "status": "info",
                "detail": probs.get("error", "Not available"),
            })

    if dynatrace_entities:
        ents = dynatrace_entities
        if ents.get("configured") and not ents.get("error") and ents.get("total_count", 0) > 0:
            report["checks"].append({
                "category": "Dynatrace Entities",
                "status": "pass",
                "detail": f"{ents.get('total_count')} entities monitored",
            })
        elif ents.get("configured") and not ents.get("error"):
            report["checks"].append({
                "category": "Dynatrace Entities",
                "status": "info",
                "detail": "No entities found",
            })
        elif ents.get("configured") and ents.get("error"):
            detail = ents.get("error", "API unavailable")
            if "403" in detail:
                detail = "Dynatrace MCP available (direct API requires classic token)"
            report["checks"].append({
                "category": "Dynatrace Entities",
                "status": "info",
                "detail": detail,
            })

    if dynatrace_domain_data:
        dd = dynatrace_domain_data
        if dd.get("configured") and dd.get("has_monitoring_data"):
            report["dynatrace_enhanced"] = True
            for ent in dd.get("entities", []):
                health = ent.get("health_state", "unknown")
                status = "pass" if health in ("HEALTHY",) else ("warn" if health in ("UNHEALTHY",) else "info")
                report["checks"].append({
                    "category": "Dynatrace Domain Entity",
                    "status": status,
                    "detail": f"Entity: {ent.get('name', 'Unknown')} ({ent.get('type', '?')}) — health: {health}",
                })
            for prob in dd.get("problems", []):
                severity = prob.get("severity", "unknown")
                status = "fail" if severity in ("CRITICAL", "ERROR") else "warn"
                report["checks"].append({
                    "category": "Dynatrace Domain Problem",
                    "status": status,
                    "detail": f"{prob.get('title', 'Unknown')} ({severity})",
                })
                issues += 1
                score -= 15
                report["recommendations"].append(
                    f"Dynatrace detected a {severity.lower()} problem affecting this site: {prob.get('title', 'Unknown')}. "
                    f"Investigate in Dynatrace for root cause."
                )
            if dd.get("problems_found", 0) == 0 and dd.get("entities_found", 0) > 0:
                report["checks"].append({
                    "category": "Dynatrace Domain Monitoring",
                    "status": "pass",
                    "detail": f"Dynatrace monitors {dd.get('entities_found')} entity(ies) for this domain — no active problems",
                })
        elif dd.get("configured") and not dd.get("error"):
            report["checks"].append({
                "category": "Dynatrace Domain Lookup",
                "status": "info",
                "detail": dd.get("message", "No Dynatrace data for this domain"),
            })

    score = max(0, min(100, score))
    if score >= 80:
        status = "healthy"
    elif score >= 50:
        status = "warning"
    else:
        status = "critical"

    report["summary"] = {
        "status": status,
        "score": score,
        "issues_found": issues,
    }

    return report


def format_report_for_display(report: dict) -> str:
    """Format a health report dict into a human-readable markdown string."""
    s = report.get("summary", {})
    lines = [
        f"# WordPress Health Report",
        f"**Site:** {report.get('site_url', 'N/A')}",
        f"**Time:** {report.get('timestamp', 'N/A')}",
        f"",
        f"## Summary",
        f"- **Status:** {s.get('status', 'unknown').upper()}",
        f"- **Health Score:** {s.get('score', 0)}/100",
        f"- **Issues Found:** {s.get('issues_found', 0)}",
        f"",
        f"## Checks",
    ]
    if report.get("dynatrace_enhanced"):
        lines.append("")
        lines.append("> 🔭 **Dynatrace Enhanced** — Analysis includes domain-specific Dynatrace monitoring data")

    for c in report.get("checks", []):
        emoji = {"pass": "✅", "fail": "❌", "warn": "⚠️", "info": "ℹ️"}.get(
            c.get("status", "info"), "❓"
        )
        lines.append(f"- {emoji} **{c.get('category')}:** {c.get('detail', 'N/A')}")

    if report.get("recommendations"):
        lines.extend(["", "## Recommendations"])
        for i, r in enumerate(report.get("recommendations", []), 1):
            lines.append(f"{i}. {r}")

    return "\n".join(lines)
