"""
智谱 AI 插件单元测试
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from plugins.interface import MonitorStatus
from plugins.zhipu.balance import ZhipuBalanceMonitor


class TestZhipuBalanceMonitor:
    """ZhipuBalanceMonitor 测试类"""

    @pytest.fixture
    def monitor(self) -> ZhipuBalanceMonitor:
        """创建测试用监控实例"""
        return ZhipuBalanceMonitor(
            service_id="test_zhipu",
            alias="测试智谱",
            credentials={"api_key": "test-api-key"},
        )

    def test_display_name(self, monitor: ZhipuBalanceMonitor) -> None:
        """测试显示名称"""
        assert monitor.display_name == "智谱 AI"

    def test_icon(self, monitor: ZhipuBalanceMonitor) -> None:
        """测试图标"""
        assert monitor.icon == "smart_toy"

    def test_required_credentials(self, monitor: ZhipuBalanceMonitor) -> None:
        """测试必需凭据"""
        assert monitor.required_credentials == ["api_key"]

    @pytest.mark.asyncio
    async def test_fetch_data_no_api_key(self) -> None:
        """测试没有 API Key 时返回错误"""
        monitor = ZhipuBalanceMonitor(
            service_id="test",
            alias="测试",
            credentials={},
        )

        result = await monitor.fetch_data()

        assert result.status == MonitorStatus.ERROR
        assert "未配置 API Key" in (result.error_message or "")

    @pytest.mark.asyncio
    async def test_fetch_data_success(self, monitor: ZhipuBalanceMonitor) -> None:
        """测试成功获取余额"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "balance": 100.50,
            "currency": "CNY",
            "packages": [
                {
                    "name": "免费额度",
                    "remaining": 1000,
                    "total": 5000,
                    "expires_at": "2025-12-31T23:59:59Z",
                }
            ],
        }

        with patch("plugins.zhipu.balance.httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.get.return_value = mock_response
            mock_instance.__aenter__.return_value = mock_instance
            mock_instance.__aexit__.return_value = None
            mock_client.return_value = mock_instance

            result = await monitor.fetch_data()

        assert result.status == MonitorStatus.ONLINE
        assert "¥100.50" in result.kpi.value
        assert len(result.details) == 1
        assert result.details[0]["name"] == "免费额度"

    @pytest.mark.asyncio
    async def test_fetch_data_low_balance(self, monitor: ZhipuBalanceMonitor) -> None:
        """测试低余额警告"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "balance": 5.00,
            "currency": "CNY",
            "packages": [],
        }

        with patch("plugins.zhipu.balance.httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.get.return_value = mock_response
            mock_instance.__aenter__.return_value = mock_instance
            mock_instance.__aexit__.return_value = None
            mock_client.return_value = mock_instance

            result = await monitor.fetch_data()

        assert result.status == MonitorStatus.WARNING

    @pytest.mark.asyncio
    async def test_fetch_data_auth_error(self, monitor: ZhipuBalanceMonitor) -> None:
        """测试认证失败"""
        mock_response = MagicMock()
        mock_response.status_code = 401

        with patch("plugins.zhipu.balance.httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.get.return_value = mock_response
            mock_instance.__aenter__.return_value = mock_instance
            mock_instance.__aexit__.return_value = None
            mock_client.return_value = mock_instance

            result = await monitor.fetch_data()

        assert result.status == MonitorStatus.ERROR
        assert "无效或已过期" in (result.error_message or "")

    @pytest.mark.asyncio
    async def test_fetch_data_timeout(self, monitor: ZhipuBalanceMonitor) -> None:
        """测试请求超时"""
        import httpx

        with patch("plugins.zhipu.balance.httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.get.side_effect = httpx.TimeoutException("timeout")
            mock_instance.__aenter__.return_value = mock_instance
            mock_instance.__aexit__.return_value = None
            mock_client.return_value = mock_instance

            result = await monitor.fetch_data()

        assert result.status == MonitorStatus.ERROR
        assert "超时" in (result.error_message or "")

    def test_render_card(self, monitor: ZhipuBalanceMonitor) -> None:
        """测试渲染卡片"""
        from plugins.interface import KPIData, MonitorResult

        data = MonitorResult(
            status=MonitorStatus.ONLINE,
            kpi=KPIData(label="账户余额", value="¥100.00"),
            details=[],
            last_updated="2025-01-01T12:00:00",
        )

        card = monitor.render_card(data)

        # 验证返回了 Flet Control
        assert card is not None
