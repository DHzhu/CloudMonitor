"""
DigitalOcean Billing 费用监控插件

使用 DigitalOcean REST API 获取账户余额和账单信息。
"""

import flet as ft
import httpx

from core.models import MetricData, MonitorResult
from core.plugin_mgr import register_plugin
from core.thread_utils import run_blocking
from plugins.interface import BaseMonitor

# DigitalOcean API 基础 URL
DO_API_BASE = "https://api.digitalocean.com/v2"


@register_plugin("digitalocean_cost")
class DigitalOceanCostMonitor(BaseMonitor):
    """
    DigitalOcean 费用监控

    监控 DigitalOcean 账户的余额和账单信息。
    """

    @property
    def plugin_id(self) -> str:
        return "digitalocean_cost"

    @property
    def display_name(self) -> str:
        return "DigitalOcean 费用"

    @property
    def provider_name(self) -> str:
        return "DigitalOcean"

    @property
    def icon(self) -> str:
        return "attach_money"

    @property
    def icon_path(self) -> str:
        return "icons/digitalocean.png"

    @property
    def required_credentials(self) -> list[str]:
        return ["api_token"]

    async def fetch_data(self) -> MonitorResult:
        """
        获取 DigitalOcean 账户余额和账单信息
        """
        api_token = self.credentials.get("api_token", "")

        if not api_token:
            return self._create_error_result("未配置 DigitalOcean API Token")

        try:
            result = await run_blocking(
                self._fetch_billing_sync,
                api_token,
            )
            return result
        except Exception as e:
            return self._create_error_result(f"获取账单失败: {e!s}")

    def _fetch_billing_sync(
        self,
        api_token: str,
    ) -> MonitorResult:
        """同步获取账单数据（在线程池中执行）"""
        headers = {
            "Authorization": f"Bearer {api_token}",
            "Content-Type": "application/json",
        }

        try:
            with httpx.Client(timeout=30) as client:
                # 获取账户余额
                balance_response = client.get(
                    f"{DO_API_BASE}/customers/my/balance",
                    headers=headers,
                )

                if balance_response.status_code == 401:
                    return self._create_error_result("API Token 无效")
                elif balance_response.status_code == 403:
                    return self._create_error_result("API Token 无权限访问账单")
                elif balance_response.status_code != 200:
                    return self._create_error_result(
                        f"API 错误: {balance_response.status_code}"
                    )

                balance_data = balance_response.json()

                # 获取账单历史（最近的账单）
                billing_response = client.get(
                    f"{DO_API_BASE}/customers/my/billing_history",
                    headers=headers,
                    params={"per_page": 5},
                )

                billing_history = []
                if billing_response.status_code == 200:
                    billing_data = billing_response.json()
                    billing_history = billing_data.get("billing_history", [])

            return self._parse_billing_response(balance_data, billing_history)

        except httpx.TimeoutException:
            return self._create_error_result("请求超时")
        except httpx.RequestError as e:
            return self._create_error_result(f"网络错误: {e!s}")

    def _parse_billing_response(
        self,
        balance_data: dict,
        billing_history: list,
    ) -> MonitorResult:
        """解析账单响应数据"""
        # 解析余额信息
        # month_to_date_balance: 本月至今的费用
        # account_balance: 账户余额（正数表示欠费，负数表示有额度）
        # month_to_date_usage: 本月至今的使用量
        month_to_date = float(balance_data.get("month_to_date_balance", "0"))
        account_balance = float(balance_data.get("account_balance", "0"))
        month_to_date_usage = float(balance_data.get("month_to_date_usage", "0"))

        # 确定状态
        if account_balance > 50:
            status = "warning"
        elif account_balance > 100:
            status = "error"
        else:
            status = "normal"

        metrics = [
            MetricData(
                label="本月费用 (MTD)",
                value=f"${month_to_date_usage:.2f}",
                unit="USD",
                status=status,
                trend="up" if month_to_date_usage > 10 else "flat",
            ),
            MetricData(
                label="账户余额",
                value=(
                    f"${-account_balance:.2f}"
                    if account_balance <= 0
                    else f"-${account_balance:.2f}"
                ),
                unit="USD",
                status="normal" if account_balance <= 0 else "warning",
            ),
            MetricData(
                label="待付款",
                value=f"${month_to_date:.2f}",
                unit="USD",
                status="normal",
            ),
        ]

        # 添加最近账单记录
        for record in billing_history[:3]:
            description = record.get("description", "未知")
            amount = float(record.get("amount", "0"))
            record_type = record.get("type", "")

            # 缩短描述
            if len(description) > 25:
                description = description[:22] + "..."

            if record_type == "Payment":
                value_str = f"+${abs(amount):.2f}"
            else:
                value_str = f"-${abs(amount):.2f}"

            metrics.append(
                MetricData(
                    label=description,
                    value=value_str,
                    status="normal",
                )
            )

        return self._create_success_result(metrics)

    def render_card(self, data: MonitorResult) -> ft.Control:
        """渲染 DigitalOcean 费用监控卡片"""
        status_colors = {
            "normal": ft.Colors.GREEN_400,
            "warning": ft.Colors.AMBER,
            "error": ft.Colors.RED,
        }
        color = status_colors.get(data.overall_status, ft.Colors.GREY)

        main_metric = data.metrics[0] if data.metrics else None
        if not main_metric:
            return self._render_error_card(data)

        detail_rows = []
        for metric in data.metrics[1:6]:
            detail_rows.append(
                ft.Row(
                    controls=[
                        ft.Text(metric.label, size=11, color=ft.Colors.WHITE_70, expand=True),
                        ft.Text(metric.value, size=11, color=ft.Colors.WHITE),
                    ],
                    spacing=8,
                )
            )

        return ft.Container(
            content=ft.Column(
                controls=[
                    ft.Row(
                        controls=[
                            ft.Icon(self.icon_value, color=ft.Colors.BLUE_400, size=24),
                            ft.Text(
                                self.alias or self.display_name,
                                size=16,
                                weight=ft.FontWeight.BOLD,
                                color=ft.Colors.WHITE,
                            ),
                            ft.Container(content=ft.Icon(ft.Icons.CIRCLE, color=color, size=10)),
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
                    ft.Text("账单详情", size=12, color=ft.Colors.WHITE_54),
                    *detail_rows,
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
            border=ft.Border.all(1, ft.Colors.with_opacity(0.2, ft.Colors.BLUE)),
        )

    def _render_error_card(self, data: MonitorResult) -> ft.Control:
        """渲染错误状态卡片"""
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
