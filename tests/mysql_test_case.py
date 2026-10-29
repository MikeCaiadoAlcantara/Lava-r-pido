import os
import unittest
import uuid

import mysql.connector

from app.database import Database


class MySQLTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.previous_database_name = os.environ.get("LAVA_DB_NAME")
        self.test_database_name = f"lava_test_{uuid.uuid4().hex}"
        self.addCleanup(self._restore_database_name)
        os.environ["LAVA_DB_NAME"] = self.test_database_name
        self.addCleanup(self._drop_test_database)
        self.database = Database()

    def _restore_database_name(self) -> None:
        if self.previous_database_name is None:
            os.environ.pop("LAVA_DB_NAME", None)
        else:
            os.environ["LAVA_DB_NAME"] = self.previous_database_name

    def _drop_test_database(self) -> None:
        connection = mysql.connector.connect(
            host=os.getenv("LAVA_DB_HOST", "127.0.0.1"),
            port=int(os.getenv("LAVA_DB_PORT", "3306")),
            user=os.getenv("LAVA_DB_USER", "root"),
            password=os.getenv("LAVA_DB_PASSWORD", ""),
        )
        try:
            cursor = connection.cursor()
            try:
                cursor.execute(f"DROP DATABASE IF EXISTS `{self.test_database_name}`")
                connection.commit()
            finally:
                cursor.close()
        finally:
            connection.close()