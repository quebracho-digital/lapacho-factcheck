# Process: how the Lapacho Fact-check model is built, measured and improved

Audience: human judges and AI agents. Every section is self-contained; tables use fixed columns.
Append-only record of changes and decisions: [`LOG.md`](LOG.md). This file is the current state.

Last updated: 2026-10-23 · Status: **training-data repair done, retrain not run yet**

## 1. What this is, in five lines

- A fact-checker that runs a fine-tuned Gemma 4 E2B on the user's device. The user, not the model, decides which sources count.
- The model does one narrow job: given a claim and numbered passages, answer `supported`, `contradicted` or `not_enough_evidence`, citing the passage and an exact quote.
- The fine-tune (LoRA) exists to make that job strict: **judge only from the passages shown**, never from what the model knows about the world.
- We measured it, found our own eval and training data were flawed, and are fixing them in the open. This file records how.
- Nothing here is final. Each claim says whether it was measured, estimated or only planned.

## 2. Where everything is

| Path | What it is |
|---|---|
| `train/data.py` | Builds the dataset (VitaminC + FEVER base, Spanish translation, adversarial cases, teacher labels) |
| `train/repair.py` | Cleans the training rows for the strict rule (section 5) |
| `train/lora.py`, `train/night.sh` | LoRA training, merge, GGUF export |
| `train/eval.py` | Scores a model run on the eval set |
| `train/adjudicate.py` | Applies the strict expected verdicts to the eval and rescores old runs |
| `train/data/eval_adjudication.json` | Every change to an expected verdict, with a reason |
| `train/data/eval_review.md` | The review file the panel of models read |
| `train/data/eval_out/` | Model outputs and scores, original and adjudicated |
| `examples/trusted-example.txt` | Example trusted-sites list: one person's judgment, not read by the plugin |
| `docs/LOG.md` | Dated log of every change and decision |

## 3. The rule everything depends on

> Judge only from the passages shown. A passage that does not name the claim's subject cannot support or contradict it.

Why this rule: the app gives the model search snippets **without titles** (`crates/factcheck-core/src/lib.rs:49`). Real snippets often start mid-sentence ("The film was heavily panned..."). A model that fills in the missing subject will confirm claims it has no evidence for. For a fact-checker, answering "not enough evidence" is the safe failure.

## 4. Measured results so far

Gemma 4 E2B Q4_K_M, laptop CPU. Claims only (no outlet copies or political pairs). Source: `train/data/eval_out/*.score.json`.

| Measure | Stock E2B | Fine-tuned (v1) | Status |
|---|---|---|---|
| Accuracy, expected verdicts as the datasets gave them (99 claims) | 57.6% | 77.8% | measured |
| Accuracy, strict rule applied (97 claims) | 70.1% | 78.4% | measured |
| "not enough evidence" right, strict rule (36) | 28 | 24 | measured |
| Verdict flips when only the outlet changes (20 groups) | 1 | 0 | measured |
| Verdict flips when only the political side changes | 1 | 1 | measured, 4 of 10 pairs need a rerun |

Reading: under the strict rule the fine-tune's lead over the stock model falls from 20 points to 8, and it is behind on the answer that matters most. The cause is in the training data (section 5). A person has not reviewed the strict labels.

## 5. What was wrong, and the fix

