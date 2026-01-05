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
                "project_id": "test-project",
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
        assert "project_id" in monitor.required_credentials

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
        """测试成功获取计费状态"""
        mock_result = MonitorResult(
            plugin_id="gcp_cost",
            provider_name="GCP",
            metrics=[
                MetricData(label="计费状态", value="已启用", status="normal"),
                MetricData(label="计费账户", value="XXXXXX-...", status="normal"),
            ],
        )

        with patch.object(monitor, "_fetch_cost_sync", return_value=mock_result):
            result = await monitor.fetch_data()

        assert result.overall_status == "normal"
        assert "已启用" in result.metrics[0].value

    @pytest.mark.asyncio
    async def test_fetch_data_billing_disabled(self, monitor: GCPCostMonitor) -> None:
        """测试计费未启用"""
        mock_result = MonitorResult(
            plugin_id="gcp_cost",
            provider_name="GCP",
            metrics=[
                MetricData(label="计费状态", value="未启用", status="warning"),
            ],
        )

        with patch.object(monitor, "_fetch_cost_sync", return_value=mock_result):
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

        with patch.object(monitor, "_fetch_cost_sync", return_value=mock_result):
            result = await monitor.fetch_data()

        assert result.overall_status == "error"
        assert "凭据无效" in (result.raw_error or "")

    def test_render_card(self, monitor: GCPCostMonitor) -> None:
        """测试渲染卡片"""
        data = MonitorResult(
            plugin_id="gcp_cost",
            provider_name="GCP",
            metrics=[
                MetricData(label="计费状态", value="已启用", status="normal"),
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
