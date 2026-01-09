"""
Azure 插件单元测试
"""

from unittest.mock import patch

import pytest
from azure.core.exceptions import ClientAuthenticationError

from core.models import MetricData, MonitorResult
from plugins.azure.cost import AzureCostMonitor
from plugins.azure.vm import AzureVMMonitor


class TestAzureVMMonitor:
    """AzureVMMonitor 测试类"""

    @pytest.fixture
    def monitor(self) -> AzureVMMonitor:
        """创建测试用监控实例"""
        return AzureVMMonitor(
            service_id="test_azure_vm",
            alias="测试 Azure VM",
            credentials={
                "tenant_id": "test-tenant",
                "client_id": "test-client",
                "client_secret": "test-secret",
                "subscription_id": "test-subscription",
            },
        )

    def test_display_name(self, monitor: AzureVMMonitor) -> None:
        """测试显示名称"""
        assert monitor.display_name == "Azure VM"

    def test_required_credentials(self, monitor: AzureVMMonitor) -> None:
        """测试必需凭据"""
        assert "tenant_id" in monitor.required_credentials
        assert "client_id" in monitor.required_credentials
        assert "client_secret" in monitor.required_credentials
        assert "subscription_id" in monitor.required_credentials

    @pytest.mark.asyncio
    async def test_fetch_data_no_credentials(self) -> None:
        """测试没有凭据时返回错误"""
        monitor = AzureVMMonitor(
            service_id="test",
            alias="测试",
            credentials={},
        )

        result = await monitor.fetch_data()

        assert result.overall_status == "error"
        assert "未配置 Azure 凭据" in (result.raw_error or "")

    @pytest.mark.asyncio
    async def test_fetch_data_auth_error(self, monitor: AzureVMMonitor) -> None:
        """测试认证失败"""
        with patch(
            "plugins.azure.vm.AzureVMMonitor._fetch_vms_sync"
        ) as mock_fetch:
            mock_fetch.side_effect = ClientAuthenticationError("Invalid credentials")

            result = await monitor.fetch_data()

        assert result.overall_status == "error"

    def test_render_card(self, monitor: AzureVMMonitor) -> None:
        """测试渲染卡片"""
        data = MonitorResult(
            plugin_id="azure_vm",
            provider_name="Azure",
            metrics=[
                MetricData(label="运行中 VM", value="2/3", unit="虚拟机", status="normal"),
            ],
        )

        card = monitor.render_card(data)
        assert card is not None


class TestAzureCostMonitor:
    """AzureCostMonitor 测试类"""

    @pytest.fixture
    def monitor(self) -> AzureCostMonitor:
        """创建测试用监控实例"""
        return AzureCostMonitor(
            service_id="test_azure_cost",
            alias="测试 Azure 费用",
            credentials={
                "tenant_id": "test-tenant",
                "client_id": "test-client",
                "client_secret": "test-secret",
                "billing_account_id": "test-billing-account",
                "billing_profile_id": "test-billing-profile",
            },
        )

    def test_display_name(self, monitor: AzureCostMonitor) -> None:
        """测试显示名称"""
        assert monitor.display_name == "Azure 费用"

    @pytest.mark.asyncio
    async def test_fetch_data_no_credentials(self) -> None:
        """测试没有凭据时返回错误"""
        monitor = AzureCostMonitor(
            service_id="test",
            alias="测试",
            credentials={},
        )

        result = await monitor.fetch_data()

        assert result.overall_status == "error"
        assert "未配置 Azure 凭据" in (result.raw_error or "")

    def test_render_card(self, monitor: AzureCostMonitor) -> None:
        """测试渲染卡片"""
        data = MonitorResult(
            plugin_id="azure_cost",
            provider_name="Azure",
            metrics=[
                MetricData(label="本月费用", value="$100.00", unit="USD", status="normal"),
            ],
        )

        card = monitor.render_card(data)
        assert card is not None

    def test_required_credentials(self, monitor: AzureCostMonitor) -> None:
        """测试必需凭据"""
        assert "billing_account_id" in monitor.required_credentials
        assert "billing_profile_id" in monitor.required_credentials
        assert "subscription_id" not in monitor.required_credentials

    @pytest.mark.asyncio
    async def test_fetch_cost_scope(self, monitor: AzureCostMonitor) -> None:
        """测试生成的 API 查询范围 (scope)"""
        # 由于 CostManagementClient 是在方法内部导入的，
        # 我们需要 patch 导入它的模块路径。
        with patch("azure.mgmt.costmanagement.CostManagementClient") as mock_client_cls:
            mock_client = mock_client_cls.return_value

            # 模拟执行同步方法
            with patch("plugins.azure.cost.datetime") as mock_date:
                from datetime import datetime
                mock_date.now.return_value = datetime(2024, 1, 15)

                # 调用被测方法
                monitor._fetch_cost_sync(
                    tenant_id="t",
                    client_id="c",
                    client_secret="s",
                    billing_account_id="ACC123",
                    billing_profile_id="PROF456"
                )

                # 验证传递给 query.usage 的 scope 参数
                assert mock_client.query.usage.called
                args, kwargs = mock_client.query.usage.call_args
                expected_scope = (
                    "/providers/Microsoft.Billing/billingAccounts/ACC123"
                    "/billingProfiles/PROF456"
                )
                assert kwargs["scope"] == expected_scope
