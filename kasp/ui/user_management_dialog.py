"""
KASP User Management Dialog (v2.1)

Standalone dialog for:
  - Creating new users with roles
  - Deleting users
  - Resetting passwords (admin)
  - Setting security questions
  - Password recovery via security question

Accessible from login screen ("Kullanici Yonetimi" button) and admin panel.
"""

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QHeaderView,
    QGroupBox,
)

from kasp.security import hash_password, generate_initial_admin_password
from kasp.core.user_manager import validate_password_policy
from kasp.i18n import tr


class UserManagementDialog(QDialog):
    def __init__(self, db, current_user, parent=None):
        super().__init__(parent)
        self._db = db
        self._current_user = current_user
        self._is_admin = current_user and current_user.role == "admin"
        self._setup_ui()
        self._load_users()

    def _setup_ui(self):
        self.setWindowTitle(tr("Kullanici Yonetimi"))
        self.setMinimumSize(650, 500)
        self.resize(700, 550)

        layout = QVBoxLayout(self)
        layout.setSpacing(8)

        title = QLabel(tr("Kullanici Yonetimi"))
        title.setFont(QFont("Segoe UI", 14, QFont.Bold))
        layout.addWidget(title)

        self._user_table = QTableWidget()
        self._user_table.setColumnCount(5)
        self._user_table.setHorizontalHeaderLabels([
            tr("Kullanici Adi"), tr("Rol"), tr("Ad Soyad"),
            tr("Aktif"), tr("Son Giris")
        ])
        self._user_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self._user_table.setSelectionBehavior(QTableWidget.SelectRows)
        self._user_table.setEditTriggers(QTableWidget.NoEditTriggers)
        layout.addWidget(self._user_table)

        if self._is_admin:
            admin_group = QGroupBox(tr("Admin Islemleri"))
            admin_layout = QVBoxLayout(admin_group)

            form = QFormLayout()
            self._new_username = QLineEdit()
            self._new_username.setPlaceholderText(tr("kullanici_adi"))
            self._new_password = QLineEdit()
            self._new_password.setEchoMode(QLineEdit.Password)
            self._new_password.setPlaceholderText(tr("En az 8 karakter, buyuk+kucuk harf+rakam"))
            self._new_fullname = QLineEdit()
            self._new_fullname.setPlaceholderText(tr("Ad Soyad (opsiyonel)"))
            self._role_combo = QComboBox()
            self._role_combo.addItems(["user", "engineer", "viewer", "admin"])
            self._role_combo.setCurrentText("user")

            form.addRow(tr("Kullanici Adi:"), self._new_username)
            form.addRow(tr("Sifre:"), self._new_password)
            form.addRow(tr("Ad Soyad:"), self._new_fullname)
            form.addRow(tr("Rol:"), self._role_combo)
            admin_layout.addLayout(form)

            btn_layout = QHBoxLayout()
            add_btn = QPushButton(tr("Kullanici Ekle"))
            add_btn.clicked.connect(self._add_user)
            reset_btn = QPushButton(tr("Secili Kullanicinin Sifresini Sifirla"))
            reset_btn.clicked.connect(self._reset_selected_password)
            delete_btn = QPushButton(tr("Secili Kullaniciyi Sil"))
            delete_btn.clicked.connect(self._delete_selected)
            delete_btn.setStyleSheet("QPushButton { color: #c62828; }")

            btn_layout.addWidget(add_btn)
            btn_layout.addWidget(reset_btn)
            btn_layout.addWidget(delete_btn)
            admin_layout.addLayout(btn_layout)
            layout.addWidget(admin_group)

        self._status_label = QLabel("")
        layout.addWidget(self._status_label)

        close_btn = QPushButton(tr("Kapat"))
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn)

    def _load_users(self):
        self._user_table.setRowCount(0)
        users = self._db.get_all_users()
        for u in users:
            row = self._user_table.rowCount()
            self._user_table.insertRow(row)
            self._user_table.setItem(row, 0, QTableWidgetItem(u.get("username", "")))
            self._user_table.setItem(row, 1, QTableWidgetItem(u.get("role", "")))
            self._user_table.setItem(row, 2, QTableWidgetItem(u.get("full_name", "")))
            active = tr("Evet") if u.get("is_active", 1) else tr("Hayir")
            self._user_table.setItem(row, 3, QTableWidgetItem(active))
            self._user_table.setItem(row, 4, QTableWidgetItem(u.get("last_login", "-")))

    def _selected_username(self):
        row = self._user_table.currentRow()
        if row < 0:
            return None
        item = self._user_table.item(row, 0)
        return item.text() if item else None

    def _add_user(self):
        username = self._new_username.text().strip()
        password = self._new_password.text()
        fullname = self._new_fullname.text().strip()
        role = self._role_combo.currentText()

        if not username:
            self._status_label.setText(tr("Kullanici adi zorunludur."))
            return
        if not password:
            self._status_label.setText(tr("Sifre zorunludur."))
            return

        policy_err = validate_password_policy(password)
        if policy_err:
            self._status_label.setText(policy_err)
            return

        existing = self._db.get_user_by_username(username)
        if existing:
            self._status_label.setText(tr(f"'{username}' zaten kayitli."))
            return

        user_id = self._db.create_user(username, hash_password(password), role, fullname)
        if user_id is None:
            self._status_label.setText(tr("Kullanici olusturulamadi."))
            return

        self._status_label.setText(tr(f"'{username}' olusturuldu."))
        self._new_username.clear()
        self._new_password.clear()
        self._new_fullname.clear()
        self._load_users()

    def _reset_selected_password(self):
        username = self._selected_username()
        if not username:
            self._status_label.setText(tr("Lutfen bir kullanici secin."))
            return

        reply = QMessageBox.question(
            self, tr("Sifre Sifirla"),
            tr(f"'{username}' kullanicisinin sifresi sifirlanacak.\nDevam et?"),
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return

        new_pw = generate_initial_admin_password()
        user = self._db.get_user_by_username(username)
        if not user:
            self._status_label.setText(tr("Kullanici bulunamadi."))
            return

        ok = self._db.update_user(
            user["id"], password_hash=hash_password(new_pw), must_change_password=1
        )
        if ok:
            QMessageBox.information(
                self, tr("Sifre Sifirlandi"),
                tr(f"'{username}' icin gecici sifre: {new_pw}\n\n"
                   f"Bu sifreyi kullaniciya iletin. Ilk giris sonrasi degistirmesi zorunludur.")
            )
            self._status_label.setText(tr(f"'{username}' sifresi sifirlandi."))
        else:
            self._status_label.setText(tr("Sifre sifirlanamadi."))

    def _delete_selected(self):
        username = self._selected_username()
        if not username:
            self._status_label.setText(tr("Lutfen bir kullanici secin."))
            return
        if username == self._current_user.username:
            self._status_label.setText(tr("Kendinizi silemezsiniz."))
            return

        reply = QMessageBox.warning(
            self, tr("Kullanici Sil"),
            tr(f"'{username}' kullanicisini silmek istediginize emin misiniz?\n\n"
               f"Bu islem geri alinamaz!"),
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return

        user = self._db.get_user_by_username(username)
        if user:
            self._db.delete_user(user["id"])
            self._status_label.setText(tr(f"'{username}' silindi."))
            self._load_users()
