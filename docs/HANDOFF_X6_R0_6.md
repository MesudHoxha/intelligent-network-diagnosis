# X6-R0.6 test-environment reproducibility correction

X6-R0.6 is an append-only source-only packaging correction after published
X6-R0.5. The `test` optional dependency now directly declares
`pytest>=9,<10`, which includes the successfully accepted environment's
pytest 9.1.1 while avoiding an arbitrary patch pin. The existing httpx test
dependency is preserved.

The clean-install contract is `python -m pip install -e '.[test]'`, followed
by `python -m pytest`. Acceptance requires an archive-free temporary checkout
and a newly created virtual environment without system site packages. This
release changes no topology, F1 parameter, threshold, runtime evidence,
scientific result, X5 authority, or claim. It authorizes no Containerlab
lifecycle. X6-R1 remains paused until X6-R0.6 is reviewed and published; F2
through F4 and P9-R2 remain paused.
