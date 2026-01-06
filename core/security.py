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

    # Windows Credential Manager 单条凭据最大字节数限制
    MAX_CREDENTIAL_SIZE = 2000

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

            # 检查凭据长度，超长则分块存储
            if len(value.encode("utf-8")) > self.MAX_CREDENTIAL_SIZE:
                return self._set_chunked_credential(key, value)

            keyring.set_password(self.service_name, key, value)
            return True
        except KeyringError:
            return False

    def _set_chunked_credential(self, key: str, value: str) -> bool:
        """分块存储超长凭据"""
        try:
            # 将值转换为字节并分块
            value_bytes = value.encode("utf-8")
            chunks = []
            for i in range(0, len(value_bytes), self.MAX_CREDENTIAL_SIZE):
                chunk = value_bytes[i : i + self.MAX_CREDENTIAL_SIZE]
                chunks.append(chunk.decode("utf-8", errors="replace"))

            # 存储块数量
            keyring.set_password(self.service_name, f"{key}:chunks", str(len(chunks)))

            # 存储每个块
            for idx, chunk in enumerate(chunks):
                keyring.set_password(self.service_name, f"{key}:chunk:{idx}", chunk)

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

            # 先检查是否为分块存储
            chunks_count = keyring.get_password(self.service_name, f"{key}:chunks")
            if chunks_count:
                return self._get_chunked_credential(key, int(chunks_count))

            return keyring.get_password(self.service_name, key)
        except KeyringError:
            return None

    def _get_chunked_credential(self, key: str, chunks_count: int) -> str | None:
        """读取并合并分块凭据"""
        try:
            chunks = []
            for idx in range(chunks_count):
                chunk = keyring.get_password(self.service_name, f"{key}:chunk:{idx}")
                if chunk is None:
                    return None
                chunks.append(chunk)
            return "".join(chunks)
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

            # 检查是否为分块存储
            chunks_count = keyring.get_password(self.service_name, f"{key}:chunks")
            if chunks_count:
                self._delete_chunked_credential(key, int(chunks_count))

            # 尝试删除普通凭据
            try:
                keyring.delete_password(self.service_name, key)
            except KeyringError:
                pass  # 可能不存在普通凭据

            return True
        except KeyringError:
            return False

    def _delete_chunked_credential(self, key: str, chunks_count: int) -> None:
        """删除分块凭据"""
        try:
            # 删除所有块
            for idx in range(chunks_count):
                try:
                    keyring.delete_password(self.service_name, f"{key}:chunk:{idx}")
                except KeyringError:
                    pass
            # 删除块数量记录
            keyring.delete_password(self.service_name, f"{key}:chunks")
        except KeyringError:
            pass

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
