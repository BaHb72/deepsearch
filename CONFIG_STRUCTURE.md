# DeepSearch Configuration Structure

## Overview

DeepSearch uses an environment-specific configuration system where each environment has its own complete configuration
file:

```
deepsearch/
└── deepsearch/
    └── config/                     # Configuration module
        ├── __init__.py
        ├── constant.py             # Configuration constants
        ├── setting.py              # Configuration management (pydantic models)
        ├── settings.dev.yaml       # Development environment configuration
        └── settings.prod.yaml      # Production environment configuration
```

## Configuration Loading

The configuration system directly loads the environment-specific file based on:

1. **Environment variable** `APP__ENV` (if set)
2. **Default**: `prod` if not specified

Example:

- `APP__ENV=dev` → loads `settings.dev.yaml`
- `APP__ENV=prod` or unset → loads `settings.prod.yaml`

## Configuration Files

### `settings.dev.yaml`

Complete development environment configuration with:

- DEBUG logging level
- Local database settings
- Development-specific features enabled
- Debug options (profiling, tracing, SQL logging)

### `settings.prod.yaml`

Complete production environment configuration with:

- INFO logging level, JSON format
- Production database connection
- Security settings (TLS)
- Performance optimization
- Monitoring configuration

## Configuration Options

### Core Configuration

```yaml
app:
  name: DeepSearch
  author: BaHb
  env: dev/prod

log:
  active: true
  level: DEBUG/INFO/WARNING/ERROR/CRITICAL
  rotation: "00:00"
  retention_days: 7
  json: false/true

database:
  url: null  # or postgresql://...
```

### Message Bus Configuration

```yaml
message_bus:
  buses:
    zmq:       # ZeroMQ high-performance messaging
    inmem:     # In-memory for single process
    timeseries: # ZeroMQ with Redis persistence
  routes:      # Topic routing rules
```

### Environment-Specific Sections

#### Development Only

```yaml
debug:
  enable_profiling: true
  enable_tracing: true
  log_sql: true
```

#### Production Only

```yaml
monitoring:
  enable_metrics: true
  metrics_port: 9090

security:
  enable_tls: true
  cert_file: /path/to/cert.pem
  key_file: /path/to/key.pem

performance:
  max_workers: 64
  queue_size: 50000
  batch_size: 500
```

## Environment Variables

Override any configuration value using environment variables with `__` delimiter:

```bash
# Basic overrides
export APP__ENV=dev
export LOG__LEVEL=DEBUG

# Nested configuration
export MESSAGE_BUS__BUSES__ZMQ__CONFIG__HOST=10.0.0.5
export MESSAGE_BUS__ROUTES__0__BUSES='["zmq", "inmem"]'

# Sensitive data
export DATABASE__URL=postgresql://user:${DB_PASSWORD}@db/deepsearch
export MESSAGE_BUS__BUSES__TIMESERIES__CONFIG__STORAGE_CONFIG__PASSWORD=${REDIS_PASSWORD}
```

## Adding New Environments

To add a new environment (e.g., staging):

1. Create `deepsearch/config/settings.staging.yaml`
2. Include all required configuration (complete file, not just overrides)
3. Set `APP__ENV=staging` to use it

## Best Practices

1. **Keep sensitive data in environment variables** - Never commit passwords or keys
2. **Use complete configuration files** - Each environment file should be self-contained
3. **Document environment differences** - Add comments explaining why values differ
4. **Test configuration loading** - Verify new environments load correctly
5. **Version control all environment files** - Track configuration changes

## Migration from Old Structure

If migrating from the old structure with `setting.yaml`:

1. Each environment now has a complete configuration file
2. No more base template + overrides
3. Direct loading based on `APP__ENV`
4. Simplified configuration management without merging