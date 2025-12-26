"""
Azure 插件包

包含 Azure 云平台的监控插件。
"""

from plugins.azure.cost import AzureCostMonitor
from plugins.azure.vm import AzureVMMonitor

__all__ = ["AzureVMMonitor", "AzureCostMonitor"]
