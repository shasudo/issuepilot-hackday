# Profile format

A profile is YAML with these keys (all optional except where noted):

```yaml
display_name: Ada            # shown in Compare view
tech_stack: [python, react]  # frameworks/tools you know
languages: [python]          # programming languages
level: beginner              # beginner | intermediate | advanced
interests: [docs, testing]   # matched against labels/topics
hours_per_week: 4            # informational, not yet scored
```

Missing file or keys fall back to defaults (intermediate, empty lists), which
yields difficulty-only ranking instead of personalized fit.

CLI flags `--stack`, `--level`, `--interests` override file values.
See `profiles/beginner-python.yaml` and `profiles/advanced-web.yaml`.
