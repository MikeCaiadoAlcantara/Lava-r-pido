from PySide6.QtCore import QDate, Qt
from PySide6.QtGui import QDoubleValidator
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDateEdit,
    QDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.database import Database


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


class AdminDialog(QDialog):
    def __init__(self, database: Database, parent: QWidget | None = None):
        super().__init__(parent)
        self.database = database
        self.setWindowTitle("Lava Rápido Alcantara | Administração")
        self.setMinimumSize(940, 690)
        layout = QVBoxLayout(self)
        header = QHBoxLayout()
        heading = QLabel("Administração")
        heading.setObjectName("pageTitle")
        header.addWidget(heading)
        header.addStretch()
        self.report_button = QPushButton("Relatório")
        self.report_button.clicked.connect(self.open_reports)
        header.addWidget(self.report_button)
        layout.addLayout(header)
        self.tabs = QTabWidget()
        self.report_page = self.build_summary()
        self.tabs.addTab(self.report_page, "Relatórios")
        self.tabs.addTab(self.build_expenses(), "Despesas")
        self.tabs.addTab(self.build_team(), "Equipe e frequência")
        self.tabs.addTab(self.build_benefits(), "Benefícios")
        layout.addWidget(self.tabs)
        self.refresh_all()

    def build_summary(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        date_row = QHBoxLayout()
        today = QDate.currentDate()
        month_start = QDate(today.year(), today.month(), 1)
        self.period_preset = QComboBox()
        self.period_preset.addItem("Semana atual", "week")
        self.period_preset.addItem("Mês atual", "month")
        self.period_preset.addItem("Últimos 3 meses", "three_months")
        self.period_preset.addItem("Últimos 6 meses", "six_months")
        self.period_preset.addItem("Ano atual", "year")
        self.period_preset.addItem("Ano anterior", "previous_year")
        self.period_preset.addItem("Personalizado", "custom")
        self.period_preset.setCurrentIndex(self.period_preset.findData("month"))
        self._updating_period = False
        self.range_start = date_input(month_start)
        self.range_end = date_input(today)
        self.range_start.dateChanged.connect(self._mark_custom_period)
        self.range_end.dateChanged.connect(self._mark_custom_period)
        date_row.addWidget(self.period_preset)
        date_row.addWidget(QLabel("De"))
        date_row.addWidget(self.range_start)
        date_row.addWidget(QLabel("Até"))
        date_row.addWidget(self.range_end)
        refresh = QPushButton("Gerar relatório")
        refresh.clicked.connect(self.generate_report)
        date_row.addWidget(refresh)
        date_row.addStretch()
        layout.addLayout(date_row)

        metrics = QGridLayout()
        self.metric_values: dict[str, QLabel] = {}
        labels = ["Lavagens", "Faturamento", "Despesas + benefícios", "Saldo registrado", "Folha estimada"]
        for index, label in enumerate(labels):
            panel = QFrame()
            panel.setObjectName("surface")
            panel_layout = QVBoxLayout(panel)
            caption = QLabel(label)
            caption.setObjectName("muted")
            value = QLabel("—")
            value.setObjectName("metric")
            self.metric_values[label] = value
            panel_layout.addWidget(caption)
            panel_layout.addWidget(value)
            metrics.addWidget(panel, index // 3, index % 3)
        layout.addLayout(metrics)
        explanation = QLabel("Saldo registrado = faturamento menos despesas e benefícios. A folha estimada considera a diária do funcionário e desconta faltas do período.")
        explanation.setWordWrap(True)
        explanation.setObjectName("muted")
        layout.addWidget(explanation)
        layout.addWidget(QLabel("Faltas registradas no período"))
        self.absence_leaders = QLabel("Mais faltas: — | Menos faltas: —")
        self.absence_leaders.setObjectName("muted")
        layout.addWidget(self.absence_leaders)
        self.attendance_table = table(["Funcionário", "Faltas", "Diária"])
        layout.addWidget(self.attendance_table, 1)
        return page

    def open_reports(self) -> None:
        self.tabs.setCurrentWidget(self.report_page)
        self.generate_report()

    def _mark_custom_period(self) -> None:
        if not self._updating_period:
            self.period_preset.setCurrentIndex(self.period_preset.findData("custom"))

    def generate_report(self) -> None:
        today = QDate.currentDate()
        preset = self.period_preset.currentData()
        start = self.range_start.date()
        end = self.range_end.date()

        if preset == "week":
            start = today.addDays(1 - today.dayOfWeek())
            end = today
        elif preset == "month":
            start = QDate(today.year(), today.month(), 1)
            end = today
        elif preset == "three_months":
            start = QDate(today.year(), today.month(), 1).addMonths(-2)
            end = today
        elif preset == "six_months":
            start = QDate(today.year(), today.month(), 1).addMonths(-5)
            end = today
        elif preset == "year":
            start = QDate(today.year(), 1, 1)
            end = today
        elif preset == "previous_year":
            start = QDate(today.year() - 1, 1, 1)
            end = QDate(today.year() - 1, 12, 31)

        self._updating_period = True
        self.range_start.setDate(start)
        self.range_end.setDate(end)
        self._updating_period = False
        try:
            self.refresh_all()
        except ValueError as error:
            QMessageBox.warning(self, "Período inválido", str(error))

    def build_expenses(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        form = QFrame()
        form.setObjectName("surface")
        fields = QGridLayout(form)
        self.expense_date = date_input()
        self.expense_category = QComboBox()
        self.expense_category.setEditable(True)
        self.expense_category.addItems(["Produtos", "Diárias", "Manutenção", "Contas", "Outros"])
        self.expense_description = QLineEdit()
        self.expense_description.setPlaceholderText("Ex.: shampoo automotivo")
        self.expense_amount = money_input()
        fields.addWidget(QLabel("Data"), 0, 0)
        fields.addWidget(QLabel("Categoria"), 0, 1)
        fields.addWidget(QLabel("Descrição"), 0, 2)
        fields.addWidget(QLabel("Valor (R$)"), 0, 3)
        fields.addWidget(self.expense_date, 1, 0)
        fields.addWidget(self.expense_category, 1, 1)
        fields.addWidget(self.expense_description, 1, 2)
        fields.addWidget(self.expense_amount, 1, 3)
        add = QPushButton("Lançar despesa")
        add.clicked.connect(self.add_expense)
        fields.addWidget(add, 1, 4)
        layout.addWidget(form)
        self.expense_table = table(["Data", "Categoria", "Descrição", "Valor"])
        layout.addWidget(self.expense_table, 1)
        return page

    def build_team(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        form = QFrame()
        form.setObjectName("surface")
        fields = QGridLayout(form)
        self.employee_name = QLineEdit()
        self.employee_phone = QLineEdit()
        self.employee_salary = money_input()
        fields.addWidget(QLabel("Nome"), 0, 0)
        fields.addWidget(QLabel("Telefone"), 0, 1)
        fields.addWidget(QLabel("Valor por dia (R$)"), 0, 2)
        fields.addWidget(self.employee_name, 1, 0)
        fields.addWidget(self.employee_phone, 1, 1)
        fields.addWidget(self.employee_salary, 1, 2)
        add = QPushButton("Cadastrar funcionário")
        add.clicked.connect(self.add_employee)
        fields.addWidget(add, 1, 3)
        layout.addWidget(form)

        attendance = QFrame()
        attendance.setObjectName("surface")
        row = QHBoxLayout(attendance)
        self.attendance_employee = QComboBox()
        self.attendance_date = date_input()
        self.absent_check = QCheckBox("Faltou")
        self.attendance_paid = money_input()
        self.attendance_paid.setPlaceholderText("Valor recebido na diária")
        self.attendance_note = QLineEdit()
        self.attendance_note.setPlaceholderText("Observação (opcional)")
        mark = QPushButton("Salvar frequência")
        mark.clicked.connect(self.mark_attendance)
        row.addWidget(QLabel("Funcionário"))
        row.addWidget(self.attendance_employee, 2)
        row.addWidget(self.attendance_date)
        row.addWidget(self.absent_check)
        row.addWidget(self.attendance_paid)
        row.addWidget(self.attendance_note, 2)
        row.addWidget(mark)
        layout.addWidget(attendance)
        self.employee_table = table(["Funcionário", "Telefone", "Diária"])
        layout.addWidget(self.employee_table, 1)
        return page

    def build_benefits(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        form = QFrame()
        form.setObjectName("surface")
        fields = QGridLayout(form)
        self.benefit_employee = QComboBox()
        self.benefit_period = date_input(QDate.currentDate())
        self.benefit_period.setDisplayFormat("MM/yyyy")
        self.benefit_kind = QComboBox()
        self.benefit_kind.addItems(["Cesta básica", "Bônus", "Sem bônus"])
        self.benefit_amount = money_input()
        self.benefit_note = QLineEdit()
        self.benefit_note.setPlaceholderText("Observação (opcional)")
        fields.addWidget(QLabel("Funcionário"), 0, 0)
        fields.addWidget(QLabel("Período"), 0, 1)
        fields.addWidget(QLabel("Tipo"), 0, 2)
        fields.addWidget(QLabel("Valor (R$)"), 0, 3)
        fields.addWidget(QLabel("Observação"), 0, 4)
        fields.addWidget(self.benefit_employee, 1, 0)
        fields.addWidget(self.benefit_period, 1, 1)
        fields.addWidget(self.benefit_kind, 1, 2)
        fields.addWidget(self.benefit_amount, 1, 3)
        fields.addWidget(self.benefit_note, 1, 4)
        add = QPushButton("Registrar benefício")
        add.clicked.connect(self.add_benefit)
        fields.addWidget(add, 1, 5)
        layout.addWidget(form)
        info = QLabel("Os benefícios registrados entram no custo do período. Registre em Despesas pagamentos que não sejam benefícios.")
        info.setWordWrap(True)
        info.setObjectName("muted")
        layout.addWidget(info)
        return page

    def selected_period(self) -> tuple[str, str]:
        start, end = date_text(self.range_start), date_text(self.range_end)
        if start > end:
            raise ValueError("A data inicial deve ser anterior ou igual à data final.")
        return start, end

    def refresh_all(self) -> None:
        start, end = self.selected_period()
        report = self.database.report(start, end)
        self.metric_values["Lavagens"].setText(str(report["service_count"]))
        self.metric_values["Faturamento"].setText(money_text(report["revenue_cents"]))
        self.metric_values["Despesas + benefícios"].setText(money_text(report["expense_cents"] + report["benefit_cents"]))
        self.metric_values["Saldo registrado"].setText(money_text(report["net_cents"]))
        self.metric_values["Folha estimada"].setText(money_text(report["payroll_estimate_cents"]))
        if report["attendance"]:
            most_names = ", ".join(report["most_absences_names"])
            least_names = ", ".join(report["least_absences_names"])
            self.absence_leaders.setText(
                f"Mais faltas: {most_names} ({report['most_absences']}) | "
                f"Menos faltas: {least_names} ({report['least_absences']})"
            )
        else:
            self.absence_leaders.setText("Mais faltas: — | Menos faltas: —")
        self.attendance_table.setRowCount(0)
        for employee in report["attendance"]:
            name = employee["name"]
            absences = employee["absences"] or 0
            put_row(self.attendance_table, [f"{name} ({absences} falta(s))", str(absences), money_text(employee["monthly_salary_cents"])])
        self.refresh_expenses()
        self.refresh_employees()

    def refresh_expenses(self) -> None:
        if not hasattr(self, "expense_table"):
            return
        start, end = self.selected_period()
        rows = self.database.expenses_between(start, end)
        self.expense_table.setRowCount(0)
        for item in rows:
            put_row(self.expense_table, [item["expense_day"], item["category"], item["description"], money_text(item["amount_cents"])])

    def refresh_employees(self) -> None:
        employees = self.database.employees()
        if hasattr(self, "employee_table"):
            self.employee_table.setRowCount(0)
            for employee in employees:
                put_row(self.employee_table, [employee["name"], employee["phone"], money_text(employee["monthly_salary_cents"])], employee["id"])
        for combo in (getattr(self, "attendance_employee", None), getattr(self, "benefit_employee", None)):
            if combo is None:
                continue
            selected_id = combo.currentData()
            combo.clear()
            for employee in employees:
                combo.addItem(employee["name"], employee["id"])
            if selected_id is not None:
                index = combo.findData(selected_id)
                if index >= 0:
                    combo.setCurrentIndex(index)

    def add_expense(self) -> None:
        try:
            description = self.expense_description.text().strip()
            cents = parse_money(self.expense_amount.text())
            if not description or cents <= 0:
                raise ValueError("Informe uma descrição e um valor maior que zero.")
            self.database.add_expense(date_text(self.expense_date), self.expense_category.currentText(), description, cents)
        except ValueError as error:
            QMessageBox.warning(self, "Confira os dados", str(error) or "Informe um valor válido.")
            return
        self.expense_description.clear()
        self.expense_amount.clear()
        self.refresh_all()

    def add_employee(self) -> None:
        try:
            name = self.employee_name.text().strip()
            salary = parse_money(self.employee_salary.text())
            if not name or salary < 0:
                raise ValueError("Informe o nome e um salário válido.")
            self.database.add_employee(name, self.employee_phone.text(), salary)
        except ValueError as error:
            QMessageBox.warning(self, "Confira os dados", str(error) or "Informe um salário válido.")
            return
        self.employee_name.clear()
        self.employee_phone.clear()
        self.employee_salary.clear()
        self.refresh_all()

    def mark_attendance(self) -> None:
        employee_id = self.attendance_employee.currentData()
        if employee_id is None:
            QMessageBox.information(self, "Sem funcionários", "Cadastre um funcionário antes de lançar frequência.")
            return
        paid_cents = parse_money(self.attendance_paid.text()) if self.attendance_paid.text().strip() else 0
        self.database.set_attendance(
            employee_id,
            date_text(self.attendance_date),
            self.absent_check.isChecked(),
            self.attendance_note.text(),
            paid_cents,
        )
        self.attendance_paid.clear()
        self.attendance_note.clear()
        self.refresh_all()

    def add_benefit(self) -> None:
        employee_id = self.benefit_employee.currentData()
        if employee_id is None:
            QMessageBox.information(self, "Sem funcionários", "Cadastre um funcionário antes de registrar benefícios.")
            return
        kind = self.benefit_kind.currentText()
        if kind == "Sem bônus":
            cents = 0
        else:
            try:
                cents = parse_money(self.benefit_amount.text())
                if cents <= 0:
                    raise ValueError("O valor precisa ser maior que zero.")
            except ValueError as error:
                QMessageBox.warning(self, "Confira os dados", str(error) or "Informe um valor válido.")
                return
        period = self.benefit_period.date().toString("yyyy-MM")
        self.database.add_benefit(
            employee_id, period, kind, cents, self.benefit_note.text()
        )
        self.benefit_amount.clear()
        self.benefit_note.clear()
        self.refresh_all()
