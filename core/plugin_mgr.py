"""
插件管理模块

动态发现、加载和管理监控插件。
"""

import importlib
import pkgutil
from typing import TYPE_CHECKING

from core.config_mgr import ConfigManager, ServiceConfig
from core.security import SecurityManager

if TYPE_CHECKING:
    from plugins.interface import BaseMonitor


# 插件类型注册表
PLUGIN_REGISTRY: dict[str, type["BaseMonitor"]] = {}


def register_plugin(plugin_type: str) -> type[type["BaseMonitor"]]:
    """
    插件注册装饰器

    用法:
        @register_plugin("aws_cost")
        class AWSCostMonitor(BaseMonitor):
            ...

    Args:
        plugin_type: 插件类型标识符

    Returns:
        装饰器函数
    """

    def decorator(cls: type["BaseMonitor"]) -> type["BaseMonitor"]:
        PLUGIN_REGISTRY[plugin_type] = cls
        return cls

    return decorator


class PluginManager:
    """
    插件管理器

    负责插件的发现、加载、实例化和生命周期管理。
    """

    def __init__(
        self,
        config_mgr: ConfigManager | None = None,
        security_mgr: SecurityManager | None = None,
    ) -> None:
        """
        初始化插件管理器

        Args:
            config_mgr: 配置管理器实例
            security_mgr: 安全管理器实例
        """
        self.config_mgr = config_mgr or ConfigManager()
        self.security_mgr = security_mgr or SecurityManager()
        self._instances: dict[str, BaseMonitor] = {}
        self._loaded = False

    def discover_plugins(self) -> list[str]:
        """
        发现所有可用的插件类型

        Returns:
            list[str]: 已注册的插件类型列表
        """
        if not self._loaded:
            self._load_plugins()
        return list(PLUGIN_REGISTRY.keys())

    def _load_plugins(self) -> None:
        """加载所有插件模块"""
        import plugins

        # 遍历 plugins 包下的所有子模块
        for _, module_name, is_pkg in pkgutil.iter_modules(plugins.__path__):
            if is_pkg and module_name not in ("__pycache__",):
                try:
                    # 动态导入插件子包
                    importlib.import_module(f"plugins.{module_name}")
                except ImportError as e:
                    print(f"Warning: Failed to load plugin module '{module_name}': {e}")

        self._loaded = True

    def get_plugin_class(self, plugin_type: str) -> type["BaseMonitor"] | None:
        """
        获取插件类

        Args:
            plugin_type: 插件类型

        Returns:
            插件类，不存在时返回 None
        """
        if not self._loaded:
            self._load_plugins()
        return PLUGIN_REGISTRY.get(plugin_type)

    def get_plugin_info(self, plugin_type: str) -> dict[str, str] | None:
        """
        获取插件信息

        Args:
            plugin_type: 插件类型

        Returns:
            包含插件信息的字典
        """
        cls = self.get_plugin_class(plugin_type)
        if cls is None:
            return None

        # 创建临时实例获取元信息
        temp_instance = cls.__new__(cls)
        temp_instance.service_id = ""
        temp_instance.alias = ""
        temp_instance.credentials = {}

        return {
            "type": plugin_type,
            "display_name": temp_instance.display_name,
            "icon": temp_instance.icon,
            "icon_path": temp_instance.icon_path,
            "required_credentials": temp_instance.required_credentials,
        }

    def create_instance(
        self,
        service_config: ServiceConfig,
    ) -> "BaseMonitor | None":
        """
        创建插件实例

        Args:
            service_config: 服务配置

        Returns:
            插件实例，创建失败时返回 None
        """
        cls = self.get_plugin_class(service_config.plugin_type)
        if cls is None:
            return None

        # 获取凭据
        temp_instance = cls.__new__(cls)
        temp_instance.service_id = ""
        temp_instance.alias = ""
        temp_instance.credentials = {}
        required_creds = temp_instance.required_credentials

        credentials = self.security_mgr.get_credentials(
            service_config.service_id,
            required_creds,
        )

        # 创建实例
        instance = cls(
            service_id=service_config.service_id,
            alias=service_config.alias,
            credentials=credentials,
        )
        instance.enabled = service_config.enabled

        # 缓存实例
        self._instances[service_config.service_id] = instance
        return instance

    def get_instance(self, service_id: str) -> "BaseMonitor | None":
        """
        获取已创建的插件实例

        Args:
            service_id: 服务 ID

        Returns:
            插件实例，不存在时返回 None
        """
        return self._instances.get(service_id)

    def load_all_services(self) -> list["BaseMonitor"]:
        """
        加载所有已配置的服务

        Returns:
            list[BaseMonitor]: 所有插件实例列表
        """
        services = self.config_mgr.get_all_services()
        instances = []

        for service in services:
            instance = self.create_instance(service)
            if instance:
                instances.append(instance)

        return instances

    def load_enabled_services(self) -> list["BaseMonitor"]:
        """
        加载所有启用的服务

        Returns:
            list[BaseMonitor]: 启用的插件实例列表
        """
        services = self.config_mgr.get_enabled_services()
        instances = []

        for service in services:
            instance = self.create_instance(service)
            if instance:
                instances.append(instance)

        return instances

    def add_service(
        self,
        plugin_type: str,
        alias: str,
        credentials: dict[str, str],
    ) -> "BaseMonitor | None":
        """
        添加新服务

        Args:
            plugin_type: 插件类型
            alias: 用户别名
            credentials: 凭据字典

        Returns:
            创建的插件实例
        """
        # 验证插件类型
        if self.get_plugin_class(plugin_type) is None:
            return None

        # 添加服务配置
        service_id = self.config_mgr.add_service(plugin_type, alias)

        # 存储凭据
        self.security_mgr.set_credentials(service_id, credentials)

        # 获取配置并创建实例
        service_config = self.config_mgr.get_service(service_id)
        if service_config:
            return self.create_instance(service_config)
        return None

    def remove_service(self, service_id: str) -> bool:
        """
        移除服务

        Args:
            service_id: 服务 ID

        Returns:
            bool: 是否移除成功
        """
        # 获取插件实例以获取凭据列表
        instance = self._instances.get(service_id)
        if instance:
            # 删除凭据
            self.security_mgr.delete_all_credentials(
                service_id,
                instance.required_credentials,
            )
            # 移除实例
            del self._instances[service_id]

        # 删除缓存
        self.config_mgr.clear_cache(service_id)

        # 删除服务配置
        return self.config_mgr.delete_service(service_id)

    async def refresh_all(self) -> dict[str, "BaseMonitor"]:
        """
        刷新所有启用的服务数据

        Returns:
            dict[str, BaseMonitor]: 服务 ID 到实例的映射
        """
        results = {}
        for service_id, instance in self._instances.items():
            if instance.enabled:
                try:
                    await instance.refresh()
                    results[service_id] = instance
                except Exception as e:
                    print(f"Error refreshing service '{service_id}': {e}")
        return results

    async def refresh_single_service(self, service_id: str) -> bool:
        """
        刷新单个服务的数据

        Args:
            service_id: 服务 ID

        Returns:
            bool: 是否刷新成功
        """
        instance = self._instances.get(service_id)
        if instance is None:
            return False

        try:
            await instance.refresh()
            return True
        except Exception as e:
            print(f"Error refreshing service '{service_id}': {e}")
            return False

    def update_service_credentials(
        self,
        service_id: str,
        alias: str | None = None,
        credentials: dict[str, str] | None = None,
    ) -> "BaseMonitor | None":
        """
        更新服务的凭据和别名

        Args:
            service_id: 服务 ID
            alias: 新别名（可选）
            credentials: 新凭据字典（可选）

        Returns:
            更新后的插件实例，失败时返回 None
        """
        # 获取现有配置
        service_config = self.config_mgr.get_service(service_id)
        if service_config is None:
            return None

        # 更新别名
        if alias:
            self.config_mgr.update_service(service_id, alias=alias)

        # 更新凭据
        if credentials:
            # 获取旧实例以便删除旧凭据
            old_instance = self._instances.get(service_id)
            if old_instance:
                self.security_mgr.delete_all_credentials(
                    service_id,
                    old_instance.required_credentials,
                )

            # 保存新凭据
            self.security_mgr.set_credentials(service_id, credentials)

        # 移除旧实例
        if service_id in self._instances:
            del self._instances[service_id]

        # 重新获取配置并创建新实例
        updated_config = self.config_mgr.get_service(service_id)
        if updated_config:
            return self.create_instance(updated_config)
        return None

