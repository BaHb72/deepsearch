from pathlib import Path

files = [
    Path(r"d:\Stock\code\deepsearch\deepsearch\config\database_connections.dev.yaml"),
    Path(r"d:\Stock\code\deepsearch\deepsearch\config\database_connections.prod.yaml"),
]

for file_path in files:
    if not file_path.exists():
        continue

    print(f"Updating {file_path}...")
    content = file_path.read_text(encoding="utf-8")

    # Generic replacement to reset status and enable connections
    # Note: This is a brute-force string replacement to ensure we catch the exact block structure
    # We replace 'status: error' with 'status: unknown' and 'enabled: false' with 'enabled: true'

    # For DuckDB (ID 2)
    # Pattern: enabled: false/true \n status: error
    # We want to force enabled: true and status: unknown

    # Regex for DuckDB block
    # We look for "type: duckdb" and then the following lines
    # Simplified string replace approach for safety if structure is known
    # DuckDB
    content = content.replace(
        "type: duckdb\n  host: localhost\n  port: 0\n  database: data/analytics/market.duckdb\n  password: ''\n  enabled: false\n  status: error",
        "type: duckdb\n  host: localhost\n  port: 0\n  database: data/analytics/market.duckdb\n  password: ''\n  enabled: true\n  status: unknown",
    )
    content = content.replace(
        "type: duckdb\n  host: localhost\n  port: 0\n  database: data/analytics/market.duckdb\n  password: ''\n  enabled: true\n  status: error",
        "type: duckdb\n  host: localhost\n  port: 0\n  database: data/analytics/market.duckdb\n  password: ''\n  enabled: true\n  status: unknown",
    )

    # Redis (ID 3)
    content = content.replace(
        "type: redis\n  host: localhost\n  port: 6379\n  database: '0'\n  username: default\n  password: ''\n  enabled: false\n  status: error",
        "type: redis\n  host: localhost\n  port: 6379\n  database: '0'\n  username: default\n  password: ''\n  enabled: true\n  status: unknown",
    )
    content = content.replace(
        "type: redis\n  host: localhost\n  port: 6379\n  database: '0'\n  username: default\n  password: ''\n  enabled: true\n  status: error",
        "type: redis\n  host: localhost\n  port: 6379\n  database: '0'\n  username: default\n  password: ''\n  enabled: true\n  status: unknown",
    )

    # Postgres (ID 1) - Just reset status, keep enablement as is (it was false in prod, true? in dev)
    # User needs to edit password anyway. But let's set status to unknown to clear the red error
    content = content.replace(
        "type: postgresql\n  host: localhost\n  port: 5432\n  database: deepsearch\n  username: postgres\n  password: ''\n  enabled: false\n  status: error",
        "type: postgresql\n  host: localhost\n  port: 5432\n  database: deepsearch\n  username: postgres\n  password: ''\n  enabled: true\n  status: unknown",
    )

    file_path.write_text(content, encoding="utf-8")
    print(f"Updated {file_path}")
