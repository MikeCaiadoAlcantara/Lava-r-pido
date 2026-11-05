from mysql_test_case import MySQLTestCase


class DatabaseTests(MySQLTestCase):
    def test_admin_password_is_verified_without_storing_plaintext(self) -> None:
        self.database.create_admin("gerente", "senha-forte-123")

        self.assertTrue(self.database.authenticate("GERENTE", "senha-forte-123"))
        self.assertFalse(self.database.authenticate("gerente", "errada"))
        with self.database.connect() as connection:
            stored_hash = connection.execute("SELECT password_hash FROM administrators").fetchone()[0]
        self.assertNotIn("senha-forte-123", stored_hash)

    def test_new_installation_has_no_default_admin(self) -> None:
        self.assertFalse(self.database.has_admin())

        self.database.create_admin("gerente", "senha-forte-123")

        self.assertTrue(self.database.authenticate("gerente", "senha-forte-123"))

    def test_requested_legacy_credentials_can_be_created_and_persist(self) -> None:
        self.database.create_admin("José", "941225")

        from app.database import Database

        reopened = Database()

        self.assertTrue(reopened.has_admin())
        self.assertTrue(reopened.authenticate("José", "941225"))

    def test_initial_setup_saves_business_and_employees(self) -> None:
        self.database.create_initial_setup(
            "Lava Rápido Azul",
            "gerente",
            "senha-segura",
            [("Ana", "11999990000", 15000)],
        )

        self.assertEqual(self.database.business_name(), "Lava Rápido Azul")
        self.assertEqual(self.database.employees()[0]["name"], "Ana")
        self.assertEqual(self.database.employees()[0]["monthly_salary_cents"], 15000)

    def test_legacy_business_name_is_cleared_without_deleting_other_data(self) -> None:
        self.database.create_admin("gerente", "senha-segura")
        self.database.add_service("2026-09-10", "ABC-1234", "Lavagem", 5000, "Pix")
        with self.database.connect() as connection:
            connection.execute(
                "UPDATE app_settings SET setting_value = ? WHERE setting_key = ?",
                ("Lava Rápido Alcantara", "business_name"),
            )
            connection.execute(
                "DELETE FROM app_settings WHERE setting_key = ?",
                ("business_name_default_migration",),
            )

        from app.database import Database

        reopened = Database()

        self.assertEqual(reopened.business_name(), "")
        self.assertTrue(reopened.authenticate("gerente", "senha-segura"))
        self.assertEqual(len(reopened.services_for_day("2026-09-10")), 1)

    def test_daily_rate_changes_take_effect_on_the_selected_date(self) -> None:
        self.database.add_employee("Ana", "", 10000, "2026-09-01")
        employee_id = self.database.employees()[0]["id"]
        self.database.change_employee_daily_rate(employee_id, 20000, "2026-09-16")

        report = self.database.report("2026-09-01", "2026-09-30")

        self.assertEqual(report["payroll_estimate_cents"], 450000)

    def test_daily_payroll_estimate_deducts_absences(self) -> None:
        self.database.add_employee("Ana", "11999990000", 180000)
        employee_id = self.database.employees()[0]["id"]
        self.database.set_attendance(employee_id, "2026-09-03", True)

        report = self.database.report("2026-09-01", "2026-09-30")

        self.assertEqual(report["payroll_estimate_cents"], 180000 * 29)

    def test_period_report_totals_services_costs_benefits_and_absences(self) -> None:
        self.database.add_service("2026-09-10", "ABC-1234", "Lavagem completa", 5000, "Pix")
        self.database.add_service("2026-09-12", "XYZ-9876", "Lavagem simples", 12500, "Dinheiro")
        self.database.add_service("2026-08-31", "", "Fora do período", 9000, "Pix")
        self.database.add_expense("2026-09-11", "Produtos", "Shampoo", 3000)
        self.database.add_employee("Ana", "11999990000", 180000)
        employee_id = self.database.employees()[0]["id"]
        self.database.set_attendance(employee_id, "2026-09-03", True)
        self.database.set_attendance(employee_id, "2026-09-04", False)
        self.database.add_benefit(employee_id, "2026-09", "Cesta básica", 25000)

        report = self.database.report("2026-09-01", "2026-09-30")

        self.assertEqual(report["service_count"], 2)
        self.assertEqual(report["revenue_cents"], 17500)
        self.assertEqual(report["expense_cents"], 3000)
        self.assertEqual(report["benefit_cents"], 25000)
        self.assertEqual(report["employee_daily_cost_cents"], 180000)
        self.assertEqual(report["outflow_cents"], 208000)
        self.assertEqual(report["net_cents"], -190500)
        self.assertEqual(report["simple_count"], 1)
        self.assertEqual(report["complete_count"], 1)
        self.assertEqual(len(report["services"]), 2)
        self.assertEqual(report["services"][0]["vehicle"], "XYZ-9876")
        self.assertEqual(len(report["service_breakdown"]), 2)
        self.assertEqual(len(report["expenses"]), 1)
        self.assertEqual(report["benefits"][0]["employee_name"], "Ana")
        self.assertEqual(report["payroll_estimate_cents"], 180000 * 29)
        self.assertEqual(report["attendance"][0]["absences"], 1)
        self.assertEqual(report["most_absences_names"], ["Ana"])
        self.assertEqual(report["least_absences_names"], ["Ana"])

    def test_only_marked_present_days_add_daily_expenses(self) -> None:
        today = __import__("datetime").date.today().isoformat()
        self.database.add_employee("Ana", "", 15000, today)
        self.database.add_employee("Bia", "", 20000, today)
        employees = {employee["name"]: employee["id"] for employee in self.database.employees()}
        self.database.set_attendance(employees["Ana"], today, False)
        self.database.set_attendance(employees["Bia"], today, False, paid_cents=12000)
        self.database.add_employee("Caio", "", 30000, today)

        report = self.database.report(today, today)

        self.assertEqual(report["employee_daily_cost_cents"], 27000)
        self.assertEqual(report["outflow_cents"], 27000)
        self.assertEqual(
            [row["employee_name"] for row in report["employee_daily_expenses"]],
            ["Ana", "Bia"],
        )
        self.assertEqual(report["employee_daily_expenses"][1]["amount_cents"], 12000)

    def test_business_details_are_persisted(self) -> None:
        details = {
            "business_name": "Lava Rápido Azul",
            "business_cnpj": "12.345.678/0001-90",
            "business_phone": "(11) 99999-0000",
            "business_owner": "Ana Souza",
            "business_address": "Rua Central, 10",
        }

        self.database.set_business_details(details)

        self.assertEqual(self.database.business_details(), details)

    def test_records_survive_reopening_database(self) -> None:
        self.database.add_service("2026-09-22", "", "Lavagem simples", 4500, "Pix")

        from app.database import Database

        reopened = Database()

        self.assertEqual(len(reopened.services_for_day("2026-09-22")), 1)


if __name__ == "__main__":
    import unittest

    unittest.main()