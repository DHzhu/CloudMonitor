"""
智谱 AI 余额监控插件

使用 httpx 调用智谱 API 获取账户余额和资源包信息。
"""

from datetime import datetime

import flet as ft
import httpx

from core.models import MetricData, MonitorResult
from core.plugin_mgr import register_plugin
from plugins.interface import BaseMonitor


@register_plugin("zhipu_balance")
class ZhipuBalanceMonitor(BaseMonitor):
    """
    智谱 AI 余额监控

    监控智谱 AI 账户的余额和资源包状态。
    """

    API_BASE_URL = "https://open.bigmodel.cn/api/paas/v4"

    @property
    def plugin_id(self) -> str:
        return "zhipu_balance"

    @property
    def display_name(self) -> str:
        return "智谱 AI"

    @property
    def provider_name(self) -> str:
        return "智谱"

    @property
    def icon(self) -> str:
        return "smart_toy"

    @property
    def icon_path(self) -> str:
        return "icons/zhipu.png"

    @property
    def required_credentials(self) -> list[str]:
        return ["api_key"]

    async def fetch_data(self) -> MonitorResult:
        """获取智谱 AI 账户余额信息"""
        api_key = self.credentials.get("api_key", "")

        if not api_key:
            return self._create_error_result("未配置 API Key")

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    f"{self.API_BASE_URL}/users/me/balance",
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json",
                    },
                )

                if response.status_code == 200:
                    data = response.json()
                    return self._parse_balance_response(data)
                elif response.status_code == 401:
                    return self._create_error_result("API Key 无效或已过期")
                else:
                    return self._create_error_result(
                        f"HTTP {response.status_code}: {response.text}"
                    )

        except httpx.TimeoutException:
            return self._create_error_result("请求超时，请检查网络连接")
        except httpx.RequestError as e:
            return self._create_error_result(f"网络请求失败: {e!s}")

    def _parse_balance_response(self, data: dict) -> MonitorResult:
        """解析余额响应数据"""
        balance = data.get("balance", 0)
        currency = data.get("currency", "CNY")
        packages = data.get("packages", [])

        if balance <= 0:
            status = "error"
        elif balance < 10:
            status = "warning"
        else:
            status = "normal"

        currency_symbol = "¥" if currency == "CNY" else "$"

        metrics = [
            MetricData(
                label="账户余额",
                value=f"{currency_symbol}{balance:.2f}",
                unit=currency,
                status=status,
                trend="down" if balance < 50 else "flat",
            )
        ]

        # 添加资源包信息
        for pkg in packages[:3]:
            remaining = pkg.get("remaining", 0)
            total = pkg.get("total", 0)
            expires_at = pkg.get("expires_at", "")

            expiry_info = ""
            if expires_at:
                try:
                    exp_date = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
                    days_left = (exp_date - datetime.now(exp_date.tzinfo)).days
                    if days_left < 0:
                        expiry_info = "已过期"
                    elif days_left < 7:
                        expiry_info = f"即将过期({days_left}天)"
                    else:
                        expiry_info = f"剩余{days_left}天"
                except ValueError:
                    expiry_info = expires_at

            usage_percent = (total - remaining) / total * 100 if total > 0 else 0
            pkg_status = "warning" if usage_percent > 80 or "即将" in expiry_info else "normal"

            metrics.append(
                MetricData(
                    label=pkg.get("name", "资源包"),
                    value=f"{remaining:,}/{total:,}",
                    unit=expiry_info,
                    status=pkg_status,
                )
            )

        return self._create_success_result(metrics)

    def render_card(self, data: MonitorResult) -> ft.Control:
        """渲染智谱 AI 监控卡片"""
        status_colors = {
            "normal": ft.Colors.GREEN_400,
            "warning": ft.Colors.AMBER,
            "error": ft.Colors.RED,
        }
        color = status_colors.get(data.overall_status, ft.Colors.GREY)

        main_metric = data.metrics[0] if data.metrics else None
        if not main_metric:
            return self._render_error_card(data)

        package_rows = []
        for metric in data.metrics[1:4]:
            package_rows.append(
                ft.Column(
                    controls=[
                        ft.Text(metric.label, size=12, color=ft.Colors.WHITE_70),
                        ft.Row(
                            controls=[
                                ft.Text(metric.value, size=11, color=ft.Colors.WHITE),
                                ft.Text(
                                    metric.unit or "",
                                    size=10,
                                    color=ft.Colors.AMBER
                                    if "即将" in (metric.unit or "")
                                    else ft.Colors.WHITE_54,
                                ),
                            ],
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        ),
                    ],
                    spacing=4,
                )
            )

        return ft.Container(
            content=ft.Column(
                controls=[
                    ft.Row(
                        controls=[
                            ft.Icon(self.icon_value, color=color, size=24),
                            ft.Text(
                                self.alias or self.display_name,
                                size=16,
                                weight=ft.FontWeight.BOLD,
                                color=ft.Colors.WHITE,
                            ),
                            ft.Container(content=ft.Icon("circle", color=color, size=10)),
                        ],
                        alignment=ft.MainAxisAlignment.START,
                        spacing=8,
                    ),
                    ft.Container(
                        content=ft.Column(
                            controls=[
                                ft.Text(main_metric.label, size=12, color=ft.Colors.WHITE_70),
                                ft.Text(
                                    main_metric.value,
                                    size=28,
                                    weight=ft.FontWeight.BOLD,
                                    color=color,
                                ),
                            ],
                            spacing=2,
                        ),
                        padding=ft.Padding.symmetric(vertical=10),
                    ),
                    *package_rows,
                    *(
                        [ft.Text(data.raw_error, size=11, color=ft.Colors.RED_300, italic=True)]
                        if data.raw_error
                        else []
                    ),
                    ft.Text(
                        self._format_update_time(data.last_updated),
                        size=10,
                        color=ft.Colors.WHITE_38,
                    ),
                ],
                spacing=8,
            ),
            padding=16,
            border_radius=12,
            bgcolor=ft.Colors.with_opacity(0.1, ft.Colors.WHITE),
            border=ft.Border.all(1, ft.Colors.with_opacity(0.2, color)),
        )

    def _render_error_card(self, data: MonitorResult) -> ft.Control:
        return ft.Container(
            content=ft.Column(
                controls=[
                    ft.Row(
                        controls=[
                            ft.Icon(self.icon_value, color=ft.Colors.RED, size=24),
                            ft.Text(
                                self.alias or self.display_name,
                                size=16,
                                weight=ft.FontWeight.BOLD,
                                color=ft.Colors.WHITE,
                            ),
                        ],
                        spacing=8,
                    ),
                    ft.Text(data.raw_error or "未知错误", size=12, color=ft.Colors.RED_300),
                ],
                spacing=8,
            ),
            padding=16,
            border_radius=12,
            bgcolor=ft.Colors.with_opacity(0.1, ft.Colors.RED),
        )
