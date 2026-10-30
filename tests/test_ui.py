import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication
from PySide6.QtWidgets import QDialog
from PySide6.QtCore import QDate

from app.admin import AdminDialog
from app.ui import AdminSetupDialog, MainWindow
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
        self.assertEqual(admin_window.tabs.count(), 4)
        self.assertEqual(admin_window.tabs.tabText(0), "Relatórios")

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

    def test_initial_setup_saves_custom_admin_for_login(self) -> None:
        setup = AdminSetupDialog(self.database)
        setup.username.setText("proprietaria")
        setup.password.setText("senha-forte-123")
        setup.confirm.setText("senha-forte-123")

        setup.accept()

        self.assertEqual(setup.result(), QDialog.DialogCode.Accepted)
        self.assertTrue(self.database.authenticate("proprietaria", "senha-forte-123"))


if __name__ == "__main__":
    unittest.main()