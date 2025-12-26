"""
Azure Cost Management 费用监控插件

使用 Azure Cost Management SDK 获取账单信息。
"""

from datetime import datetime

import flet as ft
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

from core.plugin_mgr import register_plugin
from plugins.interface import BaseMonitor, KPIData, MonitorResult, MonitorStatus


@register_plugin("azure_cost")
class AzureCostMonitor(BaseMonitor):
    """
    Azure 费用监控

    监控 Azure 订阅的本月费用。
    """

    @property
    def display_name(self) -> str:
        return "Azure 费用"

    @property
    def icon(self) -> str:
        return "attach_money"

    @property
    def required_credentials(self) -> list[str]:
        return ["tenant_id", "client_id", "client_secret", "subscription_id"]

    async def fetch_data(self) -> MonitorResult:
        """
        获取 Azure 本月费用信息

        Returns:
            MonitorResult: 包含费用信息的结果
        """
        tenant_id = self.credentials.get("tenant_id", "")
        client_id = self.credentials.get("client_id", "")
        client_secret = self.credentials.get("client_secret", "")
        subscription_id = self.credentials.get("subscription_id", "")

        if not all([tenant_id, client_id, client_secret, subscription_id]):
            return MonitorResult(
                status=MonitorStatus.ERROR,
                kpi=KPIData(label="本月费用", value="N/A"),
                details=[],
                error_message="未配置 Azure 凭据",
            )

        try:
            # 创建 Azure 认证凭据
            credential = ClientSecretCredential(
                tenant_id=tenant_id,
                client_id=client_id,
                client_secret=client_secret,
            )

            # 创建 Cost Management 客户端
            cost_client = CostManagementClient(
                credential=credential,
                subscription_id=subscription_id,
            )

            # 计算日期范围
            today = datetime.now()
            start_of_month = today.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

            # 构建查询定义
            scope = f"/subscriptions/{subscription_id}"

            query_definition = QueryDefinition(
                type=ExportType.ACTUAL_COST,
                timeframe=TimeframeType.CUSTOM,
                time_period=QueryTimePeriod(
                    from_property=start_of_month,
                    to=today,
                ),
                dataset=QueryDataset(
                    granularity="None",
                    aggregation={
                        "totalCost": QueryAggregation(
                            name="Cost",
                            function="Sum",
                        ),
                    },
                    grouping=[
                        QueryGrouping(
                            type="Dimension",
                            name="ResourceGroup",
                        ),
                    ],
                ),
            )

            # 执行查询
            result = cost_client.query.usage(scope=scope, parameters=query_definition)
            return self._parse_cost_response(result)

        except ClientAuthenticationError:
            return MonitorResult(
                status=MonitorStatus.ERROR,
                kpi=KPIData(label="本月费用", value="认证失败"),
                details=[],
                error_message="Azure 凭据无效",
            )

        except HttpResponseError as e:
            if "Authorization" in str(e) or "Forbidden" in str(e):
                return MonitorResult(
                    status=MonitorStatus.ERROR,
                    kpi=KPIData(label="本月费用", value="权限不足"),
                    details=[],
                    error_message="需要 Cost Management Reader 权限",
                )
            return MonitorResult(
                status=MonitorStatus.ERROR,
                kpi=KPIData(label="本月费用", value="请求失败"),
                details=[],
                error_message=f"API 错误: {e!s}",
            )

        except AzureError as e:
            return MonitorResult(
                status=MonitorStatus.ERROR,
                kpi=KPIData(label="本月费用", value="错误"),
                details=[],
                error_message=f"Azure 错误: {e!s}",
            )

    def _parse_cost_response(self, result: object) -> MonitorResult:
        """解析 Cost Management 响应数据"""
        # 解析响应中的列和行
        columns = result.columns if hasattr(result, "columns") else []
        rows = result.rows if hasattr(result, "rows") else []

        # 找到 Cost 和 ResourceGroup 列的索引
        cost_idx = -1
        rg_idx = -1
        for i, col in enumerate(columns):
            col_name = col.name if hasattr(col, "name") else str(col)
            if col_name.lower() in ("cost", "totalcost"):
                cost_idx = i
            elif col_name.lower() in ("resourcegroup", "resource group"):
                rg_idx = i

        if cost_idx == -1:
            # 如果没有找到 cost 列，返回零费用
            return MonitorResult(
                status=MonitorStatus.ONLINE,
                kpi=KPIData(label="本月费用", value="$0.00", unit="USD"),
                details=[],
                last_updated=datetime.now().isoformat(),
            )

        # 计算总费用和资源组明细
        total_cost = 0.0
        resource_group_costs: list[dict] = []

        for row in rows:
            cost = float(row[cost_idx]) if cost_idx < len(row) else 0.0
            rg_name = row[rg_idx] if rg_idx >= 0 and rg_idx < len(row) else "Unknown"

            if cost > 0.01:  # 只显示大于 $0.01 的资源组
                total_cost += cost
                resource_group_costs.append({
                    "resource_group": rg_name or "Unassigned",
                    "cost": cost,
                })

        # 按费用排序
        resource_group_costs.sort(key=lambda x: x["cost"], reverse=True)

        # 确定状态
        if total_cost > 100:
            status = MonitorStatus.WARNING
        else:
            status = MonitorStatus.ONLINE

        # 计算各资源组占比
        details = []
        for item in resource_group_costs[:10]:  # 只显示前 10 个
            percentage = (item["cost"] / total_cost * 100) if total_cost > 0 else 0
            details.append({
                "resource_group": item["resource_group"],
                "cost": item["cost"],
                "percentage": percentage,
            })

        return MonitorResult(
            status=status,
            kpi=KPIData(
                label="本月费用 (MTD)",
                value=f"${total_cost:.2f}",
                unit="USD",
                status=status,
            ),
            details=details,
            last_updated=datetime.now().isoformat(),
        )

    def render_card(self, data: MonitorResult) -> ft.Control:
        """渲染 Azure 费用监控卡片"""
        status_colors = {
            MonitorStatus.ONLINE: ft.Colors.GREEN_400,
            MonitorStatus.WARNING: ft.Colors.AMBER,
            MonitorStatus.ERROR: ft.Colors.RED,
            MonitorStatus.LOADING: ft.Colors.GREY,
        }

        color = status_colors.get(data.status, ft.Colors.GREY)

        # 构建资源组费用明细
        rg_rows = []
        for detail in data.details[:5]:  # 只显示前 5 个
            rg_rows.append(
                ft.Row(
                    controls=[
                        ft.Text(
                            self._shorten_rg_name(detail.get("resource_group", "")),
                            size=11,
                            color=ft.Colors.WHITE_70,
                            expand=True,
                        ),
                        ft.Text(
                            f"${detail.get('cost', 0):.2f}",
                            size=11,
                            color=ft.Colors.WHITE,
                        ),
                        ft.Text(
                            f"({detail.get('percentage', 0):.1f}%)",
                            size=10,
                            color=ft.Colors.WHITE_54,
                        ),
                    ],
                    spacing=8,
                )
            )

        return ft.Container(
            content=ft.Column(
                controls=[
                    # 标题行
                    ft.Row(
                        controls=[
                            ft.Icon(self.icon, color=ft.Colors.BLUE, size=24),
                            ft.Text(
                                self.alias or self.display_name,
                                size=16,
                                weight=ft.FontWeight.BOLD,
                                color=ft.Colors.WHITE,
                            ),
                            ft.Container(
                                content=ft.Icon(
                                    "circle",
                                    color=color,
                                    size=10,
                                ),
                            ),
                        ],
                        alignment=ft.MainAxisAlignment.START,
                        spacing=8,
                    ),
                    # KPI 显示
                    ft.Container(
                        content=ft.Column(
                            controls=[
                                ft.Text(
                                    data.kpi.label,
                                    size=12,
                                    color=ft.Colors.WHITE_70,
                                ),
                                ft.Text(
                                    data.kpi.value,
                                    size=28,
                                    weight=ft.FontWeight.BOLD,
                                    color=color,
                                ),
                            ],
                            spacing=2,
                        ),
                        padding=ft.Padding.symmetric(vertical=10),
                    ),
                    # 资源组费用明细
                    ft.Text(
                        "资源组明细",
                        size=12,
                        color=ft.Colors.WHITE_54,
                    ),
                    *rg_rows,
                    # 错误信息
                    *(
                        [
                            ft.Text(
                                data.error_message,
                                size=11,
                                color=ft.Colors.RED_300,
                                italic=True,
                            )
                        ]
                        if data.error_message
                        else []
                    ),
                    # 更新时间
                    ft.Text(
                        f"更新于: {data.last_updated[:19] if data.last_updated else 'N/A'}",
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

    def _shorten_rg_name(self, name: str) -> str:
        """缩短资源组名称"""
        return name[:25] + "..." if len(name) > 25 else name
