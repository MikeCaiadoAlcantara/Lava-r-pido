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

    def test_legacy_default_admin_is_removed(self) -> None:
        self.database.create_admin("José", "941225")

        self.database.remove_legacy_default_admin()

        self.assertFalse(self.database.has_admin())

    def test_daily_payroll_estimate_deducts_absences(self) -> None:
        self.database.add_employee("Ana", "11999990000", 180000)
        employee_id = self.database.employees()[0]["id"]
        self.database.set_attendance(employee_id, "2026-09-03", True)

        report = self.database.report("2026-09-01", "2026-09-30")

        self.assertEqual(report["payroll_estimate_cents"], 180000 * 29)

    def test_period_report_totals_services_costs_benefits_and_absences(self) -> None:
        self.database.add_service("2026-09-10", "ABC-1234", "Lavagem", 5000, "Pix")
        self.database.add_service("2026-09-12", "", "Higienização", 12500, "Dinheiro")
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
        self.assertEqual(report["net_cents"], -10500)
        self.assertEqual(report["payroll_estimate_cents"], 180000 * 29)
        self.assertEqual(report["attendance"][0]["absences"], 1)
        self.assertEqual(report["most_absences_names"], ["Ana"])
        self.assertEqual(report["least_absences_names"], ["Ana"])

    def test_records_survive_reopening_database(self) -> None:
        self.database.add_service("2026-09-22", "", "Lavagem simples", 4500, "Pix")

        from app.database import Database

        reopened = Database()

        self.assertEqual(len(reopened.services_for_day("2026-09-22")), 1)


if __name__ == "__main__":
    unittest.main()