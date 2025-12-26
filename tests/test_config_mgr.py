"""
配置管理器单元测试
"""



from core.config_mgr import ConfigManager


class TestConfigManager:
    """ConfigManager 测试类"""

    def test_init_creates_tables(self, config_mgr: ConfigManager) -> None:
        """测试初始化时创建数据库表"""
        with config_mgr._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = {row[0] for row in cursor.fetchall()}

        assert "services" in tables
        assert "cache" in tables
        assert "preferences" in tables

    def test_add_service(self, config_mgr: ConfigManager) -> None:
        """测试添加服务"""
        service_id = config_mgr.add_service("aws_cost", "个人 AWS")

        assert service_id is not None
        assert "aws_cost" in service_id

        service = config_mgr.get_service(service_id)
        assert service is not None
        assert service.plugin_type == "aws_cost"
        assert service.alias == "个人 AWS"
        assert service.enabled is True

    def test_get_all_services(self, config_mgr: ConfigManager) -> None:
        """测试获取所有服务"""
        config_mgr.add_service("aws_cost", "AWS 1")
        config_mgr.add_service("zhipu_balance", "智谱")

        services = config_mgr.get_all_services()
        assert len(services) == 2

    def test_get_enabled_services(self, config_mgr: ConfigManager) -> None:
        """测试获取启用的服务"""
        id1 = config_mgr.add_service("aws_cost", "AWS 1")
        config_mgr.add_service("zhipu_balance", "智谱")

        # 禁用第一个服务
        config_mgr.update_service(id1, enabled=False)

        enabled = config_mgr.get_enabled_services()
        assert len(enabled) == 1
        assert enabled[0].plugin_type == "zhipu_balance"

    def test_update_service(self, config_mgr: ConfigManager) -> None:
        """测试更新服务"""
        service_id = config_mgr.add_service("aws_cost", "旧名称")

        result = config_mgr.update_service(service_id, alias="新名称", enabled=False)
        assert result is True

        service = config_mgr.get_service(service_id)
        assert service is not None
        assert service.alias == "新名称"
        assert service.enabled is False

    def test_delete_service(self, config_mgr: ConfigManager) -> None:
        """测试删除服务"""
        service_id = config_mgr.add_service("aws_cost", "测试")

        result = config_mgr.delete_service(service_id)
        assert result is True

        service = config_mgr.get_service(service_id)
        assert service is None

    def test_set_and_get_cache(self, config_mgr: ConfigManager) -> None:
        """测试缓存读写"""
        service_id = config_mgr.add_service("aws_cost", "AWS")
        data = {"cost": 10.5, "currency": "USD"}

        config_mgr.set_cache(service_id, data)
        cached = config_mgr.get_cache(service_id)

        assert cached is not None
        assert cached.data == data

    def test_clear_cache(self, config_mgr: ConfigManager) -> None:
        """测试清除缓存"""
        id1 = config_mgr.add_service("aws_cost", "AWS")
        id2 = config_mgr.add_service("zhipu_balance", "智谱")

        config_mgr.set_cache(id1, {"data": 1})
        config_mgr.set_cache(id2, {"data": 2})

        # 清除特定服务缓存
        count = config_mgr.clear_cache(id1)
        assert count == 1
        assert config_mgr.get_cache(id1) is None
        assert config_mgr.get_cache(id2) is not None

        # 清除所有缓存
        count = config_mgr.clear_cache()
        assert count == 1

    def test_preferences(self, config_mgr: ConfigManager) -> None:
        """测试偏好设置"""
        config_mgr.set_preference("theme", "dark")
        config_mgr.set_preference("refresh_interval", 60)

        assert config_mgr.get_preference("theme") == "dark"
        assert config_mgr.get_preference("refresh_interval") == 60
        assert config_mgr.get_preference("nonexistent", "default") == "default"

        config_mgr.delete_preference("theme")
        assert config_mgr.get_preference("theme") is None
