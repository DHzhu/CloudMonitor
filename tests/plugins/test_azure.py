"""
Azure 插件单元测试
"""

from unittest.mock import MagicMock, patch

import pytest
from azure.core.exceptions import ClientAuthenticationError

from plugins.azure.cost import AzureCostMonitor
from plugins.azure.vm import AzureVMMonitor
from plugins.interface import KPIData, MonitorResult, MonitorStatus


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

        assert result.status == MonitorStatus.ERROR
        assert "未配置 Azure 凭据" in (result.error_message or "")

    @pytest.mark.asyncio
    async def test_fetch_data_auth_error(self, monitor: AzureVMMonitor) -> None:
        """测试认证失败"""
        with patch("plugins.azure.vm.ClientSecretCredential") as mock_cred:
            mock_cred.side_effect = ClientAuthenticationError("Invalid credentials")

            result = await monitor.fetch_data()

        assert result.status == MonitorStatus.ERROR
        assert "认证失败" in result.kpi.value or "凭据无效" in (result.error_message or "")

    @pytest.mark.asyncio
    async def test_fetch_data_success(self, monitor: AzureVMMonitor) -> None:
        """测试成功获取 VM 状态"""
        # 模拟 VM 对象
        mock_vm1 = MagicMock()
        mock_vm1.id = (
            "/subscriptions/test/resourceGroups/rg1"
            "/providers/Microsoft.Compute/virtualMachines/vm1"
        )
        mock_vm1.name = "vm1"
        mock_vm1.location = "eastus"
        mock_vm1.hardware_profile.vm_size = "Standard_D2s_v3"

        mock_vm2 = MagicMock()
        mock_vm2.id = (
            "/subscriptions/test/resourceGroups/rg1"
            "/providers/Microsoft.Compute/virtualMachines/vm2"
        )
        mock_vm2.name = "vm2"
        mock_vm2.location = "eastus"
        mock_vm2.hardware_profile.vm_size = "Standard_B2s"

        # 模拟 instance_view 状态
        mock_status_running = MagicMock()
        mock_status_running.code = "PowerState/running"
        mock_status_stopped = MagicMock()
        mock_status_stopped.code = "PowerState/deallocated"

        with (
            patch("plugins.azure.vm.ClientSecretCredential"),
            patch("plugins.azure.vm.ComputeManagementClient") as mock_client_class,
        ):
            mock_client = MagicMock()
            mock_client.virtual_machines.list_all.return_value = [mock_vm1, mock_vm2]

            # 模拟 instance_view 返回
            def get_instance_view(resource_group_name: str, vm_name: str) -> MagicMock:
                view = MagicMock()
                if vm_name == "vm1":
                    view.statuses = [mock_status_running]
                else:
                    view.statuses = [mock_status_stopped]
                return view

            mock_client.virtual_machines.instance_view.side_effect = get_instance_view
            mock_client_class.return_value = mock_client

            result = await monitor.fetch_data()

        assert result.status == MonitorStatus.ONLINE
        assert "1/2" in result.kpi.value
        assert len(result.details) == 2

    def test_render_card(self, monitor: AzureVMMonitor) -> None:
        """测试渲染卡片"""
        data = MonitorResult(
            status=MonitorStatus.ONLINE,
            kpi=KPIData(label="运行中 VM", value="2/3", unit="虚拟机"),
            details=[
                {
                    "name": "vm1",
                    "resource_group": "rg1",
                    "location": "eastus",
                    "size": "Standard_D2s_v3",
                    "state": "running",
                },
            ],
            last_updated="2025-01-01T12:00:00",
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
                "subscription_id": "test-subscription",
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

        assert result.status == MonitorStatus.ERROR
        assert "未配置 Azure 凭据" in (result.error_message or "")

    @pytest.mark.asyncio
    async def test_fetch_data_success(self, monitor: AzureCostMonitor) -> None:
        """测试成功获取费用"""
        # 模拟查询结果
        mock_result = MagicMock()
        mock_col1 = MagicMock()
        mock_col1.name = "Cost"
        mock_col2 = MagicMock()
        mock_col2.name = "ResourceGroup"
        mock_result.columns = [mock_col1, mock_col2]
        mock_result.rows = [
            [50.0, "rg-production"],
            [30.0, "rg-development"],
        ]

        with (
            patch("plugins.azure.cost.ClientSecretCredential"),
            patch("plugins.azure.cost.CostManagementClient") as mock_client_class,
        ):
            mock_client = MagicMock()
            mock_client.query.usage.return_value = mock_result
            mock_client_class.return_value = mock_client

            result = await monitor.fetch_data()

        assert result.status == MonitorStatus.ONLINE
        assert "$80.00" in result.kpi.value
        assert len(result.details) == 2

    def test_render_card(self, monitor: AzureCostMonitor) -> None:
        """测试渲染卡片"""
        data = MonitorResult(
            status=MonitorStatus.ONLINE,
            kpi=KPIData(label="本月费用", value="$100.00", unit="USD"),
            details=[
                {"resource_group": "rg-prod", "cost": 60.0, "percentage": 60.0},
                {"resource_group": "rg-dev", "cost": 40.0, "percentage": 40.0},
            ],
            last_updated="2025-01-01T12:00:00",
        )

        card = monitor.render_card(data)
        assert card is not None
