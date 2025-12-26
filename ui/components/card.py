"""
监控卡片组件

提供统一的监控数据卡片展示组件。
"""

import flet as ft

from plugins.interface import MonitorResult, MonitorStatus

# 状态颜色映射
STATUS_COLORS = {
    MonitorStatus.ONLINE: ft.Colors.GREEN_400,
    MonitorStatus.WARNING: ft.Colors.AMBER,
    MonitorStatus.ERROR: ft.Colors.RED,
    MonitorStatus.LOADING: ft.Colors.GREY,
}


class MonitorCard(ft.Container):
    """
    监控卡片组件

    用于展示单个监控服务的状态和数据。
    """

    def __init__(
        self,
        title: str,
        icon: str,
        data: MonitorResult | None = None,
        on_refresh: ft.ControlEvent | None = None,
        accent_color: str = ft.Colors.BLUE,
    ) -> None:
        self.title = title
        self.icon_name = icon
        self.data = data
        self.on_refresh_callback = on_refresh
        self.accent_color = accent_color

        super().__init__(
            content=self._build_content(),
            padding=16,
            border_radius=12,
            bgcolor=ft.Colors.with_opacity(0.1, ft.Colors.WHITE),
            border=ft.Border.all(1, ft.Colors.with_opacity(0.2, self._get_status_color())),
            animate=ft.Animation(200, ft.AnimationCurve.EASE_IN_OUT),
        )

    def _get_status_color(self) -> str:
        """获取当前状态对应的颜色"""
        if self.data is None:
            return ft.Colors.GREY
        return STATUS_COLORS.get(self.data.status, ft.Colors.GREY)

    def _build_content(self) -> ft.Control:
        """构建卡片内容"""
        color = self._get_status_color()

        if self.data is None:
            # 加载中状态
            return ft.Column(
                controls=[
                    self._build_header(color),
                    ft.Container(
                        content=ft.ProgressRing(
                            width=30,
                            height=30,
                            stroke_width=3,
                            color=ft.Colors.BLUE_400,
                        ),
                        alignment=ft.Alignment.CENTER,
                        padding=20,
                    ),
                ],
                spacing=8,
            )

        return ft.Column(
            controls=[
                self._build_header(color),
                self._build_kpi(color),
                *self._build_details(),
                *self._build_error(),
                self._build_footer(),
            ],
            spacing=8,
        )

    def _build_header(self, color: str) -> ft.Control:
        """构建标题行"""
        return ft.Row(
            controls=[
                ft.Icon(self.icon_name, color=self.accent_color, size=24),
                ft.Text(
                    self.title,
                    size=16,
                    weight=ft.FontWeight.BOLD,
                    color=ft.Colors.WHITE,
                    expand=True,
                ),
                ft.Icon("circle", color=color, size=10),
            ],
            alignment=ft.MainAxisAlignment.START,
            spacing=8,
        )

    def _build_kpi(self, color: str) -> ft.Control:
        """构建 KPI 显示"""
        if self.data is None:
            return ft.Container()

        return ft.Container(
            content=ft.Column(
                controls=[
                    ft.Text(
                        self.data.kpi.label,
                        size=12,
                        color=ft.Colors.WHITE_70,
                    ),
                    ft.Row(
                        controls=[
                            ft.Text(
                                self.data.kpi.value,
                                size=28,
                                weight=ft.FontWeight.BOLD,
                                color=color,
                            ),
                            ft.Text(
                                self.data.kpi.unit,
                                size=14,
                                color=ft.Colors.WHITE_54,
                            ) if self.data.kpi.unit else ft.Container(),
                        ],
                        spacing=8,
                        vertical_alignment=ft.CrossAxisAlignment.END,
                    ),
                ],
                spacing=2,
            ),
            padding=ft.Padding.symmetric(vertical=10),
        )

    def _build_details(self) -> list[ft.Control]:
        """构建详情列表"""
        if self.data is None or not self.data.details:
            return []

        rows = []
        for detail in self.data.details[:5]:
            # 根据详情类型渲染不同内容
            if "service" in detail:
                # AWS 费用格式
                rows.append(
                    ft.Row(
                        controls=[
                            ft.Text(
                                str(detail.get("service", ""))[:20],
                                size=11,
                                color=ft.Colors.WHITE_70,
                                expand=True,
                            ),
                            ft.Text(
                                f"${detail.get('cost', 0):.2f}",
                                size=11,
                                color=ft.Colors.WHITE,
                            ),
                        ],
                        spacing=8,
                    )
                )
            elif "state" in detail:
                # EC2 实例格式
                state = detail.get("state", "unknown")
                state_color = (
                    ft.Colors.GREEN_400 if state == "running"
                    else ft.Colors.RED_400 if state == "stopped"
                    else ft.Colors.AMBER
                )
                rows.append(
                    ft.Row(
                        controls=[
                            ft.Icon("circle", color=state_color, size=10),
                            ft.Text(
                                str(detail.get("name", ""))[:20],
                                size=11,
                                color=ft.Colors.WHITE,
                                expand=True,
                            ),
                            ft.Text(
                                str(detail.get("type", "")),
                                size=10,
                                color=ft.Colors.WHITE_54,
                            ),
                        ],
                        spacing=8,
                    )
                )
            elif "remaining" in detail:
                # 资源包格式
                usage_percent = detail.get("usage_percent", 0)
                rows.append(
                    ft.Column(
                        controls=[
                            ft.Text(
                                str(detail.get("name", "资源包")),
                                size=12,
                                color=ft.Colors.WHITE_70,
                            ),
                            ft.ProgressBar(
                                value=usage_percent / 100,
                                color=ft.Colors.BLUE_400,
                                bgcolor=ft.Colors.WHITE_10,
                            ),
                            ft.Row(
                                controls=[
                                    ft.Text(
                                        f"剩余: {detail.get('remaining', 0):,}",
                                        size=10,
                                        color=ft.Colors.WHITE_54,
                                    ),
                                ],
                            ),
                        ],
                        spacing=4,
                    )
                )

        return rows

    def _build_error(self) -> list[ft.Control]:
        """构建错误信息"""
        if self.data is None or not self.data.error_message:
            return []

        return [
            ft.Text(
                self.data.error_message,
                size=11,
                color=ft.Colors.RED_300,
                italic=True,
            )
        ]

    def _build_footer(self) -> ft.Control:
        """构建底部更新时间"""
        updated = "N/A"
        if self.data and self.data.last_updated:
            updated = self.data.last_updated[:19]

        return ft.Text(
            f"更新于: {updated}",
            size=10,
            color=ft.Colors.WHITE_38,
        )

    def update_data(self, data: MonitorResult) -> None:
        """更新卡片数据"""
        self.data = data
        self.content = self._build_content()
        self.border = ft.Border.all(1, ft.Colors.with_opacity(0.2, self._get_status_color()))


