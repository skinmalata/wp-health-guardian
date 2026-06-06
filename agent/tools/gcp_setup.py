import os
import logging

logger = logging.getLogger(__name__)


def is_running_on_gcp() -> bool:
    """Detect if we're running on Google Cloud (Cloud Run, GCE, etc.)."""
    return bool(
        os.environ.get("K_SERVICE")
        or os.environ.get("GOOGLE_CLOUD_PROJECT")
        or os.environ.get("GCP_PROJECT")
    )


def get_project_id() -> str:
    return os.environ.get("GOOGLE_CLOUD_PROJECT", "") or os.environ.get(
        "GCP_PROJECT", ""
    )


def get_cloud_run_url() -> str:
    return os.environ.get("CLOUD_RUN_SERVICE_URL", "")


def _can_use_vertex_ai() -> bool:
    """Check if Vertex AI credentials are actually available."""
    # Running on Cloud Run / GCE → metadata server provides creds
    if os.environ.get("K_SERVICE"):
        return True
    # Explicit service account file
    if os.environ.get("GOOGLE_APPLICATION_CREDENTIALS"):
        return True
    return False


def get_backend_mode() -> str:
    """Returns 'vertex_ai', 'gemini_api', or 'none' based on available credentials."""
    api_key = os.environ.get("GOOGLE_API_KEY", "")

    if _can_use_vertex_ai():
        return "vertex_ai"

    if api_key:
        return "gemini_api"

    return "none"


def check_gcp_config() -> dict:
    """Tool function: report GCP configuration status."""
    project = get_project_id()
    mode = get_backend_mode()
    on_gcp = is_running_on_gcp()
    cloud_run_url = get_cloud_run_url()

    services = {
        "firestore": bool(project),
        "vertex_ai": mode == "vertex_ai",
        "logging": on_gcp,
        "cloud_run": on_gcp,
    }

    return {
        "project_id": project or "not set",
        "backend_mode": mode,
        "running_on_gcp": on_gcp,
        "cloud_run_url": cloud_run_url or "not deployed",
        "services_available": services,
        "message": "Google Cloud is fully configured" if on_gcp
        else "Running locally with Gemini API"
        if mode == "gemini_api"
        else "No Google Cloud configuration found",
    }
