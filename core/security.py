"""
密钥管理模块

使用 keyring 库安全存储 API 密钥，支持多账户管理。
"""

import keyring
from keyring.errors import KeyringError


class SecurityManager:
    """
    安全管理器

    使用系统安全凭据库存储敏感信息：
    - Windows: Credential Manager
    - macOS: Keychain
    - Linux: SecretService (如 GNOME Keyring)
    """

    SERVICE_NAME = "CloudMonitor"

    def __init__(self, service_name: str | None = None) -> None:
        """
        初始化安全管理器

        Args:
            service_name: 服务名称前缀，用于区分不同应用
        """
        self.service_name = service_name or self.SERVICE_NAME

    def _make_key(self, service_id: str, credential_name: str) -> str:
        """
        生成凭据存储键

        Args:
            service_id: 服务 ID
            credential_name: 凭据名称（如 'api_key', 'secret_key'）

        Returns:
            str: 完整的存储键
        """
        return f"{self.service_name}:{service_id}:{credential_name}"

    def set_credential(self, service_id: str, credential_name: str, value: str) -> bool:
        """
        存储凭据

        Args:
            service_id: 服务 ID
            credential_name: 凭据名称
            value: 凭据值

        Returns:
            bool: 是否存储成功
        """
        try:
            key = self._make_key(service_id, credential_name)
            keyring.set_password(self.service_name, key, value)
            return True
        except KeyringError:
            return False

    def get_credential(self, service_id: str, credential_name: str) -> str | None:
        """
        获取凭据

        Args:
            service_id: 服务 ID
            credential_name: 凭据名称

        Returns:
            str | None: 凭据值，不存在时返回 None
        """
        try:
            key = self._make_key(service_id, credential_name)
            return keyring.get_password(self.service_name, key)
        except KeyringError:
            return None

    def delete_credential(self, service_id: str, credential_name: str) -> bool:
        """
        删除凭据

        Args:
            service_id: 服务 ID
            credential_name: 凭据名称

        Returns:
            bool: 是否删除成功
        """
        try:
            key = self._make_key(service_id, credential_name)
            keyring.delete_password(self.service_name, key)
            return True
        except KeyringError:
            return False

    def get_credentials(self, service_id: str, credential_names: list[str]) -> dict[str, str]:
        """
        批量获取凭据

        Args:
            service_id: 服务 ID
            credential_names: 凭据名称列表

        Returns:
            dict[str, str]: 凭据字典，仅包含存在的凭据
        """
        result = {}
        for name in credential_names:
            value = self.get_credential(service_id, name)
            if value is not None:
                result[name] = value
        return result

    def set_credentials(self, service_id: str, credentials: dict[str, str]) -> bool:
        """
        批量存储凭据

        Args:
            service_id: 服务 ID
            credentials: 凭据字典

        Returns:
            bool: 是否全部存储成功
        """
        success = True
        for name, value in credentials.items():
            if not self.set_credential(service_id, name, value):
                success = False
        return success

    def delete_all_credentials(self, service_id: str, credential_names: list[str]) -> bool:
        """
        删除服务的所有凭据

        Args:
            service_id: 服务 ID
            credential_names: 凭据名称列表

        Returns:
            bool: 是否全部删除成功
        """
        success = True
        for name in credential_names:
            if not self.delete_credential(service_id, name):
                success = False
        return success

    def has_credentials(self, service_id: str, credential_names: list[str]) -> bool:
        """
        检查是否存在所有必需的凭据

        Args:
            service_id: 服务 ID
            credential_names: 必需的凭据名称列表

        Returns:
            bool: 是否所有凭据都存在
        """
        for name in credential_names:
            if self.get_credential(service_id, name) is None:
                return False
        return True
