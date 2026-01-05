"""
AWS Cost Explorer 费用监控插件

使用 boto3 调用 AWS Cost Explorer API 获取账单信息。
"""

from datetime import datetime, timedelta

import flet as ft

from core.models import MetricData, MonitorResult
from core.plugin_mgr import register_plugin
from core.thread_utils import run_blocking
from plugins.interface import BaseMonitor


@register_plugin("aws_cost")
class AWSCostMonitor(BaseMonitor):
    """
    AWS 费用监控

    监控 AWS 账户的本月至今 (MTD) 费用。
    """

    @property
    def plugin_id(self) -> str:
        return "aws_cost"

    @property
    def display_name(self) -> str:
        return "AWS 费用"

    @property
    def provider_name(self) -> str:
        return "AWS"

    @property
    def icon(self) -> str:
        return "cloud"

    @property
    def icon_path(self) -> str:
        return "icons/aws.png"

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
            return self._create_error_result("未配置 AWS 凭据")

        try:
            # 使用线程池包装同步 boto3 调用
            result = await run_blocking(
                self._fetch_cost_sync,
                access_key,
                secret_key,
                region,
            )
            return result

        except Exception as e:
            return self._create_error_result(f"获取费用失败: {e!s}")

    def _fetch_cost_sync(
        self,
        access_key: str,
        secret_key: str,
        region: str,
    ) -> MonitorResult:
        """同步获取费用数据（在线程池中执行）"""
        import boto3
        from botocore.exceptions import BotoCoreError, ClientError

        try:
            # 创建 Cost Explorer 客户端
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
                return self._create_error_result("AWS 凭据无效")
            elif error_code == "AccessDeniedException":
                return self._create_error_result("需要 Cost Explorer 访问权限")
            else:
                return self._create_error_result(f"{error_code}: {error_msg}")

        except BotoCoreError as e:
            return self._create_error_result(f"AWS SDK 错误: {e!s}")

    def _parse_cost_response(self, response: dict) -> MonitorResult:
        """解析 Cost Explorer 响应数据"""
        results_by_time = response.get("ResultsByTime", [])

        if not results_by_time:
            return self._create_success_result(
                [
                    MetricData(
                        label="本月费用",
                        value="$0.00",
                        unit="USD",
                        status="normal",
                    )
                ]
            )

        # 获取本月数据
        current_month = results_by_time[0]
        groups = current_month.get("Groups", [])

        # 计算总费用和服务明细
        total_cost = 0.0
        service_costs: list[tuple[str, float]] = []

        for group in groups:
            service_name = group.get("Keys", ["Unknown"])[0]
            metrics_data = group.get("Metrics", {})
            blended_cost = float(metrics_data.get("BlendedCost", {}).get("Amount", 0))

            if blended_cost > 0.01:  # 只显示大于 $0.01 的服务
                total_cost += blended_cost
                service_costs.append((service_name, blended_cost))

        # 按费用排序
        service_costs.sort(key=lambda x: x[1], reverse=True)

        # 确定状态
        status = "warning" if total_cost > 100 else "normal"

        # 构建指标列表
        metrics = [
            MetricData(
                label="本月费用 (MTD)",
                value=f"${total_cost:.2f}",
                unit="USD",
                status=status,
                trend="up" if total_cost > 50 else "flat",
            )
        ]

        # 添加前 5 个服务的费用作为额外指标
        for service, cost in service_costs[:5]:
            short_name = self._shorten_service_name(service)
            percentage = (cost / total_cost * 100) if total_cost > 0 else 0
            metrics.append(
                MetricData(
                    label=short_name,
                    value=f"${cost:.2f} ({percentage:.1f}%)",
                    status="normal",
                )
            )

        return self._create_success_result(metrics)

    def render_card(self, data: MonitorResult) -> ft.Control:
        """渲染 AWS 费用监控卡片"""
        status_colors = {
            "normal": ft.Colors.GREEN_400,
            "warning": ft.Colors.AMBER,
            "error": ft.Colors.RED,
        }

        color = status_colors.get(data.overall_status, ft.Colors.GREY)

        # 获取主要 KPI
        main_metric = data.metrics[0] if data.metrics else None
        if not main_metric:
            return self._render_error_card(data)

        # 构建服务费用明细
        service_rows = []
        for metric in data.metrics[1:6]:  # 跳过第一个（总费用），显示最多5个服务
            service_rows.append(
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
                            ft.Icon(self.icon_value, color=ft.Colors.ORANGE, size=24),
                            ft.Text(
                                self.alias or self.display_name,
                                size=16,
                                weight=ft.FontWeight.BOLD,
                                color=ft.Colors.WHITE,
                            ),
                            ft.Container(
                                content=ft.Icon(ft.Icons.CIRCLE, color=color, size=10),
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
                                    main_metric.label,
                                    size=12,
                                    color=ft.Colors.WHITE_70,
                                ),
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
                    # 服务费用明细
                    ft.Text("服务明细", size=12, color=ft.Colors.WHITE_54),
                    *service_rows,
                    # 错误信息
                    *(
                        [
                            ft.Text(
                                data.raw_error,
                                size=11,
                                color=ft.Colors.RED_300,
                                italic=True,
                            )
                        ]
                        if data.raw_error
                        else []
                    ),
                    # 更新时间
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
            border=ft.Border.all(1, ft.Colors.with_opacity(0.2, ft.Colors.ORANGE)),
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
                    ft.Text(
                        data.raw_error or "未知错误",
                        size=12,
                        color=ft.Colors.RED_300,
                    ),
                ],
                spacing=8,
            ),
            padding=16,
            border_radius=12,
            bgcolor=ft.Colors.with_opacity(0.1, ft.Colors.RED),
        )

    def _shorten_service_name(self, name: str) -> str:
        """缩短 AWS 服务名称"""
        replacements = {
            "Amazon ": "",
            "AWS ": "",
            "Elastic Compute Cloud - Compute": "EC2",
            "Simple Storage Service": "S3",
            "Relational Database Service": "RDS",
        }
        result = name
        for old, new in replacements.items():
            result = result.replace(old, new)
        return result[:25] + "..." if len(result) > 25 else result
