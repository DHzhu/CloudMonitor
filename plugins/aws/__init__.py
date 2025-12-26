"""
AWS 插件包

包含 AWS 云平台的监控插件。
"""

from plugins.aws.cost import AWSCostMonitor
from plugins.aws.ec2 import AWSEC2Monitor

__all__ = ["AWSCostMonitor", "AWSEC2Monitor"]
