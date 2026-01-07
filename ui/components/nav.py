"""
导航组件

提供应用导航栏和侧边栏组件。
"""

import flet as ft


class AppNavigationRail(ft.NavigationRail):
    """
    应用侧边导航栏

    提供主要页面的导航功能。
    """

    def __init__(
        self,
        on_change: ft.ControlEvent | None = None,
        selected_index: int = 0,
    ) -> None:
        super().__init__(
            selected_index=selected_index,
            label_type=ft.NavigationRailLabelType.ALL,
            min_width=100,
            min_extended_width=200,
            bgcolor=ft.Colors.with_opacity(0.05, ft.Colors.WHITE),
            leading=ft.Container(
                content=ft.Column(
                    controls=[
                        ft.Image(
                            src="/icon.png",
                            width=48,
                            height=48,
                            fit=ft.ImageFit.CONTAIN,
                        ),
                        ft.Text(
                            "CloudMonitor",
                            size=12,
                            weight=ft.FontWeight.BOLD,
                            color=ft.Colors.WHITE,
                        ),
                    ],
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    spacing=4,
                ),
                padding=ft.Padding.only(top=20, bottom=20),
            ),
            destinations=[
                ft.NavigationRailDestination(
                    icon=ft.Icons.DASHBOARD_OUTLINED,
                    selected_icon=ft.Icons.DASHBOARD,
                    label="仪表盘",
                ),
                ft.NavigationRailDestination(
                    icon=ft.Icons.SETTINGS_OUTLINED,
                    selected_icon=ft.Icons.SETTINGS,
                    label="设置",
                ),
            ],
            on_change=on_change,
        )


class AppBar(ft.AppBar):
    """
    应用顶部栏

    显示页面标题和操作按钮。
    """

    def __init__(
        self,
        title: str = "CloudMonitor Pro",
        on_refresh: ft.ControlEvent | None = None,
    ) -> None:
        super().__init__(
            leading=ft.Icon(ft.Icons.CLOUD, color=ft.Colors.BLUE_400),
            leading_width=40,
            title=ft.Text(
                title,
                size=20,
                weight=ft.FontWeight.BOLD,
                color=ft.Colors.WHITE,
            ),
            center_title=False,
            bgcolor=ft.Colors.with_opacity(0.1, ft.Colors.WHITE),
            actions=[
                ft.IconButton(
                    icon=ft.Icons.REFRESH,
                    icon_color=ft.Colors.WHITE,
                    tooltip="刷新所有",
                    on_click=on_refresh,
                ),
            ],
        )


class PageHeader(ft.Container):
    """
    页面标题组件

    用于页面内部的标题显示。
    """

    def __init__(
        self,
        title: str,
        subtitle: str | None = None,
        actions: list[ft.Control] | None = None,
    ) -> None:
        title_controls = [
            ft.Text(
                title,
                size=24,
                weight=ft.FontWeight.BOLD,
                color=ft.Colors.WHITE,
            ),
        ]

        if subtitle:
            title_controls.append(
                ft.Text(
                    subtitle,
                    size=14,
                    color=ft.Colors.WHITE_54,
                )
            )

        content_controls = [
            ft.Column(
                controls=title_controls,
                spacing=4,
                expand=True,
            ),
        ]

        if actions:
            content_controls.append(
                ft.Row(
                    controls=actions,
                    spacing=8,
                )
            )

        super().__init__(
            content=ft.Row(
                controls=content_controls,
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                vertical_alignment=ft.CrossAxisAlignment.START,
            ),
            padding=ft.Padding.only(bottom=16),
        )
