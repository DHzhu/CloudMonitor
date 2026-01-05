"""
监控卡片组件

提供统一的监控数据卡片展示组件，支持骨架屏加载效果。
"""

import flet as ft

from core.models import MonitorResult

# 状态颜色映射
STATUS_COLORS = {
    "normal": ft.Colors.GREEN_400,
    "warning": ft.Colors.AMBER,
    "error": ft.Colors.RED,
}


class SkeletonCard(ft.Container):
    """
    骨架屏卡片

    在数据加载时显示的占位卡片，模拟内容布局。
    """

    def __init__(self, accent_color: str = ft.Colors.BLUE) -> None:
        super().__init__(
            content=ft.Column(
                controls=[
                    # 标题骨架
                    ft.Row(
                        controls=[
                            ft.Container(
                                width=24,
                                height=24,
                                border_radius=4,
                                bgcolor=ft.Colors.with_opacity(0.1, ft.Colors.WHITE),
                            ),
                            ft.Container(
                                width=120,
                                height=16,
                                border_radius=4,
                                bgcolor=ft.Colors.with_opacity(0.1, ft.Colors.WHITE),
                            ),
                        ],
                        spacing=8,
                    ),
                    # KPI 骨架
                    ft.Container(
                        content=ft.Column(
                            controls=[
                                ft.Container(
                                    width=80,
                                    height=12,
                                    border_radius=4,
                                    bgcolor=ft.Colors.with_opacity(0.05, ft.Colors.WHITE),
                                ),
                                ft.Container(
                                    width=100,
                                    height=28,
                                    border_radius=4,
                                    bgcolor=ft.Colors.with_opacity(0.1, ft.Colors.WHITE),
                                ),
                            ],
                            spacing=4,
                        ),
                        padding=ft.Padding.symmetric(vertical=10),
                    ),
                    # 详情骨架行
                    *[
                        ft.Row(
                            controls=[
                                ft.Container(
                                    width=100,
                                    height=11,
                                    border_radius=3,
                                    bgcolor=ft.Colors.with_opacity(0.05, ft.Colors.WHITE),
                                    expand=True,
                                ),
                                ft.Container(
                                    width=50,
                                    height=11,
                                    border_radius=3,
                                    bgcolor=ft.Colors.with_opacity(0.05, ft.Colors.WHITE),
                                ),
                            ],
                            spacing=8,
                        )
                        for _ in range(3)
                    ],
                    # 底部骨架
                    ft.Container(
                        width=100,
                        height=10,
                        border_radius=3,
                        bgcolor=ft.Colors.with_opacity(0.03, ft.Colors.WHITE),
                    ),
                ],
                spacing=8,
            ),
            padding=16,
            border_radius=12,
            bgcolor=ft.Colors.with_opacity(0.1, ft.Colors.WHITE),
            border=ft.Border.all(1, ft.Colors.with_opacity(0.1, accent_color)),
            animate=ft.Animation(300, ft.AnimationCurve.EASE_IN_OUT),
        )


