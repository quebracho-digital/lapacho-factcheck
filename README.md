# Lapacho Fact-check

Fact-check a clip with **Gemma running on your own device**, phone or desktop.
A [Lapacho](https://github.com/quebracho-digital/lapacho) plugin, built for
DEV's Hacktoberfest Open-Source AI Challenge, Week 3 (Oct 19–25, 2026).

> Status: idea and plan. Started 2026-10-22. Any commit after the deadline
> (2026-10-25 23:59 PDT) will be listed here.

## What it does

1. You copy a dubious claim. Lapacho keeps it as a clip.
2. You send the clip to *Fact-check*, like any other Lapacho plugin.
3. **On the device**, a fine-tuned Gemma reads the clip and writes 1–3 search
   queries.
4. Only those queries go out, to SerpApi: first restricted to trusted sites
   — **yours**: an editable `trusted.txt`, no outlet built in as the arbiter
   — then an open search if nothing comes back.
5. Gemma, still on the device, reads the results and writes a verdict for each
   claim, **according to your sources**: supported, contradicted or not
   enough evidence, each with the URLs and the passage it rests on. Sources from the open search are marked unverified.
6. The verdict comes back to Lapacho as a new clip.

## Why on-device, stated honestly

It is not offline: the search needs the internet. What stays on the device:

- **The clip.** Only the queries the model wrote leave it. Queries are made
  from the clip, so they can carry part of it; the plugin shows them before
  sending (and you can edit them).
- **The model and its cost.** No API key for the model, no per-token bill, no
  provider reading what you check.

## Why fine-tune Gemma

A small model (E2B) is fast enough on a phone but sloppy at two narrow jobs:
writing search queries and writing a verdict that only claims what the
sources say. Those are exactly the jobs we tune it for, with LoRA on the open
weights.

**The model doesn't decide who to trust; you do.** Which sources count is the
user's list, not something baked into the weights. So the tuning teaches a
skill with no editorial line in it: *does this passage support, contradict
or not address this claim?* The model is never told which outlet a passage
comes from, and its own opinion of the claim is not part of the verdict.

- **Teacher:** a large open model (Qwen3.6-35B-A3B on our own server) labels
  claims → queries, and claims + search results → verdicts with citations.
- **Data:** claims paired with passages, not with a ruling on the claim:
  the same claim with a passage that supports it, one that contradicts it and
  one off topic. Both sides of contested claims, in Spanish and English, with
  passages anonymized (no outlet name). Plus adversarial cases: a passage that
  sounds sure but doesn't address the claim, a prompt injection hidden in a
  result.
- **Labels checked by a person**, not only by the teacher: the teacher model
  has its own leanings, and the eval set is where they would show.
- **Eval before and after**, on a held-out set: output format kept (where
  small models fail most), verdict accuracy, query quality (does a trusted
  source come back), and citations that really support the sentence. Same method as Lapacho's `terms-eval`.
- **Cheaper work on the weights**, measured either way: Q4 vs Q8 and E2B vs
  E4B (quality, seconds per check, RAM, app size).
- **Weights published** on Hugging Face (Apache-2.0, like Gemma 4), with the
  dataset card and the eval numbers.

## How it is built

One Rust core, two front ends, the same shape as Lapacho Voice:

```
crates/factcheck-core    queries → SerpApi → verdict; prompts; trusted.txt
                         llama.cpp (GGUF) for Gemma
apps/desktop             `lapacho-factcheck` binary: stdin → stdout,
                         a Lapacho external plugin
apps/android             plugin app: RUN_PLUGIN intent, uniffi bridge to the
                         core, settings (SerpApi key, model download)
train/                   dataset building, LoRA (Unsloth), eval, GGUF export
```

- **Model:** Gemma 4 E2B on the phone, E4B where it fits; GGUF q4 through
  llama.cpp, so desktop and Android run the same file.
- **SerpApi key:** you paste your own in the settings. Never committed.
- **Network:** only this plugin app holds the internet permission. Lapacho and
  its keyboard don't.

## Built on

Lapacho's plugin contract (`docs/PLUGINS.md` in Lapacho) is the only thing
taken from Lapacho; the fact-check logic, prompts, training and eval are new
in this repo. Android plugin-app boilerplate (manifest, intent handling)
follows *Lapacho Terms*.

## Licence

MIT OR Apache-2.0, like Lapacho. Gemma 4 weights: Apache-2.0.
