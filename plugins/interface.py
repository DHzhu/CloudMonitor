"""
插件接口定义模块

定义所有监控插件必须实现的抽象基类 BaseMonitor。
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Any

import flet as ft


class MonitorStatus(Enum):
    """监控状态枚举"""

    ONLINE = "online"
    WARNING = "warning"
    ERROR = "error"
    LOADING = "loading"


@dataclass
class KPIData:
    """KPI 数据结构"""

    label: str
    value: str
    unit: str = ""
    status: MonitorStatus = MonitorStatus.ONLINE


@dataclass
class MonitorResult:
    """监控结果数据结构"""

    status: MonitorStatus
    kpi: KPIData
    details: list[dict[str, Any]]
    error_message: str | None = None
    last_updated: str | None = None


class BaseMonitor(ABC):
    """
    监控插件抽象基类

    所有监控插件必须继承此类并实现以下抽象方法：
    - display_name: 返回服务显示名称
    - fetch_data: 异步获取监控数据
    - render_card: 渲染 Flet UI 组件
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
    def display_name(self) -> str:
        """返回服务显示名称，如 'AWS EC2'"""
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

        Returns:
            MonitorResult: 包含状态、KPI 和详细信息的结果对象

        Raises:
            Exception: 获取数据失败时抛出异常
        """
        ...

    @abstractmethod
    def render_card(self, data: MonitorResult) -> ft.Control:
        """
        渲染监控卡片 UI 组件

        Args:
            data: 监控结果数据

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
