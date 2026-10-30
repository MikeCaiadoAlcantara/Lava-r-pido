from datetime import date

from PySide6.QtCore import QDate, Qt
from PySide6.QtGui import QDoubleValidator
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDateEdit,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.database import Database
from app.admin import AdminDialog


def date_text(widget: QDateEdit) -> str:
    return widget.date().toString("yyyy-MM-dd")


def money_text(cents: int) -> str:
    amount = f"{cents / 100:,.2f}"
    return "R$ " + amount.replace(",", "_").replace(".", ",").replace("_", ".")


def parse_money(text: str) -> int:
    normalized = text.strip().replace("R$", "").replace(" ", "")
    if "," in normalized:
        normalized = normalized.replace(".", "").replace(",", ".")
    return round(float(normalized) * 100)


def count_label_text(count: int) -> str:
    if count == 1:
        return "1 lavagem"
    return f"{count} lavagens"


def money_input() -> QLineEdit:
    field = QLineEdit()
    field.setPlaceholderText("0,00")
    field.setValidator(QDoubleValidator(0, 99_999_999, 2, field))
    return field


def date_input(value: QDate | None = None) -> QDateEdit:
    field = QDateEdit(value or QDate.currentDate())
    field.setCalendarPopup(True)
    field.setDisplayFormat("dd/MM/yyyy")
    return field


def table(headers: list[str]) -> QTableWidget:
    widget = QTableWidget(0, len(headers))
    widget.setHorizontalHeaderLabels(headers)
    widget.setAlternatingRowColors(True)
    widget.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
    widget.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
    widget.verticalHeader().setVisible(False)
    widget.horizontalHeader().setStretchLastSection(True)
    return widget


def put_row(widget: QTableWidget, values: list[str], hidden_id: int | None = None) -> None:
    row = widget.rowCount()
    widget.insertRow(row)
    for column, value in enumerate(values):
        item = QTableWidgetItem(value)
        if column == 0 and hidden_id is not None:
            item.setData(Qt.ItemDataRole.UserRole, hidden_id)
        widget.setItem(row, column, item)


class AdminSetupDialog(QDialog):
    def __init__(self, database: Database):
        super().__init__()
        self.database = database
        self.setWindowTitle("Configurar administrador")
        self.setMinimumWidth(390)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Crie a conta que protegerá os dados administrativos."))
        form = QFormLayout()
        self.username = QLineEdit()
        self.password = QLineEdit()
        self.password.setEchoMode(QLineEdit.EchoMode.Password)
        self.confirm = QLineEdit()
        self.confirm.setEchoMode(QLineEdit.EchoMode.Password)
        form.addRow("Usuário", self.username)
        form.addRow("Senha (mínimo 6 caracteres)", self.password)
        form.addRow("Confirme a senha", self.confirm)
        layout.addLayout(form)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def accept(self) -> None:
        if not self.username.text().strip():
            QMessageBox.warning(self, "Dados necessários", "Informe um nome de usuário.")
            return
        if len(self.password.text()) < 6:
            QMessageBox.warning(self, "Senha curta", "A senha precisa ter pelo menos 6 caracteres.")
            return
        if self.password.text() != self.confirm.text():
            QMessageBox.warning(self, "Senhas diferentes", "A confirmação não corresponde à senha.")
            return
        try:
            self.database.create_admin(self.username.text(), self.password.text())
        except Exception:
            QMessageBox.warning(self, "Erro ao salvar", "Não foi possível salvar o administrador no banco de dados.")
            return
        super().accept()


class LoginDialog(QDialog):
    def __init__(self, database: Database, title: str = "Acesso ao sistema"):
        super().__init__()
        self.database = database
        self.setWindowTitle(title)
        self.setMinimumWidth(360)
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.username = QLineEdit()
        self.password = QLineEdit()
        self.password.setEchoMode(QLineEdit.EchoMode.Password)
        form.addRow("Usuário", self.username)
        form.addRow("Senha", self.password)
        layout.addLayout(form)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.check_credentials)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def check_credentials(self) -> None:
        if self.database.authenticate(self.username.text(), self.password.text()):
            self.accept()
        else:
            self.password.clear()
            QMessageBox.warning(self, "Acesso negado", "Usuário ou senha incorretos.")


class AdminLoginDialog(LoginDialog):
    def __init__(self, database: Database):
        super().__init__(database, "Acesso administrativo")


