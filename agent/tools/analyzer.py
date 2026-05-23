import json
import datetime


def generate_health_report(
    url: str,
    uptime_data: str,
    ssl_data: str,
    wp_data: str,
    dynatrace_data: str = "",
) -> dict:
    """Generate a structured health report from all collected data.

    Uses stringified dict data and combines it into a report structure.
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
    }

    try:
        up = json.loads(uptime_data) if isinstance(uptime_data, str) else uptime_data
    except (json.JSONDecodeError, TypeError):
        up = {}

    try:
        ssl = json.loads(ssl_data) if isinstance(ssl_data, str) else ssl_data
    except (json.JSONDecodeError, TypeError):
        ssl = {}

    try:
        wp = json.loads(wp_data) if isinstance(wp_data, str) else wp_data
    except (json.JSONDecodeError, TypeError):
        wp = {}

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

    if dynatrace_data and dynatrace_data != "{}":
        try:
            dt = json.loads(dynatrace_data) if isinstance(dynatrace_data, str) else dynatrace_data
            report["checks"].append({
                "category": "Dynatrace Observability",
                "status": "info",
                "detail": f"Dynatrace data available: {json.dumps(dt)[:200]}",
            })
        except (json.JSONDecodeError, TypeError):
            pass

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
