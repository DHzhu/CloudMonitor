"""
pytest 配置文件

提供测试 fixtures 和共享配置。
"""

import tempfile
from collections.abc import Generator
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from core.config_mgr import ConfigManager
from core.security import SecurityManager


@pytest.fixture
def temp_db_path() -> Generator[Path]:
    """创建临时数据库路径"""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        path = Path(f.name)
    yield path
    # 清理
    if path.exists():
        path.unlink()


@pytest.fixture
def config_mgr(temp_db_path: Path) -> ConfigManager:
    """创建临时配置管理器实例"""
    return ConfigManager(db_path=temp_db_path)


@pytest.fixture
def mock_keyring() -> Generator[MagicMock]:
    """Mock keyring 模块"""
    storage: dict[str, str] = {}

    def mock_set_password(service: str, key: str, value: str) -> None:
        storage[f"{service}:{key}"] = value

    def mock_get_password(service: str, key: str) -> str | None:
        return storage.get(f"{service}:{key}")

    def mock_delete_password(service: str, key: str) -> None:
        full_key = f"{service}:{key}"
        if full_key in storage:
            del storage[full_key]

    with patch("core.security.keyring") as mock:
        mock.set_password = mock_set_password
        mock.get_password = mock_get_password
        mock.delete_password = mock_delete_password
        yield mock


@pytest.fixture
def security_mgr(mock_keyring: MagicMock) -> SecurityManager:
    """创建带 Mock keyring 的安全管理器实例"""
    return SecurityManager()
