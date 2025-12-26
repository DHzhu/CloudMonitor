"""
Azure VM 状态监控插件

使用 Azure SDK 监控虚拟机的运行状态。
"""

from datetime import datetime

import flet as ft
from azure.core.exceptions import AzureError, ClientAuthenticationError
from azure.identity import ClientSecretCredential
from azure.mgmt.compute import ComputeManagementClient

from core.plugin_mgr import register_plugin
from plugins.interface import BaseMonitor, KPIData, MonitorResult, MonitorStatus


@register_plugin("azure_vm")
class AzureVMMonitor(BaseMonitor):
    """
    Azure VM 状态监控

    监控 Azure 虚拟机的运行状态。
    """

    @property
    def display_name(self) -> str:
        return "Azure VM"

    @property
    def icon(self) -> str:
        return "computer"

    @property
    def required_credentials(self) -> list[str]:
        return ["tenant_id", "client_id", "client_secret", "subscription_id"]

    async def fetch_data(self) -> MonitorResult:
        """
        获取 Azure VM 实例状态信息

        Returns:
            MonitorResult: 包含实例状态的结果
        """
        tenant_id = self.credentials.get("tenant_id", "")
        client_id = self.credentials.get("client_id", "")
        client_secret = self.credentials.get("client_secret", "")
        subscription_id = self.credentials.get("subscription_id", "")

        if not all([tenant_id, client_id, client_secret, subscription_id]):
            return MonitorResult(
                status=MonitorStatus.ERROR,
                kpi=KPIData(label="VM 状态", value="N/A"),
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

            # 创建 Compute 管理客户端
            compute_client = ComputeManagementClient(
                credential=credential,
                subscription_id=subscription_id,
            )

            # 获取所有虚拟机
            vms = list(compute_client.virtual_machines.list_all())
            return self._parse_vm_list(vms, compute_client)

        except ClientAuthenticationError:
            return MonitorResult(
                status=MonitorStatus.ERROR,
                kpi=KPIData(label="VM 状态", value="认证失败"),
                details=[],
                error_message="Azure 凭据无效",
            )

        except AzureError as e:
            return MonitorResult(
                status=MonitorStatus.ERROR,
                kpi=KPIData(label="VM 状态", value="请求失败"),
                details=[],
                error_message=f"Azure 错误: {e!s}",
            )

    def _parse_vm_list(
        self, vms: list, compute_client: ComputeManagementClient
    ) -> MonitorResult:
        """解析 VM 列表"""
        instances: list[dict] = []

        for vm in vms:
            # 解析资源组名称 (从 ID 中提取)
            resource_group = ""
            if vm.id:
                parts = vm.id.split("/")
                for i, part in enumerate(parts):
                    if part.lower() == "resourcegroups" and i + 1 < len(parts):
                        resource_group = parts[i + 1]
                        break

            # 获取 VM 电源状态
            power_state = "unknown"
            try:
                instance_view = compute_client.virtual_machines.instance_view(
                    resource_group_name=resource_group,
                    vm_name=vm.name,
                )
                for status in instance_view.statuses or []:
                    if status.code and status.code.startswith("PowerState/"):
                        power_state = status.code.replace("PowerState/", "")
                        break
            except AzureError:
                pass  # 如果获取状态失败，保持 unknown

            instances.append({
                "name": vm.name,
                "resource_group": resource_group,
                "location": vm.location,
                "size": vm.hardware_profile.vm_size if vm.hardware_profile else "",
                "state": power_state,
            })

        # 统计运行中的 VM 数量
        running_count = sum(1 for i in instances if i["state"] == "running")
        total_count = len(instances)

        # 确定整体状态
        if running_count == 0 and total_count > 0:
            status = MonitorStatus.WARNING
        elif any(i["state"] not in ("running", "deallocated", "stopped") for i in instances):
            status = MonitorStatus.WARNING
        else:
            status = MonitorStatus.ONLINE

        kpi_value = f"{running_count}/{total_count}"

        return MonitorResult(
            status=status,
            kpi=KPIData(
                label="运行中 VM",
                value=kpi_value,
                unit="虚拟机",
                status=status,
            ),
            details=instances,
            last_updated=datetime.now().isoformat(),
        )

    def render_card(self, data: MonitorResult) -> ft.Control:
        """渲染 Azure VM 状态监控卡片"""
        status_colors = {
            MonitorStatus.ONLINE: ft.Colors.GREEN_400,
            MonitorStatus.WARNING: ft.Colors.AMBER,
            MonitorStatus.ERROR: ft.Colors.RED,
            MonitorStatus.LOADING: ft.Colors.GREY,
        }

        state_colors = {
            "running": ft.Colors.GREEN_400,
            "deallocated": ft.Colors.GREY,
            "stopped": ft.Colors.RED_400,
            "starting": ft.Colors.AMBER,
            "stopping": ft.Colors.AMBER,
            "unknown": ft.Colors.GREY,
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
                            self._shorten_vm_size(detail.get("size", "")),
                            size=10,
                            color=ft.Colors.WHITE_54,
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
                    f"... 还有 {remaining} 个 VM",
                    size=10,
                    color=ft.Colors.WHITE_38,
                    italic=True,
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

    def _shorten_vm_size(self, size: str) -> str:
        """缩短 Azure VM 大小名称"""
        # Azure VM 大小通常很长，如 Standard_D2s_v3
        if size.startswith("Standard_"):
            return size.replace("Standard_", "")
        return size[:15] + "..." if len(size) > 15 else size
