"""
AWS EC2 状态监控插件

使用 boto3 监控 EC2 实例的运行状态和基本指标。
"""

from datetime import datetime

import boto3
import flet as ft
from botocore.exceptions import BotoCoreError, ClientError

from core.plugin_mgr import register_plugin
from plugins.interface import BaseMonitor, KPIData, MonitorResult, MonitorStatus


@register_plugin("aws_ec2")
class AWSEC2Monitor(BaseMonitor):
    """
    AWS EC2 状态监控

    监控 EC2 实例的运行状态。
    """

    @property
    def display_name(self) -> str:
        return "AWS EC2"

    @property
    def icon(self) -> str:
        return "dns"

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
            return MonitorResult(
                status=MonitorStatus.ERROR,
                kpi=KPIData(label="实例状态", value="N/A"),
                details=[],
                error_message="未配置 AWS 凭据",
            )

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
                return MonitorResult(
                    status=MonitorStatus.ERROR,
                    kpi=KPIData(label="实例状态", value="认证失败"),
                    details=[],
                    error_message="AWS 凭据无效",
                )
            elif error_code == "UnauthorizedOperation":
                return MonitorResult(
                    status=MonitorStatus.ERROR,
                    kpi=KPIData(label="实例状态", value="权限不足"),
                    details=[],
                    error_message="需要 EC2 DescribeInstances 权限",
                )
            else:
                return MonitorResult(
                    status=MonitorStatus.ERROR,
                    kpi=KPIData(label="实例状态", value="请求失败"),
                    details=[],
                    error_message=f"{error_code}: {error_msg}",
                )

        except BotoCoreError as e:
            return MonitorResult(
                status=MonitorStatus.ERROR,
                kpi=KPIData(label="实例状态", value="错误"),
                details=[],
                error_message=f"AWS SDK 错误: {e!s}",
            )

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

                # 获取公网 IP
                public_ip = instance.get("PublicIpAddress", "")
                private_ip = instance.get("PrivateIpAddress", "")

                instances.append({
                    "id": instance_id,
                    "name": name,
                    "state": state,
                    "type": instance_type,
                    "public_ip": public_ip,
                    "private_ip": private_ip,
                })

        # 统计运行中的实例数量
        running_count = sum(1 for i in instances if i["state"] == "running")
        total_count = len(instances)

        # 确定整体状态
        if running_count == 0 and total_count > 0:
            status = MonitorStatus.WARNING
        elif any(i["state"] not in ("running", "stopped") for i in instances):
            status = MonitorStatus.WARNING
        else:
            status = MonitorStatus.ONLINE

        kpi_value = f"{running_count}/{total_count}"
        kpi_label = f"运行中 ({region})"

        return MonitorResult(
            status=status,
            kpi=KPIData(
                label=kpi_label,
                value=kpi_value,
                unit="实例",
                status=status,
            ),
            details=[{
                "id": i["id"],
                "name": i["name"],
                "state": i["state"],
                "type": i["type"],
                "ip": i["public_ip"] or i["private_ip"],
            } for i in instances],
            last_updated=datetime.now().isoformat(),
        )

    def render_card(self, data: MonitorResult) -> ft.Control:
        """渲染 EC2 状态监控卡片"""
        status_colors = {
            MonitorStatus.ONLINE: ft.Colors.GREEN_400,
            MonitorStatus.WARNING: ft.Colors.AMBER,
            MonitorStatus.ERROR: ft.Colors.RED,
            MonitorStatus.LOADING: ft.Colors.GREY,
        }

        state_colors = {
            "running": ft.Colors.GREEN_400,
            "stopped": ft.Colors.RED_400,
            "pending": ft.Colors.AMBER,
            "stopping": ft.Colors.AMBER,
            "terminated": ft.Colors.GREY,
        }

        color = status_colors.get(data.status, ft.Colors.GREY)

        # 构建实例列表
        instance_rows = []
        for detail in data.details[:6]:  # 最多显示 6 个实例
            state = detail.get("state", "unknown")
            state_color = state_colors.get(state, ft.Colors.GREY)

            instance_rows.append(
                ft.Row(
                    controls=[
                        ft.Icon(
                            "circle",
                            color=state_color,
                            size=10,
                        ),
                        ft.Text(
                            detail.get("name", "")[:20],
                            size=11,
                            color=ft.Colors.WHITE,
                            expand=True,
                        ),
                        ft.Text(
                            detail.get("type", ""),
                            size=10,
                            color=ft.Colors.WHITE54,
                        ),
                    ],
                    spacing=8,
                )
            )

        # 如果有更多实例
        remaining = len(data.details) - 6
        if remaining > 0:
            instance_rows.append(
                ft.Text(
                    f"... 还有 {remaining} 个实例",
                    size=10,
                    color=ft.Colors.WHITE38,
                    italic=True,
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
                                ft.Row(
                                    controls=[
                                        ft.Text(
                                            data.kpi.value,
                                            size=28,
                                            weight=ft.FontWeight.BOLD,
                                            color=color,
                                        ),
                                        ft.Text(
                                            data.kpi.unit,
                                            size=14,
                                            color=ft.Colors.WHITE54,
                                        ),
                                    ],
                                    spacing=8,
                                    vertical_alignment=ft.CrossAxisAlignment.END,
                                ),
                            ],
                            spacing=2,
                        ),
                        padding=ft.padding.symmetric(vertical=10),
                    ),
                    # 实例列表
                    *instance_rows,
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
