"""
Google Gemini 插件包

包含 Google Gemini API 的监控插件。
"""

from plugins.gemini.quota import GeminiQuotaMonitor

__all__ = ["GeminiQuotaMonitor"]