class MonitorCard(ft.Container):
    """
    监控卡片组件

    用于展示单个监控服务的状态和数据。
    支持 Pydantic MonitorResult 模型。
    """

    def __init__(
        self,
        title: str,
        icon: str,
        data: MonitorResult | None = None,
        on_refresh: ft.ControlEvent | None = None,
        accent_color: str = ft.Colors.BLUE,
        show_skeleton: bool = False,
    ) -> None:
        self.title = title
        self.icon_name = icon
        # 将图标名称转换为 ft.Icons 常量
        self._icon_value = getattr(ft.Icons, icon.upper(), ft.Icons.CLOUD)
        self.data = data
        self.on_refresh_callback = on_refresh
        self.accent_color = accent_color
        self._show_skeleton = show_skeleton

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
        return STATUS_COLORS.get(self.data.overall_status, ft.Colors.GREY)

    def _build_content(self) -> ft.Control:
        """构建卡片内容"""
        # 显示骨架屏
        if self._show_skeleton or self.data is None:
            return self._build_skeleton_content()

        color = self._get_status_color()

        return ft.Column(
            controls=[
                self._build_header(color),
                self._build_kpi(color),
                *self._build_metrics(),
                *self._build_error(),
                self._build_footer(),
            ],
            spacing=8,
        )

    def _build_skeleton_content(self) -> ft.Control:
        """构建骨架屏内容"""
        return ft.Column(
            controls=[
                # 标题骨架
                ft.Row(
                    controls=[
                        ft.Container(
                            content=ft.Icon(self._icon_value, color=self.accent_color, size=24),
                        ),
                        ft.Text(
                            self.title,
                            size=16,
                            weight=ft.FontWeight.BOLD,
                            color=ft.Colors.WHITE,
                            expand=True,
                        ),
                        ft.ProgressRing(
                            width=16, height=16, stroke_width=2, color=self.accent_color
                        ),
                    ],
                    spacing=8,
                ),
                # 加载中提示
                ft.Container(
                    content=ft.Column(
                        controls=[
                            ft.Container(
                                width=80,
                                height=12,
                                border_radius=4,
                                bgcolor=ft.Colors.with_opacity(0.05, ft.Colors.WHITE),
                            ),
                            ft.Container(
                                width=100,
                                height=28,
                                border_radius=4,
                                bgcolor=ft.Colors.with_opacity(0.1, ft.Colors.WHITE),
                            ),
                        ],
                        spacing=4,
                    ),
                    padding=ft.Padding.symmetric(vertical=10),
                ),
                # 骨架行
                *[
                    ft.Row(
                        controls=[
                            ft.Container(
                                width=100,
                                height=11,
                                border_radius=3,
                                bgcolor=ft.Colors.with_opacity(0.05, ft.Colors.WHITE),
                                expand=True,
                            ),
                            ft.Container(
                                width=50,
                                height=11,
                                border_radius=3,
                                bgcolor=ft.Colors.with_opacity(0.05, ft.Colors.WHITE),
                            ),
                        ],
                        spacing=8,
                    )
                    for _ in range(3)
                ],
            ],
            spacing=8,
        )

    def _build_header(self, color: str) -> ft.Control:
        """构建标题行"""
        return ft.Row(
            controls=[
                ft.Icon(self._icon_value, color=self.accent_color, size=24),
                ft.Text(
                    self.title,
                    size=16,
                    weight=ft.FontWeight.BOLD,
                    color=ft.Colors.WHITE,
                    expand=True,
                ),
                ft.Icon(ft.Icons.CIRCLE, color=color, size=10),
            ],
            alignment=ft.MainAxisAlignment.START,
            spacing=8,
        )

    def _build_kpi(self, color: str) -> ft.Control:
        """构建主 KPI 显示"""
        if self.data is None or not self.data.metrics:
            return ft.Container()

        main_metric = self.data.metrics[0]

        return ft.Container(
            content=ft.Column(
                controls=[
                    ft.Text(
                        main_metric.label,
                        size=12,
                        color=ft.Colors.WHITE_70,
                    ),
                    ft.Row(
                        controls=[
                            ft.Text(
                                main_metric.value,
                                size=28,
                                weight=ft.FontWeight.BOLD,
                                color=color,
                            ),
                            (
                                ft.Text(
                                    main_metric.unit,
                                    size=14,
                                    color=ft.Colors.WHITE_54,
                                )
                                if main_metric.unit
                                else ft.Container()
                            ),
                        ],
                        spacing=8,
                        vertical_alignment=ft.CrossAxisAlignment.END,
                    ),
                ],
                spacing=2,
            ),
            padding=ft.Padding.symmetric(vertical=10),
        )

    def _build_metrics(self) -> list[ft.Control]:
        """构建次要指标列表"""
        if self.data is None or len(self.data.metrics) <= 1:
            return []

        rows = []
        for metric in self.data.metrics[1:6]:  # 最多显示5个次要指标
            rows.append(
                ft.Row(
                    controls=[
                        ft.Text(
                            metric.label,
                            size=11,
                            color=ft.Colors.WHITE_70,
                            expand=True,
                        ),
                        ft.Text(
                            metric.value,
                            size=11,
                            color=ft.Colors.WHITE,
                        ),
                        (
                            ft.Text(
                                metric.unit,
                                size=10,
                                color=ft.Colors.WHITE_54,
                            )
                            if metric.unit
                            else ft.Container()
                        ),
                    ],
                    spacing=8,
                )
            )

        return rows

    def _build_error(self) -> list[ft.Control]:
        """构建错误信息"""
        if self.data is None or not self.data.raw_error:
            return []

        return [
            ft.Text(
                self.data.raw_error,
                size=11,
                color=ft.Colors.RED_300,
                italic=True,
            )
        ]

    def _build_footer(self) -> ft.Control:
        """构建底部更新时间"""
        updated = "N/A"
        if self.data and self.data.last_updated:
            updated = self.data.last_updated.strftime("%Y-%m-%d %H:%M:%S")

        return ft.Text(
            f"更新于: {updated}",
            size=10,
            color=ft.Colors.WHITE_38,
        )

    def update_data(self, data: MonitorResult) -> None:
        """更新卡片数据"""
        self.data = data
        self._show_skeleton = False
        self.content = self._build_content()
        self.border = ft.Border.all(1, ft.Colors.with_opacity(0.2, self._get_status_color()))
        self.update()

    def show_loading(self) -> None:
        """显示加载状态（骨架屏）"""
        self._show_skeleton = True
        self.content = self._build_content()
        self.update()


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
