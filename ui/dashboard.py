"""
仪表盘页面

显示所有监控服务的状态概览，支持自动刷新。
"""

import asyncio
from typing import Any

import flet as ft

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

    展示所有启用的监控服务状态，支持自动刷新。
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

        # 自动刷新配置
        self._auto_refresh_interval: int = 300  # 默认 5 分钟
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
            on_change=self._on_interval_change,
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

        # 创建卡片
        cards = []
        for monitor in self.monitors:
            card = MonitorCard(
                title=monitor.alias or monitor.display_name,
                icon=monitor.icon,
                data=monitor.last_result,
                accent_color=self._get_accent_color(monitor),
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
        elif "zhipu" in plugin_type:
            return ft.Colors.GREEN
        elif "gemini" in plugin_type:
            return ft.Colors.PURPLE
        else:
            return ft.Colors.BLUE_400

    async def _refresh_all_async(self) -> None:
        """异步刷新所有服务"""
        if self._is_refreshing:
            return

        self._is_refreshing = True
        tasks = []
        for monitor in self.monitors:
            if monitor.enabled:
                tasks.append(self._refresh_monitor(monitor))

        await asyncio.gather(*tasks)
        self._is_refreshing = False
        self.app_page.update()

    async def _refresh_monitor(self, monitor: BaseMonitor) -> None:
        """刷新单个监控服务"""
        try:
            result = await monitor.refresh()

            # 更新卡片
            if monitor.service_id in self.cards:
                self.cards[monitor.service_id].update_data(result)

        except Exception as e:
            print(f"Error refreshing {monitor.service_id}: {e}")

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
        asyncio.create_task(self._refresh_all_async())

    def _on_go_to_settings(self, e: ft.ControlEvent) -> None:
        """跳转到设置页面"""
        # 通过导航栏切换
        if self.app_page.navigation:
            self.app_page.navigation.selected_index = 1
            self.app_page.update()

    def refresh(self) -> None:
        """刷新页面内容"""
        self.content = self._build_content()

    async def initial_load(self) -> None:
        """初始加载数据"""
        await self._refresh_all_async()
        # 启动自动刷新
        self._start_auto_refresh()

    def dispose(self) -> None:
        """清理资源"""
        self._stop_auto_refresh()
