"""
DigitalOcean 插件单元测试
"""

from unittest.mock import patch

import pytest

from core.models import MetricData, MonitorResult
from plugins.digitalocean.cost import DigitalOceanCostMonitor


class TestDigitalOceanCostMonitor:
    """DigitalOceanCostMonitor 测试类"""

    @pytest.fixture
    def monitor(self) -> DigitalOceanCostMonitor:
        """创建测试用监控实例"""
        return DigitalOceanCostMonitor(
            service_id="test_do_cost",
            alias="测试 DigitalOcean",
            credentials={
                "api_token": "test-token-12345",
            },
        )

    def test_plugin_id(self, monitor: DigitalOceanCostMonitor) -> None:
        """测试插件 ID"""
        assert monitor.plugin_id == "digitalocean_cost"

    def test_display_name(self, monitor: DigitalOceanCostMonitor) -> None:
        """测试显示名称"""
        assert monitor.display_name == "DigitalOcean 费用"

    def test_provider_name(self, monitor: DigitalOceanCostMonitor) -> None:
        """测试提供商名称"""
        assert monitor.provider_name == "DigitalOcean"

    def test_required_credentials(self, monitor: DigitalOceanCostMonitor) -> None:
        """测试必需凭据"""
        assert "api_token" in monitor.required_credentials

    def test_icon_path(self, monitor: DigitalOceanCostMonitor) -> None:
        """测试图标路径"""
        assert monitor.icon_path == "icons/digitalocean.png"

    @pytest.mark.asyncio
    async def test_fetch_data_no_credentials(self) -> None:
        """测试没有凭据时返回错误"""
        monitor = DigitalOceanCostMonitor(
            service_id="test",
            alias="测试",
            credentials={},
        )

        result = await monitor.fetch_data()

        assert result.overall_status == "error"
        assert "未配置 DigitalOcean API Token" in (result.raw_error or "")

    @pytest.mark.asyncio
    async def test_fetch_data_success(self, monitor: DigitalOceanCostMonitor) -> None:
        """测试成功获取账单信息"""
        mock_result = MonitorResult(
            plugin_id="digitalocean_cost",
            provider_name="DigitalOcean",
            metrics=[
                MetricData(label="本月费用 (MTD)", value="$25.50", unit="USD", status="normal"),
                MetricData(label="账户余额", value="$100.00", unit="USD", status="normal"),
                MetricData(label="待付款", value="$25.50", unit="USD", status="normal"),
            ],
        )

        with patch.object(monitor, "_fetch_billing_sync", return_value=mock_result):
            result = await monitor.fetch_data()

        assert result.overall_status == "normal"
        assert "$25.50" in result.metrics[0].value

    @pytest.mark.asyncio
    async def test_fetch_data_warning_balance(self, monitor: DigitalOceanCostMonitor) -> None:
        """测试余额不足时的警告状态"""
        mock_result = MonitorResult(
            plugin_id="digitalocean_cost",
            provider_name="DigitalOcean",
            metrics=[
                MetricData(label="本月费用 (MTD)", value="$75.00", unit="USD", status="warning"),
                MetricData(label="账户余额", value="-$50.00", unit="USD", status="warning"),
            ],
        )

        with patch.object(monitor, "_fetch_billing_sync", return_value=mock_result):
            result = await monitor.fetch_data()

        assert result.overall_status == "warning"

    @pytest.mark.asyncio
    async def test_fetch_data_auth_error(self, monitor: DigitalOceanCostMonitor) -> None:
        """测试认证失败"""
        mock_result = MonitorResult(
            plugin_id="digitalocean_cost",
            provider_name="DigitalOcean",
            metrics=[MetricData(label="错误", value="获取失败", status="error")],
            raw_error="API Token 无效",
        )

        with patch.object(monitor, "_fetch_billing_sync", return_value=mock_result):
            result = await monitor.fetch_data()

        assert result.overall_status == "error"
        assert "Token 无效" in (result.raw_error or "")

    def test_render_card(self, monitor: DigitalOceanCostMonitor) -> None:
        """测试渲染卡片"""
        data = MonitorResult(
            plugin_id="digitalocean_cost",
            provider_name="DigitalOcean",
            metrics=[
                MetricData(label="本月费用 (MTD)", value="$50.00", unit="USD", status="normal"),
            ],
        )

        card = monitor.render_card(data)
        assert card is not None

    def test_render_error_card(self, monitor: DigitalOceanCostMonitor) -> None:
        """测试渲染错误卡片"""
        data = MonitorResult(
            plugin_id="digitalocean_cost",
            provider_name="DigitalOcean",
            metrics=[],
            raw_error="测试错误",
        )

        card = monitor.render_card(data)
        assert card is not None

    def test_parse_billing_response(self, monitor: DigitalOceanCostMonitor) -> None:
        """测试解析账单响应"""
        balance_data = {
            "month_to_date_balance": "25.50",
            "account_balance": "-100.00",
            "month_to_date_usage": "25.50",
            "generated_at": "2026-01-05T12:00:00Z",
        }
        billing_history = [
            {
                "description": "Invoice for January 2026",
                "amount": "30.00",
                "type": "Invoice",
            },
            {
                "description": "Payment via Credit Card",
                "amount": "50.00",
                "type": "Payment",
            },
        ]

        result = monitor._parse_billing_response(balance_data, billing_history)

        assert result.overall_status == "normal"
        assert len(result.metrics) >= 3
        assert "25.50" in result.metrics[0].value
