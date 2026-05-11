"""Project-wide Jinja2 templates loader."""

from __future__ import annotations

from pathlib import Path

from fastapi.templating import Jinja2Templates

TEMPLATES_DIR: Path = Path(__file__).parent / "templates"
templates: Jinja2Templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
