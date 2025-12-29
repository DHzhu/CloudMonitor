"""
AWS EC2 状态监控插件

使用 boto3 监控 EC2 实例的运行状态和基本指标。
"""

import flet as ft

from core.models import MetricData, MonitorResult
from core.plugin_mgr import register_plugin
from core.thread_utils import run_blocking
from plugins.interface import BaseMonitor


@register_plugin("aws_ec2")
class AWSEC2Monitor(BaseMonitor):
    """
    AWS EC2 状态监控

    监控 EC2 实例的运行状态。
    """

    @property
    def plugin_id(self) -> str:
        return "aws_ec2"

    @property
    def display_name(self) -> str:
        return "AWS EC2"

    @property
    def provider_name(self) -> str:
        return "AWS"

    @property
    def icon(self) -> str:
        return "dns"

    @property
    def icon_path(self) -> str:
        return "icons/aws.png"

    @property
    def required_credentials(self) -> list[str]:
        return ["access_key_id", "secret_access_key", "region"]

    async def fetch_data(self) -> MonitorResult:
        """
        获取 EC2 实例状态信息

        Returns:
            MonitorResult: 包含实例状态的结果
        """
        access_key = self.credentials.get("access_key_id", "")
        secret_key = self.credentials.get("secret_access_key", "")
        region = self.credentials.get("region", "us-east-1")

        if not access_key or not secret_key:
            return self._create_error_result("未配置 AWS 凭据")

        try:
            # 使用线程池包装同步 boto3 调用
            result = await run_blocking(
                self._fetch_instances_sync,
                access_key,
                secret_key,
                region,
            )
            return result

        except Exception as e:
            return self._create_error_result(f"获取实例状态失败: {e!s}")

    def _fetch_instances_sync(
        self,
        access_key: str,
        secret_key: str,
        region: str,
    ) -> MonitorResult:
        """同步获取 EC2 实例数据（在线程池中执行）"""
        import boto3
        from botocore.exceptions import BotoCoreError, ClientError

        try:
            # 创建 EC2 客户端
            client = boto3.client(
                "ec2",
                aws_access_key_id=access_key,
                aws_secret_access_key=secret_key,
                region_name=region,
            )

            # 获取所有实例
            response = client.describe_instances()
            return self._parse_instances_response(response, region)

        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "Unknown")
            error_msg = e.response.get("Error", {}).get("Message", str(e))

            if error_code in ("InvalidAccessKeyId", "SignatureDoesNotMatch"):
                return self._create_error_result("AWS 凭据无效")
            elif error_code == "UnauthorizedOperation":
                return self._create_error_result("需要 EC2 DescribeInstances 权限")
            else:
                return self._create_error_result(f"{error_code}: {error_msg}")

        except BotoCoreError as e:
            return self._create_error_result(f"AWS SDK 错误: {e!s}")

    def _parse_instances_response(self, response: dict, region: str) -> MonitorResult:
        """解析 EC2 实例响应数据"""
        instances: list[dict] = []

        for reservation in response.get("Reservations", []):
            for instance in reservation.get("Instances", []):
                instance_id = instance.get("InstanceId", "")
                state = instance.get("State", {}).get("Name", "unknown")
                instance_type = instance.get("InstanceType", "")

                # 获取实例名称
                name = instance_id
                for tag in instance.get("Tags", []):
                    if tag.get("Key") == "Name":
                        name = tag.get("Value", instance_id)
                        break

                # 获取 IP
                public_ip = instance.get("PublicIpAddress", "")
                private_ip = instance.get("PrivateIpAddress", "")

                instances.append(
                    {
                        "id": instance_id,
                        "name": name,
                        "state": state,
                        "type": instance_type,
                        "ip": public_ip or private_ip,
                    }
                )

        # 统计运行中的实例数量
        running_count = sum(1 for i in instances if i["state"] == "running")
        stopped_count = sum(1 for i in instances if i["state"] == "stopped")
        total_count = len(instances)

        # 确定整体状态
        if running_count == 0 and total_count > 0:
            status = "warning"
        elif any(i["state"] not in ("running", "stopped") for i in instances):
            status = "warning"
        else:
            status = "normal"

        # 构建指标列表
        metrics = [
            MetricData(
                label=f"运行中 ({region})",
                value=f"{running_count}/{total_count}",
                unit="实例",
                status=status,
            ),
            MetricData(
                label="已停止",
                value=str(stopped_count),
                unit="实例",
                status="normal" if stopped_count == 0 else "warning",
            ),
        ]

        # 添加实例详情作为指标
        for inst in instances[:5]:  # 最多显示 5 个实例
            state_status = "normal" if inst["state"] == "running" else "warning"
            if inst["state"] == "stopped":
                state_status = "error"
            metrics.append(
                MetricData(
                    label=inst["name"][:20],
                    value=inst["state"],
                    unit=inst["type"],
                    status=state_status,
                )
            )

        return self._create_success_result(metrics)

    def render_card(self, data: MonitorResult) -> ft.Control:
        """渲染 EC2 状态监控卡片"""
        status_colors = {
            "normal": ft.Colors.GREEN_400,
            "warning": ft.Colors.AMBER,
            "error": ft.Colors.RED,
        }

        state_colors = {
            "running": ft.Colors.GREEN_400,
            "stopped": ft.Colors.RED_400,
            "pending": ft.Colors.AMBER,
            "stopping": ft.Colors.AMBER,
            "terminated": ft.Colors.GREY,
        }

        color = status_colors.get(data.overall_status, ft.Colors.GREY)

        # 获取主要 KPI（运行中实例数）
        main_metric = data.metrics[0] if data.metrics else None
        if not main_metric:
            return self._render_error_card(data)

        # 构建实例列表（从第3个指标开始是实例详情）
        instance_rows = []
        for metric in data.metrics[2:8]:  # 跳过前两个统计指标，最多显示6个实例
            state = metric.value
            state_color = state_colors.get(state, ft.Colors.GREY)

            instance_rows.append(
                ft.Row(
                    controls=[
                        ft.Icon("circle", color=state_color, size=10),
                        ft.Text(
                            metric.label,
                            size=11,
                            color=ft.Colors.WHITE,
                            expand=True,
                        ),
                        ft.Text(
                            metric.unit or "",  # instance type
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
                            ft.Icon(self.icon, color=ft.Colors.ORANGE, size=24),
                            ft.Text(
                                self.alias or self.display_name,
                                size=16,
                                weight=ft.FontWeight.BOLD,
                                color=ft.Colors.WHITE,
                            ),
                            ft.Container(
                                content=ft.Icon("circle", color=color, size=10),
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
                                ft.Row(
                                    controls=[
                                        ft.Text(
                                            main_metric.value,
                                            size=28,
                                            weight=ft.FontWeight.BOLD,
                                            color=color,
                                        ),
                                        ft.Text(
                                            main_metric.unit or "",
                                            size=14,
                                            color=ft.Colors.WHITE_54,
                                        ),
                                    ],
                                    spacing=8,
                                    vertical_alignment=ft.CrossAxisAlignment.END,
                                ),
                            ],
                            spacing=2,
                        ),
                        padding=ft.Padding.symmetric(vertical=10),
                    ),
                    # 实例列表
                    *instance_rows,
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
                            ft.Icon(self.icon, color=ft.Colors.RED, size=24),
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
