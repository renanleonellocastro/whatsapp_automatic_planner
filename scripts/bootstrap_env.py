#!/usr/bin/env python3
"""Create the project virtualenv and install dependencies into it.

All installs target the project-local ``.venv`` only — nothing global — which is
the safe, isolated pattern. Run with the system interpreter:

    python3 scripts/bootstrap_env.py

Idempotent: re-running upgrades/installs the pinned set into the existing venv.
"""

from __future__ import annotations

import subprocess
import sys
import venv
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VENV = ROOT / ".venv"

# Runtime + dev dependencies. Pinned loosely now; lock later via requirements.
DEPS = [
    "pydantic>=2,<3",
    "pydantic-settings>=2,<3",
    "httpx>=0.27",
    "jinja2>=3",
    "python-docx>=1.1",
    "reportlab>=4",
    "fastapi>=0.111",
    "uvicorn[standard]>=0.30",
    "openai>=1.40",
    "boto3>=1.34",
    # dev / test
    "pytest>=8",
    "pytest-cov>=5",
    "pytest-asyncio>=0.23",
    "ruff>=0.5",
    "mypy>=1.10",
]


def venv_python(v: Path) -> Path:
    return v / ("Scripts" if sys.platform == "win32" else "bin") / "python"


def main() -> int:
    if not venv_python(VENV).exists():
        print(f"Creating virtualenv at {VENV} ...")
        venv.EnvBuilder(with_pip=True, upgrade_deps=True).create(VENV)
    py = str(venv_python(VENV))
    print("Installing dependencies into the venv ...")
    subprocess.run([py, "-m", "pip", "install", "--upgrade", "pip"], check=True)
    subprocess.run([py, "-m", "pip", "install", *DEPS], check=True)
    print("\nDone. Activate with:  source .venv/bin/activate")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
