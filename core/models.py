"""
数据模型定义模块

使用 Pydantic 定义标准数据契约，确保插件与 UI 解耦。
"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class MetricData(BaseModel):
    """单个指标数据"""

    label: str = Field(..., description="指标标签，如 '本月费用'")
    value: str = Field(..., description="指标值，如 '$12.50'")
    unit: str | None = Field(default=None, description="单位，如 'USD'、'个'")
    status: Literal["normal", "warning", "error"] = Field(
        default="normal", description="状态：normal/warning/error"
    )
    trend: Literal["up", "down", "flat"] | None = Field(
        default=None, description="趋势：up/down/flat"
    )


class MonitorResult(BaseModel):
    """插件返回结果包"""

    plugin_id: str = Field(..., description="插件唯一标识符")
    provider_name: str = Field(..., description="服务提供商名称，如 'AWS'、'Azure'")
    metrics: list[MetricData] = Field(default_factory=list, description="指标数据列表")
    raw_error: str | None = Field(default=None, description="错误信息，仅在出错时填充")
    last_updated: datetime | None = Field(default=None, description="最后更新时间")

    @property
    def has_error(self) -> bool:
        """是否存在错误"""
        return self.raw_error is not None

    @property
    def overall_status(self) -> Literal["normal", "warning", "error"]:
        """获取整体状态，优先返回最严重的状态"""
        if self.has_error:
            return "error"

        status_priority = {"error": 2, "warning": 1, "normal": 0}
        max_status = "normal"
        for metric in self.metrics:
            if status_priority.get(metric.status, 0) > status_priority.get(max_status, 0):
                max_status = metric.status
        return max_status


class CachedResult(BaseModel):
    """缓存的监控结果，用于 SQLite 持久化"""

    service_id: str = Field(..., description="服务唯一标识符")
    plugin_id: str = Field(..., description="插件类型标识符")
    result_json: str = Field(..., description="MonitorResult 的 JSON 序列化")
    cached_at: datetime = Field(default_factory=datetime.now, description="缓存时间")
