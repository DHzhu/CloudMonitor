"""
AWS 插件单元测试
"""

from unittest.mock import MagicMock, patch

import pytest
from botocore.exceptions import ClientError

from plugins.aws.cost import AWSCostMonitor
from plugins.aws.ec2 import AWSEC2Monitor
from plugins.interface import MonitorStatus


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

        assert result.status == MonitorStatus.ERROR
        assert "未配置 AWS 凭据" in (result.error_message or "")

    @pytest.mark.asyncio
    async def test_fetch_data_success(self, monitor: AWSCostMonitor) -> None:
        """测试成功获取费用"""
        mock_response = {
            "ResultsByTime": [
                {
                    "Groups": [
                        {
                            "Keys": ["Amazon EC2"],
                            "Metrics": {
                                "BlendedCost": {"Amount": "50.00", "Unit": "USD"},
                            },
                        },
                        {
                            "Keys": ["Amazon S3"],
                            "Metrics": {
                                "BlendedCost": {"Amount": "10.00", "Unit": "USD"},
                            },
                        },
                    ]
                }
            ]
        }

        with patch("plugins.aws.cost.boto3.client") as mock_boto:
            mock_client = MagicMock()
            mock_client.get_cost_and_usage.return_value = mock_response
            mock_boto.return_value = mock_client

            result = await monitor.fetch_data()

        assert result.status == MonitorStatus.ONLINE
        assert "$60.00" in result.kpi.value
        assert len(result.details) == 2

    @pytest.mark.asyncio
    async def test_fetch_data_auth_error(self, monitor: AWSCostMonitor) -> None:
        """测试认证失败"""
        error_response = {
            "Error": {
                "Code": "InvalidAccessKeyId",
                "Message": "The AWS Access Key Id you provided is not valid.",
            }
        }

        with patch("plugins.aws.cost.boto3.client") as mock_boto:
            mock_client = MagicMock()
            mock_client.get_cost_and_usage.side_effect = ClientError(
                error_response, "GetCostAndUsage"
            )
            mock_boto.return_value = mock_client

            result = await monitor.fetch_data()

        assert result.status == MonitorStatus.ERROR
        assert "凭据无效" in (result.error_message or "")

    def test_render_card(self, monitor: AWSCostMonitor) -> None:
        """测试渲染卡片"""
        from plugins.interface import KPIData, MonitorResult

        data = MonitorResult(
            status=MonitorStatus.ONLINE,
            kpi=KPIData(label="本月费用", value="$100.00"),
            details=[{"service": "EC2", "cost": 50.0, "percentage": 50.0}],
            last_updated="2025-01-01T12:00:00",
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
        mock_response = {
            "Reservations": [
                {
                    "Instances": [
                        {
                            "InstanceId": "i-12345",
                            "State": {"Name": "running"},
                            "InstanceType": "t3.micro",
                            "Tags": [{"Key": "Name", "Value": "Web Server"}],
                            "PublicIpAddress": "1.2.3.4",
                        },
                        {
                            "InstanceId": "i-67890",
                            "State": {"Name": "stopped"},
                            "InstanceType": "t3.small",
                            "Tags": [],
                        },
                    ]
                }
            ]
        }

        with patch("plugins.aws.ec2.boto3.client") as mock_boto:
            mock_client = MagicMock()
            mock_client.describe_instances.return_value = mock_response
            mock_boto.return_value = mock_client

            result = await monitor.fetch_data()

        assert result.status == MonitorStatus.ONLINE
        assert "1/2" in result.kpi.value
        assert len(result.details) == 2
        assert result.details[0]["name"] == "Web Server"
        assert result.details[0]["state"] == "running"

    @pytest.mark.asyncio
    async def test_fetch_data_all_stopped(self, monitor: AWSEC2Monitor) -> None:
        """测试所有实例都停止时的警告状态"""
        mock_response = {
            "Reservations": [
                {
                    "Instances": [
                        {
                            "InstanceId": "i-12345",
                            "State": {"Name": "stopped"},
                            "InstanceType": "t3.micro",
                            "Tags": [],
                        },
                    ]
                }
            ]
        }

        with patch("plugins.aws.ec2.boto3.client") as mock_boto:
            mock_client = MagicMock()
            mock_client.describe_instances.return_value = mock_response
            mock_boto.return_value = mock_client

            result = await monitor.fetch_data()

        assert result.status == MonitorStatus.WARNING

    def test_render_card(self, monitor: AWSEC2Monitor) -> None:
        """测试渲染卡片"""
        from plugins.interface import KPIData, MonitorResult

        data = MonitorResult(
            status=MonitorStatus.ONLINE,
            kpi=KPIData(label="运行中", value="2/3", unit="实例"),
            details=[
                {
                    "id": "i-1",
                    "name": "Server1",
                    "state": "running",
                    "type": "t3.micro",
                    "ip": "1.2.3.4",
                },
            ],
            last_updated="2025-01-01T12:00:00",
        )

        card = monitor.render_card(data)
        assert card is not None
