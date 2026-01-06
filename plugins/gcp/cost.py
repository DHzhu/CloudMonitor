"""
GCP Cloud Billing Budgets 费用监控插件

使用 Google Cloud Billing Budgets API 获取预算和支出信息。
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

    使用 Cloud Billing Budgets API 监控预算和实际支出。
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
        return ["service_account_json", "gcp_billing_account"]

    async def fetch_data(self) -> MonitorResult:
        """
        获取 GCP 预算和支出信息
        """
        import asyncio

        service_account_json = self.credentials.get("service_account_json", "")
        billing_account_id = self.credentials.get("gcp_billing_account", "")

        if not service_account_json or not billing_account_id:
            return self._create_error_result("未配置 GCP 凭据")

        try:
            # 添加 30 秒超时
            result = await asyncio.wait_for(
                run_blocking(
                    self._fetch_budgets_sync,
                    service_account_json,
                    billing_account_id,
                ),
                timeout=30.0,
            )
            return result
        except asyncio.TimeoutError:
            return self._create_error_result("请求超时（30秒），请检查网络连接")
        except Exception as e:
            return self._create_error_result(f"获取费用失败: {e!s}")

    def _fetch_budgets_sync(
        self,
        service_account_json: str,
        billing_account_id: str,
    ) -> MonitorResult:
        """同步获取预算数据（在线程池中执行）"""
        import json
        from datetime import datetime, timedelta, timezone

        try:
            from google.cloud.billing import budgets_v1
            from google.cloud import monitoring_v3
            from google.oauth2 import service_account
        except ImportError:
            return self._create_error_result(
                "请安装 google-cloud-billing-budgets 和 google-cloud-monitoring 依赖"
            )

        try:
            # 解析服务账号 JSON
            if service_account_json.startswith("{"):
                service_account_info = json.loads(service_account_json)
                project_id = service_account_info.get("project_id", "")
                credentials = service_account.Credentials.from_service_account_info(
                    service_account_info,
                    scopes=[
                        "https://www.googleapis.com/auth/cloud-billing",
                        "https://www.googleapis.com/auth/monitoring.read",
                    ],
                )
            else:
                credentials = service_account.Credentials.from_service_account_file(
                    service_account_json,
                    scopes=[
                        "https://www.googleapis.com/auth/cloud-billing",
                        "https://www.googleapis.com/auth/monitoring.read",
                    ],
                )
                project_id = ""

            # 创建 Budgets 客户端
            budget_client = budgets_v1.BudgetServiceClient(credentials=credentials)

            # 格式化计费账户名称
            if not billing_account_id.startswith("billingAccounts/"):
                parent = f"billingAccounts/{billing_account_id}"
            else:
                parent = billing_account_id

            # 列出所有预算
            try:
                budgets = list(budget_client.list_budgets(parent=parent))
            except Exception as e:
                error_msg = str(e)
                error_lower = error_msg.lower()
                if "permission" in error_lower or "forbidden" in error_lower or "403" in error_msg:
                    return self._create_error_result(
                        "权限不足：请为服务账号添加 'Billing Account Viewer' 角色"
                    )
                elif "not found" in error_lower or "404" in error_msg:
                    return self._create_error_result(
                        f"计费账户 '{billing_account_id}' 不存在"
                    )
                elif "api" in error_lower and "enabled" in error_lower:
                    return self._create_error_result(
                        "请在 GCP 控制台启用 Cloud Billing Budget API"
                    )
                return self._create_error_result(f"API 错误: {error_msg}")

            if not budgets:
                return self._create_success_result(
                    [
                        MetricData(
                            label="预算状态",
                            value="无预算",
                            status="warning",
                        ),
                        MetricData(
                            label="提示",
                            value="请在 GCP 控制台创建预算",
                            status="normal",
                        ),
                    ]
                )

            # 尝试获取预算使用率（通过 Cloud Monitoring）
            budget_usage = {}
            if project_id:
                try:
                    monitoring_client = monitoring_v3.MetricServiceClient(credentials=credentials)
                    
                    # 查询预算使用率指标
                    now = datetime.now(timezone.utc)
                    interval = monitoring_v3.TimeInterval(
                        end_time={"seconds": int(now.timestamp())},
                        start_time={"seconds": int((now - timedelta(hours=1)).timestamp())},
                    )
                    
                    # 构造查询
                    results = monitoring_client.list_time_series(
                        request={
                            "name": f"projects/{project_id}",
                            "filter": 'metric.type = "billing.googleapis.com/billing/budget/amount_used_ratio"',
                            "interval": interval,
                            "view": monitoring_v3.ListTimeSeriesRequest.TimeSeriesView.FULL,
                        }
                    )
                    
                    for series in results:
                        budget_name = series.resource.labels.get("budget_name", "")
                        if series.points:
                            # 获取最新的使用率
                            usage_ratio = series.points[0].value.double_value
                            budget_usage[budget_name] = usage_ratio
                            
                except Exception as e:
                    # Cloud Monitoring 查询失败，继续使用预算信息
                    print(f"Cloud Monitoring 查询失败: {e}")

            # 解析预算信息
            total_budget = 0.0
            total_spent = 0.0
            budget_details = []

            for budget in budgets:
                budget_name = budget.display_name or "未命名预算"
                budget_id = budget.name.split("/")[-1] if budget.name else ""
                
                # 获取预算金额
                budget_amount = 0.0
                currency = "USD"
                if budget.amount and budget.amount.specified_amount:
                    budget_amount = float(budget.amount.specified_amount.units or 0)
                    budget_amount += float(budget.amount.specified_amount.nanos or 0) / 1e9
                    currency = budget.amount.specified_amount.currency_code or "USD"
                
                if budget_amount > 0:
                    total_budget += budget_amount
                
                # 获取使用率
                usage_ratio = budget_usage.get(budget_id, budget_usage.get(budget_name, None))
                spent_amount = None
                if usage_ratio is not None and budget_amount > 0:
                    spent_amount = budget_amount * usage_ratio
                    total_spent += spent_amount

                # 构建预算详情
                budget_details.append({
                    "name": budget_name,
                    "amount": budget_amount,
                    "currency": currency,
                    "usage_ratio": usage_ratio,
                    "spent": spent_amount,
                })

            # 汇总信息
            summary_metrics = []
            
            # 如果有支出数据，显示总支出
            if total_spent > 0:
                usage_percent = (total_spent / total_budget * 100) if total_budget > 0 else 0
                status = "normal" if usage_percent < 80 else ("warning" if usage_percent < 100 else "error")
                summary_metrics.append(
                    MetricData(
                        label="本月支出",
                        value=f"${total_spent:.2f}",
                        unit=f"/ ${total_budget:.2f}",
                        status=status,
                        trend="up" if usage_percent > 50 else "flat",
                    )
                )
                summary_metrics.append(
                    MetricData(
                        label="使用进度",
                        value=f"{usage_percent:.1f}%",
                        status=status,
                    )
                )
            else:
                # 没有支出数据，只显示预算信息
                summary_metrics.append(
                    MetricData(
                        label="预算总数",
                        value=str(len(budgets)),
                        unit="个",
                        status="normal",
                    )
                )
                if total_budget > 0:
                    summary_metrics.append(
                        MetricData(
                            label="预算总额",
                            value=f"${total_budget:.2f}",
                            unit="USD",
                            status="normal",
                        )
                    )

            # 添加各预算详情（最多显示 3 个）
            for detail in budget_details[:3]:
                if detail["spent"] is not None:
                    usage_pct = detail["usage_ratio"] * 100 if detail["usage_ratio"] else 0
                    status = "normal" if usage_pct < 80 else ("warning" if usage_pct < 100 else "error")
                    value = f"${detail['spent']:.2f} / ${detail['amount']:.2f} ({usage_pct:.0f}%)"
                elif detail["amount"] > 0:
                    value = f"${detail['amount']:.2f}"
                    status = "normal"
                else:
                    continue
                    
                summary_metrics.append(
                    MetricData(
                        label=self._shorten_name(detail["name"]),
                        value=value,
                        status=status,
                    )
                )

            return self._create_success_result(summary_metrics)

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

    def _shorten_name(self, name: str) -> str:
        """缩短名称"""
        return name[:20] + "..." if len(name) > 20 else name

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
                        ft.Text(
                            f"{metric.value} {metric.unit or ''}".strip(),
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
                    ft.Text("预算详情", size=12, color=ft.Colors.WHITE_54),
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
