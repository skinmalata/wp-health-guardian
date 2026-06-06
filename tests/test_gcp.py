import os
from agent.tools.gcp_setup import check_gcp_config, get_backend_mode, is_running_on_gcp


def test_check_gcp_config_no_project():
    project = os.environ.pop("GOOGLE_CLOUD_PROJECT", None)
    api_key = os.environ.pop("GOOGLE_API_KEY", None)
    try:
        cfg = check_gcp_config()
        assert cfg["project_id"] == "not set"
        assert cfg["backend_mode"] == "none"
    finally:
        if project is not None:
            os.environ["GOOGLE_CLOUD_PROJECT"] = project
        if api_key is not None:
            os.environ["GOOGLE_API_KEY"] = api_key


def test_get_backend_mode_with_project():
    old_project = os.environ.get("GOOGLE_CLOUD_PROJECT")
    old_adc = os.environ.pop("GOOGLE_APPLICATION_CREDENTIALS", None)
    old_key = os.environ.pop("GOOGLE_API_KEY", None)
    old_service = os.environ.pop("K_SERVICE", None)
    os.environ["GOOGLE_CLOUD_PROJECT"] = "my-project"
    try:
        # Project alone (no Vertex AI creds, no API key) → none
        assert get_backend_mode() == "none"
    finally:
        if old_project is None:
            del os.environ["GOOGLE_CLOUD_PROJECT"]
        else:
            os.environ["GOOGLE_CLOUD_PROJECT"] = old_project
        if old_adc is not None:
            os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = old_adc
        if old_key is not None:
            os.environ["GOOGLE_API_KEY"] = old_key
        if old_service is not None:
            os.environ["K_SERVICE"] = old_service


def test_get_backend_mode_with_api_key():
    old_key = os.environ.get("GOOGLE_API_KEY")
    old_project = os.environ.pop("GOOGLE_CLOUD_PROJECT", None)
    old_adc = os.environ.pop("GOOGLE_APPLICATION_CREDENTIALS", None)
    old_service = os.environ.pop("K_SERVICE", None)
    os.environ["GOOGLE_API_KEY"] = "test-key"
    try:
        assert get_backend_mode() == "gemini_api"
    finally:
        if old_key is None:
            del os.environ["GOOGLE_API_KEY"]
        else:
            os.environ["GOOGLE_API_KEY"] = old_key
        if old_project is not None:
            os.environ["GOOGLE_CLOUD_PROJECT"] = old_project
        if old_adc is not None:
            os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = old_adc
        if old_service is not None:
            os.environ["K_SERVICE"] = old_service


def test_is_running_on_gcp_false():
    old_service = os.environ.pop("K_SERVICE", None)
    old_project = os.environ.pop("GOOGLE_CLOUD_PROJECT", None)
    try:
        assert is_running_on_gcp() is False
    finally:
        if old_service is not None:
            os.environ["K_SERVICE"] = old_service
        if old_project is not None:
            os.environ["GOOGLE_CLOUD_PROJECT"] = old_project


def test_get_backend_mode_vertex_ai_on_cloud_run():
    old_service = os.environ.get("K_SERVICE")
    old_adc = os.environ.pop("GOOGLE_APPLICATION_CREDENTIALS", None)
    os.environ["K_SERVICE"] = "cloud-run-service"
    try:
        assert get_backend_mode() == "vertex_ai"
    finally:
        if old_service is None:
            del os.environ["K_SERVICE"]
        else:
            os.environ["K_SERVICE"] = old_service
        if old_adc is not None:
            os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = old_adc
