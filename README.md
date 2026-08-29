# Intelligent Network Diagnosis

## Source-test environment

Create a fresh virtual environment and install the project test extra before
running the default source suite:

```bash
python -m venv .venv
.venv/bin/python -m pip install -e '.[test]'
.venv/bin/python -m pytest -q
```

Ignored runtime archives are not required by the default source suite.
Archive-dependent acceptance checks remain a separate explicit verification
tier.
