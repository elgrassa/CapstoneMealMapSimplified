# Demo corpus — licensing + provenance

This directory bundles a **small, truncated, pre-processed demo dataset** so the
capstone runs end-to-end without live scraping. Everything here is either a
public-domain U.S. government work (17 USC § 105) or CC-licensed open-textbook
content.

## Sources

| Collection | Doc ID | Title | License | Source URL |
|---|---|---|---|---|
| recipes | `utah_wic_recipe_book` | Utah WIC Recipe Book | Public domain (17 USC § 105) | https://wic.utah.gov/wp-content/uploads/WIC-Recipe-Book.pdf |
| recipes | `lets_cook_with_kids_ca_wic` | Let's Cook With Kids (California WIC) | Public domain (17 USC § 105) | https://www.smchealth.org/sites/main/files/file-attachments/wic-ne-cookingwithchildren-letscookwithkids.pdf |
| nutrition_science | `nutrition_science_everyday_application` | Nutrition: Science and Everyday Application | CC BY 4.0 | https://openoregon.pressbooks.pub/nutritionscience2e/ |
| nutrition_science | `human_nutrition_hawaii` | Human Nutrition (U. Hawai'i) | CC BY 4.0 | https://pressbooks.oer.hawaii.edu/humannutrition2/ |

## Truncation

- Recipes: **≤15 recipes total** (demo starts with 5; expands as full bake runs)
- Nutrition: **≤25 fact entries total** (demo starts with 10)

The raw files under `recipes/raw/` and `nutrition_science/raw/` are
**hand-curated summaries** derived from the above sources — they are short
factual paragraphs of the kind a public-domain text contains, written for the
demo with explicit attribution. Each file begins with a header block naming
the source URL, license, and SHA256 fingerprint.

## Reproducibility

`python3 scripts/seed_demo.py` rebuilds the BM25 indexes from the raw files
in <5 s. It verifies every `.txt` file's SHA256 against
`provenance_manifest.json` and loads the pickled `index/bm25.pkl` for each
collection. If a SHA256 mismatches (e.g. you edited a raw file), the script
re-chunks and re-indexes that collection only.

## No sentence-transformer embeddings in this slice

To keep the first ship of the capstone under 5 MB total committed size and to
avoid the ~90 MB model download on first run, this demo uses **BM25 only**.
The hybrid retrieval code path is exercised in production at
https://meal-map.app. Installing the `[ml]` extra and re-running
`scripts/seed_demo.py --embed` adds embeddings locally.

## Derived artifacts

- `derived/dri_table.json` — small Recommended Dietary Allowance lookup extracted
  from the bundled nutrition textbooks.
- `derived/nutrient_cofactors.json` — 10-entry cofactor table (e.g. vitamin C
  enhances non-heme iron absorption) derived from the bundled content.

## Full corpus

The production MealMaster deployment at https://meal-map.app carries the full
5-collection corpus with ~hundreds of curated documents, full sentence-transformer
embeddings, reranking with a cross-encoder, and safety-escalation routing.
