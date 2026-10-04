# Installation

## Requirements

- Python 3.10 or newer
- pip

## Install from PyPI (when published)

```bash
pip install ecbtkit
```

## Install from source

```bash
git clone https://github.com/emmanueletim/ecbtkit.git
cd ecbtkit
pip install -e .
```

## Optional database drivers

```bash
pip install ecbtkit[postgres]   # PostgreSQL
pip install ecbtkit[mysql]      # MySQL
pip install ecbtkit[dev]        # development tools
```

## Verify

```bash
ecbt version
```

Initialize or upgrade the database before normal startup:

```bash
ecbt migrate
```

The app does not auto-create or alter tables at startup. `ecbt dev` enables automatic table creation for local development only.
