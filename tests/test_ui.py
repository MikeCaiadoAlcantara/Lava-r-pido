import os
import unittest
from datetime import date
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QHeaderView
from PySide6.QtWidgets import QDialog
from PySide6.QtCore import QDate

from app.admin import AdminDialog
from app.ui import (
    AdminSetupDialog,
    AdminLoginDialog,
    BusinessNameDialog,
    LoginDialog,
    MainWindow,
)
from mysql_test_case import MySQLTestCase


class UserInterfaceSmokeTests(MySQLTestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.application = QApplication.instance() or QApplication([])

    def test_operation_and_admin_windows_construct(self) -> None:
        operation_window = MainWindow(self.database)
        admin_window = AdminDialog(self.database)

        self.assertEqual(operation_window.service_table.rowCount(), 0)
        self.assertIsNotNone(admin_window.tabs)
        self.assertEqual(admin_window.tabs.count(), 5)
        self.assertEqual(admin_window.tabs.tabText(0), "Relatórios")

    def test_service_history_and_financial_report_show_period_details(self) -> None:
        today = date.today().isoformat()
        self.database.add_service(today, "ABC-1234", "Lavagem simples", 4500, "Observação")
        self.database.add_service(today, "XYZ-9876", "Lavagem completa", 10000, "")
        self.database.add_expense(today, "Produtos", "Shampoo", 1500)
        self.database.add_employee("Ana", "11999990000", 180000)
        employee_id = self.database.employees()[0]["id"]
        self.database.add_benefit(employee_id, today[:7], "Cesta básica", 2500)

        operation_window = MainWindow(self.database)
        admin_window = AdminDialog(self.database)
        admin_window.generate_report()

        self.assertEqual(operation_window.service_table.rowCount(), 2)
        self.assertEqual(operation_window.service_table.item(0, 0).text(), "XYZ-9876")
        header = operation_window.service_table.horizontalHeader()
        self.assertEqual(
            header.sectionResizeMode(4),
            QHeaderView.ResizeMode.ResizeToContents,
        )
        self.assertFalse(header.stretchLastSection())
        self.assertEqual(admin_window.metric_values["Carros / serviços"].text(), "2")
        self.assertEqual(admin_window.metric_values["Lavagens simples"].text(), "1")
        self.assertEqual(admin_window.metric_values["Lavagens completas"].text(), "1")
        self.assertEqual(admin_window.metric_values["Faturamento"].text(), "R$ 145,00")
        self.assertEqual(admin_window.metric_values["Total de saídas"].text(), "R$ 40,00")
        self.assertEqual(admin_window.metric_values["Saldo registrado"].text(), "R$ 105,00")
        self.assertEqual(admin_window.service_detail_table.rowCount(), 2)
        self.assertEqual(admin_window.service_type_table.rowCount(), 2)
        self.assertEqual(admin_window.expense_report_table.rowCount(), 1)
        self.assertEqual(admin_window.benefit_report_table.rowCount(), 1)
        self.assertEqual(admin_window.benefit_table.rowCount(), 1)

    def test_report_button_generates_week_and_annual_periods(self) -> None:
        admin_window = AdminDialog(self.database)
        today = admin_window.range_end.date()

        admin_window.period_preset.setCurrentIndex(admin_window.period_preset.findData("week"))
        admin_window.report_button.click()

        self.assertEqual(admin_window.tabs.currentWidget(), admin_window.report_page)
        self.assertEqual(admin_window.range_start.date().dayOfWeek(), 1)
        self.assertEqual(admin_window.range_end.date(), today)

        expected_periods = {
            "month": QDate(today.year(), today.month(), 1),
            "three_months": QDate(today.year(), today.month(), 1).addMonths(-2),
            "six_months": QDate(today.year(), today.month(), 1).addMonths(-5),
            "year": QDate(today.year(), 1, 1),
            "previous_year": QDate(today.year() - 1, 1, 1),
        }
        for preset, expected_start in expected_periods.items():
            admin_window.period_preset.setCurrentIndex(admin_window.period_preset.findData(preset))
            admin_window.generate_report()
            self.assertEqual(admin_window.range_start.date(), expected_start)
            expected_end = QDate(today.year() - 1, 12, 31) if preset == "previous_year" else today
            self.assertEqual(admin_window.range_end.date(), expected_end)

        custom_start = QDate(2025, 5, 12)
        custom_end = QDate(2025, 5, 31)
        admin_window.range_start.setDate(custom_start)
        admin_window.range_end.setDate(custom_end)
        admin_window.generate_report()
        self.assertEqual(admin_window.period_preset.currentData(), "custom")
        self.assertEqual(admin_window.range_start.date(), custom_start)
        self.assertEqual(admin_window.range_end.date(), custom_end)

    def test_initial_setup_saves_requested_credentials_for_login(self) -> None:
        setup = AdminSetupDialog(self.database)
        setup.business_name.setText("Lava Rápido Azul")
        setup.username.setText("José")
        setup.password.setText("941225")
        setup.confirm.setText("941225")
        setup.employee_name.setText("Ana")
        setup.employee_phone.setText("11999990000")
        setup.employee_daily_rate.setText("150,00")
        setup.add_pending_employee()

        setup.accept()

        self.assertEqual(setup.result(), QDialog.DialogCode.Accepted)
        self.assertEqual(self.database.business_name(), "Lava Rápido Azul")
        self.assertEqual(self.database.employees()[0]["name"], "Ana")
        login = LoginDialog(self.database)
        login.username.setText("José")
        login.password.setText("941225")
        login.check_credentials()
        self.assertEqual(login.result(), QDialog.DialogCode.Accepted)

    def test_team_tab_can_change_employee_daily_rate(self) -> None:
        self.database.add_employee("Ana", "11999990000", 15000)
        admin_window = AdminDialog(self.database)
        admin_window.employee_table.selectRow(0)
        admin_window.employee_rate_date.setDate(QDate.currentDate())
        admin_window.employee_new_rate.setText("200,00")

        admin_window.change_employee_rate()

        self.assertEqual(self.database.employees()[0]["monthly_salary_cents"], 20000)
        self.assertEqual(admin_window.employee_table.item(0, 2).text(), "R$ 200,00")

    def test_attendance_expense_appears_in_expenses_tab(self) -> None:
        today = date.today().isoformat()
        self.database.add_employee("Ana", "11999990000", 15000, today)
        self.database.add_employee("Bia", "11999990001", 18000, today)
        employees = {employee["name"]: employee["id"] for employee in self.database.employees()}
        self.database.set_attendance(employees["Ana"], today, False)
        self.database.set_attendance(employees["Bia"], today, False)
        self.database.add_expense(today, "Produtos", "Shampoo", 5000)
        self.database.add_expense(today, "Água", "Conta", 3000)

        admin_window = AdminDialog(self.database)
        admin_window.generate_report()

        self.assertEqual(admin_window.metric_values["Diárias da equipe"].text(), "R$ 330,00")
        self.assertEqual(
            admin_window.expense_summary_values["Total de saídas"].text(), "R$ 410,00"
        )
        self.assertEqual(admin_window.employee_expense_table.rowCount(), 2)
        self.assertEqual(admin_window.employee_expense_table.item(0, 1).text(), "Ana")
        self.assertEqual(admin_window.employee_expense_table.item(1, 1).text(), "Bia")
        self.assertEqual(admin_window.expense_table.rowCount(), 4)
        expense_names = [
            admin_window.expense_table.item(row, 2).text()
            for row in range(admin_window.expense_table.rowCount())
        ]
        self.assertIn("Ana", expense_names)
        self.assertIn("Bia", expense_names)
        self.assertEqual(
            [admin_window.expense_category_table.item(row, 0).text() for row in range(4)],
            ["Diária do pessoal", "Produtos", "Água", "Outros"],
        )
        self.assertEqual(admin_window.expense_category_table.item(0, 2).text(), "R$ 330,00")
        self.assertEqual(admin_window.expense_category_table.item(1, 2).text(), "R$ 50,00")
        self.assertEqual(admin_window.expense_category_table.item(2, 2).text(), "R$ 30,00")
        self.assertEqual(
            [admin_window.expense_category.itemText(index) for index in range(
                admin_window.expense_category.count()
            )],
            ["Diária do pessoal", "Produtos", "Água", "Outros"],
        )

    def test_saving_each_attendance_adds_employee_to_expenses_immediately(self) -> None:
        today = date.today().isoformat()
        self.database.add_employee("Ana", "11999990000", 15000, today)
        self.database.add_employee("Bia", "11999990001", 18000, today)
        admin_window = AdminDialog(self.database)
        admin_window.attendance_date.setDate(QDate.currentDate())

        admin_window.mark_attendance()
        self.assertEqual(admin_window.expense_table.rowCount(), 1)
        self.assertEqual(admin_window.expense_table.item(0, 2).text(), "Ana")

        admin_window.attendance_employee.setCurrentIndex(
            admin_window.attendance_employee.findData(
                next(employee["id"] for employee in self.database.employees() if employee["name"] == "Bia")
            )
        )
        admin_window.mark_attendance()

        self.assertEqual(admin_window.expense_table.rowCount(), 2)
        expense_names = {
            admin_window.expense_table.item(row, 2).text()
            for row in range(admin_window.expense_table.rowCount())
        }
        self.assertEqual(expense_names, {"Ana", "Bia"})

    def test_business_details_can_be_saved_from_admin(self) -> None:
        admin_window = AdminDialog(self.database)
        admin_window.business_name_field.setText("Lava Rápido Azul")
        admin_window.business_cnpj_field.setText("12.345.678/0001-90")
        admin_window.business_phone_field.setText("(11) 99999-0000")
        admin_window.business_owner_field.setText("Ana Souza")
        admin_window.business_address_field.setText("Rua Central, 10")

        with patch("app.admin.QMessageBox.information"):
            admin_window.save_business_details()

        self.assertEqual(
            self.database.business_details(),
            {
                "business_name": "Lava Rápido Azul",
                "business_cnpj": "12.345.678/0001-90",
                "business_phone": "(11) 99999-0000",
                "business_owner": "Ana Souza",
                "business_address": "Rua Central, 10",
            },
        )

    def test_business_name_can_be_configured_and_renamed(self) -> None:
        setup = BusinessNameDialog(self.database)
        setup.business_name.setText("Lava Rápido Azul")
        setup.accept()
        self.assertEqual(setup.result(), QDialog.DialogCode.Accepted)

        operation_window = MainWindow(self.database)
        self.assertEqual(operation_window.business_title.text(), "Lava Rápido Azul")

        self.database.set_business_name("Lava Rápido Central")
        operation_window.set_business_name(self.database.business_name())
        self.assertEqual(operation_window.business_title.text(), "Lava Rápido Central")

    def test_login_offers_registration_only_when_no_admin_exists(self) -> None:
        login = LoginDialog(self.database)
        self.assertFalse(login.register_button.isHidden())
        self.assertTrue(login.register_button.isEnabled())

        self.database.create_admin("proprietaria", "senha6")
        login.update_registration_button()
        self.assertFalse(login.register_button.isEnabled())

        admin_login = AdminLoginDialog(self.database)
        self.assertTrue(admin_login.register_button.isHidden())


if __name__ == "__main__":
    unittest.main()