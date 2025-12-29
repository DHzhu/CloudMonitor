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
