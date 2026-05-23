import os
from pathlib import Path
from urllib.parse import urlparse, urlunparse

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover
    load_dotenv = None


if load_dotenv is not None:
    repo_env_path = Path(__file__).resolve().parents[3] / ".env"
    load_dotenv(dotenv_path=repo_env_path, override=True)


def _is_truthy(value: str | None) -> bool:
    return (value or "").strip().lower() in {"1", "true", "yes", "on"}


def _clean_env(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned or None


def _running_in_container() -> bool:
    return os.path.exists("/.dockerenv")


def _normalize_base_url(value: str) -> str:
    return value.rstrip("/")


def _derive_base_url_from_completion_endpoint(endpoint: str | None) -> str | None:
    if not endpoint:
        return None

    parsed = urlparse(endpoint)
    if not parsed.scheme or not parsed.netloc:
        return None

    path = parsed.path.rstrip("/")
    suffix = "/chat/completions"
    if path.endswith(suffix):
        path = path[: -len(suffix)]

    return urlunparse((parsed.scheme, parsed.netloc, path or "/v1", "", "", "")).rstrip("/")


def resolve_api_base_url() -> str:
    explicit_local = (
        os.getenv("GRAPH_API_BASE_URL")
        or os.getenv("LOCAL_LLM_BASE_URL")
        or os.getenv("LOCAL_GATEWAY_BASE_URL")
    )
    if explicit_local:
        return _normalize_base_url(explicit_local)

    prefer_local_gateway = _is_truthy(os.getenv("PREFER_LOCAL_GATEWAY"))
    completion_endpoint = os.getenv("COMPL_ENDPOINT")

    if prefer_local_gateway:
        derived_base_url = _derive_base_url_from_completion_endpoint(completion_endpoint)
        if _running_in_container():
            if derived_base_url and "upstream-service" in derived_base_url:
                return derived_base_url
            return "http://upstream-service:18080/v1"
        return "http://127.0.0.1:8000/v1"

    return _normalize_base_url(
        os.getenv(
            "API_BASE_URL",
            "https://open.bigmodel.cn/api/paas/v4/",
        )
    )


class Settings:
    def __init__(self) -> None:
        self.api_interface = _clean_env(os.getenv("API_INTERFACE")) or "openai_compatible"
        self.api_base_url = resolve_api_base_url()
        self.api_key = (
            _clean_env(os.getenv("API_KEY"))
            or _clean_env(os.getenv("LLM_API_KEY"))
            or _clean_env(os.getenv("OPENAI_API_KEY"))
            or "EMPTY"
        )
        self.default_model = _clean_env(os.getenv("DEFAULT_MODEL"))
        self.request_timeout = float(os.getenv("API_TIMEOUT", "60"))
        self.mcp_enabled = _is_truthy(os.getenv("MCP_ENABLED"))
        self.mcp_server_url = _clean_env(os.getenv("MCP_SERVER_URL"))
        self.mcp_tool_cache_ttl_seconds = float(os.getenv("MCP_TOOL_CACHE_TTL_SECONDS", "60"))
        self.mcp_request_timeout_seconds = float(os.getenv("MCP_REQUEST_TIMEOUT_SECONDS", "10"))
        self.mcp_tool_max_concurrency = int(os.getenv("MCP_TOOL_MAX_CONCURRENCY", "5"))
        self.mcp_tool_call_timeout_seconds = float(os.getenv("MCP_TOOL_CALL_TIMEOUT_SECONDS", "30"))
        self.default_system_prompt = os.getenv(
            "DEFAULT_SYSTEM_PROMPT",
            "你是一个脾气暴躁的赛博朋克黑客，回答问题必须以 '[Cyber Hack]' 开头，并且语气非常高冷、精简。",
        )

        if not self.default_model:
            raise ValueError("Missing required environment variable: DEFAULT_MODEL")

    @property
    def supports_openai_compatible(self) -> bool:
        return self.api_interface == "openai_compatible"


settings = Settings()