**Finding.** Training rows have the same flaw as the eval: Wikipedia sentences whose subject was replaced by "The film...", labelled `supported` because the dataset knows the page title. By a heuristic (the claim's capitalised words appear nowhere in the cited passage) 224 of 1,275 single-claim rows with a firm verdict had it.

**Fix (`train/repair.py`, run 2026-10-23).**

| Step | Rows | Result |
|---|---|---|
| Headless rows found | 224 | |
| Teacher rewrote the passage to name the subject, verdict kept | 224 tried | 189 kept, 35 failed |
| Original passage kept, relabelled `not_enough_evidence` | 224 | all |
| Same attribute, different entity → `not_enough_evidence` | 300 tried | 121 kept |
| Search-snippet look (date in front, "..." behind) on some passages | | 377 rows |
| Total rows | 3,212 → 3,522 | `not_enough_evidence` 592 → 937 (27% → 37%) |

All 583 new or changed rows were checked: every quote is inside its passage. **Known noise:** the teacher sometimes puts the wrong name in (example: it wrote "Dracula Untold was a royal ward" where the film title replaced the character). Not yet measured how often; planned check in section 8.

## 6. How the eval's expected verdicts were checked

1. The teacher (Qwen3.6-35B-A3B) answered the eval with the app's own prompt; it disagreed with the dataset on 28 of 99 claims.
2. Three outside models (Gemini, Perplexity, getmerlin) read `eval_review.md` and ruled on each. They contradicted each other on e016, e028, e029, e056 and e073, so none was taken as the answer. A fourth (Grok) said nearly every expected verdict was correct, including e060 and e084 where the passage plainly settles the claim; not used.
3. Each disputed item was read against its own passages, with the rule in section 3.
4. Outcome: 15 changed to `not_enough_evidence`, 3 corrected, 2 dropped as ambiguous, 4 kept (the teacher was wrong), 4 political passages rewritten. All in `eval_adjudication.json`; the original verdict stays in `gold_original`.
5. **Not reviewed by a person.** Stated everywhere results appear.

## 7. Source and licence decisions

| Source | Decision | Reason |
|---|---|---|
| VitaminC, FEVER | use (base) | CC BY-SA 3.0; our dataset must stay CC BY-SA |
| AVeriTeC | rejected | CC-BY-NC-4.0 (confirmed by the authors' text); NC would taint a paid hosted plan and the Apache-2.0 weights |
| whitehousehistory.org | rejected | a private association, not the US government; copyrighted |
| Encyclopaedia Britannica | rejected | copyrighted (the 1911 edition is public domain but outdated) |
| The Bible | rejected | poor fit: claims about scripture are interpretive |
| Archivo General de la Nación | postponed | reuse terms not confirmed; scanned historical documents |
| Interviews | rejected | copyright belongs to the outlet; transcripts do not free them |
| Federal Register, Boletín Oficial, court opinions | planned (section 8) | government works / open data; confirm the exact licence of each site before publishing a derived set |
| University theses | planned, 1–2 | licence varies per document; accept only CC BY / CC0, checked one by one |

## 8. Plan and how to reproduce

Current plan, in order. Each step records its result in `LOG.md`.

1. **Ablation on samples (planned).** Small LoRA runs on equal-sized samples: original rows vs repaired rows. Same eval, strict labels. Goal: estimate the benefit of the repair before the overnight run. Cost: about 40 minutes per arm on the Radeon 890M; the teacher server must be stopped meanwhile.
2. **Real-document eval (planned).** About 100 items from the Federal Register and the Boletín Oficial, built with controlled mutations (change a number, date or condition) plus same-document `not_enough_evidence` cases. One or two Spanish academic theses with an open licence for the academic register. Held out of training this round.
3. **Overnight retrain on `train_repaired.jsonl`** (4 hours). The v1 model stays as the fallback and is published if v2 does not beat it.
4. **Report both numbers** (original and strict labels) for v1, v2 and stock, with the confusion matrix and the recall of `not_enough_evidence`.
5. **Audit the repair noise:** sample 50 repaired rows and check the restored subject by hand or by a second model family.

Reproduce:

```
python3 -I train/data.py                       # build the dataset (needs the teacher server)
LLAMA_KEY=... python3 -I train/repair.py       # clean the rows → data/train_repaired.jsonl
sh train/night.sh                              # LoRA, merge, GGUF (on the training machine)
python3 -I train/eval.py data/eval_out/NAME.jsonl          # score as the datasets gave the labels
python3 -I train/adjudicate.py data/eval_out/NAME.jsonl    # rescore with the strict labels
```

## 9. After the hackathon

- Train on the real-document sources once the eval shows they help; keep a held-out slice per source.
- Force the hard cases when a model writes the claims: contradictions that share most words with the passage and change one condition, number or operator; `not_enough_evidence` from the same document on another aspect; subject always named.
- Replace the single-teacher labelling with two model families plus a person on disagreements; record inter-annotator agreement.
- Optional hosted search for people who do not want a SerpApi key, with no logs and anonymous subscriber tokens (see README, Roadmap). Not built.
- Publish weights and dataset on Hugging Face only after a person has reviewed the eval labels (decision of the project owner).
