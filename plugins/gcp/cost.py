"""
GCP Cloud Billing 费用监控插件

使用 Google Cloud Billing API 获取账单信息。
"""

import flet as ft

from core.models import MetricData, MonitorResult
from core.plugin_mgr import register_plugin
from core.thread_utils import run_blocking
from plugins.interface import BaseMonitor


@register_plugin("gcp_cost")
class GCPCostMonitor(BaseMonitor):
    """
    GCP 费用监控

    监控 Google Cloud Platform 项目的本月费用。
    """

    @property
    def plugin_id(self) -> str:
        return "gcp_cost"

    @property
    def display_name(self) -> str:
        return "GCP 费用"

    @property
    def provider_name(self) -> str:
        return "GCP"

    @property
    def icon(self) -> str:
        return "attach_money"

    @property
    def icon_path(self) -> str:
        return "icons/gcp.png"

    @property
    def required_credentials(self) -> list[str]:
        return ["service_account_json", "project_id"]

    async def fetch_data(self) -> MonitorResult:
        """
        获取 GCP 本月费用信息
        """
        service_account_json = self.credentials.get("service_account_json", "")
        project_id = self.credentials.get("project_id", "")

        if not service_account_json or not project_id:
            return self._create_error_result("未配置 GCP 凭据")

        try:
            result = await run_blocking(
                self._fetch_cost_sync,
                service_account_json,
                project_id,
            )
            return result
        except Exception as e:
            return self._create_error_result(f"获取费用失败: {e!s}")

    def _fetch_cost_sync(
        self,
        service_account_json: str,
        project_id: str,
    ) -> MonitorResult:
        """同步获取费用数据（在线程池中执行）"""
        import json

        try:
            from google.cloud import billing_v1
            from google.oauth2 import service_account
        except ImportError:
            return self._create_error_result("请安装 google-cloud-billing 依赖")

        try:
            # 解析服务账号 JSON（可能是 JSON 字符串或文件路径）
            if service_account_json.startswith("{"):
                # JSON 字符串
                service_account_info = json.loads(service_account_json)
                credentials = service_account.Credentials.from_service_account_info(
                    service_account_info,
                    scopes=["https://www.googleapis.com/auth/cloud-billing"],
                )
            else:
                # 文件路径
                credentials = service_account.Credentials.from_service_account_file(
                    service_account_json,
                    scopes=["https://www.googleapis.com/auth/cloud-billing"],
                )

            # 创建 Cloud Billing 客户端
            client = billing_v1.CloudBillingClient(credentials=credentials)

            # 获取项目对应的计费账户
            project_name = f"projects/{project_id}"
            try:
                project_billing_info = client.get_project_billing_info(name=project_name)
            except Exception as e:
                error_msg = str(e)
                error_lower = error_msg.lower()
                if "permission" in error_lower or "forbidden" in error_lower or "403" in error_msg:
                    return self._create_error_result(
                        "权限不足：请在 GCP 控制台 -> Billing -> "
                        "账户管理中为服务账号添加 'Billing Account Viewer' 角色"
                    )
                elif "not found" in error_lower or "404" in error_msg:
                    return self._create_error_result(
                        f"项目 '{project_id}' 不存在或未关联计费账户"
                    )
                elif "invalid" in error_lower:
                    return self._create_error_result("服务账号凭据无效")
                elif "api" in error_lower and "enabled" in error_lower:
                    return self._create_error_result(
                        "请在 GCP 控制台启用 Cloud Billing API"
                    )
                return self._create_error_result(f"API 错误: {error_msg}")

            if not project_billing_info.billing_enabled:
                return self._create_success_result(
                    [
                        MetricData(
                            label="计费状态",
                            value="未启用",
                            status="warning",
                        )
                    ]
                )

            billing_account_name = project_billing_info.billing_account_name

            # 注意：完整的消费查询需要使用 BigQuery 导出或 Cloud Billing Budget API
            # 这里我们返回计费账户信息和状态
            metrics = [
                MetricData(
                    label="计费状态",
                    value="已启用",
                    status="normal",
                ),
                MetricData(
                    label="计费账户",
                    value=self._shorten_billing_account(billing_account_name),
                    status="normal",
                ),
                MetricData(
                    label="项目",
                    value=project_id,
                    status="normal",
                ),
            ]

            # 尝试获取计费账户详情
            try:
                billing_account = client.get_billing_account(name=billing_account_name)
                metrics.append(
                    MetricData(
                        label="计费账户名称",
                        value=billing_account.display_name or "未命名",
                        status="normal",
                    )
                )
            except Exception:
                pass  # 忽略获取计费账户详情的错误

            return self._create_success_result(metrics)

        except json.JSONDecodeError:
            return self._create_error_result("服务账号 JSON 格式无效")
        except FileNotFoundError:
            return self._create_error_result("服务账号文件不存在")
        except Exception as e:
            error_str = str(e).lower()
            if "permission" in error_str or "forbidden" in error_str:
                return self._create_error_result("需要 Billing Account Viewer 权限")
            elif "authentication" in error_str or "credential" in error_str:
                return self._create_error_result("GCP 凭据无效")
            return self._create_error_result(f"GCP 错误: {e!s}")

    def _shorten_billing_account(self, name: str) -> str:
        """缩短计费账户名称"""
        # billingAccounts/XXXXXX-XXXXXX-XXXXXX -> XXXXXX-...
        if name.startswith("billingAccounts/"):
            account_id = name.replace("billingAccounts/", "")
            if len(account_id) > 10:
                return account_id[:10] + "..."
            return account_id
        return name

    def render_card(self, data: MonitorResult) -> ft.Control:
        """渲染 GCP 费用监控卡片"""
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
                            ft.Icon(self.icon_value, color=ft.Colors.RED, size=24),
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
                    ft.Text("详情", size=12, color=ft.Colors.WHITE_54),
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
            border=ft.Border.all(1, ft.Colors.with_opacity(0.2, ft.Colors.RED)),
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
