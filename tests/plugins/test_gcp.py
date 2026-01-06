"""
GCP 插件单元测试
"""

from unittest.mock import patch

import pytest

from core.models import MetricData, MonitorResult
from plugins.gcp.cost import GCPCostMonitor


class TestGCPCostMonitor:
    """GCPCostMonitor 测试类"""

    @pytest.fixture
    def monitor(self) -> GCPCostMonitor:
        """创建测试用监控实例"""
        return GCPCostMonitor(
            service_id="test_gcp_cost",
            alias="测试 GCP",
            credentials={
                "service_account_json": '{"type": "service_account", "project_id": "test"}',
                "billing_account_id": "XXXXXX-XXXXXX-XXXXXX",
            },
        )

    def test_plugin_id(self, monitor: GCPCostMonitor) -> None:
        """测试插件 ID"""
        assert monitor.plugin_id == "gcp_cost"

    def test_display_name(self, monitor: GCPCostMonitor) -> None:
        """测试显示名称"""
        assert monitor.display_name == "GCP 费用"

    def test_provider_name(self, monitor: GCPCostMonitor) -> None:
        """测试提供商名称"""
        assert monitor.provider_name == "GCP"

    def test_required_credentials(self, monitor: GCPCostMonitor) -> None:
        """测试必需凭据"""
        assert "service_account_json" in monitor.required_credentials
        assert "billing_account_id" in monitor.required_credentials

    def test_icon_path(self, monitor: GCPCostMonitor) -> None:
        """测试图标路径"""
        assert monitor.icon_path == "icons/gcp.png"

    @pytest.mark.asyncio
    async def test_fetch_data_no_credentials(self) -> None:
        """测试没有凭据时返回错误"""
        monitor = GCPCostMonitor(
            service_id="test",
            alias="测试",
            credentials={},
        )

        result = await monitor.fetch_data()

        assert result.overall_status == "error"
        assert "未配置 GCP 凭据" in (result.raw_error or "")

    @pytest.mark.asyncio
    async def test_fetch_data_success(self, monitor: GCPCostMonitor) -> None:
        """测试成功获取预算信息"""
        mock_result = MonitorResult(
            plugin_id="gcp_cost",
            provider_name="GCP",
            metrics=[
                MetricData(label="预算总数", value="2", unit="个", status="normal"),
                MetricData(label="预算总额", value="$100.00", unit="USD", status="normal"),
            ],
        )

        with patch.object(monitor, "_fetch_budgets_sync", return_value=mock_result):
            result = await monitor.fetch_data()

        assert result.overall_status == "normal"
        assert result.metrics[0].value == "2"

    @pytest.mark.asyncio
    async def test_fetch_data_no_budgets(self, monitor: GCPCostMonitor) -> None:
        """测试无预算时返回警告"""
        mock_result = MonitorResult(
            plugin_id="gcp_cost",
            provider_name="GCP",
            metrics=[
                MetricData(label="预算状态", value="无预算", status="warning"),
            ],
        )

        with patch.object(monitor, "_fetch_budgets_sync", return_value=mock_result):
            result = await monitor.fetch_data()

        assert result.overall_status == "warning"

    @pytest.mark.asyncio
    async def test_fetch_data_auth_error(self, monitor: GCPCostMonitor) -> None:
        """测试认证失败"""
        mock_result = MonitorResult(
            plugin_id="gcp_cost",
            provider_name="GCP",
            metrics=[MetricData(label="错误", value="获取失败", status="error")],
            raw_error="GCP 凭据无效",
        )

        with patch.object(monitor, "_fetch_budgets_sync", return_value=mock_result):
            result = await monitor.fetch_data()

        assert result.overall_status == "error"
        assert "凭据无效" in (result.raw_error or "")

    @pytest.mark.asyncio
    async def test_fetch_data_timeout(self, monitor: GCPCostMonitor) -> None:
        """测试请求超时"""
        import asyncio

        async def mock_timeout(*args: object, **kwargs: object) -> None:
            raise asyncio.TimeoutError()

        with patch("plugins.gcp.cost.run_blocking", side_effect=mock_timeout):
            result = await monitor.fetch_data()

        assert result.overall_status == "error"
        assert "超时" in (result.raw_error or "")

    def test_render_card(self, monitor: GCPCostMonitor) -> None:
        """测试渲染卡片"""
        data = MonitorResult(
            plugin_id="gcp_cost",
            provider_name="GCP",
            metrics=[
                MetricData(label="预算总数", value="2", unit="个", status="normal"),
            ],
        )

        card = monitor.render_card(data)
        assert card is not None

    def test_render_error_card(self, monitor: GCPCostMonitor) -> None:
        """测试渲染错误卡片"""
        data = MonitorResult(
            plugin_id="gcp_cost",
            provider_name="GCP",
            metrics=[],
            raw_error="测试错误",
        )

        card = monitor.render_card(data)
        assert card is not None

    def test_shorten_name(self, monitor: GCPCostMonitor) -> None:
        """测试名称缩短"""
        short = monitor._shorten_name("短名称")
        assert short == "短名称"

        # 使用超过 20 个字符的名称
        long_name = "This is a very long budget name that needs truncation"
        shortened = monitor._shorten_name(long_name)
        assert len(shortened) <= 23  # 20 + "..."
        assert shortened.endswith("...")
