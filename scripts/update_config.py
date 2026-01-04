from pathlib import Path

file_path = Path(r"d:\Stock\code\deepsearch\deepsearch\config\database_connections.dev.yaml")
content = file_path.read_text(encoding="utf-8")

# Parse is risky if comments are lost. Let's do string replacement with context.
# DuckDB (id: 2)
content = content.replace(
    "  name: 分析数据库\n  type: duckdb\n  host: localhost\n  port: 0\n  database: data/analytics/market.duckdb\n  password: ''\n  enabled: false",
    "  name: 分析数据库\n  type: duckdb\n  host: localhost\n  port: 0\n  database: data/analytics/market.duckdb\n  password: ''\n  enabled: true",
)

# Redis (id: 3)
content = content.replace(
    "  name: 缓存数据库\n  type: redis\n  host: localhost\n  port: 6379\n  database: '0'\n  username: default\n  password: ''\n  enabled: false",
    "  name: 缓存数据库\n  type: redis\n  host: localhost\n  port: 6379\n  database: '0'\n  username: default\n  password: ''\n  enabled: true",
)

file_path.write_text(content, encoding="utf-8")
print("Updated config file.")
