import httpx
import ssl
import socket
import datetime
from urllib.parse import urlparse


def _extract_hostname(url_or_hostname: str) -> str:
    parsed = urlparse(url_or_hostname)
    hostname = parsed.hostname or url_or_hostname.split("/")[0]
    return hostname.strip()


def check_site_uptime(url: str) -> dict:
    """Check if a WordPress site is reachable and measure response time."""
    try:
        start = datetime.datetime.now()
        resp = httpx.get(
            url,
            timeout=15.0,
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"},
            follow_redirects=True,
        )
        elapsed = (datetime.datetime.now() - start).total_seconds()
        return {
            "status_code": resp.status_code,
            "response_time_seconds": round(elapsed, 2),
            "is_up": resp.status_code < 500,
            "content_length": len(resp.text),
            "final_url": str(resp.url),
        }
    except httpx.TimeoutException:
        return {"error": "Request timed out after 15s", "is_up": False}
    except Exception as e:
        return {"error": str(e), "is_up": False}


def check_ssl_certificate(url_or_hostname: str) -> dict:
    """Check SSL certificate expiry for a domain. Accepts a URL or bare hostname."""
    try:
        hostname = _extract_hostname(url_or_hostname)
        context = ssl.create_default_context()
        with socket.create_connection((hostname, 443), timeout=10) as sock:
            with context.wrap_socket(sock, server_hostname=hostname) as ssock:
                cert = ssock.getpeercert()
        expiry = datetime.datetime.strptime(
            cert["notAfter"], "%b %d %H:%M:%S %Y %Z"
        )
        remaining = (expiry - datetime.datetime.now()).days
        issuer = {}
        if cert.get("issuer"):
            for rdn in cert["issuer"]:
                for attr in rdn:
                    if len(attr) >= 2:
                        issuer[attr[0]] = attr[1]
        return {
            "hostname": hostname,
            "issuer": issuer,
            "expiry_date": expiry.isoformat(),
            "days_remaining": remaining,
            "is_expiring_soon": remaining < 30,
            "is_valid": remaining > 0,
        }
    except Exception as e:
        return {"error": str(e), "is_valid": False}


def check_wordpress_specific(url: str) -> dict:
    """Check WordPress-specific health indicators."""
    results = {}
    base = url.rstrip("/")
    endpoints = [
        ("Login Page", f"{base}/wp-admin"),
        ("REST API", f"{base}/wp-json"),
        ("Health Check", f"{base}/wp-admin/health-check"),
    ]
    for name, endpoint in endpoints:
        try:
            resp = httpx.get(
                endpoint,
                timeout=10,
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"},
                follow_redirects=False,
            )
            results[name] = {"status_code": resp.status_code, "url": endpoint}
        except Exception as e:
            results[name] = {"error": str(e)}
    return results


def check_dns_resolution(hostname_or_url: str) -> dict:
    """Check DNS resolution for a domain."""
    try:
        hostname = _extract_hostname(hostname_or_url)
        addr = socket.getaddrinfo(hostname, 443)
        ips = list(set(a[4][0] for a in addr))
        return {
            "hostname": hostname,
            "resolved_ips": ips,
            "ip_count": len(ips),
        }
    except Exception as e:
        return {"error": str(e)}
