"""
插件管理器单元测试
"""

from unittest.mock import MagicMock, patch

import pytest

from core.config_mgr import ConfigManager
from core.plugin_mgr import PLUGIN_REGISTRY, PluginManager, register_plugin
from core.security import SecurityManager
from plugins.interface import BaseMonitor, KPIData, MonitorResult, MonitorStatus


# 创建测试用插件
class MockMonitor(BaseMonitor):
    """测试用 Mock 插件"""

    @property
    def display_name(self) -> str:
        return "Mock Service"

    @property
    def icon(self) -> str:
        return "cloud"

    @property
    def required_credentials(self) -> list[str]:
        return ["api_key"]

    async def fetch_data(self) -> MonitorResult:
        return MonitorResult(
            status=MonitorStatus.ONLINE,
            kpi=KPIData(label="测试", value="100"),
            details=[],
        )

    def render_card(self, data: MonitorResult) -> MagicMock:
        return MagicMock()


class TestRegisterPlugin:
    """register_plugin 装饰器测试"""

    def test_register_plugin(self) -> None:
        """测试插件注册"""
        # 清理注册表
        if "test_plugin" in PLUGIN_REGISTRY:
            del PLUGIN_REGISTRY["test_plugin"]

        @register_plugin("test_plugin")
        class TestPlugin(MockMonitor):
            pass

        assert "test_plugin" in PLUGIN_REGISTRY
        assert PLUGIN_REGISTRY["test_plugin"] == TestPlugin

        # 清理
        del PLUGIN_REGISTRY["test_plugin"]


class TestPluginManager:
    """PluginManager 测试类"""

    @pytest.fixture
    def plugin_mgr(
        self, config_mgr: ConfigManager, security_mgr: SecurityManager
    ) -> PluginManager:
        """创建插件管理器实例"""
        # 注册 Mock 插件
        PLUGIN_REGISTRY["mock_service"] = MockMonitor
        return PluginManager(config_mgr=config_mgr, security_mgr=security_mgr)

    def test_discover_plugins(self, plugin_mgr: PluginManager) -> None:
        """测试插件发现"""
        with patch.object(plugin_mgr, "_load_plugins"):
            plugin_mgr._loaded = True
            plugins = plugin_mgr.discover_plugins()
            assert "mock_service" in plugins

    def test_get_plugin_class(self, plugin_mgr: PluginManager) -> None:
        """测试获取插件类"""
        plugin_mgr._loaded = True
        cls = plugin_mgr.get_plugin_class("mock_service")
        assert cls == MockMonitor

        cls = plugin_mgr.get_plugin_class("nonexistent")
        assert cls is None

    def test_get_plugin_info(self, plugin_mgr: PluginManager) -> None:
        """测试获取插件信息"""
        plugin_mgr._loaded = True
        info = plugin_mgr.get_plugin_info("mock_service")

        assert info is not None
        assert info["type"] == "mock_service"
        assert info["display_name"] == "Mock Service"
        assert info["required_credentials"] == ["api_key"]

    def test_add_service(self, plugin_mgr: PluginManager) -> None:
        """测试添加服务"""
        plugin_mgr._loaded = True
        instance = plugin_mgr.add_service(
            plugin_type="mock_service",
            alias="测试服务",
            credentials={"api_key": "test-key"},
        )

        assert instance is not None
        assert instance.alias == "测试服务"
        assert instance.credentials.get("api_key") == "test-key"

    def test_add_invalid_service(self, plugin_mgr: PluginManager) -> None:
        """测试添加无效服务"""
        plugin_mgr._loaded = True
        instance = plugin_mgr.add_service(
            plugin_type="nonexistent",
            alias="测试",
            credentials={},
        )

        assert instance is None

    def test_remove_service(self, plugin_mgr: PluginManager) -> None:
        """测试移除服务"""
        plugin_mgr._loaded = True
        instance = plugin_mgr.add_service(
            plugin_type="mock_service",
            alias="测试",
            credentials={"api_key": "key"},
        )

        assert instance is not None
        service_id = instance.service_id

        result = plugin_mgr.remove_service(service_id)
        assert result is True
        assert plugin_mgr.get_instance(service_id) is None

    def test_load_enabled_services(self, plugin_mgr: PluginManager) -> None:
        """测试加载启用的服务"""
        plugin_mgr._loaded = True

        # 添加两个服务
        instance1 = plugin_mgr.add_service("mock_service", "服务1", {"api_key": "k1"})
        instance2 = plugin_mgr.add_service("mock_service", "服务2", {"api_key": "k2"})

        assert instance1 is not None
        assert instance2 is not None

        # 禁用第一个
        plugin_mgr.config_mgr.update_service(instance1.service_id, enabled=False)

        # 清除实例缓存
        plugin_mgr._instances.clear()

        # 重新加载
        instances = plugin_mgr.load_enabled_services()
        assert len(instances) == 1
        assert instances[0].alias == "服务2"

    @pytest.mark.asyncio
    async def test_refresh_all(self, plugin_mgr: PluginManager) -> None:
        """测试刷新所有服务"""
        plugin_mgr._loaded = True
        plugin_mgr.add_service("mock_service", "服务1", {"api_key": "k1"})

        results = await plugin_mgr.refresh_all()
        assert len(results) == 1
