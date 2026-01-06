"""
安全管理器单元测试
"""

from core.security import SecurityManager


class TestSecurityManager:
    """SecurityManager 测试类"""

    def test_set_and_get_credential(self, security_mgr: SecurityManager) -> None:
        """测试凭据存取"""
        result = security_mgr.set_credential("service1", "api_key", "test-key-123")
        assert result is True

        value = security_mgr.get_credential("service1", "api_key")
        assert value == "test-key-123"

    def test_get_nonexistent_credential(self, security_mgr: SecurityManager) -> None:
        """测试获取不存在的凭据"""
        value = security_mgr.get_credential("nonexistent", "api_key")
        assert value is None

    def test_delete_credential(self, security_mgr: SecurityManager) -> None:
        """测试删除凭据"""
        security_mgr.set_credential("service1", "api_key", "test-key")

        result = security_mgr.delete_credential("service1", "api_key")
        assert result is True

        value = security_mgr.get_credential("service1", "api_key")
        assert value is None

    def test_get_credentials_batch(self, security_mgr: SecurityManager) -> None:
        """测试批量获取凭据"""
        security_mgr.set_credential("service1", "api_key", "key1")
        security_mgr.set_credential("service1", "secret_key", "secret1")

        credentials = security_mgr.get_credentials(
            "service1", ["api_key", "secret_key", "nonexistent"]
        )

        assert credentials == {"api_key": "key1", "secret_key": "secret1"}

    def test_set_credentials_batch(self, security_mgr: SecurityManager) -> None:
        """测试批量存储凭据"""
        credentials = {"api_key": "key1", "secret_key": "secret1"}

        result = security_mgr.set_credentials("service1", credentials)
        assert result is True

        assert security_mgr.get_credential("service1", "api_key") == "key1"
        assert security_mgr.get_credential("service1", "secret_key") == "secret1"

    def test_delete_all_credentials(self, security_mgr: SecurityManager) -> None:
        """测试删除所有凭据"""
        security_mgr.set_credential("service1", "api_key", "key1")
        security_mgr.set_credential("service1", "secret_key", "secret1")

        result = security_mgr.delete_all_credentials("service1", ["api_key", "secret_key"])
        assert result is True

        assert security_mgr.get_credential("service1", "api_key") is None
        assert security_mgr.get_credential("service1", "secret_key") is None

    def test_has_credentials(self, security_mgr: SecurityManager) -> None:
        """测试检查凭据是否存在"""
        security_mgr.set_credential("service1", "api_key", "key1")
        security_mgr.set_credential("service1", "secret_key", "secret1")

        assert security_mgr.has_credentials("service1", ["api_key", "secret_key"]) is True
        assert security_mgr.has_credentials("service1", ["api_key", "nonexistent"]) is False

    def test_make_key(self, security_mgr: SecurityManager) -> None:
        """测试键生成"""
        key = security_mgr._make_key("service1", "api_key")
        assert key == "CloudMonitor:service1:api_key"

    def test_chunked_credential_storage(self, security_mgr: SecurityManager) -> None:
        """测试分块凭据存储（大凭据）"""
        # 创建一个超过 MAX_CREDENTIAL_SIZE 的大凭据
        large_value = "A" * (security_mgr.MAX_CREDENTIAL_SIZE + 500)

        result = security_mgr.set_credential("service1", "large_key", large_value)
        assert result is True

        # 验证能正确读取
        retrieved = security_mgr.get_credential("service1", "large_key")
        assert retrieved == large_value

    def test_chunked_credential_with_unicode(self, security_mgr: SecurityManager) -> None:
        """测试分块凭据存储（包含 Unicode 字符）"""
        # 创建包含中文的大凭据，模拟 JSON 数据
        json_like = '{"name": "测试服务", "key": "' + "X" * 2000 + '"}'

        result = security_mgr.set_credential("service1", "json_data", json_like)
        assert result is True

        retrieved = security_mgr.get_credential("service1", "json_data")
        assert retrieved == json_like

    def test_delete_chunked_credential(self, security_mgr: SecurityManager) -> None:
        """测试删除分块凭据"""
        large_value = "B" * (security_mgr.MAX_CREDENTIAL_SIZE + 500)
        security_mgr.set_credential("service1", "large_key", large_value)

        result = security_mgr.delete_credential("service1", "large_key")
        assert result is True

        # 验证已删除
        retrieved = security_mgr.get_credential("service1", "large_key")
        assert retrieved is None

    def test_update_chunked_credential(self, security_mgr: SecurityManager) -> None:
        """测试更新分块凭据"""
        # 先存储一个大凭据
        large_value1 = "C" * (security_mgr.MAX_CREDENTIAL_SIZE + 500)
        security_mgr.set_credential("service1", "large_key", large_value1)

        # 更新为另一个大凭据
        large_value2 = "D" * (security_mgr.MAX_CREDENTIAL_SIZE + 800)
        result = security_mgr.set_credential("service1", "large_key", large_value2)
        assert result is True

        # 验证读取到的是新值
        retrieved = security_mgr.get_credential("service1", "large_key")
        assert retrieved == large_value2
