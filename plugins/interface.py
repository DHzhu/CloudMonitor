"""
插件接口定义模块

定义所有监控插件必须实现的抽象基类 BaseMonitor。
"""

from abc import ABC, abstractmethod
from datetime import datetime
from typing import TYPE_CHECKING

import flet as ft

from core.models import MetricData, MonitorResult

if TYPE_CHECKING:
    pass


# 保留旧的枚举以便向后兼容，但标记为deprecated
# 新代码应使用 core.models 中的 Literal 类型
class MonitorStatus:
    """监控状态常量（已废弃，请使用字符串字面量）"""

    ONLINE = "normal"  # 映射到新的 "normal"
    WARNING = "warning"
    ERROR = "error"
    LOADING = "loading"


class BaseMonitor(ABC):
    """
    监控插件抽象基类

    所有监控插件必须继承此类并实现以下抽象方法：
    - display_name: 返回服务显示名称
    - icon: 返回服务图标
    - required_credentials: 返回所需凭据字段
    - fetch_data: 异步获取监控数据
    - render_card: 渲染 Flet UI 组件

    数据契约：
    - fetch_data 必须返回 core.models.MonitorResult (Pydantic 模型)
    - 插件不再直接返回 UI 控件数据，而是返回标准数据对象
    """

    def __init__(self, service_id: str, alias: str, credentials: dict[str, str]) -> None:
        """
        初始化监控插件

        Args:
            service_id: 服务唯一标识符
            alias: 用户自定义别名
            credentials: 认证凭据字典
        """
        self.service_id = service_id
        self.alias = alias
        self.credentials = credentials
        self._enabled = True
        self._last_result: MonitorResult | None = None

    @property
    @abstractmethod
    def plugin_id(self) -> str:
        """返回插件类型标识符，如 'aws_cost'"""
        ...

    @property
    @abstractmethod
    def display_name(self) -> str:
        """返回服务显示名称，如 'AWS Cost'"""
        ...

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """返回服务提供商名称，如 'AWS'、'Azure'"""
        ...

    @property
    @abstractmethod
    def icon(self) -> str:
        """返回服务图标名称"""
        ...

    @property
    @abstractmethod
    def required_credentials(self) -> list[str]:
        """返回所需的凭据字段列表"""
        ...

    @property
    def enabled(self) -> bool:
        """返回插件是否启用"""
        return self._enabled

    @enabled.setter
    def enabled(self, value: bool) -> None:
        """设置插件启用状态"""
        self._enabled = value

    @property
    def last_result(self) -> MonitorResult | None:
        """返回上次获取的结果"""
        return self._last_result

    @abstractmethod
    async def fetch_data(self) -> MonitorResult:
        """
        异步获取监控数据

        规则:
        1. 必须是 async。
        2. 原生 Async SDK (如 google-genai) -> 直接 await。
        3. 同步 SDK (如 boto3) -> 必须使用 core.thread_utils.run_blocking 包装。

        Returns:
            MonitorResult: 包含指标数据的 Pydantic 模型

        注意: 插件内部必须捕获所有 SDK 异常，异常发生时返回带有 raw_error 的结果
        """
        ...

    @abstractmethod
    def render_card(self, data: MonitorResult) -> ft.Control:
        """
        渲染监控卡片 UI 组件

        Args:
            data: 监控结果数据 (Pydantic 模型)

        Returns:
            ft.Control: Flet UI 控件
        """
        ...

    async def refresh(self) -> MonitorResult:
        """
        刷新数据并缓存结果

        Returns:
            MonitorResult: 最新的监控结果
        """
        self._last_result = await self.fetch_data()
        return self._last_result

    def validate_credentials(self) -> bool:
        """
        验证凭据是否完整

        Returns:
            bool: 凭据是否有效
        """
        return all(key in self.credentials for key in self.required_credentials)

    def _create_error_result(self, error_message: str) -> MonitorResult:
        """
        创建错误结果的辅助方法

        Args:
            error_message: 错误信息

        Returns:
            MonitorResult: 包含错误信息的结果
        """
        return MonitorResult(
            plugin_id=self.plugin_id,
            provider_name=self.provider_name,
            metrics=[
                MetricData(
                    label="错误",
                    value="获取失败",
                    status="error",
                )
            ],
            raw_error=error_message,
            last_updated=datetime.now(),
        )

    def _create_success_result(self, metrics: list[MetricData]) -> MonitorResult:
        """
        创建成功结果的辅助方法

        Args:
            metrics: 指标数据列表

        Returns:
            MonitorResult: 包含指标数据的结果
        """
        return MonitorResult(
            plugin_id=self.plugin_id,
            provider_name=self.provider_name,
            metrics=metrics,
            last_updated=datetime.now(),
        )

    def _format_update_time(self, last_updated: datetime | None) -> str:
        """
        格式化更新时间

        Args:
            last_updated: 最后更新时间

        Returns:
            str: 格式化的时间字符串
        """
        if last_updated is None:
            return "更新于: N/A"
        return f"更新于: {last_updated.strftime('%Y-%m-%d %H:%M:%S')}"

