"""
AWS Cost Explorer 费用监控插件

使用 boto3 调用 AWS Cost Explorer API 获取账单信息。
"""

from datetime import datetime, timedelta

import boto3
import flet as ft
from botocore.exceptions import BotoCoreError, ClientError

from core.plugin_mgr import register_plugin
from plugins.interface import BaseMonitor, KPIData, MonitorResult, MonitorStatus


@register_plugin("aws_cost")
class AWSCostMonitor(BaseMonitor):
    """
    AWS 费用监控

    监控 AWS 账户的本月至今 (MTD) 费用。
    """

    @property
    def display_name(self) -> str:
        return "AWS 费用"

    @property
    def icon(self) -> str:
        return "cloud"

    @property
    def required_credentials(self) -> list[str]:
        return ["access_key_id", "secret_access_key", "region"]

    async def fetch_data(self) -> MonitorResult:
        """
        获取 AWS 本月费用信息

        Returns:
            MonitorResult: 包含费用信息的结果
        """
        access_key = self.credentials.get("access_key_id", "")
        secret_key = self.credentials.get("secret_access_key", "")
        region = self.credentials.get("region", "us-east-1")

        if not access_key or not secret_key:
            return MonitorResult(
                status=MonitorStatus.ERROR,
                kpi=KPIData(label="本月费用", value="N/A"),
                details=[],
                error_message="未配置 AWS 凭据",
            )

        try:
            # 创建 Cost Explorer 客户端
            # 注意: boto3 是同步的，在生产环境中应该使用 run_in_executor
            client = boto3.client(
                "ce",
                aws_access_key_id=access_key,
                aws_secret_access_key=secret_key,
                region_name=region,
            )

            # 计算日期范围 (本月1日到今天)
            today = datetime.now()
            start_of_month = today.replace(day=1)
            end_date = today + timedelta(days=1)  # Cost Explorer 需要排他的结束日期

            # 调用 Cost Explorer API
            response = client.get_cost_and_usage(
                TimePeriod={
                    "Start": start_of_month.strftime("%Y-%m-%d"),
                    "End": end_date.strftime("%Y-%m-%d"),
                },
                Granularity="MONTHLY",
                Metrics=["BlendedCost", "UnblendedCost"],
                GroupBy=[
                    {"Type": "DIMENSION", "Key": "SERVICE"},
                ],
            )

            return self._parse_cost_response(response)

        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "Unknown")
            error_msg = e.response.get("Error", {}).get("Message", str(e))

            if error_code in ("InvalidAccessKeyId", "SignatureDoesNotMatch"):
                return MonitorResult(
                    status=MonitorStatus.ERROR,
                    kpi=KPIData(label="本月费用", value="认证失败"),
                    details=[],
                    error_message="AWS 凭据无效",
                )
            elif error_code == "AccessDeniedException":
                return MonitorResult(
                    status=MonitorStatus.ERROR,
                    kpi=KPIData(label="本月费用", value="权限不足"),
                    details=[],
                    error_message="需要 Cost Explorer 访问权限",
                )
            else:
                return MonitorResult(
                    status=MonitorStatus.ERROR,
                    kpi=KPIData(label="本月费用", value="请求失败"),
                    details=[],
                    error_message=f"{error_code}: {error_msg}",
                )

        except BotoCoreError as e:
            return MonitorResult(
                status=MonitorStatus.ERROR,
                kpi=KPIData(label="本月费用", value="错误"),
                details=[],
                error_message=f"AWS SDK 错误: {e!s}",
            )

    def _parse_cost_response(self, response: dict) -> MonitorResult:
        """解析 Cost Explorer 响应数据"""
        results_by_time = response.get("ResultsByTime", [])

        if not results_by_time:
            return MonitorResult(
                status=MonitorStatus.ONLINE,
                kpi=KPIData(label="本月费用", value="$0.00", unit="USD"),
                details=[],
                last_updated=datetime.now().isoformat(),
            )

        # 获取本月数据
        current_month = results_by_time[0]
        groups = current_month.get("Groups", [])

        # 计算总费用和服务明细
        total_cost = 0.0
        service_costs: list[dict] = []

        for group in groups:
            service_name = group.get("Keys", ["Unknown"])[0]
            metrics = group.get("Metrics", {})
            blended_cost = float(metrics.get("BlendedCost", {}).get("Amount", 0))

            if blended_cost > 0.01:  # 只显示大于 $0.01 的服务
                total_cost += blended_cost
                service_costs.append({
                    "service": service_name,
                    "cost": blended_cost,
                })

        # 按费用排序
        service_costs.sort(key=lambda x: x["cost"], reverse=True)

        # 确定状态
        if total_cost > 100:
            status = MonitorStatus.WARNING
        else:
            status = MonitorStatus.ONLINE

        # 计算各服务占比
        details = []
        for item in service_costs[:10]:  # 只显示前 10 个服务
            percentage = (item["cost"] / total_cost * 100) if total_cost > 0 else 0
            details.append({
                "service": item["service"],
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
        """渲染 AWS 费用监控卡片"""
        status_colors = {
            MonitorStatus.ONLINE: ft.Colors.GREEN_400,
            MonitorStatus.WARNING: ft.Colors.AMBER,
            MonitorStatus.ERROR: ft.Colors.RED,
            MonitorStatus.LOADING: ft.Colors.GREY,
        }

        color = status_colors.get(data.status, ft.Colors.GREY)

        # 构建服务费用明细
        service_rows = []
        for detail in data.details[:5]:  # 只显示前 5 个
            service_rows.append(
                ft.Row(
                    controls=[
                        ft.Text(
                            self._shorten_service_name(detail.get("service", "")),
                            size=11,
                            color=ft.Colors.WHITE70,
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
                            color=ft.Colors.WHITE54,
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
                            ft.Icon(self.icon, color=ft.Colors.ORANGE, size=24),
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
                                    color=ft.Colors.WHITE70,
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
                        padding=ft.padding.symmetric(vertical=10),
                    ),
                    # 服务费用明细
                    ft.Text(
                        "服务明细",
                        size=12,
                        color=ft.Colors.WHITE54,
                    ),
                    *service_rows,
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
                        color=ft.Colors.WHITE38,
                    ),
                ],
                spacing=8,
            ),
            padding=16,
            border_radius=12,
            bgcolor=ft.Colors.with_opacity(0.1, ft.Colors.WHITE),
            border=ft.border.all(1, ft.Colors.with_opacity(0.2, ft.Colors.ORANGE)),
        )

    def _shorten_service_name(self, name: str) -> str:
        """缩短 AWS 服务名称"""
        # AWS 服务名称通常很长，需要缩短
        replacements = {
            "Amazon ": "",
            "AWS ": "",
            "Elastic Compute Cloud - Compute": "EC2",
            "Simple Storage Service": "S3",
            "Relational Database Service": "RDS",
            "Lambda": "Lambda",
        }
        result = name
        for old, new in replacements.items():
            result = result.replace(old, new)
        return result[:25] + "..." if len(result) > 25 else result
