# Log

Append-only. One entry per change or decision, newest at the bottom. Format:
`ID · date · type · what · why · evidence`. Types: `decision`, `change`, `finding`, `rejected`.
Current state is in [`PROCESS.md`](PROCESS.md).

---

**L-001 · 2026-10-22 · finding** · Gemma 4 E2B timed in three quantizations (Q4_K_M, QAT q4_0, Q8_0) on Ryzen AI 9 HX 370, iGPU and CPU. · Choose the quantization for the phone. · Table in the brief.

**L-002 · 2026-10-23 · finding** · LoRA v1 on the original dataset: accuracy 57.6% → 77.8% on 99 eval claims, expected verdicts as the datasets gave them. · First result. · `train/data/eval_out/*.score.json`.

**L-003 · 2026-10-23 · decision** · The example trusted-sites list no longer carries any third-party rating or the rater's name; tags are one person's judgment on two axes (lean, ownership); outlets tied to a state are off by default. · Avoid licence and trademark trouble; lean and state ownership are different questions. The BBC is tagged `[state-funded]` (a licence fee), not `[state-controlled]`, because the second would be false. The old name remains in git history; the repo is public and this was accepted. · commit 53c8e0f.

**L-004 · 2026-10-23 · decision** · README states what leaves the device: the 1–3 approved queries, visible to SerpApi and the search engine; the clip never leaves. Hosted search plan written as a roadmap item (no logs, anonymous tokens, relay), not built. · A fact-checker's privacy claim must include its limit. · commit 53c8e0f.

**L-005 · 2026-10-23 · finding** · Three outside models and the teacher disagreed on eval labels; many "expected" verdicts rested on passages that never name the subject. · The eval was measuring a rule the product does not follow. · `train/data/eval_review.md`.

**L-006 · 2026-10-23 · decision** · Strict rule adopted: judge only from the passages shown. Eval re-labelled by it (15 to `not_enough_evidence`, 3 corrected, 2 dropped, 4 kept, 4 political passages rewritten). Original verdicts kept in `gold_original`. · Matches what the app gives the model (snippets without titles). · `train/data/eval_adjudication.json`, commit 05ad53a.

**L-007 · 2026-10-23 · finding** · Under the strict rule: stock 70.1%, fine-tuned 78.4%; the fine-tune's lead falls from 20 to 8 points and it is behind on `not_enough_evidence` (24/36 vs 28/36). · The training data has the same flaw. · `train/data/eval_out/*.adjudicated.score.json`.

**L-008 · 2026-10-23 · rejected** · Grok's review (nearly all expected verdicts correct) not used. · It contradicts the passages of e060 and e084. · —

**L-009 · 2026-10-23 · rejected** · AVeriTeC (CC-BY-NC-4.0), whitehousehistory.org (private association), Britannica (copyright), the Bible (poor fit), interviews (copyright). Archivo General de la Nación postponed (terms unconfirmed). · See PROCESS.md section 7. · The AVeriTeC licence text was supplied by the project owner.

**L-010 · 2026-10-23 · rejected** · A second SerpApi account to get more free searches. · Likely against their terms. The eval's searches are cached in `serp_cache.json`; the remaining quota is kept for the demo video and the phone test. · —

**L-011 · 2026-10-23 · change** · Added `train/repair.py` and ran it: 224 headless rows found; 189 repaired with the verdict kept, 35 only relabelled; the original passages relabelled `not_enough_evidence`; 121 "other entity" cases; 377 snippet-look rows. 3,212 → 3,522 rows, `not_enough_evidence` 27% → 37%. · Train the model the same rule the eval uses. · `train/data/train_repaired.jsonl`; all 583 new or changed rows have their quote inside the passage.

**L-012 · 2026-10-23 · finding** · Repair noise seen in a spot check: the teacher sometimes inserts a wrong name (film title in place of the character). · Rate unknown. · Audit of 50 rows planned.

**L-013 · 2026-10-23 · decision** · New sources go first into a held-out real-document eval (Federal Register, Boletín Oficial, one or two open-licence Spanish theses), not into the overnight training. · Change one thing at a time so the result can be attributed. · Plan in PROCESS.md section 8.

**L-014 · 2026-10-23 · change** · Published on HF: `quebracho-digital/lapacho-factcheck-data` (train, eval, eval_adjudicated) and `quebracho-digital/gemma-4-E2B-it-factcheck` (Q4_K_M, Q8_0, adapter), after the jury review of the eval (L-005..L-008). Files and sizes checked against the API. · Ship the v1 numbers with their limits. · huggingface.co API tree listing; commit 2fac75c (README, cards).

**L-015 · 2026-10-23 · decision** · Human review of the dataset is out of this version: no time and no expertise on the team. It moves to the next version, with a more curated dataset from the new sources. README says so. · Say plainly what was and was not checked; the jury of models (L-005..L-008) is not a person. · README, "Adjudicating the eval", point 5.

**L-016 · 2026-10-23 · decision** · Ablation kept basic, to measure one thing: the effect of repairing the training rows. Two LoRAs, same recipe, 600 rows each (seed 0), one from `train.jsonl` and one from `train_repaired.jsonl`; same strict eval. New sources come after, as a separate step. · One change at a time (L-013). · `train/ablate.sh`.

**L-017 · 2026-10-23 · change** · Ablation launched on minisforum (74 steps per arm, about 50 min each, teacher router stopped while it runs; restarts by itself on exit). Note: the first `ssh ... nohup &` call hung the client until its timeout; the job itself was fine. · — · `~/factcheck-train/work/ablate.log`.
