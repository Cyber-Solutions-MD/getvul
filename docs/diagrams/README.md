# Diagrams

Mermaid source files (`.mmd`) and rendered PNGs for the diagrams used throughout the docs.

| File | Used by | Topic |
|------|---------|-------|
| [architecture-system.mmd](architecture-system.mmd) / `.png` | [02-architecture.md](../02-architecture.md) | High-level system map |
| [sync-pipeline.mmd](sync-pipeline.mmd) / `.png` | [02-architecture.md](../02-architecture.md) | Connector sync pipeline (scheduler tick) |
| [auth-oidc-flow.mmd](auth-oidc-flow.mmd) / `.png` | [02-architecture.md](../02-architecture.md), [16-security.md](../16-security.md) | Cross-replica OIDC login (post-Phase 1) |
| [configuration-flow.mmd](configuration-flow.mmd) / `.png` | [05-configuration.md](../05-configuration.md) | How env vars reach each component |
| [data-model-er.mmd](data-model-er.mmd) / `.png` | [09-data-model.md](../09-data-model.md) | Postgres entity-relationship diagram |
| [pipelines-cicd.mmd](pipelines-cicd.mmd) / `.png` | [12-pipelines-cicd.md](../12-pipelines-cicd.md) | CI + CD overview |

## Re-rendering

PNGs are rendered with `@mermaid-js/mermaid-cli`:

```bash
cd docs/diagrams
for f in *.mmd; do
  npx -y -p @mermaid-js/mermaid-cli@10.9.1 mmdc -i "$f" -o "${f%.mmd}.png" -b transparent -t default
done
```

If you tweak a `.mmd`, re-render and commit both files. The Mermaid sources are the source of truth.
