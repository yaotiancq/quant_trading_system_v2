# Decisions

## Phase 1

- Treat `/home/yaotian/project/quant_trading_system_v2` as the repository root.
- Use Pydantic v2 for Phase 1 domain model validation and JSON-compatible serialization.
- Use `Decimal` for order, cash, fill, position, and account arithmetic fields.
- Keep all concrete broker and data integrations out of Phase 1.
- Use `.venv/bin/python` for commands because `python` is not currently exposed on PATH.

