"""
Azure VM 状态监控插件

使用 Azure SDK 监控虚拟机的运行状态。
"""

import flet as ft

from core.models import MetricData, MonitorResult
from core.plugin_mgr import register_plugin
from core.thread_utils import run_blocking
from plugins.interface import BaseMonitor


@register_plugin("azure_vm")
class AzureVMMonitor(BaseMonitor):
    """
    Azure VM 状态监控

    监控 Azure 虚拟机的运行状态。
    """

    @property
    def plugin_id(self) -> str:
        return "azure_vm"

    @property
    def display_name(self) -> str:
        return "Azure VM"

    @property
    def provider_name(self) -> str:
        return "Azure"

    @property
    def icon(self) -> str:
        return "computer"

    @property
    def icon_path(self) -> str:
        return "icons/azure.png"

    @property
    def required_credentials(self) -> list[str]:
        return ["tenant_id", "client_id", "client_secret", "subscription_id"]

    async def fetch_data(self) -> MonitorResult:
        """获取 Azure VM 实例状态信息"""
        tenant_id = self.credentials.get("tenant_id", "")
        client_id = self.credentials.get("client_id", "")
        client_secret = self.credentials.get("client_secret", "")
        subscription_id = self.credentials.get("subscription_id", "")

        if not all([tenant_id, client_id, client_secret, subscription_id]):
            return self._create_error_result("未配置 Azure 凭据")

        try:
            result = await run_blocking(
                self._fetch_vms_sync,
                tenant_id,
                client_id,
                client_secret,
                subscription_id,
            )
            return result
        except Exception as e:
            return self._create_error_result(f"获取VM状态失败: {e!s}")

    def _fetch_vms_sync(
        self,
        tenant_id: str,
        client_id: str,
        client_secret: str,
        subscription_id: str,
    ) -> MonitorResult:
        """同步获取VM数据（在线程池中执行）"""
        from azure.core.exceptions import AzureError, ClientAuthenticationError
        from azure.identity import ClientSecretCredential
        from azure.mgmt.compute import ComputeManagementClient

        try:
            credential = ClientSecretCredential(
                tenant_id=tenant_id,
                client_id=client_id,
                client_secret=client_secret,
            )

            compute_client = ComputeManagementClient(
                credential=credential,
                subscription_id=subscription_id,
            )

            vms = list(compute_client.virtual_machines.list_all())
            return self._parse_vm_list(vms, compute_client)

        except ClientAuthenticationError:
            return self._create_error_result("Azure 凭据无效")
        except AzureError as e:
            return self._create_error_result(f"Azure 错误: {e!s}")

    def _parse_vm_list(self, vms: list, compute_client: object) -> MonitorResult:
        """解析 VM 列表"""
        from azure.core.exceptions import AzureError

        instances: list[dict] = []

        for vm in vms:
            resource_group = ""
            if vm.id:
                parts = vm.id.split("/")
                for i, part in enumerate(parts):
                    if part.lower() == "resourcegroups" and i + 1 < len(parts):
                        resource_group = parts[i + 1]
                        break

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
                pass

            instances.append(
                {
                    "name": vm.name,
                    "resource_group": resource_group,
                    "location": vm.location,
                    "size": vm.hardware_profile.vm_size if vm.hardware_profile else "",
                    "state": power_state,
                }
            )

        running_count = sum(1 for i in instances if i["state"] == "running")
        stopped_count = sum(1 for i in instances if i["state"] in ("deallocated", "stopped"))
        total_count = len(instances)

        if running_count == 0 and total_count > 0:
            status = "warning"
        elif any(i["state"] not in ("running", "deallocated", "stopped") for i in instances):
            status = "warning"
        else:
            status = "normal"

        metrics = [
            MetricData(
                label="运行中 VM",
                value=f"{running_count}/{total_count}",
                unit="虚拟机",
                status=status,
            ),
            MetricData(
                label="已停止",
                value=str(stopped_count),
                unit="虚拟机",
                status="normal" if stopped_count == 0 else "warning",
            ),
        ]

        for inst in instances[:5]:
            state_status = "normal" if inst["state"] == "running" else "warning"
            if inst["state"] in ("deallocated", "stopped"):
                state_status = "error"
            metrics.append(
                MetricData(
                    label=inst["name"][:20],
                    value=inst["state"],
                    unit=self._shorten_vm_size(inst["size"]),
                    status=state_status,
                )
            )

        return self._create_success_result(metrics)

    def render_card(self, data: MonitorResult) -> ft.Control:
        """渲染 Azure VM 状态监控卡片"""
        status_colors = {
            "normal": ft.Colors.GREEN_400,
            "warning": ft.Colors.AMBER,
            "error": ft.Colors.RED,
        }
        state_colors = {
            "running": ft.Colors.GREEN_400,
            "deallocated": ft.Colors.GREY,
            "stopped": ft.Colors.RED_400,
            "starting": ft.Colors.AMBER,
            "stopping": ft.Colors.AMBER,
            "unknown": ft.Colors.GREY,
        }

        color = status_colors.get(data.overall_status, ft.Colors.GREY)
        main_metric = data.metrics[0] if data.metrics else None
        if not main_metric:
            return self._render_error_card(data)

        instance_rows = []
        for metric in data.metrics[2:8]:
            state = metric.value
            state_color = state_colors.get(state, ft.Colors.GREY)
            instance_rows.append(
                ft.Row(
                    controls=[
                        ft.Icon("circle", color=state_color, size=10),
                        ft.Text(metric.label, size=11, color=ft.Colors.WHITE, expand=True),
                        ft.Text(metric.unit or "", size=10, color=ft.Colors.WHITE_54),
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
                    *instance_rows,
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

    def _shorten_vm_size(self, size: str) -> str:
        if size.startswith("Standard_"):
            return size.replace("Standard_", "")
        return size[:15] + "..." if len(size) > 15 else size
