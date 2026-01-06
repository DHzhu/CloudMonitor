"""
CloudMonitor Pro - 应用入口

多云平台与大模型服务监控桌面应用。
"""

import io
import os
import sys

# 修复 Windows 打包后 console=False 导致 sys.stdout/stderr 为 None 的问题
# 这会导致 uvicorn/logging 模块调用 isatty() 时报错
if sys.stdout is None:
    sys.stdout = io.StringIO()
if sys.stderr is None:
    sys.stderr = io.StringIO()

# 禁用不必要的日志输出
os.environ.setdefault("FLET_LOG_LEVEL", "warning")

import asyncio

import flet as ft

from core.config_mgr import ConfigManager
from core.plugin_mgr import PluginManager
from core.security import SecurityManager
from ui.components.nav import AppNavigationRail
from ui.dashboard import DashboardPage
from ui.settings import SettingsPage


class CloudMonitorApp:
    """
    CloudMonitor 主应用类

    管理应用生命周期和页面路由。
    """

    def __init__(self, page: ft.Page) -> None:
        self.page = page
        self._setup_page()
        self._init_managers()
        self._build_ui()

    def _setup_page(self) -> None:
        """配置页面属性"""
        self.page.title = "CloudMonitor Pro"
        self.page.theme_mode = ft.ThemeMode.DARK
        self.page.padding = 0
        self.page.spacing = 0
        self.page.bgcolor = ft.Colors.SURFACE

        # Material 3 主题配置
        self.page.theme = ft.Theme(
            color_scheme_seed=ft.Colors.BLUE,
            use_material3=True,
        )

        # 窗口配置
        self.page.window.width = 1280
        self.page.window.height = 800
        self.page.window.min_width = 800
        self.page.window.min_height = 600
        self.page.window.center()

    def _init_managers(self) -> None:
        """初始化管理器"""
        self.config_mgr = ConfigManager()
        self.security_mgr = SecurityManager()
        self.plugin_mgr = PluginManager(
            config_mgr=self.config_mgr,
            security_mgr=self.security_mgr,
        )

        # 发现并加载插件
        self.plugin_mgr.discover_plugins()

    def _build_ui(self) -> None:
        """构建主界面"""
        # 创建页面
        self.dashboard_page = DashboardPage(
            plugin_mgr=self.plugin_mgr,
            page=self.page,
        )

        self.settings_page = SettingsPage(
            plugin_mgr=self.plugin_mgr,
            config_mgr=self.config_mgr,
            security_mgr=self.security_mgr,
            page=self.page,
        )

        # 页面容器
        self.content_area = ft.Container(
            content=self.dashboard_page,
            expand=True,
        )

        # 导航栏
        self.nav_rail = AppNavigationRail(
            on_change=self._on_nav_change,
            selected_index=0,
        )
        self.page.navigation = self.nav_rail

        # 主布局
        self.page.add(
            ft.Row(
                controls=[
                    self.nav_rail,
                    ft.VerticalDivider(width=1, color=ft.Colors.with_opacity(0.1, ft.Colors.WHITE)),
                    self.content_area,
                ],
                expand=True,
                spacing=0,
            )
        )

        # 初始加载数据
        self.page.run_task(self._initial_load)

    async def _initial_load(self) -> None:
        """初始加载数据"""
        await self.dashboard_page.initial_load()

    def _on_nav_change(self, e: ft.ControlEvent) -> None:
        """导航变更事件"""
        index = e.control.selected_index

        if index == 0:
            self.dashboard_page.refresh()
            self.content_area.content = self.dashboard_page
        elif index == 1:
            self.settings_page.refresh()
            self.content_area.content = self.settings_page

        self.page.update()


def main(page: ft.Page) -> None:
    """应用入口函数"""
    CloudMonitorApp(page)


if __name__ == "__main__":
    # 检测是否为打包环境
    is_frozen = getattr(sys, 'frozen', False)

    if is_frozen:
        # 打包后使用原生窗口模式
        ft.run(main, assets_dir="assets")
    else:
        # 开发环境：可选择 Web 模式方便调试
        # 如需原生窗口，改为: ft.run(main)
        ft.run(main, view=ft.AppView.WEB_BROWSER, port=8550, assets_dir="assets")
