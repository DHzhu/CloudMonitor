"""
Azure Cost Management 费用监控插件

使用 Azure Cost Management SDK 获取账单信息。
"""

from datetime import datetime

import flet as ft

from core.models import MetricData, MonitorResult
from core.plugin_mgr import register_plugin
from core.thread_utils import run_blocking
from plugins.interface import BaseMonitor


@register_plugin("azure_cost")
class AzureCostMonitor(BaseMonitor):
    """
    Azure 费用监控

    监控 Azure 订阅的本月费用。
    """

    @property
    def plugin_id(self) -> str:
        return "azure_cost"

    @property
    def display_name(self) -> str:
        return "Azure 费用"

    @property
    def provider_name(self) -> str:
        return "Azure"

    @property
    def icon(self) -> str:
        return "attach_money"

    @property
    def icon_path(self) -> str:
        return "icons/azure.png"

    @property
    def required_credentials(self) -> list[str]:
        return ["tenant_id", "client_id", "client_secret", "subscription_id"]

    async def fetch_data(self) -> MonitorResult:
        """
        获取 Azure 本月费用信息
        """
        tenant_id = self.credentials.get("tenant_id", "")
        client_id = self.credentials.get("client_id", "")
        client_secret = self.credentials.get("client_secret", "")
        subscription_id = self.credentials.get("subscription_id", "")

        if not all([tenant_id, client_id, client_secret, subscription_id]):
            return self._create_error_result("未配置 Azure 凭据")

        try:
            result = await run_blocking(
                self._fetch_cost_sync,
                tenant_id,
                client_id,
                client_secret,
                subscription_id,
            )
            return result
        except Exception as e:
            return self._create_error_result(f"获取费用失败: {e!s}")

    def _fetch_cost_sync(
        self,
        tenant_id: str,
        client_id: str,
        client_secret: str,
        subscription_id: str,
    ) -> MonitorResult:
        """同步获取费用数据（在线程池中执行）"""
        from azure.core.exceptions import AzureError, ClientAuthenticationError, HttpResponseError
        from azure.identity import ClientSecretCredential
        from azure.mgmt.costmanagement import CostManagementClient
        from azure.mgmt.costmanagement.models import (
            ExportType,
            QueryAggregation,
            QueryDataset,
            QueryDefinition,
            QueryGrouping,
            QueryTimePeriod,
            TimeframeType,
        )

        try:
            credential = ClientSecretCredential(
                tenant_id=tenant_id,
                client_id=client_id,
                client_secret=client_secret,
            )

            cost_client = CostManagementClient(
                credential=credential,
                subscription_id=subscription_id,
            )

            today = datetime.now()
            start_of_month = today.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

            scope = f"/subscriptions/{subscription_id}"

            query_definition = QueryDefinition(
                type=ExportType.ACTUAL_COST,
                timeframe=TimeframeType.CUSTOM,
                time_period=QueryTimePeriod(from_property=start_of_month, to=today),
                dataset=QueryDataset(
                    granularity="None",
                    aggregation={"totalCost": QueryAggregation(name="Cost", function="Sum")},
                    grouping=[QueryGrouping(type="Dimension", name="ResourceGroup")],
                ),
            )

            result = cost_client.query.usage(scope=scope, parameters=query_definition)
            return self._parse_cost_response(result)

        except ClientAuthenticationError:
            return self._create_error_result("Azure 凭据无效")
        except HttpResponseError as e:
            if "Authorization" in str(e) or "Forbidden" in str(e):
                return self._create_error_result("需要 Cost Management Reader 权限")
            return self._create_error_result(f"API 错误: {e!s}")
        except AzureError as e:
            return self._create_error_result(f"Azure 错误: {e!s}")

    def _parse_cost_response(self, result: object) -> MonitorResult:
        """解析 Cost Management 响应数据"""
        columns = result.columns if hasattr(result, "columns") else []
        rows = result.rows if hasattr(result, "rows") else []

        cost_idx = -1
        rg_idx = -1
        for i, col in enumerate(columns):
            col_name = col.name if hasattr(col, "name") else str(col)
            if col_name.lower() in ("cost", "totalcost"):
                cost_idx = i
            elif col_name.lower() in ("resourcegroup", "resource group"):
                rg_idx = i

        if cost_idx == -1:
            return self._create_success_result(
                [MetricData(label="本月费用", value="$0.00", unit="USD", status="normal")]
            )

        total_cost = 0.0
        resource_group_costs: list[tuple[str, float]] = []

        for row in rows:
            cost = float(row[cost_idx]) if cost_idx < len(row) else 0.0
            rg_name = row[rg_idx] if rg_idx >= 0 and rg_idx < len(row) else "Unknown"

            if cost > 0.01:
                total_cost += cost
                resource_group_costs.append((rg_name or "Unassigned", cost))

        resource_group_costs.sort(key=lambda x: x[1], reverse=True)

        status = "warning" if total_cost > 100 else "normal"

        metrics = [
            MetricData(
                label="本月费用 (MTD)",
                value=f"${total_cost:.2f}",
                unit="USD",
                status=status,
                trend="up" if total_cost > 50 else "flat",
            )
        ]

        for rg_name, cost in resource_group_costs[:5]:
            percentage = (cost / total_cost * 100) if total_cost > 0 else 0
            metrics.append(
                MetricData(
                    label=self._shorten_rg_name(rg_name),
                    value=f"${cost:.2f} ({percentage:.1f}%)",
                    status="normal",
                )
            )

        return self._create_success_result(metrics)

    def render_card(self, data: MonitorResult) -> ft.Control:
        """渲染 Azure 费用监控卡片"""
        status_colors = {
            "normal": ft.Colors.GREEN_400,
            "warning": ft.Colors.AMBER,
            "error": ft.Colors.RED,
        }
        color = status_colors.get(data.overall_status, ft.Colors.GREY)

        main_metric = data.metrics[0] if data.metrics else None
        if not main_metric:
            return self._render_error_card(data)

        rg_rows = []
        for metric in data.metrics[1:6]:
            rg_rows.append(
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
                            ft.Icon(self.icon_value, color=ft.Colors.BLUE, size=24),
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
                    ft.Text("资源组明细", size=12, color=ft.Colors.WHITE_54),
                    *rg_rows,
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

    def _shorten_rg_name(self, name: str) -> str:
        return name[:25] + "..." if len(name) > 25 else name
