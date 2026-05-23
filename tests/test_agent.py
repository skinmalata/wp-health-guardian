from agent.tools.health_check import (
    check_site_uptime,
    check_ssl_certificate,
    check_dns_resolution,
)
from agent.tools.analyzer import generate_health_report, format_report_for_display


def test_check_site_uptime_success():
    result = check_site_uptime("https://wordpress.org")
    assert result is not None
    assert "is_up" in result
    assert result["is_up"] is True
    assert "response_time_seconds" in result
    assert result["response_time_seconds"] < 10


def test_check_site_uptime_failure():
    result = check_site_uptime("https://thissitedoesnotexist-hopefully.example.com")
    assert result is not None
    assert result.get("is_up") is False


def test_check_dns_resolution():
    result = check_dns_resolution("wordpress.org")
    assert result is not None
    assert "resolved_ips" in result
    assert len(result["resolved_ips"]) > 0


def test_generate_health_report():
    uptime = '{"is_up": true, "status_code": 200, "response_time_seconds": 1.5}'
    ssl = '{"is_valid": true, "days_remaining": 90, "is_expiring_soon": false}'
    wp = '{"Login Page": {"status_code": 200}, "REST API": {"status_code": 200}}'

    report = generate_health_report(
        url="https://example.com",
        uptime_data=uptime,
        ssl_data=ssl,
        wp_data=wp,
    )

    assert report is not None
    assert report["summary"]["status"] == "healthy"
    assert report["summary"]["score"] >= 80
    assert len(report["checks"]) > 0


def test_generate_health_report_with_issues():
    uptime = '{"is_up": false, "error": "Connection refused"}'
    ssl = '{"is_valid": true, "days_remaining": 5, "is_expiring_soon": true}'
    wp = '{"Login Page": {"status_code": 403}, "REST API": {"status_code": 404}}'

    report = generate_health_report(
        url="https://example.com",
        uptime_data=uptime,
        ssl_data=ssl,
        wp_data=wp,
    )

    assert report is not None
    assert report["summary"]["issues_found"] > 0
    assert len(report["recommendations"]) > 0


def test_format_report_for_display():
    report = {
        "site_url": "https://example.com",
        "timestamp": "2026-01-01T00:00:00",
        "summary": {"status": "healthy", "score": 95, "issues_found": 0},
        "checks": [
            {"category": "Uptime", "status": "pass", "detail": "Site is up"}
        ],
        "recommendations": [],
    }
    formatted = format_report_for_display(report)
    assert "WordPress Health Report" in formatted
    assert "healthy" in formatted.lower()
