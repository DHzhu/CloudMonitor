# -*- mode: python ; coding: utf-8 -*-
"""
CloudMonitor Pro - PyInstaller 打包配置

使用方法:
    uv run pyinstaller cloudmonitor.spec

生成的可执行文件将在 dist/ 目录下。
"""

import sys
from pathlib import Path

# 获取项目根目录
project_root = Path(SPECPATH)

# 分析模块依赖
a = Analysis(
    ['main.py'],
    pathex=[str(project_root)],
    binaries=[],
    datas=[
        # 资源文件（图标等）
        ('assets', 'assets'),
    ],
    hiddenimports=[
        # Flet 依赖
        'flet',
        'flet_core',
        'flet_runtime',
        # 核心模块
        'core.config_mgr',
        'core.plugin_mgr',
        'core.security',
        'core.models',
        'core.event_bus',
        'core.cache_mgr',
        'core.thread_utils',
        # UI 模块
        'ui.dashboard',
        'ui.settings',
        'ui.components.card',
        'ui.components.dialog',
        'ui.components.nav',
        # 插件模块
        'plugins.interface',
        'plugins.aws.cost',
        'plugins.aws.ec2',
        'plugins.azure.vm',
        'plugins.azure.cost',
        'plugins.gemini.quota',
        'plugins.gcp.cost',
        'plugins.digitalocean.cost',
        # 云 SDK
        'boto3',
        'botocore',
        'azure.identity',
        'azure.mgmt.compute',
        'azure.mgmt.costmanagement',
        'google.generativeai',
        'google.cloud.billing_v1',
        'google.oauth2.service_account',
        # 其他依赖
        'httpx',
        'keyring',
        'keyring.backends',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # 排除开发依赖
        'pytest',
        'ruff',
        'mypy',
    ],
    noarchive=False,
    optimize=0,
)

# 打包为单个可执行文件的 PYZ
pyz = PYZ(a.pure)

# 可执行文件配置
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='CloudMonitor',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # 无控制台窗口
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    # 图标配置 (如有)
    # icon='assets/icon.ico',  # Windows
    # icon='assets/icon.icns',  # macOS
)

# macOS 应用包配置 (可选)
if sys.platform == 'darwin':
    app = BUNDLE(
        exe,
        name='CloudMonitor.app',
        icon=None,  # 'assets/icon.icns',
        bundle_identifier='com.cloudmonitor.pro',
        info_plist={
            'CFBundleName': 'CloudMonitor Pro',
            'CFBundleDisplayName': 'CloudMonitor Pro',
            'CFBundleVersion': '1.0.0',
            'CFBundleShortVersionString': '1.0.0',
            'NSHighResolutionCapable': True,
        },
    )
