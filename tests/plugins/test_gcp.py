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
                "gcp_bigquery_table": "project.dataset.gcp_billing_export_v1_XXXX",
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
        assert "gcp_bigquery_table" in monitor.required_credentials

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
        assert "未配置" in (result.raw_error or "")

    @pytest.mark.asyncio
    async def test_fetch_data_success(self, monitor: GCPCostMonitor) -> None:
        """测试成功获取费用信息"""
        mock_result = MonitorResult(
            plugin_id="gcp_cost",
            provider_name="GCP",
            metrics=[
                MetricData(label="本月费用", value="$50.00", unit="USD", status="normal"),
                MetricData(label="Compute Engine", value="$30.00", status="normal"),
            ],
        )

        with patch.object(monitor, "_fetch_cost_from_bigquery", return_value=mock_result):
            result = await monitor.fetch_data()

        assert result.overall_status == "normal"
        assert result.metrics[0].value == "$50.00"

    @pytest.mark.asyncio
    async def test_fetch_data_no_cost(self, monitor: GCPCostMonitor) -> None:
        """测试无费用数据"""
        mock_result = MonitorResult(
            plugin_id="gcp_cost",
            provider_name="GCP",
            metrics=[
                MetricData(label="本月费用", value="$0.00", status="normal"),
            ],
        )

        with patch.object(monitor, "_fetch_cost_from_bigquery", return_value=mock_result):
            result = await monitor.fetch_data()

        assert result.overall_status == "normal"

    @pytest.mark.asyncio
    async def test_fetch_data_auth_error(self, monitor: GCPCostMonitor) -> None:
        """测试认证失败"""
        mock_result = MonitorResult(
            plugin_id="gcp_cost",
            provider_name="GCP",
            metrics=[MetricData(label="错误", value="获取失败", status="error")],
            raw_error="GCP 凭据无效",
        )

        with patch.object(monitor, "_fetch_cost_from_bigquery", return_value=mock_result):
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
                MetricData(label="本月费用", value="$50.00", unit="USD", status="normal"),
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


class TestGCPCostMonitorBigQuery:
    """GCPCostMonitor BigQuery 方法测试"""

    @pytest.fixture
    def monitor(self) -> GCPCostMonitor:
        """创建测试用监控实例"""
        return GCPCostMonitor(
            service_id="test_gcp_cost",
            alias="测试 GCP",
            credentials={
                "service_account_json": '{"type": "service_account", "project_id": "test"}',
                "gcp_bigquery_table": "project.dataset.gcp_billing_export_v1_XXXX",
            },
        )

    def test_fetch_cost_bigquery_invalid_json_format(self, monitor: GCPCostMonitor) -> None:
        """测试无效的 JSON 格式"""
        result = monitor._fetch_cost_from_bigquery(
            "{invalid json}",
            "project.dataset.table"
        )
        assert result.overall_status == "error"
        assert "JSON" in (result.raw_error or "")

    def test_fetch_cost_bigquery_file_not_found(self, monitor: GCPCostMonitor) -> None:
        """测试文件路径不存在"""
        result = monitor._fetch_cost_from_bigquery(
            "/path/to/nonexistent/file.json",
            "project.dataset.table"
        )
        assert result.overall_status == "error"
        assert "不存在" in (result.raw_error or "") or "错误" in (result.raw_error or "")

    @pytest.mark.asyncio
    async def test_fetch_data_missing_table(self) -> None:
        """测试缺少 BigQuery 表配置"""
        monitor = GCPCostMonitor(
            service_id="test",
            alias="测试",
            credentials={
                "service_account_json": '{"type": "service_account", "project_id": "test"}',
                # 缺少 gcp_bigquery_table
            },
        )
        result = await monitor.fetch_data()
        assert result.overall_status == "error"
        assert "未配置" in (result.raw_error or "")

    @pytest.mark.asyncio
    async def test_fetch_data_missing_service_account(self) -> None:
        """测试缺少服务账号配置"""
        monitor = GCPCostMonitor(
            service_id="test",
            alias="测试",
            credentials={
                "gcp_bigquery_table": "project.dataset.table",
                # 缺少 service_account_json
            },
        )
        result = await monitor.fetch_data()
        assert result.overall_status == "error"
        assert "未配置" in (result.raw_error or "")

    @pytest.mark.asyncio
    async def test_fetch_data_with_discount(self, monitor: GCPCostMonitor) -> None:
        """测试包含折扣的费用计算"""
        # 模拟：原价 $100，折扣 -$20，实际 $80
        mock_result = MonitorResult(
            plugin_id="gcp_cost",
            provider_name="GCP",
            metrics=[
                MetricData(label="本月费用", value="$80.00", unit="USD", status="normal"),
                MetricData(label="折扣优惠", value="-$20.00", status="normal"),
                MetricData(label="Compute Engine", value="$60.00", status="normal"),
            ],
        )

        with patch.object(monitor, "_fetch_cost_from_bigquery", return_value=mock_result):
            result = await monitor.fetch_data()

        assert result.overall_status == "normal"
        assert result.metrics[0].value == "$80.00"  # 实际费用
        assert len(result.metrics) >= 2  # 包含折扣信息
