import os
import json
import httpx


def send_health_alert(report: dict) -> dict:
    """Send email notification via SendGrid when a health check detects issues.

    Returns dict with success/error info.
    """
    api_key = os.environ.get("SENDGRID_API_KEY", "").strip()
    to_email = os.environ.get("NOTIFICATION_EMAIL", "").strip()
    if not api_key or not to_email:
        return {"sent": False, "reason": "SENDGRID_API_KEY or NOTIFICATION_EMAIL not set"}

    summary = report.get("summary", {})
    status = (summary.get("status") or "unknown").lower()
    score = summary.get("score", 0)
    issues = summary.get("issues_found", 0)
    site_url = report.get("site_url", "unknown")
    checks = report.get("checks", [])

    score_threshold = int(os.environ.get("NOTIFICATION_SCORE_THRESHOLD", "70"))
    if score >= score_threshold and status not in ("critical", "warning", "degraded"):
        return {"sent": False, "reason": f"Score {score} >= threshold {score_threshold}, no alert needed"}

    issues_list = "\n".join(
        f"- [{c.get('category','?')}] {c.get('detail','')}"
        for c in checks[:10]
        if c.get("status") in ("error", "warning", "critical")
    ) or "No specific issues reported."

    recommendations = "\n".join(
        f"- {r}" for r in (report.get("recommendations") or [])[:5]
    ) or "No recommendations available."

    subject = f"[Health Alert] {site_url} — {status.upper()} (Score: {score})"
    body = f"""
Site: {site_url}
Status: {status.upper()}
Health Score: {score}/100
Issues Found: {issues}

Issues:
{issues_list}

Recommendations:
{recommendations}

View full report: {os.environ.get('SERVICE_URL', 'https://wordpress-health-guardian-948045128961.us-central1.run.app')}
    """.strip()

    data = {
        "personalizations": [{"to": [{"email": to_email}], "subject": subject}],
        "from": {"email": "health-guardian@wordpress-health-guardian.app", "name": "WordPress Health Guardian"},
        "content": [{"type": "text/plain", "value": body}],
    }

    try:
        resp = httpx.post(
            "https://api.sendgrid.com/v3/mail/send",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            content=json.dumps(data),
            timeout=15.0,
        )
        if resp.status_code in (200, 201, 202):
            return {"sent": True, "to": to_email, "subject": subject}
        return {"sent": False, "error": f"SendGrid returned {resp.status_code}: {resp.text[:200]}"}
    except Exception as e:
        return {"sent": False, "error": str(e)}
