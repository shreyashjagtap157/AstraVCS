"""Canonical product-version lookup shared by runtime surfaces."""
from pathlib import Path

def product_version() -> str:
    path=Path(__file__).resolve().parents[1]/'VERSION'
    try:return path.read_text(encoding='utf-8').strip()
    except OSError:return 'development'
