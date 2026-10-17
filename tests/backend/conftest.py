# Makes `import app...` work when pytest runs from the repo root, and gives API tests a database:
# DATABASE_URL from the environment (Postgres inside Docker), else a throw-away SQLite file.
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "backend"))

if "DATABASE_URL" not in os.environ:
    db_file = os.path.join(tempfile.mkdtemp(prefix="nascon-test-"), "test.db")
    os.environ["DATABASE_URL"] = "sqlite:///" + db_file.replace("\\", "/")
os.environ.setdefault("DAY1_SALT", "demo-salt")
