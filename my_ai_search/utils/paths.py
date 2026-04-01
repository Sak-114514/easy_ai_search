import os
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


def get_app_home() -> Path:
    override = os.getenv("OPENSEARCH_HOME")
    if override:
        return Path(override).expanduser().resolve()

    if (REPO_ROOT / "start.sh").exists() and (REPO_ROOT / "api_server").exists():
        return REPO_ROOT

    return (Path.home() / ".opensearch").resolve()


def get_config_file() -> Path:
    override = os.getenv("OPENSEARCH_ENV_FILE")
    if override:
        return Path(override).expanduser().resolve()
    return get_app_home() / ".env"


def get_data_dir() -> Path:
    override = os.getenv("OPENSEARCH_DATA_DIR")
    if override:
        return Path(override).expanduser().resolve()
    return get_app_home() / "data"


def get_logs_dir() -> Path:
    override = os.getenv("OPENSEARCH_LOG_DIR") or os.getenv("LOG_DIR")
    if override:
        return Path(override).expanduser().resolve()
    return get_data_dir() / "logs"


def get_vector_db_dir() -> Path:
    override = os.getenv("CHROMA_PERSIST_DIR")
    if override:
        return Path(override).expanduser().resolve()
    return get_data_dir() / "chroma_db"


def get_cache_db_dir() -> Path:
    override = os.getenv("CACHE_PERSIST_DIR")
    if override:
        return Path(override).expanduser().resolve()
    return get_data_dir() / "chroma_db_cache"


def get_logs_db_path() -> Path:
    db_url = os.getenv("DATABASE_URL")
    if db_url and db_url.startswith("sqlite:///"):
        return Path(db_url.replace("sqlite:///", "", 1)).expanduser().resolve()
    return get_data_dir() / "logs.db"


def resolve_runtime_path(raw_path: str, base_dir: Path) -> str:
    path = Path(raw_path).expanduser()
    if path.is_absolute():
        return str(path.resolve())
    return str((base_dir / path).resolve())


def ensure_runtime_dirs() -> None:
    for path in (get_app_home(), get_data_dir(), get_logs_dir(), get_vector_db_dir(), get_cache_db_dir()):
        path.mkdir(parents=True, exist_ok=True)
