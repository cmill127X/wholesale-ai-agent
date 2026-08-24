# Wholesale AI Agent

Zero-cost-first AI-assisted wholesale research, data cleaning, verification, deduplication, and lead scoring pipeline.

## MVP pipeline

`input -> normalize -> deduplicate -> score -> second-pass QC -> clean output`

The core pipeline currently uses only Python's standard library, so there are no required paid APIs or dependencies.

## Run

```bash
python app.py
```

## Next stages

1. Add research/source adapters.
2. Add CSV upload and export.
3. Add source-level evidence and confidence rules.
4. Add a web/API interface.
5. Connect deployment through Vercel.
6. Add a customer-facing payment/access layer only after the service works.

## Design principle

The agent should never silently turn an unverified claim into a verified lead. Every record should carry its source, confidence, and verification state.
