# Turns coverage.py's JSON report into COVERAGE.json (spec §9.3): line coverage % per backend area.
# Usage: python tests/coverage_areas.py coverage.json > COVERAGE.json
import fnmatch
import json
import sys

AREAS = {
    "fixtures": ["app/domain/fixtures_*.py", "app/routes/audit_fixtures.py"],
    "scoring": ["app/domain/scoring.py", "app/domain/sport_config.py", "app/services/events.py",
                "app/services/sports.py"],
    "standings": ["app/domain/standings.py", "app/services/leagues.py"],
    "store": ["app/services/store.py", "app/domain/receipt_pdf.py", "app/services/payment_gateway.py"],
    "roster": ["app/domain/roster_rules.py", "app/services/roster.py"],
    "rbac": ["app/auth.py", "app/policy.py", "app/routes/audit_rbac.py", "app/middleware.py"],
}


def normalise(path):
    """'backend/app/x.py' or '/srv/app/x.py' or 'app\\x.py' -> 'app/x.py'."""
    path = path.replace("\\", "/")
    return path[path.index("app/"):] if "app/" in path else path


def area_percentages(report):
    files = {normalise(name): data["summary"] for name, data in report["files"].items()}
    result = {}
    for area, patterns in AREAS.items():
        covered = total = 0
        for name, summary in files.items():
            if any(fnmatch.fnmatch(name, p) for p in patterns):
                covered += summary["covered_lines"]
                total += summary["num_statements"]
        result[area] = round(100.0 * covered / total, 1) if total else 0.0
    return result


if __name__ == "__main__":
    with open(sys.argv[1], encoding="utf-8") as f:
        print(json.dumps(area_percentages(json.load(f))))
