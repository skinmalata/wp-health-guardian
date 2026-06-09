import os
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource


def _normalize_dt_url(raw: str) -> str:
    raw = raw.strip().rstrip("/")
    for prefix in ("https://", "http://"):
        if raw.startswith(prefix):
            raw = raw.removeprefix(prefix)
    if ".dynatrace.com" not in raw:
        raw = f"{raw}.live.dynatrace.com"
    return raw


def setup_opentelemetry():
    dt_env = os.environ.get("DT_ENVIRONMENT", "").strip()
    dt_token = os.environ.get("DT_OTEL_TOKEN", "").strip()
    project = os.environ.get("GOOGLE_CLOUD_PROJECT", "unknown")

    if not dt_env or not dt_token:
        return None

    base = _normalize_dt_url(dt_env)
    otlp_endpoint = f"https://{base}/api/v2/otlp"

    resource = Resource.create({
        "service.name": "wordpress-health-guardian",
        "service.namespace": project,
        "deployment.environment": "production",
    })

    provider = TracerProvider(resource=resource)
    exporter = OTLPSpanExporter(
        endpoint=f"{otlp_endpoint}/v1/traces",
        headers={"Authorization": f"Api-Token {dt_token}"},
    )
    processor = BatchSpanProcessor(exporter)
    provider.add_span_processor(processor)
    trace.set_tracer_provider(provider)

    return provider
