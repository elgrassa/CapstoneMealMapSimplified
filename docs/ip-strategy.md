# IP strategy — what was scrubbed and why

This capstone is a public artifact. The production MealMaster at [meal-map.app](https://meal-map.app) is a commercial product. The two must co-exist: the grader needs enough code to evaluate, the product needs its commercial differentiators to stay private.

## What ships here vs what stays private

| Asset | Public in this repo | Private (stays at meal-map.app) |
|---|---|---|
| Agent architecture + code | ✅ Full | — |
| Retrieval pipeline code | ✅ Full | — |
| Evidence gate algorithm + threshold values | ✅ Full (0.3 / 0.1 — already public in `evidenceGate.js`) | — |
| Authority weights | ✅ Full (1.3 / 1.0 / 0.7) | — |
| Chunking strategies + code | ✅ Full | Tuned per-collection values |
| Canonical ingredients | 10-item USDA sample | Full 82 × 19 × EU-14 catalog |
| Medical-boundary validator | 5 phrases + 2 triggers sample | Full 44 + 9 × 3-severity catalog |
| Dietary rules corpus | Schema + 3 example rules | Full curated corpus |
| System prompts | Generic RAG template | Production-tuned prompts |
| Ground-truth queries | 7 generic public-domain queries | MealMaster-specific production queries + Polish-market queries |
| Knowledge corpus | Truncated NHLBI + WIC + Open Oregon + UH Hawai'i (28 chunks) | Full 5-collection corpus (~hundreds of documents) |
| Base44 entity schemas | — | All |
| React UI | — | All |
| GDPR / DPIA / legal docs | — | All |
| Family-setup + meal-plan generation + shopping + pantry logic | — | All |

## The license

**AGPL-3.0** (not MIT).

Why: the AGPL requires any hosted fork to open-source its modifications. This deters the specific threat of a well-funded offshore agency cloning the code, hosting it with a nominal re-skin, and selling it commercially. The GPL-for-servers provision of AGPL makes that business model unattractive.

For commercial licensing of the MealMaster trademark or a non-AGPL code license, contact the copyright holder — see `NOTICE`.

## The trademark notice

`NOTICE` explicitly states that "MealMaster" is a trademark of the copyright holder and is not licensed under the AGPL. This matters because even if someone modifies and re-hosts the code (complying with AGPL), they can't call the result "MealMaster" — they have to re-brand.

## Demo corpus — public-domain only

Every raw file under `data/rag/demo/*/raw/` is:
- Either a U.S. Government work (17 USC § 105 — no copyright, public domain).
- Or a CC BY 4.0 open textbook.

`data/rag/demo/provenance_manifest.json` records: title, source URL, license, SHA256, chunk count, per doc.

## Residual accepted risks

1. **AI training scraping** — every public GitHub repo is in every foundation model's training corpus within days. No mitigation exists. Accepted.
2. **Architectural pattern copying** — the general patterns (tiered evidence gate, 8 agent tools, adaptive chunking) are visible. These are the *grading deliverables*; the differentiators (curated content, tuning constants, production prompts) stay private.
3. **Student-to-student pattern convergence** — multiple capstone submissions will look architecturally similar. Accepted; the domain (family nutrition + health PII + EU allergen safety) is the moat, not the architecture.

## How to verify the scrub worked

```bash
# No MealMaster-named error messages in user-facing strings
grep -r "MealMaster" SimplifiedMealMasterCapstone/src SimplifiedMealMasterCapstone/ai SimplifiedMealMasterCapstone/backend

# No Polish-market terms
grep -rE "Lidl|Biedronka|PLN|\\.zl" SimplifiedMealMasterCapstone/

# No family-member names, user emails, internal URLs
grep -rE "base44|@anthropic" SimplifiedMealMasterCapstone/
```

Expected: zero hits on any of the above (modulo legitimate MealMaster mentions in README / NOTICE / LICENSE / provenance manifest as the brand name).
