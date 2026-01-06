"""
仪表盘页面

显示所有监控服务的状态概览，支持自动刷新、骨架屏加载和离线缓存。
"""

import asyncio
from typing import Any

import flet as ft

from core.cache_mgr import get_cache_manager
from core.event_bus import Event, EventType, get_event_bus
from core.plugin_mgr import PluginManager
from plugins.interface import BaseMonitor
from ui.components.card import EmptyCard, MonitorCard
from ui.components.nav import PageHeader

# 自动刷新间隔选项 (秒)
REFRESH_INTERVALS = [
    (60, "1 分钟"),
    (300, "5 分钟"),
    (600, "10 分钟"),
    (1800, "30 分钟"),
    (0, "关闭"),
]


class DashboardPage(ft.Container):
    """
    仪表盘页面

    展示所有启用的监控服务状态，支持：
    - 骨架屏加载效果
    - SQLite 离线缓存与秒开
    - 自动刷新
    - 并发数据获取
    """

    def __init__(
        self,
        plugin_mgr: PluginManager,
        page: ft.Page,
    ) -> None:
        self.plugin_mgr = plugin_mgr
        self.app_page = page
        self.cards: dict[str, MonitorCard] = {}
        self.monitors: list[BaseMonitor] = []

        # 缓存和事件总线
        self._cache_mgr = get_cache_manager()
        self._event_bus = get_event_bus()

        # 自动刷新配置
        self._auto_refresh_interval: int = 0  # 默认关闭自动刷新
        self._auto_refresh_task: asyncio.Task[Any] | None = None
        self._is_refreshing: bool = False

        super().__init__(
            content=self._build_content(),
            expand=True,
            padding=24,
        )

    def _build_content(self) -> ft.Control:
        """构建页面内容"""
        return ft.Column(
            controls=[
                PageHeader(
                    title="仪表盘",
                    subtitle="监控所有服务状态",
                    actions=self._build_header_actions(),
                ),
                ft.Container(
                    content=self._build_grid(),
                    expand=True,
                ),
            ],
            spacing=0,
            expand=True,
        )

    def _build_header_actions(self) -> list[ft.Control]:
        """构建页头动作按钮"""
        # 刷新间隔选择器
        interval_dropdown = ft.Dropdown(
            label="自动刷新",
            value=str(self._auto_refresh_interval),
            options=[
                ft.dropdown.Option(str(interval), text=label)
                for interval, label in REFRESH_INTERVALS
            ],
            on_select=self._on_interval_change,
            width=130,
            height=45,
            text_size=12,
            border_radius=8,
            content_padding=ft.Padding.symmetric(horizontal=10),
        )

        # 刷新按钮
        refresh_btn = ft.ElevatedButton(
            "刷新全部",
            icon=ft.Icons.REFRESH,
            on_click=self._on_refresh_all,
        )

        return [interval_dropdown, refresh_btn]

    def _build_grid(self) -> ft.Control:
        """构建卡片网格"""
        # 加载所有启用的服务
        self.monitors = self.plugin_mgr.load_enabled_services()

        if not self.monitors:
            return EmptyCard(
                title="暂无监控服务",
                message="请前往设置页面添加服务",
                on_add=self._on_go_to_settings,
            )

        # 加载缓存数据
        cached_results = self._cache_mgr.load_all()

        # 创建卡片，初始显示缓存或骨架屏
        cards = []
        for monitor in self.monitors:
            cached_result = cached_results.get(monitor.service_id)

            card = MonitorCard(
                title=monitor.alias or monitor.display_name,
                icon=monitor.icon,
                icon_path=monitor.icon_path,
                data=cached_result,  # 优先使用缓存
                service_id=monitor.service_id,
                on_refresh=self._on_card_refresh,
                on_edit=self._on_card_edit,
                accent_color=self._get_accent_color(monitor),
                show_skeleton=(cached_result is None),  # 无缓存时显示骨架屏
            )
            self.cards[monitor.service_id] = card
            cards.append(card)

        # 使用响应式网格布局
        return ft.GridView(
            runs_count=3,  # 每行最多 3 个卡片
            max_extent=400,
            child_aspect_ratio=1.2,
            spacing=16,
            run_spacing=16,
            controls=cards,
            expand=True,
        )

    def _get_accent_color(self, monitor: BaseMonitor) -> str:
        """根据插件类型获取强调色"""
        plugin_type = monitor.__class__.__name__.lower()

        if "aws" in plugin_type:
            return ft.Colors.ORANGE
        elif "azure" in plugin_type:
            return ft.Colors.BLUE
        elif "gemini" in plugin_type:
            return ft.Colors.PURPLE
        elif "gcp" in plugin_type:
            return ft.Colors.RED
        elif "digitalocean" in plugin_type:
            return ft.Colors.BLUE_400
        else:
            return ft.Colors.BLUE_400

    async def _refresh_all_async(self) -> None:
        """异步并发刷新所有服务"""
        if self._is_refreshing:
            return

        self._is_refreshing = True

        # 发布刷新开始事件
        await self._event_bus.publish(Event(type=EventType.REFRESH_STARTED))

        # 显示所有卡片的加载状态
        for card in self.cards.values():
            card.show_loading()
        self.app_page.update()

        # 并发刷新所有服务
        tasks = []
        for monitor in self.monitors:
            if monitor.enabled:
                tasks.append(self._refresh_monitor(monitor))

        await asyncio.gather(*tasks)

        self._is_refreshing = False
        self.app_page.update()

        # 发布刷新完成事件
        await self._event_bus.publish(Event(type=EventType.REFRESH_COMPLETED))

    async def _refresh_monitor(self, monitor: BaseMonitor) -> None:
        """刷新单个监控服务并更新缓存"""
        try:
            result = await monitor.refresh()

            # 更新卡片
            if monitor.service_id in self.cards:
                self.cards[monitor.service_id].update_data(result)

            # 更新缓存
            self._cache_mgr.save(monitor.service_id, result)

            # 发布缓存更新事件
            await self._event_bus.publish(
                Event(type=EventType.CACHE_UPDATED, data={"service_id": monitor.service_id})
            )

        except Exception as e:
            print(f"Error refreshing {monitor.service_id}: {e}")
            # 更新卡片为错误状态
            if monitor.service_id in self.cards:
                error_result = monitor._create_error_result(f"刷新失败: {e!s}")
                self.cards[monitor.service_id].update_data(error_result)

            # 发布刷新失败事件
            await self._event_bus.publish(
                Event(
                    type=EventType.REFRESH_FAILED,
                    data={"service_id": monitor.service_id, "error": str(e)},
                )
            )

    async def _auto_refresh_loop(self) -> None:
        """自动刷新循环"""
        while True:
            try:
                # 等待指定间隔
                await asyncio.sleep(self._auto_refresh_interval)

                # 如果间隔为 0，停止自动刷新
                if self._auto_refresh_interval <= 0:
                    break

                # 执行刷新
                await self._refresh_all_async()

            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"Auto refresh error: {e}")

    def _start_auto_refresh(self) -> None:
        """启动自动刷新"""
        self._stop_auto_refresh()

        if self._auto_refresh_interval > 0:
            self._auto_refresh_task = asyncio.create_task(self._auto_refresh_loop())

    def _stop_auto_refresh(self) -> None:
        """停止自动刷新"""
        if self._auto_refresh_task and not self._auto_refresh_task.done():
            self._auto_refresh_task.cancel()
            self._auto_refresh_task = None

    def _on_interval_change(self, e: ft.ControlEvent) -> None:
        """刷新间隔改变事件"""
        try:
            self._auto_refresh_interval = int(e.control.value)
            self._start_auto_refresh()
        except (ValueError, AttributeError):
            pass

    def _on_refresh_all(self, e: ft.ControlEvent) -> None:
        """刷新全部按钮点击事件"""
        self.app_page.run_task(self._refresh_all_async)

    def _on_card_refresh(self, service_id: str) -> None:
        """单个卡片刷新回调"""
        # 找到对应的 monitor
        monitor = next((m for m in self.monitors if m.service_id == service_id), None)
        if monitor:
            # 显示加载状态
            if service_id in self.cards:
                self.cards[service_id].show_loading()
            # 使用 page.run_task 代替 asyncio.create_task
            self.app_page.run_task(self._refresh_monitor, monitor)

    def _on_card_edit(self, service_id: str) -> None:
        """单个卡片编辑回调"""
        # 找到对应的 monitor
        monitor = next((m for m in self.monitors if m.service_id == service_id), None)
        if not monitor:
            return

        # 获取插件信息
        info = self.plugin_mgr.get_plugin_info(monitor.plugin_id)
        if not info:
            return

        # 导入对话框组件
        from ui.components.dialog import CredentialDialog

        # 显示编辑对话框
        dialog = CredentialDialog(
            title=f"编辑 {monitor.alias or monitor.display_name}",
            plugin_type=monitor.plugin_id,
            required_fields=info["required_credentials"],
            on_save=lambda values: self._save_card_edit(service_id, values),
            on_cancel=lambda e: self._close_dialog(e),
            initial_values={"alias": monitor.alias or ""},
            is_edit_mode=True,
        )

        self.app_page.overlay.append(dialog)
        dialog.open = True
        self.app_page.update()

    def _save_card_edit(self, service_id: str, values: dict[str, str]) -> None:
        """保存卡片编辑"""
        from ui.components.dialog import SnackBar

        alias = values.pop("alias", "")

        instance = self.plugin_mgr.update_service_credentials(
            service_id=service_id,
            alias=alias if alias else None,
            credentials=values if values else None,
        )

        if instance:
            SnackBar.show(self.app_page, f"服务 '{alias}' 更新成功")
            self.refresh()
        else:
            SnackBar.show(self.app_page, "更新服务失败", is_error=True)

        self._close_all_dialogs()

    def _close_dialog(self, e: ft.ControlEvent) -> None:
        """关闭对话框"""
        if self.app_page.overlay:
            dialog = self.app_page.overlay[-1]
            if isinstance(dialog, ft.AlertDialog):
                dialog.open = False
                self.app_page.update()

    def _close_all_dialogs(self) -> None:
        """关闭所有对话框"""
        for control in self.app_page.overlay:
            if isinstance(control, ft.AlertDialog):
                control.open = False
        self.app_page.update()

    def _on_go_to_settings(self, e: ft.ControlEvent) -> None:
        """跳转到设置页面"""
        # 通过导航栏切换并模拟导航事件
        if self.app_page.navigation:
            self.app_page.navigation.selected_index = 1
            # 触发导航栏的 on_change 回调
            if self.app_page.navigation.on_change:
                # 创建一个模拟事件对象
                class MockEvent:
                    def __init__(self, control: ft.Control) -> None:
                        self.control = control
                mock_event = MockEvent(self.app_page.navigation)
                self.app_page.navigation.on_change(mock_event)
            else:
                self.app_page.update()

    def refresh(self) -> None:
        """刷新页面内容"""
        # 记录之前已有的服务 ID
        old_service_ids = set(self.cards.keys())
        
        # 重新构建内容
        self.content = self._build_content()
        self.app_page.update()
        
        # 检测新添加的服务（在 _build_grid 中已更新 self.cards）
        new_service_ids = set(self.cards.keys()) - old_service_ids
        
        # 如果有新服务且没有缓存，触发它们的数据刷新
        if new_service_ids:
            self.app_page.run_task(self._refresh_new_services, new_service_ids)

    async def _refresh_new_services(self, service_ids: set[str]) -> None:
        """刷新新添加的服务"""
        for monitor in self.monitors:
            if monitor.service_id in service_ids:
                await self._refresh_monitor(monitor)
        self.app_page.update()

    async def initial_load(self) -> None:
        """
        初始加载数据

        优先从缓存加载（秒开），然后后台静默刷新。
        """
        # 缓存已在 _build_grid 中加载，这里启动后台刷新
        await self._refresh_all_async()
        # 启动自动刷新
        self._start_auto_refresh()

    def dispose(self) -> None:
        """清理资源"""
        self._stop_auto_refresh()
