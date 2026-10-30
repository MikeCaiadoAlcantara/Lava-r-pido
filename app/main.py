import sys

from PySide6.QtWidgets import QApplication, QDialog

from app.database import Database
from app.ui import AdminSetupDialog, LoginDialog, MainWindow


STYLESHEET = """
QWidget { background: #f3f6f3; color: #1c302b; font-family: 'Segoe UI'; font-size: 10pt; }
QMainWindow, QDialog { background: #f3f6f3; }
QLabel#pageTitle { color: #163d35; font-size: 23pt; font-weight: 700; }
QLabel#muted { color: #687a73; }
QLabel#metric { color: #146454; font-size: 17pt; font-weight: 700; }
QFrame#surface { background: #ffffff; border: 1px solid #dbe5df; border-radius: 7px; }
QLineEdit, QComboBox, QDateEdit { background: #ffffff; border: 1px solid #c9d7d0; border-radius: 5px; padding: 8px; min-height: 22px; }
QLineEdit:focus, QComboBox:focus, QDateEdit:focus { border: 2px solid #328b74; }
QPushButton { background: #176b58; color: #ffffff; border: 0; border-radius: 5px; padding: 9px 14px; font-weight: 600; }
QPushButton:hover { background: #105544; }
QPushButton#secondaryButton { background: #e1eee8; color: #145847; border: 1px solid #b7d3c7; }
QPushButton#secondaryButton:hover { background: #d2e6dc; }
QPushButton#quietButton { background: transparent; color: #a34135; border: 1px solid #e2c4bf; }
QTableWidget { background: #ffffff; alternate-background-color: #f6f9f7; border: 1px solid #dbe5df; border-radius: 5px; gridline-color: #e8eeea; }
QHeaderView::section { background: #e8f0eb; color: #29473e; padding: 9px; border: 0; font-weight: 600; }
QTabWidget::pane { border: 1px solid #dbe5df; background: #ffffff; }
QTabBar::tab { background: #e7ede9; padding: 10px 16px; margin-right: 3px; color: #34564b; }
QTabBar::tab:selected { background: #176b58; color: white; }
QCheckBox { spacing: 8px; }
"""


def main() -> int:
    application = QApplication(sys.argv)
    application.setApplicationName("Lava Rápido Alcantara")
    application.setOrganizationName("Lava Rápido Alcantara")
    application.setStyleSheet(STYLESHEET)
    database = Database()

    database.remove_legacy_default_admin()
    if not database.has_admin():
        setup = AdminSetupDialog(database)
        if setup.exec() != QDialog.DialogCode.Accepted:
            return 0

    login = LoginDialog(database)
    if login.exec() != QDialog.DialogCode.Accepted:
        return 0

    window = MainWindow(database)
    window.show()
    return application.exec()


if __name__ == "__main__":
    raise SystemExit(main())
