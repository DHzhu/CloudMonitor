"""
仪表盘页面

显示所有监控服务的状态概览。
"""

import asyncio

import flet as ft

from core.plugin_mgr import PluginManager
from plugins.interface import BaseMonitor
from ui.components.card import EmptyCard, MonitorCard
from ui.components.nav import PageHeader


class DashboardPage(ft.Container):
    """
    仪表盘页面

    展示所有启用的监控服务状态。
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
                    actions=[
                        ft.ElevatedButton(
                            "刷新全部",
                            icon=ft.Icons.REFRESH,
                            on_click=self._on_refresh_all,
                        ),
                    ],
                ),
                ft.Container(
                    content=self._build_grid(),
                    expand=True,
                ),
            ],
            spacing=0,
            expand=True,
        )

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
        else:
            return ft.Colors.BLUE_400

    async def _refresh_all_async(self) -> None:
        """异步刷新所有服务"""
        tasks = []
        for monitor in self.monitors:
            if monitor.enabled:
                tasks.append(self._refresh_monitor(monitor))

        await asyncio.gather(*tasks)
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
