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
        # service_account_json: 服务账号 JSON
        # gcp_bigquery_table: BigQuery 导出表（格式: project.dataset.table）
        return ["service_account_json", "gcp_bigquery_table"]

    async def fetch_data(self) -> MonitorResult:
        """
        获取 GCP 费用信息（通过 BigQuery 导出）
        """
        import asyncio

        service_account_json = self.credentials.get("service_account_json", "")
        bigquery_table = self.credentials.get("gcp_bigquery_table", "")

        if not service_account_json:
            return self._create_error_result("未配置服务账号 JSON")

        if not bigquery_table:
            return self._create_error_result("未配置 BigQuery 费用导出表")

        try:
            # 添加 30 秒超时
            result = await asyncio.wait_for(
                run_blocking(
                    self._fetch_cost_from_bigquery,
                    service_account_json,
                    bigquery_table,
                ),
                timeout=30.0,
            )
            return result
        except TimeoutError:
            return self._create_error_result("请求超时（30秒），请检查网络连接")
        except Exception as e:
            return self._create_error_result(f"获取费用失败: {e!s}")

    def _fetch_cost_from_bigquery(
        self,
        service_account_json: str,
        bigquery_table: str,
    ) -> MonitorResult:
        """从 BigQuery 获取费用数据"""
        import json
        from datetime import datetime

        try:
            from google.cloud import bigquery
            from google.oauth2 import service_account
        except ImportError:
            return self._create_error_result(
                "请安装 google-cloud-bigquery 依赖"
            )

        try:
            # 解析服务账号 JSON
            if service_account_json.startswith("{"):
                service_account_info = json.loads(service_account_json)
                credentials = service_account.Credentials.from_service_account_info(
                    service_account_info,
                )
            else:
                credentials = service_account.Credentials.from_service_account_file(
                    service_account_json,
                )

            # 创建 BigQuery 客户端
            client = bigquery.Client(credentials=credentials)

            # 获取当前月份
            now = datetime.now()
            current_month = now.strftime("%Y-%m")

            # 构造查询 - 获取当月费用总计和按服务分类
            # 注意: credits.amount 是负数，表示折扣金额
            # 实际费用 = cost + credits.amount
            # 排序：优先展示有实际费用的服务，其次按原价降序
            # 构造查询 - 优化排序逻辑：
            # 1. 优先展示无折扣且有实际支出的 (>= $0.01)
            # 2. 其次展示有折扣但仍有支出的
            # 3. 最后按原价排序
            query = f"""
            WITH ServiceCosts AS (
                SELECT
                    service.description AS service_name,
                    SUM(cost) AS gross_cost,
                    SUM(IFNULL((SELECT SUM(c.amount) FROM UNNEST(credits) AS c), 0))
                        AS total_credits,
                    currency
                FROM `{bigquery_table}`
                WHERE invoice.month = '{current_month.replace('-', '')}'
                GROUP BY service.description, currency
            )
            SELECT
                service_name,
                gross_cost,
                total_credits,
                gross_cost + total_credits AS net_cost,
                currency
            ORDER BY
                CASE
                    -- 无折扣且实际支出 >= 1美分
                    WHEN total_credits = 0 AND gross_cost >= 0.005 THEN 0
                    -- 有折扣但实际支出 >= 1美分
                    WHEN total_credits != 0 AND (gross_cost + total_credits) >= 0.005 THEN 1
                    -- 其余情况（如 0元项）
                    ELSE 2
                END,
                (gross_cost + total_credits) DESC,
                gross_cost DESC
            LIMIT 10
            """

            try:
                query_job = client.query(query)
                results = list(query_job.result())
            except Exception as e:
                error_msg = str(e)
                error_lower = error_msg.lower()

                if "not found" in error_lower or "404" in error_msg:
                    return self._create_error_result(
                        f"表 '{bigquery_table}' 不存在，请检查表名格式"
                    )
                elif "permission" in error_lower or "403" in error_msg:
                    return self._create_error_result(
                        "权限不足：请为服务账号添加 BigQuery Data Viewer 角色"
                    )
                elif "access denied" in error_lower:
                    return self._create_error_result(
                        "访问被拒绝：请检查服务账号权限"
                    )
                return self._create_error_result(f"BigQuery 错误: {error_msg}")

            if not results:
                return self._create_success_result(
                    [
                        MetricData(
                            label="本月费用",
                            value="$0.00",
                            status="normal",
                        ),
                        MetricData(
                            label="提示",
                            value="本月暂无费用数据",
                            status="normal",
                        ),
                    ]
                )

            # 计算总费用（原价、折扣、实际）
            sum(row.gross_cost for row in results)
            total_credits = sum(row.total_credits for row in results)
            total_net = sum(row.net_cost for row in results)
            currency = results[0].currency if results else "USD"

            # 构建指标
            metrics = [
                MetricData(
                    label="本月费用",
                    value=f"${total_net:.2f}" if total_net >= 0 else f"-${abs(total_net):.2f}",
                    unit=currency,
                    status=(
                        "normal" if total_net < 100
                        else ("warning" if total_net < 500 else "error")
                    ),
                    trend="up" if total_net > 0 else "flat",
                ),
            ]

            # 如果有折扣，显示折扣信息
            if total_credits < 0:
                metrics.append(
                    MetricData(
                        label="折扣优惠",
                        value=f"-${abs(total_credits):.2f}",
                        status="normal",
                    )
                )

            # 添加服务明细（最多 4 个）- 显示原价
            for row in results[:4]:
                service_name = self._shorten_name(row.service_name or "未知服务")
                # 显示原价（gross_cost），让用户了解各服务实际消费
                cost_value = row.gross_cost
                metrics.append(
                    MetricData(
                        label=service_name,
                        value=(
                            f"${cost_value:.2f}" if cost_value >= 0
                            else f"-${abs(cost_value):.2f}"
                        ),
                        status="normal",
                    )
                )

            return self._create_success_result(metrics)

        except json.JSONDecodeError:
            return self._create_error_result("服务账号 JSON 格式无效")
        except FileNotFoundError:
            return self._create_error_result("服务账号文件不存在")
        except Exception as e:
            error_str = str(e).lower()
            if "permission" in error_str or "forbidden" in error_str:
                return self._create_error_result("需要 BigQuery Data Viewer 权限")
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
