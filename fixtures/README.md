# fixtures/

Sample PDFs used for seeding and demos. PDFs are not committed to git (listed in `.gitignore`).

## Get the sample PDF

```bash
make fixture
```

This downloads "Attention Is All You Need" (Vaswani et al., 2017) from arXiv and saves it as `fixtures/sample.pdf`.

To download manually:

```bash
curl -L https://arxiv.org/pdf/1706.03762 -o fixtures/sample.pdf
```

## Why not committed?

PDFs are binary files that inflate pack size and git history. The fixture is a stable public-domain paper that can be fetched on demand.
