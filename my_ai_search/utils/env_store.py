import os
from pathlib import Path

from my_ai_search.utils.paths import get_config_file


def persist_env_values(values: dict[str, object]) -> Path:
    env_file = get_config_file()
    env_file.parent.mkdir(parents=True, exist_ok=True)

    lines = env_file.read_text(encoding="utf-8").splitlines() if env_file.exists() else []

    remaining = {key: _stringify_env_value(value) for key, value in values.items()}
    updated_lines = []

    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in line:
            updated_lines.append(line)
            continue

        key, _ = line.split("=", 1)
        key = key.strip()
        if key in remaining:
            updated_lines.append(f"{key}={remaining.pop(key)}")
        else:
            updated_lines.append(line)

    if remaining:
        if updated_lines and updated_lines[-1].strip():
            updated_lines.append("")
        for key, value in remaining.items():
            updated_lines.append(f"{key}={value}")

    env_file.write_text("\n".join(updated_lines).rstrip() + "\n", encoding="utf-8")

    for key, value in values.items():
        os.environ[key] = _stringify_env_value(value)

    return env_file


def _stringify_env_value(value: object) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)
