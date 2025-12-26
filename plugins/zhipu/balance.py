"""
智谱 AI 余额监控插件

使用 httpx 调用智谱 API 获取账户余额和资源包信息。
"""

from datetime import datetime

import flet as ft
import httpx

from core.plugin_mgr import register_plugin
from plugins.interface import BaseMonitor, KPIData, MonitorResult, MonitorStatus


@register_plugin("zhipu_balance")
class ZhipuBalanceMonitor(BaseMonitor):
    """
    智谱 AI 余额监控

    监控智谱 AI 账户的余额和资源包状态。
    """

    API_BASE_URL = "https://open.bigmodel.cn/api/paas/v4"

    @property
    def display_name(self) -> str:
        return "智谱 AI"

    @property
    def icon(self) -> str:
        return "smart_toy"

    @property
    def required_credentials(self) -> list[str]:
        return ["api_key"]

    async def fetch_data(self) -> MonitorResult:
        """
        获取智谱 AI 账户余额信息

        Returns:
            MonitorResult: 包含余额信息的结果
        """
        api_key = self.credentials.get("api_key", "")

        if not api_key:
            return MonitorResult(
                status=MonitorStatus.ERROR,
                kpi=KPIData(label="余额", value="N/A"),
                details=[],
                error_message="未配置 API Key",
            )

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                # 调用余额查询接口
                response = await client.get(
                    f"{self.API_BASE_URL}/users/me/balance",
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json",
                    },
                )

                if response.status_code == 200:
                    data = response.json()
                    return self._parse_balance_response(data)
                elif response.status_code == 401:
                    return MonitorResult(
                        status=MonitorStatus.ERROR,
                        kpi=KPIData(label="余额", value="认证失败"),
                        details=[],
                        error_message="API Key 无效或已过期",
                    )
                else:
                    return MonitorResult(
                        status=MonitorStatus.ERROR,
                        kpi=KPIData(label="余额", value="请求失败"),
                        details=[],
                        error_message=f"HTTP {response.status_code}: {response.text}",
                    )

        except httpx.TimeoutException:
            return MonitorResult(
                status=MonitorStatus.ERROR,
                kpi=KPIData(label="余额", value="超时"),
                details=[],
                error_message="请求超时，请检查网络连接",
            )
        except httpx.RequestError as e:
            return MonitorResult(
                status=MonitorStatus.ERROR,
                kpi=KPIData(label="余额", value="网络错误"),
                details=[],
                error_message=f"网络请求失败: {e!s}",
            )

    def _parse_balance_response(self, data: dict) -> MonitorResult:
        """解析余额响应数据"""
        # 智谱 API 返回格式示例:
        # {
        #     "balance": 100.00,
        #     "currency": "CNY",
        #     "packages": [
        #         {"name": "资源包1", "remaining": 1000, "total": 5000, "expires_at": "..."}
        #     ]
        # }

        balance = data.get("balance", 0)
        currency = data.get("currency", "CNY")
        packages = data.get("packages", [])

        # 确定状态
        if balance <= 0:
            status = MonitorStatus.ERROR
        elif balance < 10:
            status = MonitorStatus.WARNING
        else:
            status = MonitorStatus.ONLINE

        # 构建详情列表
        details = []
        for pkg in packages:
            remaining = pkg.get("remaining", 0)
            total = pkg.get("total", 0)
            expires_at = pkg.get("expires_at", "")

            # 解析过期时间
            expiry_info = ""
            if expires_at:
                try:
                    exp_date = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
                    days_left = (exp_date - datetime.now(exp_date.tzinfo)).days
                    if days_left < 0:
                        expiry_info = "已过期"
                    elif days_left < 7:
                        expiry_info = f"即将过期 ({days_left} 天)"
                    else:
                        expiry_info = f"剩余 {days_left} 天"
                except ValueError:
                    expiry_info = expires_at

            details.append({
                "name": pkg.get("name", "资源包"),
                "remaining": remaining,
                "total": total,
                "usage_percent": (total - remaining) / total * 100 if total > 0 else 0,
                "expiry": expiry_info,
            })

        currency_symbol = "¥" if currency == "CNY" else "$"

        return MonitorResult(
            status=status,
            kpi=KPIData(
                label="账户余额",
                value=f"{currency_symbol}{balance:.2f}",
                unit=currency,
                status=status,
            ),
            details=details,
            last_updated=datetime.now().isoformat(),
        )

    def render_card(self, data: MonitorResult) -> ft.Control:
        """渲染智谱 AI 监控卡片"""
        # 状态颜色映射
        status_colors = {
            MonitorStatus.ONLINE: ft.Colors.GREEN_400,
            MonitorStatus.WARNING: ft.Colors.AMBER,
            MonitorStatus.ERROR: ft.Colors.RED,
            MonitorStatus.LOADING: ft.Colors.GREY,
        }

        color = status_colors.get(data.status, ft.Colors.GREY)

        # 构建资源包详情
        package_rows = []
        for detail in data.details:
            usage_percent = detail.get("usage_percent", 0)
            package_rows.append(
                ft.Column(
                    controls=[
                        ft.Text(
                            detail.get("name", "资源包"),
                            size=12,
                            color=ft.Colors.WHITE_70,
                        ),
                        ft.ProgressBar(
                            value=usage_percent / 100,
                            color=ft.Colors.BLUE_400,
                            bgcolor=ft.Colors.WHITE_10,
                        ),
                        ft.Row(
                            controls=[
                                ft.Text(
                                    f"剩余: {detail.get('remaining', 0):,}",
                                    size=10,
                                    color=ft.Colors.WHITE_54,
                                ),
                                ft.Text(
                                    detail.get("expiry", ""),
                                    size=10,
                                    color=(
                                        ft.Colors.AMBER
                                        if "即将" in str(detail.get("expiry", ""))
                                        else ft.Colors.WHITE_54
                                    ),
                                ),
                            ],
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        ),
                    ],
                    spacing=4,
                )
            )

        return ft.Container(
            content=ft.Column(
                controls=[
                    # 标题行
                    ft.Row(
                        controls=[
                            ft.Icon(self.icon, color=color, size=24),
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
                    # 资源包详情
                    *package_rows,
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
            border=ft.Border.all(1, ft.Colors.with_opacity(0.2, color)),
        )