class MainWindow(QMainWindow):
    def __init__(self, database: Database):
        super().__init__()
        self.database = database
        self.setWindowTitle("Lava Rápido Alcantara | Operação")
        self.setMinimumSize(900, 640)
        root = QWidget()
        layout = QVBoxLayout(root)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(18)

        header = QHBoxLayout()
        title_group = QVBoxLayout()
        title = QLabel("Lava Rápido Alcantara")
        title.setObjectName("pageTitle")
        subtitle = QLabel("Registro de lavagens")
        subtitle.setObjectName("muted")
        title_group.addWidget(title)
        title_group.addWidget(subtitle)
        header.addLayout(title_group)
        header.addStretch()
        self.admin_button = QPushButton("Área administrativa")
        self.admin_button.setObjectName("secondaryButton")
        self.admin_button.clicked.connect(self.open_admin)
        header.addWidget(self.admin_button)
        layout.addLayout(header)

        daily_bar = QHBoxLayout()
        daily_bar.addWidget(QLabel("Data do movimento"))
        self.service_date = date_input()
        self.service_date.dateChanged.connect(self.refresh_services)
        daily_bar.addWidget(self.service_date)
        daily_bar.addStretch()
        self.count_label = QLabel(count_label_text(0))
        self.count_label.setObjectName("metric")
        daily_bar.addWidget(self.count_label)
        layout.addLayout(daily_bar)

        form_box = QFrame()
        form_box.setObjectName("surface")
        form_layout = QGridLayout(form_box)
        form_layout.setContentsMargins(18, 16, 18, 16)
        self.vehicle = QLineEdit()
        self.vehicle.setPlaceholderText("Opcional")
        self.description = QComboBox()
        self.description.setEditable(True)
        self.description.addItems(["Lavagem simples", "Lavagem completa", "Higienização", "Outro"])
        self.amount = money_input()
        self.observation = QLineEdit()
        self.observation.setPlaceholderText("Opcional")
        form_layout.addWidget(QLabel("Veículo / placa"), 0, 0)
        form_layout.addWidget(QLabel("Serviço"), 0, 1)
        form_layout.addWidget(QLabel("Valor (R$)"), 0, 2)
        form_layout.addWidget(QLabel("Observação"), 0, 3)
        form_layout.addWidget(self.vehicle, 1, 0)
        form_layout.addWidget(self.description, 1, 1)
        form_layout.addWidget(self.amount, 1, 2)
        form_layout.addWidget(self.observation, 1, 3)
        self.save_service = QPushButton("Registrar lavagem")
        self.save_service.clicked.connect(self.add_service)
        form_layout.addWidget(self.save_service, 1, 4)
        layout.addWidget(form_box)

        self.service_table = table(["Veículo / placa", "Serviço", "Valor", "Observação", "Lançado às"])
        layout.addWidget(self.service_table, 1)
        footer = QHBoxLayout()
        footer.addWidget(QLabel("Os valores detalhados ficam nesta tela; relatórios financeiros ficam na área administrativa."))
        footer.addStretch()
        self.delete_button = QPushButton("Excluir selecionado")
        self.delete_button.setObjectName("quietButton")
        self.delete_button.clicked.connect(self.delete_service)
        footer.addWidget(self.delete_button)
        layout.addLayout(footer)
        self.setCentralWidget(root)
        self.refresh_services()

    def add_service(self) -> None:
        try:
            description = self.description.currentText().strip()
            if not description:
                raise ValueError("Informe o serviço.")
            cents = parse_money(self.amount.text())
            if cents <= 0:
                raise ValueError("O valor precisa ser maior que zero.")
            self.database.add_service(
                date_text(self.service_date), self.vehicle.text(), description, cents, self.observation.text().strip()
            )
        except ValueError as error:
            QMessageBox.warning(self, "Confira os dados", str(error) or "Informe um valor válido.")
            return
        self.amount.clear()
        self.vehicle.clear()
        self.observation.clear()
        self.refresh_services()

    def refresh_services(self) -> None:
        rows = self.database.services_for_day(date_text(self.service_date))
        self.service_table.setRowCount(0)
        for item in rows:
            put_row(
                self.service_table,
                [item["vehicle"] or "—", item["description"], money_text(item["amount_cents"]),
                 item["payment_method"] or "—", item["created_at"][11:16]],
                item["id"],
            )
        self.count_label.setText(count_label_text(len(rows)))

    def delete_service(self) -> None:
        row = self.service_table.currentRow()
        if row < 0:
            return
        service_id = self.service_table.item(row, 0).data(Qt.ItemDataRole.UserRole)
        confirm = QMessageBox.question(self, "Excluir lavagem", "Deseja excluir este lançamento?")
        if confirm == QMessageBox.StandardButton.Yes:
            self.database.delete_service(service_id)
            self.refresh_services()

    def open_admin(self) -> None:
        login = AdminLoginDialog(self.database)
        if login.exec() == QDialog.DialogCode.Accepted:
            AdminDialog(self.database, self).exec()


