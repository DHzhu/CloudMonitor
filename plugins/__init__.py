"""
CloudMonitor Pro 插件模块

提供云服务和大模型服务的监控插件。
"""

# 导入所有插件，确保注册装饰器被执行
from plugins.aws import AWSCostMonitor, AWSEC2Monitor
from plugins.azure import AzureCostMonitor, AzureVMMonitor
from plugins.gemini import GeminiQuotaMonitor
from plugins.interface import BaseMonitor

__all__ = [
    "BaseMonitor",
    "AWSEC2Monitor",
    "AWSCostMonitor",
    "AzureVMMonitor",
    "AzureCostMonitor",
    "GeminiQuotaMonitor",
]