class LoadingCard(ft.Container):
    """加载中卡片"""

    def __init__(self, title: str = "加载中...") -> None:
        super().__init__(
            content=ft.Column(
                controls=[
                    ft.Row(
                        controls=[
                            ft.Text(
                                title,
                                size=16,
                                weight=ft.FontWeight.BOLD,
                                color=ft.Colors.WHITE,
                            ),
                        ],
                    ),
                    ft.Container(
                        content=ft.ProgressRing(
                            width=30,
                            height=30,
                            stroke_width=3,
                            color=ft.Colors.BLUE_400,
                        ),
                        alignment=ft.Alignment.CENTER,
                        padding=20,
                    ),
                ],
                spacing=8,
            ),
            padding=16,
            border_radius=12,
            bgcolor=ft.Colors.with_opacity(0.1, ft.Colors.WHITE),
            border=ft.Border.all(1, ft.Colors.with_opacity(0.2, ft.Colors.GREY)),
        )


class EmptyCard(ft.Container):
    """空状态卡片"""

    def __init__(
        self,
        title: str = "暂无数据",
        message: str = "请添加服务来开始监控",
        on_add: ft.ControlEvent | None = None,
    ) -> None:
        controls = [
            ft.Icon(ft.Icons.ADD_CIRCLE_OUTLINE, size=48, color=ft.Colors.WHITE_38),
            ft.Text(
                title,
                size=16,
                weight=ft.FontWeight.BOLD,
                color=ft.Colors.WHITE_70,
            ),
            ft.Text(
                message,
                size=12,
                color=ft.Colors.WHITE_38,
                text_align=ft.TextAlign.CENTER,
            ),
        ]

        if on_add:
            controls.append(
                ft.ElevatedButton(
                    "添加服务",
                    icon=ft.Icons.ADD,
                    on_click=on_add,
                )
            )

        super().__init__(
            content=ft.Column(
                controls=controls,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=12,
            ),
            padding=32,
            border_radius=12,
            bgcolor=ft.Colors.with_opacity(0.05, ft.Colors.WHITE),
            border=ft.Border.all(1, ft.Colors.with_opacity(0.1, ft.Colors.WHITE)),
            alignment=ft.Alignment.CENTER,
        )
