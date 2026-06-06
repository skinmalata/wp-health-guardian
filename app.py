import os
import asyncio
import sys
from opentelemetry import trace

# Force aiohttp to use ThreadedResolver instead of async DNS resolver
# This fixes "Could not contact DNS servers" on Windows
try:
    import aiohttp.resolver as ar
    ar.AsyncResolver = ar.ThreadedResolver
except Exception:
    pass

import uvicorn
from dotenv import load_dotenv

load_dotenv()

from observability.otel_setup import setup_opentelemetry
from web.server import app

otel_provider = setup_opentelemetry()
if otel_provider:
    tracer = trace.get_tracer("wordpress-health-guardian")

    @app.middleware("http")
    async def otel_trace_middleware(request, call_next):
        with tracer.start_as_current_span(
            f"{request.method} {request.url.path}",
            attributes={
                "http.method": request.method,
                "http.url": str(request.url),
            },
        ) as span:
            response = await call_next(request)
            span.set_attribute("http.status_code", response.status_code)
            return response

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)
