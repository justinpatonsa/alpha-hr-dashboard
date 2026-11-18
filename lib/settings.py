"""App settings: Streamlit secrets first, then environment variables, then an optional .env file.

On Streamlit Community Cloud every value comes from the app's Secrets (App settings → Secrets).
For local runs use .streamlit/secrets.toml (gitignored) or environment variables; ALPHA_ENV_FILE
may point at a KEY=value file. Nothing here is ever written to the repo.
"""
import os
from pathlib import Path

import streamlit as st


def _env_file() -> dict:
    path = os.environ.get("ALPHA_ENV_FILE")
    values = {}
    if path and Path(path).is_file():
        for line in Path(path).read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def get(name: str, default: str | None = None) -> str | None:
    try:
        if name in st.secrets and str(st.secrets[name]).strip():
            return str(st.secrets[name]).strip()
    except Exception:  # no secrets file at all
        pass
    if os.environ.get(name, "").strip():
        return os.environ[name].strip()
    return _env_file().get(name) or default
