"""
SQLite 缓存管理模块

提供监控结果的本地持久化缓存，支持秒开体验。
"""

import sqlite3
from collections.abc import Generator
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

from core.models import CachedResult, MonitorResult


class CacheManager:
    """
    缓存管理器

    使用 SQLite 持久化存储监控结果，支持：
    - 应用启动时快速加载缓存数据
    - 后台静默刷新后更新缓存
    - 自动清理过期缓存
    """

    def __init__(self, db_path: str | None = None) -> None:
        """
        初始化缓存管理器

        Args:
            db_path: 数据库文件路径，默认为用户数据目录
        """
        if db_path is None:
            # 默认使用用户数据目录
            data_dir = Path.home() / ".cloudmonitor"
            data_dir.mkdir(parents=True, exist_ok=True)
            db_path = str(data_dir / "cache.db")

        self.db_path = db_path
        self._init_db()

    def _init_db(self) -> None:
        """初始化数据库表"""
        with self._get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS monitor_cache (
                    service_id TEXT PRIMARY KEY,
                    plugin_id TEXT NOT NULL,
                    result_json TEXT NOT NULL,
                    cached_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_cached_at ON monitor_cache(cached_at)
            """)
            conn.commit()

    @contextmanager
    def _get_connection(self) -> Generator[sqlite3.Connection]:
        """获取数据库连接"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    def save(self, service_id: str, result: MonitorResult) -> None:
        """
        保存监控结果到缓存

        Args:
            service_id: 服务唯一标识符
            result: 监控结果
        """
        result_json = result.model_dump_json()

        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO monitor_cache (service_id, plugin_id, result_json, cached_at)
                VALUES (?, ?, ?, ?)
                """,
                (service_id, result.plugin_id, result_json, datetime.now().isoformat()),
            )
            conn.commit()

    def load(self, service_id: str) -> MonitorResult | None:
        """
        从缓存加载监控结果

        Args:
            service_id: 服务唯一标识符

        Returns:
            MonitorResult 或 None（如果不存在或解析失败）
        """
        with self._get_connection() as conn:
            cursor = conn.execute(
                "SELECT result_json FROM monitor_cache WHERE service_id = ?",
                (service_id,),
            )
            row = cursor.fetchone()

            if row is None:
                return None

            try:
                return MonitorResult.model_validate_json(row["result_json"])
            except Exception:
                # 缓存数据格式错误，删除并返回 None
                self.delete(service_id)
                return None

    def load_all(self) -> dict[str, MonitorResult]:
        """
        加载所有缓存的监控结果

        Returns:
            dict[str, MonitorResult]: 服务 ID 到结果的映射
        """
        results = {}

        with self._get_connection() as conn:
            cursor = conn.execute("SELECT service_id, result_json FROM monitor_cache")

            for row in cursor:
                try:
                    result = MonitorResult.model_validate_json(row["result_json"])
                    results[row["service_id"]] = result
                except Exception:
                    # 跳过无效缓存
                    continue

        return results

    def delete(self, service_id: str) -> bool:
        """
        删除指定服务的缓存

        Args:
            service_id: 服务唯一标识符

        Returns:
            bool: 是否成功删除
        """
        with self._get_connection() as conn:
            cursor = conn.execute(
                "DELETE FROM monitor_cache WHERE service_id = ?",
                (service_id,),
            )
            conn.commit()
            return cursor.rowcount > 0

    def clear_all(self) -> int:
        """
        清空所有缓存

        Returns:
            int: 删除的记录数
        """
        with self._get_connection() as conn:
            cursor = conn.execute("DELETE FROM monitor_cache")
            conn.commit()
            return cursor.rowcount

    def clear_expired(self, max_age_hours: int = 24) -> int:
        """
        清理过期缓存

        Args:
            max_age_hours: 最大缓存时间（小时）

        Returns:
            int: 删除的记录数
        """
        with self._get_connection() as conn:
            cursor = conn.execute(
                """
                DELETE FROM monitor_cache
                WHERE cached_at < datetime('now', ?)
                """,
                (f"-{max_age_hours} hours",),
            )
            conn.commit()
            return cursor.rowcount

    def get_cache_info(self, service_id: str) -> CachedResult | None:
        """
        获取缓存元信息

        Args:
            service_id: 服务唯一标识符

        Returns:
            CachedResult 或 None
        """
        with self._get_connection() as conn:
            sql = """
                SELECT service_id, plugin_id, result_json, cached_at
                FROM monitor_cache WHERE service_id = ?
            """
            cursor = conn.execute(sql, (service_id,))
            row = cursor.fetchone()

            if row is None:
                return None

            return CachedResult(
                service_id=row["service_id"],
                plugin_id=row["plugin_id"],
                result_json=row["result_json"],
                cached_at=datetime.fromisoformat(row["cached_at"]),
            )

    def has_cache(self, service_id: str) -> bool:
        """
        检查是否存在缓存

        Args:
            service_id: 服务唯一标识符

        Returns:
            bool: 是否存在缓存
        """
        with self._get_connection() as conn:
            cursor = conn.execute(
                "SELECT 1 FROM monitor_cache WHERE service_id = ? LIMIT 1",
                (service_id,),
            )
            return cursor.fetchone() is not None


# 全局缓存管理器实例
_cache_manager: CacheManager | None = None


def get_cache_manager() -> CacheManager:
    """获取全局缓存管理器实例"""
    global _cache_manager
    if _cache_manager is None:
        _cache_manager = CacheManager()
    return _cache_manager
