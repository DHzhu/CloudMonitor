"""
事件总线模块

提供简单的 Pub/Sub 事件机制，用于组件间通信。
"""

import asyncio
from collections.abc import Callable, Coroutine
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class EventType(Enum):
    """事件类型枚举"""

    # 数据刷新事件
    REFRESH_STARTED = "refresh_started"
    REFRESH_COMPLETED = "refresh_completed"
    REFRESH_FAILED = "refresh_failed"

    # 服务相关事件
    SERVICE_ADDED = "service_added"
    SERVICE_REMOVED = "service_removed"
    SERVICE_UPDATED = "service_updated"

    # 缓存事件
    CACHE_UPDATED = "cache_updated"
    CACHE_CLEARED = "cache_cleared"

    # 设置事件
    SETTINGS_CHANGED = "settings_changed"


@dataclass
class Event:
    """事件数据结构"""

    type: EventType
    data: Any = None
    source: str | None = None
    timestamp: float = field(default_factory=lambda: asyncio.get_event_loop().time())


# 同步回调类型
SyncCallback = Callable[[Event], None]
# 异步回调类型
AsyncCallback = Callable[[Event], Coroutine[Any, Any, None]]
# 通用回调类型
Callback = SyncCallback | AsyncCallback


class EventBus:
    """
    简单的事件总线

    支持同步和异步回调，提供发布/订阅机制。

    用法:
        bus = EventBus()

        # 订阅事件
        def on_refresh(event: Event):
            print(f"Refresh started: {event.data}")

        bus.subscribe(EventType.REFRESH_STARTED, on_refresh)

        # 发布事件
        await bus.publish(Event(type=EventType.REFRESH_STARTED, data={"service_id": "aws_1"}))

        # 取消订阅
        bus.unsubscribe(EventType.REFRESH_STARTED, on_refresh)
    """

    _instance: "EventBus | None" = None

    def __new__(cls) -> "EventBus":
        """单例模式"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._subscribers: dict[EventType, list[Callback]] = {}
        return cls._instance

    @classmethod
    def get_instance(cls) -> "EventBus":
        """获取单例实例"""
        return cls()

    @classmethod
    def reset(cls) -> None:
        """重置单例（用于测试）"""
        cls._instance = None

    def subscribe(self, event_type: EventType, callback: Callback) -> None:
        """
        订阅事件

        Args:
            event_type: 事件类型
            callback: 回调函数（可以是同步或异步函数）
        """
        if event_type not in self._subscribers:
            self._subscribers[event_type] = []

        if callback not in self._subscribers[event_type]:
            self._subscribers[event_type].append(callback)

    def unsubscribe(self, event_type: EventType, callback: Callback) -> None:
        """
        取消订阅

        Args:
            event_type: 事件类型
            callback: 要移除的回调函数
        """
        if event_type in self._subscribers:
            try:
                self._subscribers[event_type].remove(callback)
            except ValueError:
                pass  # 回调不存在，忽略

    def unsubscribe_all(self, event_type: EventType | None = None) -> None:
        """
        取消所有订阅

        Args:
            event_type: 可选，指定事件类型。如果为 None，取消所有订阅
        """
        if event_type is None:
            self._subscribers.clear()
        elif event_type in self._subscribers:
            self._subscribers[event_type].clear()

    async def publish(self, event: Event) -> None:
        """
        发布事件（异步）

        按顺序调用所有订阅者的回调函数。

        Args:
            event: 事件对象
        """
        callbacks = self._subscribers.get(event.type, [])

        for callback in callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(event)
                else:
                    callback(event)
            except Exception as e:
                # 回调异常不应中断其他回调
                print(f"EventBus callback error for {event.type}: {e}")

    def publish_sync(self, event: Event) -> None:
        """
        同步发布事件

        仅调用同步回调。用于在非异步上下文中发布事件。

        Args:
            event: 事件对象
        """
        callbacks = self._subscribers.get(event.type, [])

        for callback in callbacks:
            if not asyncio.iscoroutinefunction(callback):
                try:
                    callback(event)
                except Exception as e:
                    print(f"EventBus sync callback error for {event.type}: {e}")

    def has_subscribers(self, event_type: EventType) -> bool:
        """
        检查是否有订阅者

        Args:
            event_type: 事件类型

        Returns:
            bool: 是否有订阅者
        """
        return bool(self._subscribers.get(event_type))

    def subscriber_count(self, event_type: EventType) -> int:
        """
        获取订阅者数量

        Args:
            event_type: 事件类型

        Returns:
            int: 订阅者数量
        """
        return len(self._subscribers.get(event_type, []))


# 便捷函数
def get_event_bus() -> EventBus:
    """获取全局事件总线实例"""
    return EventBus.get_instance()
