"""
AWS 插件单元测试
"""

from unittest.mock import patch

import pytest

from core.models import MetricData, MonitorResult
from plugins.aws.cost import AWSCostMonitor
from plugins.aws.ec2 import AWSEC2Monitor


class TestAWSCostMonitor:
    """AWSCostMonitor 测试类"""

    @pytest.fixture
    def monitor(self) -> AWSCostMonitor:
        """创建测试用监控实例"""
        return AWSCostMonitor(
            service_id="test_aws_cost",
            alias="测试 AWS",
            credentials={
                "access_key_id": "test-key",
                "secret_access_key": "test-secret",
                "region": "us-east-1",
            },
        )

    def test_display_name(self, monitor: AWSCostMonitor) -> None:
        """测试显示名称"""
        assert monitor.display_name == "AWS 费用"

    def test_required_credentials(self, monitor: AWSCostMonitor) -> None:
        """测试必需凭据"""
        assert "access_key_id" in monitor.required_credentials
        assert "secret_access_key" in monitor.required_credentials
        assert "region" in monitor.required_credentials

    @pytest.mark.asyncio
    async def test_fetch_data_no_credentials(self) -> None:
        """测试没有凭据时返回错误"""
        monitor = AWSCostMonitor(
            service_id="test",
            alias="测试",
            credentials={},
        )

        result = await monitor.fetch_data()

        assert result.overall_status == "error"
        assert "未配置 AWS 凭据" in (result.raw_error or "")

    @pytest.mark.asyncio
    async def test_fetch_data_success(self, monitor: AWSCostMonitor) -> None:
        """测试成功获取费用"""
        # 模拟同步方法返回成功结果
        mock_result = MonitorResult(
            plugin_id="aws_cost",
            provider_name="AWS",
            metrics=[
                MetricData(label="本月费用", value="$60.00", unit="USD", status="normal"),
                MetricData(label="EC2", value="$50.00", status="normal"),
            ],
        )

        with patch.object(monitor, "_fetch_cost_sync", return_value=mock_result):
            result = await monitor.fetch_data()

        assert result.overall_status == "normal"
        assert "$60.00" in result.metrics[0].value

    @pytest.mark.asyncio
    async def test_fetch_data_auth_error(self, monitor: AWSCostMonitor) -> None:
        """测试认证失败"""
        mock_result = MonitorResult(
            plugin_id="aws_cost",
            provider_name="AWS",
            metrics=[MetricData(label="错误", value="获取失败", status="error")],
            raw_error="凭据无效",
        )

        with patch.object(monitor, "_fetch_cost_sync", return_value=mock_result):
            result = await monitor.fetch_data()

        assert result.overall_status == "error"
        assert "凭据无效" in (result.raw_error or "")

    def test_render_card(self, monitor: AWSCostMonitor) -> None:
        """测试渲染卡片"""
        data = MonitorResult(
            plugin_id="aws_cost",
            provider_name="AWS",
            metrics=[
                MetricData(label="本月费用", value="$100.00", unit="USD", status="normal"),
            ],
        )

        card = monitor.render_card(data)
        assert card is not None


class TestAWSEC2Monitor:
    """AWSEC2Monitor 测试类"""

    @pytest.fixture
    def monitor(self) -> AWSEC2Monitor:
        """创建测试用监控实例"""
        return AWSEC2Monitor(
            service_id="test_aws_ec2",
            alias="测试 EC2",
            credentials={
                "access_key_id": "test-key",
                "secret_access_key": "test-secret",
                "region": "us-east-1",
            },
        )

    def test_display_name(self, monitor: AWSEC2Monitor) -> None:
        """测试显示名称"""
        assert monitor.display_name == "AWS EC2"

    @pytest.mark.asyncio
    async def test_fetch_data_success(self, monitor: AWSEC2Monitor) -> None:
        """测试成功获取实例状态"""
        mock_result = MonitorResult(
            plugin_id="aws_ec2",
            provider_name="AWS",
            metrics=[
                MetricData(label="运行中实例", value="1/2", unit="实例", status="normal"),
                MetricData(label="Web Server", value="running", status="normal"),
            ],
        )

        with patch.object(monitor, "_fetch_instances_sync", return_value=mock_result):
            result = await monitor.fetch_data()

        assert result.overall_status == "normal"
        assert "1/2" in result.metrics[0].value

    @pytest.mark.asyncio
    async def test_fetch_data_all_stopped(self, monitor: AWSEC2Monitor) -> None:
        """测试所有实例都停止时的警告状态"""
        mock_result = MonitorResult(
            plugin_id="aws_ec2",
            provider_name="AWS",
            metrics=[
                MetricData(label="运行中实例", value="0/1", unit="实例", status="warning"),
            ],
        )

        with patch.object(monitor, "_fetch_instances_sync", return_value=mock_result):
            result = await monitor.fetch_data()

        assert result.overall_status == "warning"

    def test_render_card(self, monitor: AWSEC2Monitor) -> None:
        """测试渲染卡片"""
        data = MonitorResult(
            plugin_id="aws_ec2",
            provider_name="AWS",
            metrics=[
                MetricData(label="运行中", value="2/3", unit="实例", status="normal"),
            ],
        )

        card = monitor.render_card(data)
        assert card is not None
