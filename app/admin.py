from PySide6.QtCore import QDate, Qt, Signal
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
    business_name_changed = Signal(str)

    def __init__(self, database: Database, parent: QWidget | None = None):
        super().__init__(parent)
        self.database = database
        self.setWindowTitle(f"{database.business_name() or 'Administração'} | Administração")
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
        self.tabs.addTab(self.build_business_settings(), "Estabelecimento")
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
        labels = [
            "Carros / serviços",
            "Lavagens simples",
            "Lavagens completas",
            "Faturamento",
            "Despesas lançadas",
            "Diárias da equipe",
            "Benefícios",
            "Total de saídas",
            "Saldo registrado",
            "Folha estimada",
        ]
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
        explanation = QLabel(
            "O saldo registrado desconta despesas lançadas, diárias de presenças marcadas e benefícios. "
            "A folha estimada é exibida separadamente e não entra no saldo para evitar "
            "duplicar valores: diárias só contam quando a presença é registrada."
        )
        explanation.setWordWrap(True)
        explanation.setObjectName("muted")
        layout.addWidget(explanation)
        self.report_detail_tabs = QTabWidget()
        self.service_type_table = table(["Serviço", "Quantidade", "Entradas"])
        self.report_detail_tabs.addTab(self.service_type_table, "Serviços por tipo")
        self.service_detail_table = table(["Data", "Veículo / placa", "Serviço", "Valor"])
        self.report_detail_tabs.addTab(self.service_detail_table, "Atendimentos")
        self.expense_report_table = table(["Data", "Categoria", "Descrição", "Valor"])
        self.report_detail_tabs.addTab(self.expense_report_table, "Despesas")
        self.benefit_report_table = table(["Período", "Funcionário", "Tipo", "Observação", "Valor"])
        self.report_detail_tabs.addTab(self.benefit_report_table, "Benefícios")
        attendance_page = QWidget()
        attendance_layout = QVBoxLayout(attendance_page)
        attendance_layout.addWidget(QLabel("Faltas registradas no período"))
        self.absence_leaders = QLabel("Mais faltas: — | Menos faltas: —")
        self.absence_leaders.setObjectName("muted")
        attendance_layout.addWidget(self.absence_leaders)
        self.attendance_table = table(["Funcionário", "Faltas", "Diária"])
        attendance_layout.addWidget(self.attendance_table)
        self.report_detail_tabs.addTab(attendance_page, "Frequência")
        layout.addWidget(self.report_detail_tabs, 1)
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
        summary = QGridLayout()
        self.expense_summary_values: dict[str, QLabel] = {}
        for index, label in enumerate(
            ("Despesas lançadas", "Diárias da equipe", "Benefícios", "Total de saídas")
        ):
            panel = QFrame()
            panel.setObjectName("surface")
            panel_layout = QVBoxLayout(panel)
            caption = QLabel(label)
            caption.setObjectName("muted")
            value = QLabel("—")
            value.setObjectName("metric")
            self.expense_summary_values[label] = value
            panel_layout.addWidget(caption)
            panel_layout.addWidget(value)
            summary.addWidget(panel, 0, index)
        layout.addLayout(summary)

        form = QFrame()
        form.setObjectName("surface")
        fields = QGridLayout(form)
        self.expense_date = date_input()
        self.expense_category = QComboBox()
        self.expense_category.addItems(
            ["Diária do pessoal", "Produtos", "Água", "Outros"]
        )
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
        expense_note = QLabel(
            "As diárias registradas pela frequência são incluídas em “Diária do pessoal”. "
            "Não lance novamente a mesma diária manualmente."
        )
        expense_note.setObjectName("muted")
        expense_note.setWordWrap(True)
        layout.addWidget(expense_note)

        self.expense_detail_tabs = QTabWidget()
        self.expense_table = table(["Data", "Categoria", "Descrição / funcionário", "Valor"])
        self.expense_detail_tabs.addTab(self.expense_table, "Despesas lançadas")
        self.expense_category_table = table(["Tipo de despesa", "Lançamentos", "Valor"])
        self.expense_detail_tabs.addTab(self.expense_category_table, "Despesas por tipo")
        self.employee_expense_table = table(["Data", "Funcionário", "Diária considerada"])
        self.expense_detail_tabs.addTab(self.employee_expense_table, "Diárias por presença")
        layout.addWidget(self.expense_detail_tabs, 1)
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
        rate_editor = QHBoxLayout()
        self.employee_rate_date = date_input()
        self.employee_new_rate = money_input()
        self.employee_new_rate.setPlaceholderText("Nova diária")
        change_rate = QPushButton("Alterar diária do selecionado")
        change_rate.clicked.connect(self.change_employee_rate)
        rate_editor.addWidget(QLabel("Nova diária válida a partir de"))
        rate_editor.addWidget(self.employee_rate_date)
        rate_editor.addWidget(self.employee_new_rate)
        rate_editor.addWidget(change_rate)
        layout.addLayout(rate_editor)
        return page

    def build_benefits(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        heading = QLabel("Benefícios da equipe")
        heading.setObjectName("pageTitle")
        layout.addWidget(heading)
        info = QLabel(
            "Registre cada cesta básica ou bônus para um funcionário. A lista abaixo acompanha "
            "o período selecionado no relatório; benefícios entram no total de saídas."
        )
        info.setWordWrap(True)
        info.setObjectName("muted")
        layout.addWidget(info)

        form = QFrame()
        form.setObjectName("surface")
        fields = QGridLayout(form)
        fields.setContentsMargins(18, 16, 18, 16)
        fields.setHorizontalSpacing(14)
        fields.setVerticalSpacing(8)
        self.benefit_employee = QComboBox()
        self.benefit_period = date_input(QDate.currentDate())
        self.benefit_period.setDisplayFormat("MM/yyyy")
        self.benefit_kind = QComboBox()
        self.benefit_kind.addItems(["Cesta básica", "Bônus", "Sem bônus"])
        self.benefit_amount = money_input()
        self.benefit_note = QLineEdit()
        self.benefit_note.setPlaceholderText("Observação (opcional)")
        for column, label in enumerate(("Funcionário", "Período", "Tipo", "Valor (R$)")):
            fields.addWidget(QLabel(label), 0, column)
        fields.addWidget(self.benefit_employee, 1, 0)
        fields.addWidget(self.benefit_period, 1, 1)
        fields.addWidget(self.benefit_kind, 1, 2)
        fields.addWidget(self.benefit_amount, 1, 3)
        fields.addWidget(QLabel("Observação (opcional)"), 2, 0, 1, 4)
        fields.addWidget(self.benefit_note, 3, 0, 1, 4)
        add = QPushButton("Registrar benefício")
        add.setMinimumWidth(180)
        add.clicked.connect(self.add_benefit)
        fields.addWidget(add, 4, 0, 1, 4, Qt.AlignmentFlag.AlignRight)
        fields.setColumnStretch(0, 2)
        fields.setColumnStretch(1, 1)
        fields.setColumnStretch(2, 1)
        fields.setColumnStretch(3, 1)
        layout.addWidget(form)
        self.benefit_table = table(["Período", "Funcionário", "Tipo", "Valor", "Observação"])
        layout.addWidget(self.benefit_table, 1)
        return page

    def build_business_settings(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        form = QFrame()
        form.setObjectName("surface")
        fields = QGridLayout(form)
        fields.setContentsMargins(18, 16, 18, 16)
        fields.setHorizontalSpacing(14)
        fields.setVerticalSpacing(10)
        details = self.database.business_details()
        self.business_name_field = QLineEdit(details["business_name"])
        self.business_name_field.setMaxLength(255)
        self.business_name_field.setPlaceholderText("Nome do lava-rápido")
        self.business_cnpj_field = QLineEdit(details["business_cnpj"])
        self.business_cnpj_field.setPlaceholderText("CNPJ")
        self.business_phone_field = QLineEdit(details["business_phone"])
        self.business_phone_field.setPlaceholderText("Telefone")
        self.business_owner_field = QLineEdit(details["business_owner"])
        self.business_owner_field.setPlaceholderText("Nome do proprietário")
        self.business_address_field = QLineEdit(details["business_address"])
        self.business_address_field.setPlaceholderText("Endereço")
        save = QPushButton("Salvar dados")
        save.clicked.connect(self.save_business_details)
        fields.addWidget(QLabel("Nome do estabelecimento"), 0, 0)
        fields.addWidget(QLabel("CNPJ"), 0, 1)
        fields.addWidget(self.business_name_field, 1, 0)
        fields.addWidget(self.business_cnpj_field, 1, 1)
        fields.addWidget(QLabel("Telefone"), 2, 0)
        fields.addWidget(QLabel("Proprietário"), 2, 1)
        fields.addWidget(self.business_phone_field, 3, 0)
        fields.addWidget(self.business_owner_field, 3, 1)
        fields.addWidget(QLabel("Endereço"), 4, 0, 1, 2)
        fields.addWidget(self.business_address_field, 5, 0, 1, 2)
        fields.addWidget(save, 6, 0, 1, 2, Qt.AlignmentFlag.AlignRight)
        fields.setColumnStretch(0, 1)
        fields.setColumnStretch(1, 1)
        layout.addWidget(form)
        layout.addStretch()
        return page

    def save_business_details(self) -> None:
        try:
            self.database.set_business_details(
                {
                    "business_name": self.business_name_field.text(),
                    "business_cnpj": self.business_cnpj_field.text(),
                    "business_phone": self.business_phone_field.text(),
                    "business_owner": self.business_owner_field.text(),
                    "business_address": self.business_address_field.text(),
                }
            )
        except ValueError as error:
            QMessageBox.warning(self, "Dados inválidos", str(error))
            return
        except Exception as error:
            QMessageBox.warning(
                self,
                "Erro ao salvar",
                f"Não foi possível salvar os dados do estabelecimento: {error}",
            )
            return
        business_name = self.database.business_name()
        self.setWindowTitle(f"{business_name} | Administração")
        self.business_name_changed.emit(business_name)
        QMessageBox.information(
            self, "Dados salvos", "Os dados do estabelecimento foram atualizados."
        )

    def selected_period(self) -> tuple[str, str]:
        start, end = date_text(self.range_start), date_text(self.range_end)
        if start > end:
            raise ValueError("A data inicial deve ser anterior ou igual à data final.")
        return start, end

    def refresh_all(self) -> None:
        start, end = self.selected_period()
        report = self.database.report(start, end)
        self.metric_values["Carros / serviços"].setText(str(report["service_count"]))
        self.metric_values["Lavagens simples"].setText(str(report["simple_count"]))
        self.metric_values["Lavagens completas"].setText(str(report["complete_count"]))
        self.metric_values["Faturamento"].setText(money_text(report["revenue_cents"]))
        self.metric_values["Despesas lançadas"].setText(money_text(report["expense_cents"]))
        self.metric_values["Diárias da equipe"].setText(
            money_text(report["employee_daily_cost_cents"])
        )
        self.metric_values["Benefícios"].setText(money_text(report["benefit_cents"]))
        self.metric_values["Total de saídas"].setText(money_text(report["outflow_cents"]))
        self.metric_values["Saldo registrado"].setText(money_text(report["net_cents"]))
        self.metric_values["Folha estimada"].setText(money_text(report["payroll_estimate_cents"]))
        self.service_type_table.setRowCount(0)
        for item in report["service_breakdown"]:
            put_row(
                self.service_type_table,
                [item["description"], str(item["service_count"]), money_text(item["revenue_cents"])],
            )
        self.service_detail_table.setRowCount(0)
        for item in report["services"]:
            put_row(
                self.service_detail_table,
                [
                    item["service_day"],
                    item["vehicle"] or "—",
                    item["description"],
                    money_text(item["amount_cents"]),
                ],
            )
        self.expense_report_table.setRowCount(0)
        for item in report["expenses"]:
            put_row(
                self.expense_report_table,
                [
                    item["expense_day"],
                    item["category"],
                    item["description"],
                    money_text(item["amount_cents"]),
                ],
            )
        self.benefit_report_table.setRowCount(0)
        self.benefit_table.setRowCount(0)
        for item in report["benefits"]:
            benefit_row = [
                item["period"],
                item["employee_name"],
                item["kind"],
                money_text(item["amount_cents"]),
                item["note"] or "—",
            ]
            put_row(
                self.benefit_report_table,
                [benefit_row[0], benefit_row[1], benefit_row[2], benefit_row[4], benefit_row[3]],
            )
            put_row(self.benefit_table, benefit_row)
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
        self.refresh_expenses(report)
        self.refresh_employees()

    def refresh_expenses(self, report: dict | None = None) -> None:
        if not hasattr(self, "expense_table"):
            return
        if report is None:
            start, end = self.selected_period()
            report = self.database.report(start, end)
        self.expense_summary_values["Despesas lançadas"].setText(
            money_text(report["expense_cents"])
        )
        self.expense_summary_values["Diárias da equipe"].setText(
            money_text(report["employee_daily_cost_cents"])
        )
        self.expense_summary_values["Benefícios"].setText(
            money_text(report["benefit_cents"])
        )
        self.expense_summary_values["Total de saídas"].setText(
            money_text(report["outflow_cents"])
        )
        self.expense_table.setRowCount(0)
        category_totals = {
            "Diária do pessoal": [0, 0],
            "Produtos": [0, 0],
            "Água": [0, 0],
            "Outros": [0, 0],
        }
        category_aliases = {
            "diária do pessoal": "Diária do pessoal",
            "diarias": "Diária do pessoal",
            "diária": "Diária do pessoal",
            "produtos": "Produtos",
            "água": "Água",
            "agua": "Água",
            "outros": "Outros",
        }
        for item in report["expenses"]:
            category = category_aliases.get(item["category"].strip().casefold(), "Outros")
            category_totals[category][0] += 1
            category_totals[category][1] += int(item["amount_cents"])
            put_row(
                self.expense_table,
                [
                    item["expense_day"],
                    category,
                    item["description"],
                    money_text(item["amount_cents"]),
                ],
            )
        for item in report["employee_daily_expenses"]:
            amount_cents = int(item["amount_cents"])
            category_totals["Diária do pessoal"][0] += 1
            category_totals["Diária do pessoal"][1] += amount_cents
            row = self.expense_table.rowCount()
            put_row(
                self.expense_table,
                [
                    str(item["attendance_day"])[:10],
                    "Diária do pessoal",
                    item["employee_name"],
                    money_text(amount_cents),
                ],
            )
            self.expense_table.item(row, 2).setToolTip(
                "Diária calculada automaticamente pela presença registrada."
            )
        self.expense_category_table.setRowCount(0)
        for category, (count, cents) in category_totals.items():
            put_row(self.expense_category_table, [category, str(count), money_text(cents)])
        self.employee_expense_table.setRowCount(0)
        for item in report["employee_daily_expenses"]:
            put_row(
                self.employee_expense_table,
                [
                    str(item["attendance_day"])[:10],
                    item["employee_name"],
                    money_text(item["amount_cents"]),
                ],
            )

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

    def change_employee_rate(self) -> None:
        row = self.employee_table.currentRow()
        if row < 0:
            QMessageBox.information(
                self, "Selecione um funcionário", "Selecione o funcionário que terá a diária alterada."
            )
            return
        try:
            new_rate = parse_money(self.employee_new_rate.text())
            if new_rate < 0:
                raise ValueError("A diária não pode ser negativa.")
            employee_id = self.employee_table.item(row, 0).data(Qt.ItemDataRole.UserRole)
            self.database.change_employee_daily_rate(
                employee_id, new_rate, date_text(self.employee_rate_date)
            )
        except ValueError as error:
            QMessageBox.warning(self, "Confira a diária", str(error) or "Informe um valor válido.")
            return
        self.employee_new_rate.clear()
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
