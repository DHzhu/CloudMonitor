"""
Gemini 插件单元测试
"""

from unittest.mock import MagicMock, patch

import pytest

from plugins.gemini.quota import GeminiQuotaMonitor
from plugins.interface import KPIData, MonitorResult, MonitorStatus


class TestGeminiQuotaMonitor:
    """GeminiQuotaMonitor 测试类"""

    @pytest.fixture
    def monitor(self) -> GeminiQuotaMonitor:
        """创建测试用监控实例"""
        return GeminiQuotaMonitor(
            service_id="test_gemini",
            alias="测试 Gemini",
            credentials={
                "api_key": "test-api-key",
            },
        )

    def test_display_name(self, monitor: GeminiQuotaMonitor) -> None:
        """测试显示名称"""
        assert monitor.display_name == "Gemini API"

    def test_required_credentials(self, monitor: GeminiQuotaMonitor) -> None:
        """测试必需凭据"""
        assert "api_key" in monitor.required_credentials

    @pytest.mark.asyncio
    async def test_fetch_data_no_credentials(self) -> None:
        """测试没有凭据时返回错误"""
        monitor = GeminiQuotaMonitor(
            service_id="test",
            alias="测试",
            credentials={},
        )

        result = await monitor.fetch_data()

        assert result.status == MonitorStatus.ERROR
        assert "未配置 Gemini API Key" in (result.error_message or "")

    @pytest.mark.asyncio
    async def test_fetch_data_auth_error(self, monitor: GeminiQuotaMonitor) -> None:
        """测试认证失败"""
        with patch("plugins.gemini.quota.genai.Client") as mock_client_class:
            mock_client = MagicMock()
            # 模拟 API 错误
            mock_client.models.list.side_effect = Exception("API_KEY invalid or PERMISSION denied")
            mock_client_class.return_value = mock_client

            result = await monitor.fetch_data()

        assert result.status == MonitorStatus.ERROR
        assert "错误" in result.kpi.value or "失败" in result.kpi.value

    @pytest.mark.asyncio
    async def test_fetch_data_success(self, monitor: GeminiQuotaMonitor) -> None:
        """测试成功获取模型列表"""
        # 模拟模型对象
        mock_model1 = MagicMock()
        mock_model1.name = "models/gemini-1.5-pro"
        mock_model1.display_name = "Gemini 1.5 Pro"
        mock_model1.supported_generation_methods = ["generateContent"]
        mock_model1.input_token_limit = 1000000
        mock_model1.output_token_limit = 8192

        mock_model2 = MagicMock()
        mock_model2.name = "models/gemini-1.5-flash"
        mock_model2.display_name = "Gemini 1.5 Flash"
        mock_model2.supported_generation_methods = ["generateContent"]
        mock_model2.input_token_limit = 1000000
        mock_model2.output_token_limit = 8192

        # 不支持 generateContent 的模型
        mock_model3 = MagicMock()
        mock_model3.name = "models/embedding-001"
        mock_model3.display_name = "Embedding"
        mock_model3.supported_generation_methods = ["embedContent"]

        with patch("plugins.gemini.quota.genai.Client") as mock_client_class:
            mock_client = MagicMock()
            mock_client.models.list.return_value = [mock_model1, mock_model2, mock_model3]
            mock_client_class.return_value = mock_client

            result = await monitor.fetch_data()

        assert result.status == MonitorStatus.ONLINE
        assert result.kpi.value == "2"  # 只有两个模型支持 generateContent
        assert len(result.details) == 2

    def test_render_card(self, monitor: GeminiQuotaMonitor) -> None:
        """测试渲染卡片"""
        data = MonitorResult(
            status=MonitorStatus.ONLINE,
            kpi=KPIData(label="可用模型", value="5", unit="个"),
            details=[
                {
                    "name": "gemini-1.5-pro",
                    "display_name": "Gemini 1.5 Pro",
                    "input_token_limit": 1000000,
                    "output_token_limit": 8192,
                },
            ],
            last_updated="2025-01-01T12:00:00",
        )

        card = monitor.render_card(data)
        assert card is not None

    def test_shorten_model_name(self, monitor: GeminiQuotaMonitor) -> None:
        """测试模型名称缩短"""
        assert monitor._shorten_model_name("gemini-1.5-pro") == "1.5-pro"
        # models/ 前缀会被移除，但 gemini- 前缀不会被重复移除
        assert monitor._shorten_model_name("models/gemini-2.0") == "gemini-2.0"

    def test_format_tokens(self, monitor: GeminiQuotaMonitor) -> None:
        """测试 token 数量格式化"""
        assert monitor._format_tokens(1000000) == "1M"
        assert monitor._format_tokens(32000) == "32K"
        assert monitor._format_tokens(500) == "500"
