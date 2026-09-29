"""KASP Admin Paneli — Kullanıcı Yönetim Diyaloğu."""

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)
from kasp.i18n import tr
from kasp.security import Session


class AdminPanelDialog(QDialog):
    def __init__(self, user_manager, parent=None):
        super().__init__(parent)
        self._user_manager = user_manager
        self._setup_ui()
        self._refresh_table()

    def _setup_ui(self):
        self.setWindowTitle(tr("👥 Kullanıcı Yönetimi"))
        try:
            from kasp.ui.responsive import dialog_size
            self.resize(*dialog_size(0.55, 0.55))
        except Exception:
            self.resize(700, 480)

        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        title = QLabel(tr("Kullanıcı Yönetim Paneli"))
        title.setFont(QFont("Segoe UI", 13, QFont.Bold))
        layout.addWidget(title)

        # ── Kullanıcı Tablosu ──
        self._table = QTableWidget(0, 6)
        self._table.setHorizontalHeaderLabels([
            "ID", "Kullanıcı Adı", "Rol", "Ad Soyad", "Aktif", "Son Giriş"
        ])
        self._table.setSelectionBehavior(QTableWidget.SelectRows)
        self._table.setSelectionMode(QTableWidget.SingleSelection)
        self._table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self._table.setColumnHidden(0, True)
        layout.addWidget(self._table)

        # ── Butonlar ──
        btn_layout = QHBoxLayout()
        self._add_btn = QPushButton(tr("➕ Kullanıcı Ekle"))
        self._add_btn.clicked.connect(self._add_user)
        btn_layout.addWidget(self._add_btn)

        self._edit_btn = QPushButton(tr("✏️ Düzenle"))
        self._edit_btn.clicked.connect(self._edit_user)
        btn_layout.addWidget(self._edit_btn)

        self._toggle_btn = QPushButton(tr("🔄 Aktif/Pasif"))
        self._toggle_btn.clicked.connect(self._toggle_active)
        btn_layout.addWidget(self._toggle_btn)

        self._reset_btn = QPushButton(tr("🔑 Şifre Sıfırla"))
        self._reset_btn.clicked.connect(self._reset_password)
        btn_layout.addWidget(self._reset_btn)

        self._delete_btn = QPushButton(tr("🗑️ Sil"))
        self._delete_btn.clicked.connect(self._delete_user)
        btn_layout.addWidget(self._delete_btn)
        layout.addLayout(btn_layout)

        from kasp.config_manager import get_config_manager
        eng_mode = get_config_manager().get("updates.engineering_mode", False)
        self._eng_cb = QCheckBox("🛠️ Engineering Mode — detaylı hesaplama diagnoztiği (sadece admin)")
        self._eng_cb.setChecked(eng_mode)
        self._eng_cb.toggled.connect(self._toggle_engineering_mode)
        layout.addWidget(self._eng_cb)

        button_box = QDialogButtonBox(QDialogButtonBox.Close)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

    def _toggle_engineering_mode(self, checked):
        from kasp.config_manager import get_config_manager
        get_config_manager().set("updates.engineering_mode", checked)

    def _refresh_table(self):
        users = self._user_manager.list_users()
        self._table.setRowCount(len(users))
        for row, user in enumerate(users):
            self._table.setItem(row, 0, QTableWidgetItem(str(user.id)))
            self._table.setItem(row, 1, QTableWidgetItem(user.username))
            self._table.setItem(row, 2, QTableWidgetItem(user.role))
            self._table.setItem(row, 3, QTableWidgetItem(user.full_name))
            active = "✅" if user.is_active else "❌"
            self._table.setItem(row, 4, QTableWidgetItem(active))
            self._table.setItem(row, 5, QTableWidgetItem(user.last_login or "—"))

    def _selected_user_id(self):
        row = self._table.currentRow()
        if row < 0:
            return None
        item = self._table.item(row, 0)
        return int(item.text()) if item else None

    def _selected_username(self):
        row = self._table.currentRow()
        if row < 0:
            return None
        item = self._table.item(row, 1)
        return item.text() if item else None

    def _check_manage_users_permission(self):
        if not Session.authorize("manage_users"):
            QMessageBox.warning(self, tr("Yetki Yok"), tr("Kullanıcı yönetimi yetkiniz yok."))
            return False
        return True

    def _selected_user(self):
        user_id = self._selected_user_id()
        if user_id is None:
            return None
        for u in self._user_manager.list_users():
            uid = u.get("id") if isinstance(u, dict) else getattr(u, "id", None)
            if uid == user_id:
                return u
        return None

    def _add_user(self):
        if not self._check_manage_users_permission():
            return
        dialog = UserEditDialog(self, mode="add")
        if dialog.exec_() == QDialog.Accepted:
            data = dialog.get_data()
            user, err = self._user_manager.create_user(
                username=data["username"],
                password=data["password"],
                role=data["role"],
                full_name=data["full_name"],
                email=data["email"],
            )
            if err:
                QMessageBox.warning(self, tr("Hata"), err)
            else:
                self._refresh_table()

    def _edit_user(self):
        if not self._check_manage_users_permission():
            return
        user_id = self._selected_user_id()
        if user_id is None:
            QMessageBox.information(self, tr("Bilgi"), tr("Lütfen bir kullanıcı seçin."))
            return
        selected_user = self._selected_user()
        dialog = UserEditDialog(self, mode="edit", user=selected_user)
        if dialog.exec_() == QDialog.Accepted:
            data = dialog.get_data()
            updates = {}
            if data.get("role"):
                updates["role"] = data["role"]
            if "full_name" in data:
                updates["full_name"] = data["full_name"]
            if "email" in data:
                updates["email"] = data["email"]
            if updates:
                self._user_manager.update_user(user_id, **updates)
            if data.get("password"):
                ok, err = self._user_manager.admin_reset_password(user_id, data["password"])
                if err:
                    QMessageBox.warning(self, tr("Hata"), err)
            self._refresh_table()

    def _toggle_active(self):
        if not self._check_manage_users_permission():
            return
        user_id = self._selected_user_id()
        if user_id is None:
            return
        username = self._selected_username()
        current_user = Session.current_user()
        if current_user is not None and username == current_user.username:
            QMessageBox.warning(self, tr("Hata"), tr("Kendi hesabınızı pasif yapamazsınız."))
            return
        self._user_manager.toggle_user_active(user_id)
        self._refresh_table()

    def _reset_password(self):
        if not self._check_manage_users_permission():
            return
        user_id = self._selected_user_id()
        if user_id is None:
            return
        dialog = PasswordResetDialog(self)
        if dialog.exec_() == QDialog.Accepted:
            new_pw = dialog.get_password()
            ok, err = self._user_manager.admin_reset_password(user_id, new_pw)
            if err:
                QMessageBox.warning(self, tr("Hata"), err)
            else:
                QMessageBox.information(self, tr("Başarılı"), tr("Şifre sıfırlandı."))

    def _delete_user(self):
        if not self._check_manage_users_permission():
            return
        user_id = self._selected_user_id()
        if user_id is None:
            return
        username = self._selected_username()
        current_user = Session.current_user()
        if current_user is not None and username == current_user.username:
            QMessageBox.warning(self, tr("Hata"), tr("Kendi hesabınızı silemezsiniz."))
            return
        reply = QMessageBox.question(
            self, tr("Silme Onayı"),
            tr(f"'{username}' kullanıcısını silmek istediğinize emin misiniz?"),
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            self._user_manager.delete_user(user_id)
            self._refresh_table()


class UserEditDialog(QDialog):
    def __init__(self, parent=None, mode="add", user=None):
        super().__init__(parent)
        self._mode = mode
        self._user = user
        self.setWindowTitle(tr("Kullanıcı Ekle") if mode == "add" else tr("Kullanıcı Düzenle"))
        self.resize(360, 260)
        self._setup_ui()
        if user is not None:
            self._populate_from_user(user)

    def _setup_ui(self):
        layout = QFormLayout(self)
        layout.setSpacing(8)

        self._username_edit = QLineEdit()
        self._username_edit.setPlaceholderText("zorunlu")
        if self._mode == "edit":
            self._username_edit.setReadOnly(True)
        layout.addRow(tr("Kullanıcı Adı:"), self._username_edit)

        self._password_edit = QLineEdit()
        self._password_edit.setEchoMode(QLineEdit.Password)
        if self._mode == "add":
            self._password_edit.setPlaceholderText(tr("En az 8 karakter, büyük/küçük harf ve rakam"))
        else:
            self._password_edit.setPlaceholderText(tr("Boş bırakılırsa değişmez (en az 8 karakter)"))
        layout.addRow(tr("Şifre:"), self._password_edit)

        self._fullname_edit = QLineEdit()
        layout.addRow(tr("Ad Soyad:"), self._fullname_edit)

        self._email_edit = QLineEdit()
        layout.addRow(tr("E-posta:"), self._email_edit)

        self._role_combo = QComboBox()
        self._role_combo.addItems(["user", "engineer", "admin", "viewer"])
        layout.addRow(tr("Rol:"), self._role_combo)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._validate_and_accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    def _populate_from_user(self, user):
        def _val(key, default=""):
            if isinstance(user, dict):
                return user.get(key, default) or default
            return getattr(user, key, default) or default

        self._username_edit.setText(str(_val("username")))
        self._fullname_edit.setText(str(_val("full_name")))
        self._email_edit.setText(str(_val("email")))
        role = str(_val("role", "user"))
        idx = self._role_combo.findText(role)
        if idx >= 0:
            self._role_combo.setCurrentIndex(idx)

    def _validate_and_accept(self):
        if self._mode == "add":
            if not self._username_edit.text().strip():
                QMessageBox.warning(self, tr("Hata"), tr("Kullanıcı adı zorunludur."))
                return
            if len(self._password_edit.text()) < 8:
                QMessageBox.warning(self, tr("Hata"), tr("Şifre en az 8 karakter olmalıdır."))
                return
        elif self._password_edit.text() and len(self._password_edit.text()) < 8:
            QMessageBox.warning(self, tr("Hata"), tr("Şifre en az 8 karakter olmalıdır."))
            return
        self.accept()

    def get_data(self):
        return {
            "username": self._username_edit.text().strip(),
            "password": self._password_edit.text(),
            "role": self._role_combo.currentText(),
            "full_name": self._fullname_edit.text().strip(),
            "email": self._email_edit.text().strip(),
        }


class PasswordResetDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr("Şifre Sıfırla"))
        self.resize(300, 100)
        layout = QFormLayout(self)
        self._pw_edit = QLineEdit()
        self._pw_edit.setEchoMode(QLineEdit.Password)
        self._pw_edit.setPlaceholderText(tr("En az 8 karakter, büyük/küçük harf ve rakam"))
        layout.addRow(tr("Yeni Şifre:"), self._pw_edit)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._validate_and_accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    def _validate_and_accept(self):
        if len(self._pw_edit.text()) < 8:
            QMessageBox.warning(self, tr("Hata"), tr("Şifre en az 8 karakter olmalıdır."))
            return
        self.accept()

    def get_password(self):
        return self._pw_edit.text()
