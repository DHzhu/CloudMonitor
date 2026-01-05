"""
对话框组件

提供凭据输入、确认等对话框组件。
"""

import flet as ft


class CredentialDialog(ft.AlertDialog):
    """
    凭据输入对话框

    用于安全地输入 API Key 等敏感信息。
    支持新增和编辑两种模式。
    """

    def __init__(
        self,
        title: str = "添加服务",
        plugin_type: str = "",
        required_fields: list[str] | None = None,
        on_save: ft.ControlEvent | None = None,
        on_cancel: ft.ControlEvent | None = None,
        initial_values: dict[str, str] | None = None,
        is_edit_mode: bool = False,
    ) -> None:
        self.plugin_type = plugin_type
        self.required_fields = required_fields or []
        self.on_save_callback = on_save
        self.initial_values = initial_values or {}
        self.is_edit_mode = is_edit_mode
        self.field_refs: dict[str, ft.TextField] = {}

        # 创建字段
        fields = self._build_fields()

        super().__init__(
            modal=True,
            title=ft.Text(title, size=18, weight=ft.FontWeight.BOLD),
            content=ft.Container(
                content=ft.Column(
                    controls=fields,
                    spacing=16,
                    scroll=ft.ScrollMode.AUTO,
                ),
                width=400,
                padding=ft.Padding.only(top=16),
            ),
            actions=[
                ft.TextButton("取消", on_click=on_cancel),
                ft.ElevatedButton(
                    "保存",
                    on_click=self._handle_save,
                ),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )

    def _build_fields(self) -> list[ft.Control]:
        """构建输入字段"""
        fields = []

        # 编辑模式提示
        if self.is_edit_mode:
            fields.append(
                ft.Container(
                    content=ft.Text(
                        "出于安全考虑，凭据需要重新输入",
                        size=12,
                        color=ft.Colors.ORANGE_300,
                        italic=True,
                    ),
                    padding=ft.Padding.only(bottom=8),
                )
            )

        # 别名字段
        alias_field = ft.TextField(
            label="别名",
            hint_text="例如：个人账户",
            border_radius=8,
            value=self.initial_values.get("alias", ""),
        )
        self.field_refs["alias"] = alias_field
        fields.append(alias_field)

        # 凭据字段（根据 required_fields 动态生成）
        field_labels = {
            "api_key": ("API Key", "请输入 API Key"),
            "access_key_id": ("Access Key ID", "请输入 AWS Access Key ID"),
            "secret_access_key": ("Secret Access Key", "请输入 AWS Secret Access Key"),
            "region": ("区域", "例如：us-east-1"),
            "subscription_id": ("订阅 ID", "Azure 订阅 ID"),
            "tenant_id": ("租户 ID", "Azure 租户 ID"),
            "client_id": ("客户端 ID", "Azure 应用程序 ID"),
            "client_secret": ("客户端密钥", "Azure 应用程序密钥"),
        }

        for field_name in self.required_fields:
            label, hint = field_labels.get(field_name, (field_name, f"请输入 {field_name}"))
            is_password = "key" in field_name.lower() or "secret" in field_name.lower()

            field = ft.TextField(
                label=label,
                hint_text=hint,
                password=is_password,
                can_reveal_password=is_password,
                border_radius=8,
            )
            self.field_refs[field_name] = field
            fields.append(field)

        return fields

    def _handle_save(self, e: ft.ControlEvent) -> None:
        """处理保存"""
        # 收集所有字段值
        values = {}
        for name, field in self.field_refs.items():
            values[name] = field.value or ""

        # 验证必填字段
        missing = []
        for field_name in self.required_fields:
            if not values.get(field_name):
                missing.append(field_name)

        if missing:
            # 显示验证错误
            for field_name in missing:
                if field_name in self.field_refs:
                    self.field_refs[field_name].error_text = "此字段为必填项"
            if e.page:
                e.page.update()
            return

        # 调用保存回调
        if self.on_save_callback:
            self.on_save_callback(values)

    def get_values(self) -> dict[str, str]:
        """获取所有字段值"""
        return {name: field.value or "" for name, field in self.field_refs.items()}


class ConfirmDialog(ft.AlertDialog):
    """
    确认对话框

    用于危险操作的二次确认。
    """

    def __init__(
        self,
        title: str = "确认操作",
        message: str = "确定要执行此操作吗？",
        confirm_text: str = "确定",
        cancel_text: str = "取消",
        is_destructive: bool = False,
        on_confirm: ft.ControlEvent | None = None,
        on_cancel: ft.ControlEvent | None = None,
    ) -> None:
        super().__init__(
            modal=True,
            title=ft.Text(title, size=18, weight=ft.FontWeight.BOLD),
            content=ft.Text(
                message,
                size=14,
                color=ft.Colors.WHITE_70,
            ),
            actions=[
                ft.TextButton(cancel_text, on_click=on_cancel),
                ft.ElevatedButton(
                    confirm_text,
                    bgcolor=ft.Colors.RED if is_destructive else None,
                    on_click=on_confirm,
                ),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )


class SnackBar:
    """
    消息提示条

    提供简单的消息反馈。
    """

    @staticmethod
    def show(
        page: ft.Page,
        message: str,
        is_error: bool = False,
        duration: int = 3000,
    ) -> None:
        """显示消息提示"""
        snack = ft.SnackBar(
            content=ft.Text(
                message,
                color=ft.Colors.WHITE,
            ),
            bgcolor=ft.Colors.RED if is_error else ft.Colors.GREEN_700,
            duration=duration,
        )
        page.overlay.append(snack)
        snack.open = True
        page.update()
