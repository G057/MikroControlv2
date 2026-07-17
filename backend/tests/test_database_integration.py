import os
import unittest


@unittest.skipUnless(os.environ.get("DATABASE_URL", "").startswith("postgresql"), "Requiere PostgreSQL")
class DatabaseIntegrationTests(unittest.TestCase):
    def test_migrated_schema_contains_core_tables(self):
        from sqlalchemy import inspect
        from app.core.database import engine

        tables = set(inspect(engine).get_table_names())
        self.assertTrue({"users", "routers", "event_logs", "alerts", "alembic_version"}.issubset(tables))


if __name__ == "__main__":
    unittest.main()
