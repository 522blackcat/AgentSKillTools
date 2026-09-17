"""应用配置。

生成项目保留轻量配置层，真实生产可替换为 pydantic-settings。
"""

from __future__ import annotations

import os


DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///agent.db")
MODEL_PROVIDER = os.getenv("MODEL_PROVIDER", "stub")
MODEL_ID = os.getenv("MODEL_ID", "stub-chat")
BASE_URL = os.getenv("BASE_URL", "")
API_KEY = os.getenv("API_KEY", "")
APP_ENV = os.getenv("APP_ENV", "local")
