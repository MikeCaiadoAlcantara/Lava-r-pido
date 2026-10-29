import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from app.admin import AdminDialog
from app.ui import MainWindow
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


if __name__ == "__main__":
    unittest.main()