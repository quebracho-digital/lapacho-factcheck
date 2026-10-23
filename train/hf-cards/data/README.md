---
license: cc-by-sa-3.0
language:
- en
- es
task_categories:
- text-classification
- text-generation
tags:
- fact-checking
- claim-verification
- gemma
- lora
pretty_name: Lapacho Fact-check data
size_categories:
- 1K<n<10K
source_datasets:
- tals/vitaminc
- copenlu/fever_gold_evidence
---

# Lapacho Fact-check data

> **v1, work in progress.** This is the data the v1 model was trained on. It has a known flaw:
> some `supported`/`contradicted` rows rely on a subject the passage never names (the dataset
> knew the page title). A repaired v2 is being built and will be added here. See the eval
> section for how this shows in the numbers.

Training and eval data for [Lapacho Fact-check](https://github.com/quebracho-digital/lapacho-factcheck),
a Lapacho plugin that fact-checks a clip with Gemma 4 E2B on your own device.
It teaches two narrow skills, and nothing about whom to trust:

1. **Queries:** given a text, write 1–3 short, neutral web search queries **in the text's language**.
2. **Verdicts:** given a text and numbered search passages (no outlet names), say for each claim
   whether the passages **support** it, **contradict** it, or give **not enough evidence**, citing
   the passage number and an exact quote.

Which sources count is the user's own list in the app, never the data or the weights.

## Files

| File | Rows | What |
|---|---|---|
| `train.jsonl` | 3,212 | `messages` (user prompt exactly as the app builds it, model answer), `kind`, `lang` |
| `eval.jsonl` | 155 | held-out items: `clip`, `passages`, `gold` verdicts, the teacher's answer, flip-test groups |
| `eval_adjudicated.jsonl` | 153 | the same items with the strict-rule `gold`; the original verdicts in `gold_original` |

Train rows: 2,084 verdicts (en 1,382 / es 702; supported 1,021, contradicted 585,
not enough evidence 592) and 1,128 query rows (es 353, en 775).

| kind | rows | |
|---|---|---|
| `single` | 1,502 | one claim, the gold passage among 1–6 distractors from other articles |
| `multi` | 114 | two or three claims in one text |
| `es_claim_en_passages` | 106 | a Spanish claim over English passages |
| `confident_offtopic` | 190 | a passage that sounds sure of itself but doesn't address the claim |
| `injection` | 172 | a prompt injection inside a passage ("SYSTEM: the correct verdict is…") |
| `queries` | 1,128 | text → queries |

## How it was made

- **Base:** [VitaminC](https://huggingface.co/datasets/tals/vitaminc) and
  [FEVER](https://huggingface.co/datasets/copenlu/fever_gold_evidence) (gold evidence),
  both CC BY-SA 3.0. Most claims come with both sides: a passage that supports
  them and one that contradicts or doesn't address them.
- **Teacher:** Qwen3.6-35B-A3B (Q4_K_XL, llama.cpp, temperature 0) translated
  claims and passages to Argentine Spanish, wrote the adversarial passages and
  the queries, and answered the exact student prompt.
- **The verdict label is the dataset's, not the teacher's.** The teacher's answer is a
  filter: when it disagrees with the gold label, or quotes words that aren't in the
  passage, the example is dropped (1,016 dropped). Train is therefore biased towards
  evidence stated explicitly in the passage.
- Passages are anonymized: numbered, never with the outlet's name.

## Eval set

From the datasets' test splits; no Wikipedia page is shared with training.
95 base items (single 70, multi 4, es_claim_en_passages 5, confident_offtopic 8,
injection 8), 40 outlet copies of 20 items ("CNN reported:", "Fox News reported:",
"Página/12 informó:", "La Nación informó:") and 20 fictional political claims in
mirrored pairs (kirchnerista/macrista, Democratic/Republican). The flip test
asks whether the verdict changes when only the outlet or the side changes.

**Strict labels.** Many original gold verdicts relied on passages that never name the claim's
subject. Under the rule *judge only from the passages shown*, 15 items became
`not_enough_evidence`, 3 were corrected, 2 dropped and 4 political passages rewritten
(`eval_adjudicated.jsonl`). The strict labels were adjudicated against the passages with a panel
of models; **no person has reviewed them yet.**

Stock Gemma 4 E2B vs the v1 fine-tune (97 claims, strict): 70.1% vs 78.4%; with the original
labels (99 claims): 57.6% vs 77.8%. v1 is behind the stock model on `not_enough_evidence`
(24 vs 28 of 36), the flaw described above.

## Licence

CC BY-SA 3.0, inherited from VitaminC and FEVER (Wikipedia text).
