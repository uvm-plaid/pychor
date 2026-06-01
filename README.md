# PyChor: Choreographic Programming Library for Python

PyChor is a small Python library for writing choreographic programs: global
descriptions of distributed protocols that make party ownership, local
computation, and communication explicit.

## Installation

```bash
pip install pychor
```

## Documentation

Install the documentation dependencies:

```bash
python -m pip install -e ".[docs]"
```

Preview the documentation locally:

```bash
mkdocs serve
```

Validate the static site before publishing:

```bash
mkdocs build --strict
```

Deploy the documentation manually to GitHub Pages:

```bash
mkdocs gh-deploy --clean
```

Configure GitHub Pages for the repository to publish from the `gh-pages` branch.
The generated `site/` directory is ignored on `main`; `mkdocs gh-deploy` builds
the site and pushes it to `gh-pages`.

## Examples

See the documentation tutorial for a minimal current example. The `examples`
directory contains additional protocol sketches.

## Acknowledgments

This material is based upon work supported by the National Science
Foundation under Grant No. 2238442. Any opinions, findings and
conclusions or recommendations expressed in this material are those of
the author(s) and do not necessarily reflect the views of the National
Science Foundation.
