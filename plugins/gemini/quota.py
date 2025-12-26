"""
Google Gemini API 配额监控插件

使用 Google GenAI SDK 监控 API 配额和使用情况。
"""

from datetime import datetime

import flet as ft
from google import genai
from google.genai.errors import ClientError

from core.plugin_mgr import register_plugin
from plugins.interface import BaseMonitor, KPIData, MonitorResult, MonitorStatus


@register_plugin("gemini_quota")
class GeminiQuotaMonitor(BaseMonitor):
    """
    Gemini API 配额监控

    监控 Google Gemini API 的使用情况和可用性。
    """

    @property
    def display_name(self) -> str:
        return "Gemini API"

    @property
    def icon(self) -> str:
        return "auto_awesome"

    @property
    def required_credentials(self) -> list[str]:
        return ["api_key"]

    async def fetch_data(self) -> MonitorResult:
        """
        获取 Gemini API 状态信息

        通过列出可用模型来验证 API 可用性。

        Returns:
            MonitorResult: 包含 API 状态的结果
        """
        api_key = self.credentials.get("api_key", "")

        if not api_key:
            return MonitorResult(
                status=MonitorStatus.ERROR,
                kpi=KPIData(label="API 状态", value="N/A"),
                details=[],
                error_message="未配置 Gemini API Key",
            )

        try:
            # 创建客户端
            client = genai.Client(api_key=api_key)

            # 获取可用模型列表
            models_response = client.models.list()
            models = list(models_response)

            # 筛选出支持 generateContent 的模型
            available_models = []
            for model in models:
                # 检查模型是否支持内容生成
                supported_methods = getattr(model, "supported_generation_methods", [])
                if supported_methods and "generateContent" in supported_methods:
                    available_models.append({
                        "name": model.name.replace("models/", "") if model.name else "",
                        "display_name": getattr(model, "display_name", model.name),
                        "input_token_limit": getattr(model, "input_token_limit", 0),
                        "output_token_limit": getattr(model, "output_token_limit", 0),
                    })

            return MonitorResult(
                status=MonitorStatus.ONLINE,
                kpi=KPIData(
                    label="可用模型",
                    value=str(len(available_models)),
                    unit="个",
                    status=MonitorStatus.ONLINE,
                ),
                details=available_models,
                last_updated=datetime.now().isoformat(),
            )

        except ClientError as e:
            error_msg = str(e)
            if "API_KEY" in error_msg.upper() or "PERMISSION" in error_msg.upper():
                return MonitorResult(
                    status=MonitorStatus.ERROR,
                    kpi=KPIData(label="API 状态", value="认证失败"),
                    details=[],
                    error_message="API Key 无效或已过期",
                )
            return MonitorResult(
                status=MonitorStatus.ERROR,
                kpi=KPIData(label="API 状态", value="请求失败"),
                details=[],
                error_message=f"API 错误: {error_msg}",
            )

        except Exception as e:
            return MonitorResult(
                status=MonitorStatus.ERROR,
                kpi=KPIData(label="API 状态", value="错误"),
                details=[],
                error_message=f"未知错误: {e!s}",
            )

    def render_card(self, data: MonitorResult) -> ft.Control:
        """渲染 Gemini API 监控卡片"""
        status_colors = {
            MonitorStatus.ONLINE: ft.Colors.GREEN_400,
            MonitorStatus.WARNING: ft.Colors.AMBER,
            MonitorStatus.ERROR: ft.Colors.RED,
            MonitorStatus.LOADING: ft.Colors.GREY,
        }

        color = status_colors.get(data.status, ft.Colors.GREY)

        # 构建模型列表
        model_rows = []
        for detail in data.details[:5]:  # 只显示前 5 个模型
            input_limit = detail.get("input_token_limit", 0)
            output_limit = detail.get("output_token_limit", 0)

            # 格式化 token 限制
            input_str = self._format_tokens(input_limit)
            output_str = self._format_tokens(output_limit)

            model_rows.append(
                ft.Row(
                    controls=[
                        ft.Icon("smart_toy", size=14, color=ft.Colors.WHITE_54),
                        ft.Text(
                            self._shorten_model_name(detail.get("name", "")),
                            size=11,
                            color=ft.Colors.WHITE,
                            expand=True,
                        ),
                        ft.Text(
                            f"{input_str}/{output_str}",
                            size=10,
                            color=ft.Colors.WHITE_54,
                        ),
                    ],
                    spacing=8,
                )
            )

        # 如果有更多模型
        remaining = len(data.details) - 5
        if remaining > 0:
            model_rows.append(
                ft.Text(
                    f"... 还有 {remaining} 个模型",
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
                            ft.Icon(self.icon, color=ft.Colors.PURPLE, size=24),
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
                    # 模型列表标题
                    ft.Text(
                        "可用模型 (输入/输出限制)",
                        size=12,
                        color=ft.Colors.WHITE_54,
                    ),
                    *model_rows,
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
            border=ft.Border.all(1, ft.Colors.with_opacity(0.2, ft.Colors.PURPLE)),
        )

    def _shorten_model_name(self, name: str) -> str:
        """缩短模型名称"""
        # 移除常见前缀
        prefixes = ["gemini-", "models/"]
        result = name
        for prefix in prefixes:
            if result.startswith(prefix):
                result = result[len(prefix) :]
        return result[:20] + "..." if len(result) > 20 else result

    def _format_tokens(self, count: int) -> str:
        """格式化 token 数量"""
        if count >= 1_000_000:
            return f"{count // 1_000_000}M"
        elif count >= 1_000:
            return f"{count // 1_000}K"
        return str(count)
