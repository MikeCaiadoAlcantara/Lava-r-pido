import os
from contextlib import contextmanager
from typing import Any, Iterator

from app.security import hash_password, verify_password


class Database:
    def __init__(self):
        self.host = os.getenv("LAVA_DB_HOST", "127.0.0.1")
        self.port = int(os.getenv("LAVA_DB_PORT", "3306"))
        self.user = os.getenv("LAVA_DB_USER", "root")
        self.password = os.getenv("LAVA_DB_PASSWORD", "")
        self.database_name = os.getenv("LAVA_DB_NAME", "lava_rapido_alcantara")
        if not self.database_name.replace("_", "").isalnum():
            raise ValueError("LAVA_DB_NAME pode conter apenas letras, números e sublinhados.")
        self._create_mysql_database()
        self._initialize()

    @contextmanager
    def connect(self) -> Iterator[Any]:
        connection = self._connect_mysql(self.database_name)
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def _connect_mysql(self, database: str | None = None) -> Any:
        import mysql.connector

        connection = mysql.connector.connect(
            host=self.host,
            port=self.port,
            user=self.user,
            password=self.password,
            database=database,
        )
        return _MySQLConnection(connection)

    def _create_mysql_database(self) -> None:
        if not self.database_name.replace("_", "").isalnum():
            raise ValueError("Nome de banco de dados inválido.")
        connection = self._connect_mysql()
        try:
            connection.execute(
                f"CREATE DATABASE IF NOT EXISTS `{self.database_name}` "
                "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
            )
            connection.commit()
        finally:
            connection.close()

    def _initialize(self) -> None:
        statements = (
            """CREATE TABLE IF NOT EXISTS administrators (
                id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
                username VARCHAR(191) NOT NULL UNIQUE,
                password_hash VARCHAR(255) NOT NULL,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",
            """CREATE TABLE IF NOT EXISTS services (
                id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
                service_day CHAR(10) NOT NULL,
                vehicle VARCHAR(100) NOT NULL DEFAULT '',
                description VARCHAR(255) NOT NULL,
                amount_cents BIGINT NOT NULL,
                payment_method VARCHAR(100) NOT NULL,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                INDEX idx_services_day (service_day)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",
            """CREATE TABLE IF NOT EXISTS expenses (
                id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
                expense_day CHAR(10) NOT NULL,
                category VARCHAR(191) NOT NULL,
                description VARCHAR(255) NOT NULL,
                amount_cents BIGINT NOT NULL,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                INDEX idx_expenses_day (expense_day)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",
            """CREATE TABLE IF NOT EXISTS employees (
                id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
                name VARCHAR(191) NOT NULL,
                phone VARCHAR(50) NOT NULL DEFAULT '',
                monthly_salary_cents BIGINT NOT NULL,
                active TINYINT NOT NULL DEFAULT 1
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",
            """CREATE TABLE IF NOT EXISTS employee_daily_rates (
                id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
                employee_id INT NOT NULL,
                daily_rate_cents BIGINT NOT NULL,
                effective_from DATE NOT NULL,
                UNIQUE KEY uq_employee_daily_rate_date (employee_id, effective_from),
                INDEX idx_employee_daily_rate_effective (employee_id, effective_from),
                CONSTRAINT fk_daily_rate_employee FOREIGN KEY (employee_id) REFERENCES employees(id)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",
            """CREATE TABLE IF NOT EXISTS app_settings (
                setting_key VARCHAR(100) NOT NULL PRIMARY KEY,
                setting_value VARCHAR(255) NOT NULL
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",
            """CREATE TABLE IF NOT EXISTS attendance (
                id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
                employee_id INT NOT NULL,
                attendance_day CHAR(10) NOT NULL,
                absent TINYINT NOT NULL,
                paid_cents BIGINT NOT NULL DEFAULT 0,
                note VARCHAR(255) NOT NULL DEFAULT '',
                UNIQUE KEY uq_attendance_employee_day (employee_id, attendance_day),
                INDEX idx_attendance_day (attendance_day),
                CONSTRAINT fk_attendance_employee FOREIGN KEY (employee_id) REFERENCES employees(id)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",
            """CREATE TABLE IF NOT EXISTS benefits (
                id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
                employee_id INT NOT NULL,
                period CHAR(7) NOT NULL,
                kind VARCHAR(50) NOT NULL,
                amount_cents BIGINT NOT NULL,
                note VARCHAR(255) NOT NULL DEFAULT '',
                INDEX idx_benefits_period (period),
                CONSTRAINT fk_benefits_employee FOREIGN KEY (employee_id) REFERENCES employees(id)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",
        )
        with self.connect() as connection:
            for statement in statements:
                connection.execute(statement)
            connection.execute(
                "INSERT IGNORE INTO app_settings(setting_key, setting_value) VALUES (?, ?)",
                ("business_name", ""),
            )
            migration = connection.execute(
                "SELECT setting_value FROM app_settings WHERE setting_key = ?",
                ("business_name_default_migration",),
            ).fetchone()
            if migration is None:
                connection.execute(
                    "UPDATE app_settings SET setting_value = '' "
                    "WHERE setting_key = ? AND setting_value = ?",
                    ("business_name", "Lava Rápido Alcantara"),
                )
                connection.execute(
                    "INSERT INTO app_settings(setting_key, setting_value) VALUES (?, ?)",
                    ("business_name_default_migration", "done"),
                )
            connection.execute(
                "INSERT INTO employee_daily_rates(employee_id, daily_rate_cents, effective_from) "
                "SELECT e.id, e.monthly_salary_cents, '1000-01-01' FROM employees e "
                "WHERE NOT EXISTS ("
                "SELECT 1 FROM employee_daily_rates r WHERE r.employee_id = e.id"
                ")"
            )

    def has_admin(self) -> bool:
        with self.connect() as connection:
            return connection.execute("SELECT 1 FROM administrators LIMIT 1").fetchone() is not None

    def create_admin(self, username: str, password: str) -> None:
        with self.connect() as connection:
            connection.execute(
                "INSERT INTO administrators(username, password_hash) VALUES (?, ?)",
                (username.strip(), hash_password(password)),
            )

    def create_initial_setup(
        self,
        business_name: str,
        username: str,
        password: str,
        employees: list[tuple[str, str, int]],
    ) -> None:
        business_name = business_name.strip()
        username = username.strip()
        if not business_name:
            raise ValueError("Informe o nome do lava-rápido.")
        if not username:
            raise ValueError("Informe um nome de usuário.")
        with self.connect() as connection:
            connection.execute(
                "INSERT INTO administrators(username, password_hash) VALUES (?, ?)",
                (username, hash_password(password)),
            )
            connection.execute(
                "INSERT INTO app_settings(setting_key, setting_value) VALUES (?, ?) "
                "ON DUPLICATE KEY UPDATE setting_value=VALUES(setting_value)",
                ("business_name", business_name),
            )
            for name, phone, daily_rate_cents in employees:
                cursor = connection.execute(
                    "INSERT INTO employees(name, phone, monthly_salary_cents) VALUES (?, ?, ?)",
                    (name.strip(), phone.strip(), daily_rate_cents),
                )
                employee_id = cursor.cursor.lastrowid
                connection.execute(
                    "INSERT INTO employee_daily_rates(employee_id, daily_rate_cents, effective_from) "
                    "VALUES (?, ?, CURRENT_DATE)",
                    (employee_id, daily_rate_cents),
                )

    def business_name(self) -> str:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT setting_value FROM app_settings WHERE setting_key = ?",
                ("business_name",),
            ).fetchone()
        return row["setting_value"] if row else ""

    def business_details(self) -> dict[str, str]:
        keys = (
            "business_name",
            "business_cnpj",
            "business_phone",
            "business_owner",
            "business_address",
        )
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT setting_key, setting_value FROM app_settings "
                "WHERE setting_key IN (?, ?, ?, ?, ?)",
                keys,
            ).fetchall()
        details = {row["setting_key"]: row["setting_value"] for row in rows}
        return {key: details.get(key, "") for key in keys}

    def set_business_details(self, details: dict[str, str]) -> None:
        normalized = {
            "business_name": details.get("business_name", "").strip(),
            "business_cnpj": details.get("business_cnpj", "").strip(),
            "business_phone": details.get("business_phone", "").strip(),
            "business_owner": details.get("business_owner", "").strip(),
            "business_address": details.get("business_address", "").strip(),
        }
        if not normalized["business_name"]:
            raise ValueError("Informe o nome do lava-rápido.")
        with self.connect() as connection:
            for key, value in normalized.items():
                connection.execute(
                    "INSERT INTO app_settings(setting_key, setting_value) VALUES (?, ?) "
                    "ON DUPLICATE KEY UPDATE setting_value=VALUES(setting_value)",
                    (key, value),
                )

    def set_business_name(self, business_name: str) -> None:
        details = self.business_details()
        details["business_name"] = business_name
        self.set_business_details(details)

    def authenticate(self, username: str, password: str) -> bool:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT password_hash FROM administrators WHERE username = ?",
                (username.strip(),),
            ).fetchone()
        return bool(row and verify_password(password, row["password_hash"]))

    def add_service(self, day: str, vehicle: str, description: str, cents: int, payment: str) -> None:
        with self.connect() as connection:
            connection.execute(
                "INSERT INTO services(service_day, vehicle, description, amount_cents, payment_method) "
                "VALUES (?, ?, ?, ?, ?)",
                (day, vehicle.strip(), description.strip(), cents, payment),
            )

    def services_for_day(self, day: str) -> list[dict[str, Any]]:
        with self.connect() as connection:
            return connection.execute(
                "SELECT id, vehicle, description, amount_cents, payment_method, created_at "
                "FROM services WHERE service_day = ? ORDER BY id DESC",
                (day,),
            ).fetchall()

    def delete_service(self, service_id: int) -> None:
        with self.connect() as connection:
            connection.execute("DELETE FROM services WHERE id = ?", (service_id,))

    def add_expense(self, day: str, category: str, description: str, cents: int) -> None:
        with self.connect() as connection:
            connection.execute(
                "INSERT INTO expenses(expense_day, category, description, amount_cents) VALUES (?, ?, ?, ?)",
                (day, category, description.strip(), cents),
            )

    def expenses_between(self, start: str, end: str) -> list[dict[str, Any]]:
        with self.connect() as connection:
            return connection.execute(
                "SELECT id, expense_day, category, description, amount_cents FROM expenses "
                "WHERE expense_day BETWEEN ? AND ? ORDER BY expense_day DESC, id DESC",
                (start, end),
            ).fetchall()

    def add_employee(
        self, name: str, phone: str, salary_cents: int, effective_from: str | None = None
    ) -> None:
        with self.connect() as connection:
            cursor = connection.execute(
                "INSERT INTO employees(name, phone, monthly_salary_cents) VALUES (?, ?, ?)",
                (name.strip(), phone.strip(), salary_cents),
            )
            connection.execute(
                "INSERT INTO employee_daily_rates(employee_id, daily_rate_cents, effective_from) "
                "VALUES (?, ?, COALESCE(?, CURRENT_DATE))",
                (cursor.cursor.lastrowid, salary_cents, effective_from),
            )

    def change_employee_daily_rate(
        self, employee_id: int, daily_rate_cents: int, effective_from: str
    ) -> None:
        if daily_rate_cents < 0:
            raise ValueError("A diária não pode ser negativa.")
        with self.connect() as connection:
            connection.execute(
                "INSERT INTO employee_daily_rates(employee_id, daily_rate_cents, effective_from) "
                "VALUES (?, ?, ?) ON DUPLICATE KEY UPDATE daily_rate_cents=VALUES(daily_rate_cents)",
                (employee_id, daily_rate_cents, effective_from),
            )
            connection.execute(
                "UPDATE employees SET monthly_salary_cents = ? "
                "WHERE id = ? AND ? <= CURRENT_DATE",
                (daily_rate_cents, employee_id, effective_from),
            )

    def employees(self, active_only: bool = True) -> list[dict[str, Any]]:
        query = (
            "SELECT e.id, e.name, e.phone, "
            "COALESCE((SELECT r.daily_rate_cents FROM employee_daily_rates r "
            "WHERE r.employee_id = e.id AND r.effective_from <= CURRENT_DATE "
            "ORDER BY r.effective_from DESC LIMIT 1), e.monthly_salary_cents) "
            "AS monthly_salary_cents, e.active FROM employees e"
        )
        if active_only:
            query += " WHERE e.active = 1"
        query += " ORDER BY LOWER(e.name)"
        with self.connect() as connection:
            return connection.execute(query).fetchall()

    def set_attendance(self, employee_id: int, day: str, absent: bool, note: str = "", paid_cents: int = 0) -> None:
        with self.connect() as connection:
            connection.execute(
                "INSERT INTO attendance(employee_id, attendance_day, absent, paid_cents, note) VALUES (?, ?, ?, ?, ?) "
                "ON DUPLICATE KEY UPDATE absent=VALUES(absent), paid_cents=VALUES(paid_cents), note=VALUES(note)",
                (employee_id, day, int(absent), max(paid_cents, 0), note.strip()),
            )

    def add_benefit(self, employee_id: int, period: str, kind: str, cents: int, note: str = "") -> None:
        with self.connect() as connection:
            connection.execute(
                "INSERT INTO benefits(employee_id, period, kind, amount_cents, note) VALUES (?, ?, ?, ?, ?)",
                (employee_id, period, kind, cents, note.strip()),
            )

    def report(self, start: str, end: str) -> dict:
        with self.connect() as connection:
            revenue = connection.execute(
                "SELECT COALESCE(SUM(amount_cents), 0) FROM services WHERE service_day BETWEEN ? AND ?",
                (start, end),
            ).fetchone()[0]
            expense_total = connection.execute(
                "SELECT COALESCE(SUM(amount_cents), 0) FROM expenses WHERE expense_day BETWEEN ? AND ?",
                (start, end),
            ).fetchone()[0]
            benefit_total = connection.execute(
                "SELECT COALESCE(SUM(amount_cents), 0) FROM benefits "
                "WHERE kind != 'Sem bônus' AND period BETWEEN substr(?, 1, 7) AND substr(?, 1, 7)",
                (start, end),
            ).fetchone()[0]
            employee_daily_expenses = connection.execute(
                "SELECT a.attendance_day, e.id AS employee_id, e.name AS employee_name, "
                "CASE WHEN a.paid_cents > 0 THEN a.paid_cents ELSE COALESCE(("
                "SELECT r.daily_rate_cents FROM employee_daily_rates r "
                "WHERE r.employee_id = e.id AND r.effective_from <= a.attendance_day "
                "ORDER BY r.effective_from DESC LIMIT 1"
                "), e.monthly_salary_cents) END AS amount_cents "
                "FROM attendance a JOIN employees e ON e.id = a.employee_id "
                "WHERE a.absent = 0 AND a.attendance_day BETWEEN ? AND ? "
                "ORDER BY a.attendance_day DESC, LOWER(e.name)",
                (start, end),
            ).fetchall()
            employee_daily_cost_cents = sum(
                int(row["amount_cents"]) for row in employee_daily_expenses
            )
            service_count = connection.execute(
                "SELECT COUNT(*) FROM services WHERE service_day BETWEEN ? AND ?", (start, end)
            ).fetchone()[0]
            services = connection.execute(
                "SELECT service_day, vehicle, description, amount_cents "
                "FROM services WHERE service_day BETWEEN ? AND ? ORDER BY service_day DESC, id DESC",
                (start, end),
            ).fetchall()
            service_breakdown = connection.execute(
                "SELECT description, COUNT(*) AS service_count, "
                "COALESCE(SUM(amount_cents), 0) AS revenue_cents "
                "FROM services WHERE service_day BETWEEN ? AND ? "
                "GROUP BY description ORDER BY service_count DESC, LOWER(description)",
                (start, end),
            ).fetchall()
            simple_count = connection.execute(
                "SELECT COUNT(*) FROM services WHERE service_day BETWEEN ? AND ? "
                "AND LOCATE('simples', LOWER(description)) > 0",
                (start, end),
            ).fetchone()[0]
            complete_count = connection.execute(
                "SELECT COUNT(*) FROM services WHERE service_day BETWEEN ? AND ? "
                "AND LOCATE('complet', LOWER(description)) > 0",
                (start, end),
            ).fetchone()[0]
            expenses = connection.execute(
                "SELECT expense_day, category, description, amount_cents FROM expenses "
                "WHERE expense_day BETWEEN ? AND ? ORDER BY expense_day DESC, id DESC",
                (start, end),
            ).fetchall()
            benefits = connection.execute(
                "SELECT b.period, e.name AS employee_name, b.kind, b.note, b.amount_cents "
                "FROM benefits b JOIN employees e ON e.id = b.employee_id "
                "WHERE b.kind != 'Sem bônus' "
                "AND b.period BETWEEN substr(?, 1, 7) AND substr(?, 1, 7) "
                "ORDER BY b.period DESC, e.name, b.id DESC",
                (start, end),
            ).fetchall()
            attendance = connection.execute(
                "SELECT e.id, e.name, "
                "COALESCE((SELECT r.daily_rate_cents FROM employee_daily_rates r "
                "WHERE r.employee_id = e.id AND r.effective_from <= CURRENT_DATE "
                "ORDER BY r.effective_from DESC LIMIT 1), e.monthly_salary_cents) "
                "AS monthly_salary_cents, "
                "SUM(CASE WHEN a.absent = 1 THEN 1 ELSE 0 END) AS absences "
                "FROM employees e LEFT JOIN attendance a ON a.employee_id=e.id "
                "AND a.attendance_day BETWEEN ? AND ? WHERE e.active=1 "
                "GROUP BY e.id ORDER BY absences DESC, LOWER(e.name)",
                (start, end),
            ).fetchall()

            start_date = __import__("datetime").date.fromisoformat(start)
            end_date = __import__("datetime").date.fromisoformat(end)
            payroll_estimate = 0
            employees = connection.execute(
                "SELECT id, name, monthly_salary_cents FROM employees "
                "WHERE active = 1 ORDER BY LOWER(name)"
            ).fetchall()

            for employee in employees:
                employee_id = employee["id"]
                employee_rates = connection.execute(
                    "SELECT daily_rate_cents, effective_from FROM employee_daily_rates "
                    "WHERE employee_id = ? AND effective_from <= ? ORDER BY effective_from",
                    (employee_id, end),
                ).fetchall()
                rate_history = [
                    (str(row["effective_from"])[:10], int(row["daily_rate_cents"]))
                    for row in employee_rates
                    if row["effective_from"] is not None
                ]
                rate_history.sort(key=lambda item: item[0])
                records = {
                    row["attendance_day"]: row
                    for row in connection.execute(
                        "SELECT attendance_day, absent, paid_cents FROM attendance WHERE employee_id = ? AND attendance_day BETWEEN ? AND ?",
                        (employee_id, start, end),
                    ).fetchall()
                }
                current_date = start_date
                rate_index = -1
                daily_rate = int(employee["monthly_salary_cents"])
                while current_date <= end_date:
                    day_key = current_date.isoformat()
                    while (
                        rate_index + 1 < len(rate_history)
                        and rate_history[rate_index + 1][0] <= day_key
                    ):
                        rate_index += 1
                        daily_rate = rate_history[rate_index][1]
                    record = records.get(day_key)
                    if record is None:
                        payroll_estimate += daily_rate
                    elif int(record["absent"]) == 1:
                        payroll_estimate += 0
                    else:
                        paid = int(record["paid_cents"])
                        payroll_estimate += paid if paid > 0 else daily_rate
                    current_date += __import__("datetime").timedelta(days=1)

            absences = [row["absences"] or 0 for row in attendance]
            most_absences = max(absences, default=0)
            least_absences = min(absences, default=0)
            return {
                "revenue_cents": revenue,
                "expense_cents": expense_total,
                "employee_daily_cost_cents": employee_daily_cost_cents,
                "benefit_cents": benefit_total,
                "outflow_cents": expense_total + employee_daily_cost_cents + benefit_total,
                "net_cents": revenue - expense_total - employee_daily_cost_cents - benefit_total,
                "employee_daily_expenses": employee_daily_expenses,
                "service_count": service_count,
                "simple_count": simple_count,
                "complete_count": complete_count,
                "services": services,
                "service_breakdown": service_breakdown,
                "expenses": expenses,
                "benefits": benefits,
                "payroll_estimate_cents": payroll_estimate,
                "attendance": attendance,
                "most_absences": most_absences,
                "least_absences": least_absences,
                "most_absences_names": [row["name"] for row in attendance if (row["absences"] or 0) == most_absences],
                "least_absences_names": [row["name"] for row in attendance if (row["absences"] or 0) == least_absences],
            }


class _MySQLRow(dict):
    def __getitem__(self, key: Any) -> Any:
        if isinstance(key, int):
            return list(self.values())[key]
        return super().__getitem__(key)


class _MySQLCursor:
    def __init__(self, cursor: Any):
        self.cursor = cursor

    def fetchone(self) -> _MySQLRow | None:
        row = self.cursor.fetchone()
        return _MySQLRow(row) if row is not None else None

    def fetchall(self) -> list[_MySQLRow]:
        return [_MySQLRow(row) for row in self.cursor.fetchall()]


class _MySQLConnection:
    def __init__(self, connection: Any):
        self.connection = connection

    def execute(self, statement: str, parameters: tuple = ()) -> _MySQLCursor:
        cursor = self.connection.cursor(dictionary=True)
        cursor.execute(statement.replace("?", "%s"), parameters)
        return _MySQLCursor(cursor)

    def commit(self) -> None:
        self.connection.commit()

    def rollback(self) -> None:
        self.connection.rollback()

    def close(self) -> None:
        self.connection.close()
