"""
配置管理模块

使用 SQLite3 实现配置持久化，存储服务列表、缓存数据、UI 偏好。
"""

import json
import sqlite3
from collections.abc import Generator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


@dataclass
class ServiceConfig:
    """服务配置数据结构"""

    service_id: str
    plugin_type: str
    alias: str
    enabled: bool
    created_at: str
    updated_at: str


@dataclass
class CachedData:
    """缓存数据结构"""

    service_id: str
    data: dict[str, Any]
    cached_at: str


class ConfigManager:
    """
    配置管理器

    管理应用配置、服务列表和数据缓存。
    使用 SQLite3 进行持久化存储。
    """

    DEFAULT_DB_NAME = "cloudmonitor.db"

    def __init__(self, db_path: Path | None = None) -> None:
        """
        初始化配置管理器

        Args:
            db_path: 数据库文件路径，默认为用户数据目录下的 cloudmonitor.db
        """
        if db_path is None:
            # 使用用户数据目录
            data_dir = Path.home() / ".cloudmonitor"
            data_dir.mkdir(parents=True, exist_ok=True)
            db_path = data_dir / self.DEFAULT_DB_NAME

        self.db_path = db_path
        self._init_database()

    @contextmanager
    def _get_connection(self) -> Generator[sqlite3.Connection]:
        """获取数据库连接的上下文管理器"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _init_database(self) -> None:
        """初始化数据库表结构"""
        with self._get_connection() as conn:
            cursor = conn.cursor()

            # 服务配置表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS services (
                    service_id TEXT PRIMARY KEY,
                    plugin_type TEXT NOT NULL,
                    alias TEXT NOT NULL,
                    enabled INTEGER DEFAULT 1,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)

            # 数据缓存表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS cache (
                    service_id TEXT PRIMARY KEY,
                    data TEXT NOT NULL,
                    cached_at TEXT NOT NULL,
                    FOREIGN KEY (service_id) REFERENCES services(service_id)
                        ON DELETE CASCADE
                )
            """)

            # UI 偏好设置表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS preferences (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                )
            """)

    # ==================== 服务管理 ====================

    def add_service(self, plugin_type: str, alias: str) -> str:
        """
        添加新服务

        Args:
            plugin_type: 插件类型（如 'aws_cost', 'gemini_quota'）
            alias: 用户自定义别名

        Returns:
            str: 生成的服务 ID
        """
        now = datetime.now().isoformat()
        service_id = f"{plugin_type}_{now.replace(':', '-').replace('.', '-')}"

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO services "
                "(service_id, plugin_type, alias, enabled, created_at, updated_at) "
                "VALUES (?, ?, ?, 1, ?, ?)",
                (service_id, plugin_type, alias, now, now),
            )

        return service_id

    def get_service(self, service_id: str) -> ServiceConfig | None:
        """获取服务配置"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM services WHERE service_id = ?", (service_id,))
            row = cursor.fetchone()

            if row:
                return ServiceConfig(
                    service_id=row["service_id"],
                    plugin_type=row["plugin_type"],
                    alias=row["alias"],
                    enabled=bool(row["enabled"]),
                    created_at=row["created_at"],
                    updated_at=row["updated_at"],
                )
            return None

    def get_all_services(self) -> list[ServiceConfig]:
        """获取所有服务配置"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM services ORDER BY created_at")
            rows = cursor.fetchall()

            return [
                ServiceConfig(
                    service_id=row["service_id"],
                    plugin_type=row["plugin_type"],
                    alias=row["alias"],
                    enabled=bool(row["enabled"]),
                    created_at=row["created_at"],
                    updated_at=row["updated_at"],
                )
                for row in rows
            ]

    def get_enabled_services(self) -> list[ServiceConfig]:
        """获取所有启用的服务"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM services WHERE enabled = 1 ORDER BY created_at")
            rows = cursor.fetchall()

            return [
                ServiceConfig(
                    service_id=row["service_id"],
                    plugin_type=row["plugin_type"],
                    alias=row["alias"],
                    enabled=True,
                    created_at=row["created_at"],
                    updated_at=row["updated_at"],
                )
                for row in rows
            ]

    def update_service(
        self,
        service_id: str,
        alias: str | None = None,
        enabled: bool | None = None,
    ) -> bool:
        """
        更新服务配置

        Args:
            service_id: 服务 ID
            alias: 新别名（可选）
            enabled: 新启用状态（可选）

        Returns:
            bool: 是否更新成功
        """
        updates = []
        params: list[Any] = []

        if alias is not None:
            updates.append("alias = ?")
            params.append(alias)

        if enabled is not None:
            updates.append("enabled = ?")
            params.append(1 if enabled else 0)

        if not updates:
            return False

        updates.append("updated_at = ?")
        params.append(datetime.now().isoformat())
        params.append(service_id)

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                f"UPDATE services SET {', '.join(updates)} WHERE service_id = ?",
                params,
            )
            return cursor.rowcount > 0

    def delete_service(self, service_id: str) -> bool:
        """删除服务"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM services WHERE service_id = ?", (service_id,))
            return cursor.rowcount > 0

    # ==================== 缓存管理 ====================

    def set_cache(self, service_id: str, data: dict[str, Any]) -> None:
        """设置缓存数据"""
        now = datetime.now().isoformat()
        json_data = json.dumps(data, ensure_ascii=False)

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT OR REPLACE INTO cache (service_id, data, cached_at)
                VALUES (?, ?, ?)
            """,
                (service_id, json_data, now),
            )

    def get_cache(self, service_id: str) -> CachedData | None:
        """获取缓存数据"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM cache WHERE service_id = ?", (service_id,))
            row = cursor.fetchone()

            if row:
                return CachedData(
                    service_id=row["service_id"],
                    data=json.loads(row["data"]),
                    cached_at=row["cached_at"],
                )
            return None

    def clear_cache(self, service_id: str | None = None) -> int:
        """
        清除缓存

        Args:
            service_id: 指定服务 ID，为 None 时清除所有缓存

        Returns:
            int: 删除的缓存条目数
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            if service_id:
                cursor.execute("DELETE FROM cache WHERE service_id = ?", (service_id,))
            else:
                cursor.execute("DELETE FROM cache")
            return cursor.rowcount

    # ==================== 偏好设置 ====================

    # 定义偏好值类型
    PreferenceValue = str | int | float | bool | list | dict | None

    def set_preference(self, key: str, value: PreferenceValue) -> None:
        """设置偏好"""
        json_value = json.dumps(value, ensure_ascii=False)

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT OR REPLACE INTO preferences (key, value)
                VALUES (?, ?)
            """,
                (key, json_value),
            )

    def get_preference(
        self,
        key: str,
        default: PreferenceValue = None,
    ) -> PreferenceValue:
        """获取偏好"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT value FROM preferences WHERE key = ?", (key,))
            row = cursor.fetchone()

            if row:
                return json.loads(row["value"])
            return default

    def delete_preference(self, key: str) -> bool:
        """删除偏好"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM preferences WHERE key = ?", (key,))
            return cursor.rowcount > 0
