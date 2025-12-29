"""
Google Gemini API 配额监控插件

使用 Google GenAI SDK 监控 API 配额和使用情况。
"""

import flet as ft
from google import genai
from google.genai.errors import ClientError

from core.models import MetricData, MonitorResult
from core.plugin_mgr import register_plugin
from plugins.interface import BaseMonitor


@register_plugin("gemini_quota")
class GeminiQuotaMonitor(BaseMonitor):
    """
    Gemini API 配额监控

    监控 Google Gemini API 的使用情况和可用性。
    """

    @property
    def plugin_id(self) -> str:
        return "gemini_quota"

    @property
    def display_name(self) -> str:
        return "Gemini API"

    @property
    def provider_name(self) -> str:
        return "Google"

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
        """
        api_key = self.credentials.get("api_key", "")

        if not api_key:
            return self._create_error_result("未配置 Gemini API Key")

        try:
            # 创建客户端 (google-genai 支持原生异步)
            client = genai.Client(api_key=api_key)

            # 获取可用模型列表
            models_response = client.models.list()
            models = list(models_response)

            # 筛选出支持 generateContent 的模型
            available_models = []
            for model in models:
                supported_methods = getattr(model, "supported_generation_methods", [])
                if supported_methods and "generateContent" in supported_methods:
                    available_models.append(
                        {
                            "name": model.name.replace("models/", "") if model.name else "",
                            "display_name": getattr(model, "display_name", model.name),
                            "input_token_limit": getattr(model, "input_token_limit", 0),
                            "output_token_limit": getattr(model, "output_token_limit", 0),
                        }
                    )

            # 构建指标
            metrics = [
                MetricData(
                    label="可用模型",
                    value=str(len(available_models)),
                    unit="个",
                    status="normal",
                )
            ]

            # 添加模型详情
            for model_info in available_models[:5]:
                input_str = self._format_tokens(model_info["input_token_limit"])
                output_str = self._format_tokens(model_info["output_token_limit"])
                metrics.append(
                    MetricData(
                        label=self._shorten_model_name(model_info["name"]),
                        value=f"{input_str}/{output_str}",
                        status="normal",
                    )
                )

            return self._create_success_result(metrics)

        except ClientError as e:
            error_msg = str(e)
            if "API_KEY" in error_msg.upper() or "PERMISSION" in error_msg.upper():
                return self._create_error_result("API Key 无效或已过期")
            return self._create_error_result(f"API 错误: {error_msg}")

        except Exception as e:
            return self._create_error_result(f"未知错误: {e!s}")

    def render_card(self, data: MonitorResult) -> ft.Control:
        """渲染 Gemini API 监控卡片"""
        status_colors = {
            "normal": ft.Colors.GREEN_400,
            "warning": ft.Colors.AMBER,
            "error": ft.Colors.RED,
        }
        color = status_colors.get(data.overall_status, ft.Colors.GREY)

        main_metric = data.metrics[0] if data.metrics else None
        if not main_metric:
            return self._render_error_card(data)

        model_rows = []
        for metric in data.metrics[1:6]:
            model_rows.append(
                ft.Row(
                    controls=[
                        ft.Icon("smart_toy", size=14, color=ft.Colors.WHITE_54),
                        ft.Text(metric.label, size=11, color=ft.Colors.WHITE, expand=True),
                        ft.Text(metric.value, size=10, color=ft.Colors.WHITE_54),
                    ],
                    spacing=8,
                )
            )

        remaining = len(data.metrics) - 6
        if remaining > 0:
            model_rows.append(
                ft.Text(
                    f"... 还有 {remaining} 个模型", size=10, color=ft.Colors.WHITE_38, italic=True
                )
            )

        return ft.Container(
            content=ft.Column(
                controls=[
                    ft.Row(
                        controls=[
                            ft.Icon(self.icon, color=ft.Colors.PURPLE, size=24),
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
                    ft.Text("可用模型 (输入/输出限制)", size=12, color=ft.Colors.WHITE_54),
                    *model_rows,
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
            border=ft.Border.all(1, ft.Colors.with_opacity(0.2, ft.Colors.PURPLE)),
        )

    def _render_error_card(self, data: MonitorResult) -> ft.Control:
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
                    ft.Text(data.raw_error or "未知错误", size=12, color=ft.Colors.RED_300),
                ],
                spacing=8,
            ),
            padding=16,
            border_radius=12,
            bgcolor=ft.Colors.with_opacity(0.1, ft.Colors.RED),
        )

    def _shorten_model_name(self, name: str) -> str:
        prefixes = ["gemini-", "models/"]
        result = name
        for prefix in prefixes:
            if result.startswith(prefix):
                result = result[len(prefix) :]
        return result[:20] + "..." if len(result) > 20 else result

    def _format_tokens(self, count: int) -> str:
        if count >= 1_000_000:
            return f"{count // 1_000_000}M"
        elif count >= 1_000:
            return f"{count // 1_000}K"
        return str(count)
