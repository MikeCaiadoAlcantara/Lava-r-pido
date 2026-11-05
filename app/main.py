import sys

from PySide6.QtWidgets import QApplication, QDialog

from app.database import Database
from app.ui import BusinessNameDialog, LoginDialog, MainWindow


STYLESHEET = """
QWidget { background: #f2f6fc; color: #243247; font-family: 'Segoe UI'; font-size: 10pt; }
QMainWindow, QDialog { background: #f2f6fc; }
QLabel#pageTitle { color: #183c69; font-size: 23pt; font-weight: 700; }
QLabel#muted { color: #66758a; }
QLabel#metric { color: #245b9e; font-size: 17pt; font-weight: 700; }
QFrame#surface { background: #ffffff; border: 1px solid #d5e0ef; border-radius: 7px; }
QLineEdit, QComboBox, QDateEdit { background: #ffffff; border: 1px solid #c5d2e3; border-radius: 5px; padding: 8px; min-height: 22px; }
QLineEdit:focus, QComboBox:focus, QDateEdit:focus { border: 2px solid #4a80bd; }
QPushButton { background: #285f9f; color: #ffffff; border: 0; border-radius: 5px; padding: 9px 14px; font-weight: 600; }
QPushButton:hover { background: #1c4d86; }
QPushButton#secondaryButton { background: #e4edf8; color: #214f83; border: 1px solid #c4d5eb; }
QPushButton#secondaryButton:hover { background: #d5e3f3; }
QPushButton#quietButton { background: transparent; color: #a34135; border: 1px solid #e2c4bf; }
QTableWidget { background: #ffffff; alternate-background-color: #f5f8fd; border: 1px solid #d5e0ef; border-radius: 5px; gridline-color: #e4eaf2; }
QHeaderView::section { background: #e6eef8; color: #294568; padding: 9px; border: 0; font-weight: 600; }
QTabWidget::pane { border: 1px solid #d5e0ef; background: #ffffff; }
QTabBar::tab { background: #e8eef6; padding: 10px 16px; margin-right: 3px; color: #385676; }
QTabBar::tab:selected { background: #285f9f; color: white; }
QTabBar::tab:hover:!selected { background: #d8e4f2; }
QCheckBox { spacing: 8px; }
"""


def main() -> int:
    application = QApplication(sys.argv)
    application.setApplicationName("Lava Rápido")
    application.setOrganizationName("LavaRapido")
    application.setStyleSheet(STYLESHEET)
    database = Database()

    if database.has_admin() and not database.business_name():
        business_setup = BusinessNameDialog(database)
        if business_setup.exec() != QDialog.DialogCode.Accepted:
            return 0

    login = LoginDialog(database)
    if login.exec() != QDialog.DialogCode.Accepted:
        return 0

    window = MainWindow(database)
    window.show()
    return application.exec()


if __name__ == "__main__":
    raise SystemExit(main())
