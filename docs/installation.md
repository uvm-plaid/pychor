# Installation

Install PyChor from PyPI:

```bash
python -m pip install pychor
```

For local development, install the package from a checkout:

```bash
python -m pip install -e .
```

To build the documentation locally, install the documentation extra:

```bash
python -m pip install -e ".[docs]"
```

Preview the documentation site:

```bash
mkdocs serve
```

Validate a production build:

```bash
mkdocs build --strict
```

Deploy the documentation manually to GitHub Pages:

```bash
mkdocs gh-deploy --clean
```
