"""
设置页面

管理服务配置和凭据。
"""

import asyncio

import flet as ft

from core.config_mgr import ConfigManager, ServiceConfig
from core.plugin_mgr import PLUGIN_REGISTRY, PluginManager
from core.security import SecurityManager
from ui.components.dialog import ConfirmDialog, CredentialDialog, SnackBar
from ui.components.nav import PageHeader


class SettingsPage(ft.Container):
    """
    设置页面

    管理监控服务的添加、编辑和删除。
    """

    def __init__(
        self,
        plugin_mgr: PluginManager,
        config_mgr: ConfigManager,
        security_mgr: SecurityManager,
        page: ft.Page,
    ) -> None:
        self.plugin_mgr = plugin_mgr
        self.config_mgr = config_mgr
        self.security_mgr = security_mgr
        self.app_page = page

        super().__init__(
            content=self._build_content(),
            expand=True,
            padding=24,
        )

    def _build_content(self) -> ft.Control:
        """构建页面内容"""
        return ft.Column(
            controls=[
                PageHeader(
                    title="设置",
                    subtitle="管理服务配置和凭据",
                    actions=[
                        ft.ElevatedButton(
                            "添加服务",
                            icon=ft.Icons.ADD,
                            on_click=self._on_add_service,
                        ),
                    ],
                ),
                ft.Container(
                    content=self._build_service_list(),
                    expand=True,
                ),
            ],
            spacing=0,
            expand=True,
        )

    def _build_service_list(self) -> ft.Control:
        """构建服务列表"""
        services = self.config_mgr.get_all_services()

        if not services:
            return ft.Container(
                content=ft.Column(
                    controls=[
                        ft.Icon(
                            ft.Icons.SETTINGS_OUTLINED,
                            size=64,
                            color=ft.Colors.WHITE_38,
                        ),
                        ft.Text(
                            "暂无服务",
                            size=20,
                            color=ft.Colors.WHITE_54,
                        ),
                        ft.Text(
                            "点击上方按钮添加监控服务",
                            size=14,
                            color=ft.Colors.WHITE_38,
                        ),
                    ],
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    spacing=12,
                ),
                alignment=ft.Alignment.CENTER,
                expand=True,
            )

        # 构建服务卡片列表
        items = []
        for service in services:
            items.append(self._build_service_item(service))

        return ft.ListView(
            controls=items,
            spacing=8,
            expand=True,
        )

    def _build_service_item(self, service: ServiceConfig) -> ft.Control:
        """构建单个服务项"""
        plugin_info = self.plugin_mgr.get_plugin_info(service.plugin_type)
        display_name = plugin_info["display_name"] if plugin_info else service.plugin_type

        # 优先使用品牌图标，否则回退到 Material Icon
        icon_path = plugin_info.get("icon_path") if plugin_info else None
        if icon_path:
            leading_icon = ft.Image(
                src=icon_path,
                width=32,
                height=32,
                fit=ft.BoxFit.CONTAIN,
            )
        else:
            icon_name = plugin_info["icon"] if plugin_info else "cloud"
            icon_value = getattr(ft.Icons, icon_name.upper(), ft.Icons.CLOUD)
            leading_icon = ft.Icon(icon_value, size=32, color=ft.Colors.BLUE_400)

        return ft.Container(
            content=ft.Row(
                controls=[
                    leading_icon,
                    ft.Column(
                        controls=[
                            ft.TextButton(
                                content=ft.Text(
                                    service.alias,
                                    size=16,
                                    weight=ft.FontWeight.BOLD,
                                    color=ft.Colors.WHITE,
                                ),
                                on_click=lambda e,
                                    sid=service.service_id,
                                    alias=service.alias,
                                    pt=service.plugin_type: self._on_edit_service(
                                        e, sid, alias, pt
                                    ),
                                style=ft.ButtonStyle(padding=0),
                            ),
                            ft.Text(
                                display_name,
                                size=12,
                                color=ft.Colors.WHITE_54,
                            ),
                        ],
                        spacing=2,
                        expand=True,
                    ),
                    ft.Switch(
                        value=service.enabled,
                        active_color=ft.Colors.GREEN_400,
                        on_change=lambda e, sid=service.service_id: self._on_toggle_service(e, sid),
                    ),
                    ft.IconButton(
                        icon=ft.Icons.REFRESH,
                        icon_color=ft.Colors.BLUE_300,
                        tooltip="刷新服务",
                        on_click=lambda e, sid=service.service_id: (
                            self._on_refresh_service(e, sid)
                        ),
                    ),
                    ft.IconButton(
                        icon=ft.Icons.EDIT_OUTLINED,
                        icon_color=ft.Colors.ORANGE_300,
                        tooltip="编辑服务",
                        on_click=lambda e,
                            sid=service.service_id,
                            alias=service.alias,
                            pt=service.plugin_type: self._on_edit_service(e, sid, alias, pt),
                    ),
                    ft.IconButton(
                        icon=ft.Icons.DELETE_OUTLINE,
                        icon_color=ft.Colors.RED_300,
                        tooltip="删除服务",
                        on_click=lambda e, sid=service.service_id, alias=service.alias: (
                            self._on_delete_service(e, sid, alias)
                        ),
                    ),
                ],
                alignment=ft.MainAxisAlignment.START,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=16,
            ),
            padding=16,
            border_radius=8,
            bgcolor=ft.Colors.with_opacity(0.05, ft.Colors.WHITE),
            border=ft.Border.all(1, ft.Colors.with_opacity(0.1, ft.Colors.WHITE)),
        )

    def _on_add_service(self, e: ft.ControlEvent) -> None:
        """添加服务按钮点击"""
        # 显示插件类型选择对话框
        self._show_plugin_selector()

    def _show_plugin_selector(self) -> None:
        """显示插件类型选择器"""
        # 获取所有可用插件
        self.plugin_mgr.discover_plugins()

        items = []
        for plugin_type in PLUGIN_REGISTRY:
            info = self.plugin_mgr.get_plugin_info(plugin_type)
            if info:
                # 优先使用图片图标，否则回退到 Material Icon
                icon_path = info.get("icon_path")
                if icon_path:
                    leading = ft.Image(
                        src=icon_path,
                        width=32,
                        height=32,
                        fit=ft.BoxFit.CONTAIN,
                    )
                else:
                    icon_name = info["icon"]
                    icon_value = getattr(ft.Icons, icon_name.upper(), ft.Icons.CLOUD)
                    leading = ft.Icon(icon_value, color=ft.Colors.BLUE_400)

                # 使用 ListTile - 经测试在 Web 模式下可以正确渲染
                item = ft.ListTile(
                    leading=leading,
                    title=ft.Text(info["display_name"]),
                    subtitle=ft.Text(f"需要: {', '.join(info['required_credentials'])}"),
                    on_click=lambda e, pt=plugin_type: self._on_plugin_selected(e, pt),
                )
                items.append(item)

        dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text("选择服务类型", size=18, weight=ft.FontWeight.BOLD),
            content=ft.Container(
                content=ft.Column(
                    controls=items,
                    scroll=ft.ScrollMode.AUTO,
                ),
                width=420,
                height=350,
            ),
            actions=[
                ft.TextButton(
                    "取消",
                    on_click=lambda e: self._close_dialog(e),
                ),
            ],
        )

        self.app_page.overlay.append(dialog)
        dialog.open = True
        self.app_page.update()

    def _on_plugin_selected(self, e: ft.ControlEvent, plugin_type: str) -> None:
        """选择插件类型后"""
        # 关闭选择器
        self._close_dialog(e)

        # 获取插件信息
        info = self.plugin_mgr.get_plugin_info(plugin_type)
        if not info:
            return

        # 显示凭据输入对话框
        dialog = CredentialDialog(
            title=f"添加 {info['display_name']}",
            plugin_type=plugin_type,
            required_fields=info["required_credentials"],
            on_save=lambda values: self._save_service(plugin_type, values),
            on_cancel=lambda e: self._close_dialog(e),
        )

        self.app_page.overlay.append(dialog)
        dialog.open = True
        self.app_page.update()

    def _save_service(self, plugin_type: str, values: dict[str, str]) -> None:
        """保存新服务"""
        alias = values.pop("alias", "")

        if not alias:
            alias = plugin_type

        # 添加服务
        instance = self.plugin_mgr.add_service(
            plugin_type=plugin_type,
            alias=alias,
            credentials=values,
        )

        if instance:
            SnackBar.show(self.app_page, f"服务 '{alias}' 添加成功")
            self.refresh()
        else:
            SnackBar.show(self.app_page, "添加服务失败", is_error=True)

        # 关闭对话框
        self._close_all_dialogs()

    def _on_refresh_service(self, e: ft.ControlEvent, service_id: str) -> None:
        """刷新单个服务"""
        self.app_page.run_task(self._refresh_service_async, service_id)

    async def _refresh_service_async(self, service_id: str) -> None:
        """异步刷新单个服务"""
        SnackBar.show(self.app_page, "正在刷新...")
        result = await self.plugin_mgr.refresh_single_service(service_id)
        if result:
            SnackBar.show(self.app_page, "服务刷新成功")
        else:
            SnackBar.show(self.app_page, "服务刷新失败", is_error=True)

    def _on_edit_service(
        self,
        e: ft.ControlEvent,
        service_id: str,
        alias: str,
        plugin_type: str,
    ) -> None:
        """编辑服务凭据"""
        # 获取插件信息
        info = self.plugin_mgr.get_plugin_info(plugin_type)
        if not info:
            return

        # 显示编辑对话框
        dialog = CredentialDialog(
            title=f"编辑 {alias}",
            plugin_type=plugin_type,
            required_fields=info["required_credentials"],
            on_save=lambda values: self._save_edit_service(service_id, values),
            on_cancel=lambda e: self._close_dialog(e),
            initial_values={"alias": alias},
            is_edit_mode=True,
        )

        self.app_page.overlay.append(dialog)
        dialog.open = True
        self.app_page.update()

    def _save_edit_service(self, service_id: str, values: dict[str, str]) -> None:
        """保存编辑后的服务"""
        alias = values.pop("alias", "")

        instance = self.plugin_mgr.update_service_credentials(
            service_id=service_id,
            alias=alias if alias else None,
            credentials=values if values else None,
        )

        if instance:
            SnackBar.show(self.app_page, f"服务 '{alias}' 更新成功")
            self.refresh()
        else:
            SnackBar.show(self.app_page, "更新服务失败", is_error=True)

        self._close_all_dialogs()

    def _on_toggle_service(self, e: ft.ControlEvent, service_id: str) -> None:
        """切换服务启用状态"""
        enabled = e.control.value
        self.config_mgr.update_service(service_id, enabled=enabled)

        status = "启用" if enabled else "禁用"
        SnackBar.show(self.app_page, f"服务已{status}")

    def _on_delete_service(self, e: ft.ControlEvent, service_id: str, alias: str) -> None:
        """删除服务"""
        dialog = ConfirmDialog(
            title="删除服务",
            message=f"确定要删除服务 '{alias}' 吗？此操作不可撤销。",
            confirm_text="删除",
            is_destructive=True,
            on_confirm=lambda e: self._confirm_delete(e, service_id),
            on_cancel=lambda e: self._close_dialog(e),
        )

        self.app_page.overlay.append(dialog)
        dialog.open = True
        self.app_page.update()

    def _confirm_delete(self, e: ft.ControlEvent, service_id: str) -> None:
        """确认删除"""
        # 先关闭对话框，避免事件参数问题
        self._close_all_dialogs()

        result = self.plugin_mgr.remove_service(service_id)

        if result:
            SnackBar.show(self.app_page, "服务已删除")
            self.refresh()
        else:
            SnackBar.show(self.app_page, "删除失败", is_error=True)

    def _close_dialog(self, e: ft.ControlEvent) -> None:
        """关闭对话框"""
        if self.app_page.overlay:
            dialog = self.app_page.overlay[-1]
            if isinstance(dialog, ft.AlertDialog):
                dialog.open = False
                self.app_page.update()

    def _close_all_dialogs(self) -> None:
        """关闭所有对话框"""
        for control in self.app_page.overlay:
            if isinstance(control, ft.AlertDialog):
                control.open = False
        self.app_page.update()

    def refresh(self) -> None:
        """刷新页面内容"""
        self.content = self._build_content()
        self.app_page.update()
