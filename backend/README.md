# Fainder Backend

## Helpful Commands

Run tests for the grammar:

```bash
uv run pytest tests
```

Start fastapi dev server:

```bash
cd ..
fastapi dev backend/main.py
```

Start fastapi production server:

```bash
cd ..
fastapi run backend/main.py
```

Upgrade dependencies:

```bash
uv lock -U
```
