"""Application configuration module.

Loads environment variables using python-dotenv with safe fallback defaults
for local development.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Project paths
BASE_DIR = Path(__file__).resolve().parent.parent

# Load local .env if present (never committed to version control)
load_dotenv(BASE_DIR / ".env")

# Database configuration
DEFAULT_DATABASE_URL = "postgresql://picketiq:picketiq@localhost:5432/picketiq"
DATABASE_URL: str = os.getenv("DATABASE_URL", DEFAULT_DATABASE_URL)

# LLM configuration
LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "mock").lower()
LLM_API_KEY: str = os.getenv("LLM_API_KEY", "")
LLM_MODEL: str = os.getenv("LLM_MODEL", "gpt-4o-mini")
LLM_BASE_URL: str = os.getenv("LLM_BASE_URL", "https://api.openai.com/v1")
LLM_TEMPERATURE: float = float(os.getenv("LLM_TEMPERATURE", "0.0"))

