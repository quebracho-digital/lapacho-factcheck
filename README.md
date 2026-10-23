# Lapacho Fact-check

Fact-check a clip with **Gemma running on your own device**, phone or desktop.
A [Lapacho](https://github.com/quebracho-digital/lapacho) plugin, built for
DEV's Hacktoberfest Open-Source AI Challenge, Week 3 (Oct 19–25, 2026).

> Status (2026-10-23): the desktop plugin works, with our fine-tune of Gemma 4
> E2B (verdict accuracy 57.6% → 77.8% on the eval, below). The Android plugin
> app builds (llama.cpp through the NDK); testing on a phone is next. Any
> commit after the deadline (2026-10-25 23:59 PDT) will be listed here.

## What it does

1. You copy a dubious claim. Lapacho keeps it as a clip.
2. You send the clip to *Fact-check*, like any other Lapacho plugin.
3. **On the device**, a fine-tuned Gemma reads the clip and writes 1–3 search
   queries, in the clip's language.
4. Only those queries go out, to SerpApi: first restricted to **your** trusted
   sites (an editable `trusted.txt`; no outlet is built in as the arbiter),
   then an open search if nothing comes back.
5. Gemma, still on the device, reads the results and writes a verdict for each
   claim, **according to your sources**: supported, contradicted or not
   enough evidence, each with the URL and the passage it rests on. Sources
   from the open search are marked unverified.
6. The verdict comes back to Lapacho as a new clip.

A real run (fine-tuned E2B on a laptop CPU, 39 s):

```
$ echo "La inflación de Argentina en 2023 fue de 211%, la más alta desde 1991." | lapacho-factcheck
Fact-check, according to your sources

SUPPORTED: La inflación de Argentina en 2023 fue de 211%, la más alta desde 1991.
  "Argentina's annual inflation rate ended 2023 at 211.4%"
  https://www.reuters.com/markets/argentina-annual-inflation-tops-211-highest-since-early-90s-2024-01-11/

Searched for:
- inflación Argentina 2023 porcentaje
- inflación Argentina 1991 porcentaje
- historial inflación Argentina 2023
```

## Why on-device, stated honestly

It is not offline: the search needs the internet. What stays on the device:

- **The clip.** Only the queries the model wrote leave it. Queries are made
  from the clip, so they can carry part of it; the plugin can show them
  before sending, and you can write your own instead.
- **The model and its cost.** No API key for the model, no per-token bill, no
  provider reading what you check.

What does leave: the 1–3 queries, to SerpApi and the search engine behind it,
which can see them. The clip itself never goes out.

## Install (desktop)

Needs Rust and a C++ toolchain (llama.cpp is built from source by the
`llama-cpp-2` crate), and [Lapacho](https://github.com/quebracho-digital/lapacho)
for the plugin.

```sh
cargo install --path apps/desktop          # puts lapacho-factcheck in ~/.cargo/bin
mkdir -p ~/.config/lapacho-factcheck
echo /path/to/gemma-4-E2B-it-factcheck-Q4_K_M.gguf > ~/.config/lapacho-factcheck/model
echo YOUR_SERPAPI_KEY > ~/.config/lapacho-factcheck/serpapi_key   # serpapi.com, free plan: 250 searches/month
cp examples/trusted-example.txt ~/.config/lapacho-factcheck/trusted.txt  # then make it yours
cp apps/desktop/fact-check-gemma.json ~/.local/share/digital.quebracho.lapacho/plugins/
```

The plugin shows up the next time you open a clip in Lapacho. The model is
any Gemma 4 GGUF; ours is on Hugging Face (below). Without Lapacho, the
binary is a plain filter:

```sh
echo "La inflación de 2023 fue de 150%." | lapacho-factcheck
echo "..." | LAPACHO_PARAM_PREVIEW=1 lapacho-factcheck   # only show the queries
```

`SERPAPI_KEY` and `LAPACHO_FACTCHECK_MODEL` override the files.

## Build (Android)

Needs JDK 17, the Android SDK (platform 35) and NDK, Gradle 8.10, and Rust
with `cargo-ndk` and the targets `aarch64-linux-android` and
`x86_64-linux-android`:

```sh
cd apps/android
ANDROID_NDK_HOME=~/Android/Sdk/ndk/27.2.12479018 gradle :app:assembleDebug
```

The app downloads the model on first run (3.4 GB, from Hugging Face) and
answers Lapacho's `RUN_PLUGIN` intent like *Lapacho Terms*.

### CI and releases

GitHub Actions builds and tests the Rust core on every push and pull request.
Android builds (`app-debug.apk`) run on PRs and pushes to `main`. Pushing a
tag like `v1.0.0` builds a release APK, signs it with the release key (if the
secrets are set) and publishes it as a GitHub release.

## Trusted sites

`~/.config/lapacho-factcheck/trusted.txt`, one domain per line. An empty or
missing list means every source is from the open search and marked
unverified. `examples/trusted-example.txt` is the list we use in the demo: one
person's picks of wire services, primary-source and science outlets, with a
few more left commented out. Each site is tagged on two separate axes, lean
and ownership (`[state-funded]`, `[state-controlled]`), and outlets tied to a
state, from the BBC to RT, are off by default. The tags are one person's
judgment, the plugin ignores them, and nothing here endorses an outlet. Edit it; it is yours.

## Why fine-tune Gemma

A small model (E2B) is fast enough on a phone but sloppy at two narrow jobs:
writing search queries in the clip's language, and writing a verdict that only
claims what the sources say. Those are the jobs we tune it for, with LoRA on
the open weights.

**The model doesn't decide who to trust; you do.** The tuning teaches a skill
with no editorial line in it: *does this passage support, contradict or not
address this claim?* The model is never told which outlet a passage comes
from, and its own opinion of the claim is not part of the verdict.

### Data (`train/data.py`)

- **Base:** [VitaminC](https://huggingface.co/datasets/tals/vitaminc) and
  [FEVER](https://huggingface.co/datasets/copenlu/fever_gold_evidence), both
  CC BY-SA 3.0: Wikipedia claims paired with passages, usually both sides of
  the same claim (a passage that supports it and one that contradicts it or
  doesn't address it). Passages go in by number with distractors from other
  articles, exactly as the app builds the prompt.
- **Spanish:** claims and passages translated by the teacher, and Spanish
  claims over English passages.
- **Adversarial:** a passage that sounds sure of itself but doesn't address
  the claim, and a prompt injection inside a search result.
- **Teacher:** Qwen3.6-35B-A3B (on our own server) translates, writes the
  adversarial passages and the queries, and answers the same prompt the app
  sends. The **verdict comes from the dataset**, not the teacher: when the
  teacher disagrees, the example is dropped (1,016 dropped), so the model
  doesn't learn the teacher's leanings.
- **Result:** 3,212 rows: 2,084 verdicts (en 1,382 / es 702; supported 1,021,
  contradicted 585, not enough evidence 592) and 1,128 query rows (es 353).

### Training (`train/lora.py`, `train/night.sh`)

LoRA r16 / alpha 32 on the text decoder of `google/gemma-4-E2B-it` (24M
trainable parameters), transformers + PEFT in bf16 on an AMD Radeon 890M iGPU
(ROCm 7): 2 epochs, 394 steps, 4 hours. Loss only on the answer. Validation
loss 1.27 → 0.25. Merged and exported to GGUF Q4_K_M with llama.cpp.

### Eval (`train/eval.py`)

A held-out set from the datasets' test splits (no Wikipedia page shared with
training): 95 claims, plus 40 copies with an outlet name in front
("CNN reported:", "Página/12 informó:") and 20 fictional political claims
in mirrored pairs (kirchnerista/macrista, Democratic/Republican). The flip
test asks whether the verdict changes when only the outlet or the side
changes. Same method as Lapacho's `terms-eval`.

Results, Gemma 4 E2B Q4_K_M on a laptop CPU (`train/data/eval_out/`):

| | stock E2B | fine-tuned |
|---|---|---|
| Verdict accuracy, 99 claims | 57.6% | **77.8%** |
| · claims in English / Spanish | 54.4% / 61.9% | 78.9% / 76.2% |
| · prompt injection in a passage (8) | 2 | 6 |
| · Spanish claim, English passages (5) | 1 | 3 |
| JSON the app can parse | 100% (half with `source` as a string, most in code fences) | 100% |
| Sure verdicts citing the right passage | 78 of 101 | 104 of 117 |
| Quotes really in the cited passage | 93 of 101 | 117 of 117 |
| Verdict flips when only the outlet changes (20 groups) | 1 | **0** |
| Verdict flips when only the political side changes (10 pairs) | 1 | 1 |
| Spanish clips with every query in Spanish (42) | 14 | **42** |
| First query finds the claim's Wikipedia article (95) | 33 | 29 |
| Seconds: queries / verdict | 3.0 / 13.5 | 4.5 / 13.4 |

The table above uses the datasets' expected verdicts as they came. They were
not all right; see the next section for what we changed and what the numbers
look like after.

### Adjudicating the eval (`train/adjudicate.py`, `train/data/eval_adjudication.json`)

How the expected verdicts were checked, in order, so you can follow or redo it:

1. **The teacher as a flag.** Qwen3.6-35B-A3B answered the eval with the app's
   own prompt. It disagreed with the datasets' verdict on 28 of the 99 claims
   (marked ⚠ in `train/data/eval_review.md`).
2. **Three outside models as a panel.** The review file went to Gemini,
   Perplexity and getmerlin, asking for patterns and a ruling on each ⚠. They
   disagreed with each other (on e016, e028, e029, e056 and e073), so none of
   them was taken as the answer.
3. **Each ⚠ read against its own passages**, by Claude Code, with one rule:
   *judge only from the passages shown.* A passage that doesn't name the
   claim's subject ("The film was heavily panned...", "It has earned 62.06
   crore") can't support or contradict it. The datasets keep the Wikipedia
   page title next to the sentence; the model never sees it.
4. **Every decision is in `eval_adjudication.json`**, with a reason and a
   note, and the original verdict stays in `gold_original`:
   - 15 changed to *not enough evidence* (11 for a missing subject, 4 because
     the passage doesn't actually settle the claim),
   - 3 changed to what the passage says (e046, e060, e084),
   - 2 dropped as ambiguous claims (e037, e051),
   - 4 kept although the teacher disagreed, because the teacher was wrong
     (e011, e056, e073, e079: e.g. it used what it knows about Phoenix instead
     of what the passage says),
   - 4 political passages rewritten (see below).
5. **A person has not reviewed this yet.** The 8 outlet copies of the changed
   items follow their base item.

The political pairs had a different problem. The passage said "the
administration confirmed" and the claim said "the mayor announced yesterday",
a detail the passage lacks, and the teacher judged the two sides differently
(*not enough evidence* for macrista, *supported* for kirchnerista). That is
the teacher's own bias showing, and it also made the test unclean, so the four
passages (p-en-9, p-es-3) were rewritten to state the claim. Old runs saw the
old text: those four are left out of the rescore and need a new run.

`python3 -I train/adjudicate.py train/data/eval_out/NAME.jsonl` rescores a
finished run against the adjudicated verdicts.

| Verdict accuracy, claims only (no copies or pairs) | stock E2B | fine-tuned |
|---|---|---|
| Expected verdicts as they came (99) | 57.6% | 77.8% |
| Adjudicated, strict rule (97) | 70.1% | 78.4% |
| · "not enough evidence" right, as they came (25) | 17 | 19 |
| · "not enough evidence" right, adjudicated (36) | **28** | 24 |

What the stricter eval says, plainly: **the fine-tune's lead shrinks from 20
points to 8**, and on *not enough evidence*, the answer we care about most,
the stock model now does better (28 of 36 against 24 of 36). The training
data very likely has the same flaw as the eval: Wikipedia sentences with the
subject replaced by "The film...", labelled *supported* (a rough check finds
154 of 995 *supported* rows citing a passage that opens with a pronoun or a
generic noun; not yet audited). The tuned model learned to
fill the missing subject in, which is what the rule says not to do. Fixing
the training set the same way, and training again, is the next step; we ship
the numbers as they are.

## Process

How the model was built, measured and fixed, with every decision and its reason: [`docs/PROCESS.md`](docs/PROCESS.md) (current state) and [`docs/LOG.md`](docs/LOG.md) (dated log).

## How it is built

One Rust core, two front ends, the same shape as Lapacho Voice:

```
crates/factcheck-core    queries → SerpApi → verdict; prompts; trusted.txt
                         llama.cpp (GGUF) for Gemma, via llama-cpp-2
apps/desktop             `lapacho-factcheck` binary: stdin → stdout,
                         a Lapacho external plugin
apps/android             plugin app: RUN_PLUGIN intent, uniffi bridge to the
                         core, settings (SerpApi key, trusted sites, model
                         download); the queries are shown before they're sent
train/                   dataset, LoRA (transformers + PEFT), eval, GGUF export
examples/                trusted-sites list used in the demo
```

- **SerpApi key:** you paste your own. Never committed.
- **Network:** on Android only this plugin app holds the internet permission.
  Lapacho and its keyboard don't.

## Roadmap

Not built; this is the plan after the challenge.

**Hosted search, without an account on SerpApi.** Pasting a SerpApi key is fine
for a hackathon and too much for most people. A paid plan would run the search
for you. Bringing your own key stays free and supported.

The privacy commitment doesn't loosen because we'd be in the middle:

- **No logs.** The service keeps no queries, no IPs and no per-user history.
  The server is open source, so this can be checked, not only promised.
- **Valid subscriber, unknown user.** The app proves "I have a paid, current
  plan" with an anonymous token (blind signatures, as in Privacy Pass,
  RFC 9576–9578), not an account login. The service can verify the token but
  can't tell which subscriber sent it, nor link two searches to one person.
  Zero-knowledge proofs would also work; blind tokens are simpler and enough.
- **What a hosted search still sees:** the query text, and the network address
  unless it goes through a relay (Oblivious HTTP). Both stay in the plan:
  you keep approving the queries before they go, and the relay is the part
  that hides who sent them.

## Built on

Lapacho's plugin contract (`docs/PLUGINS.md` in Lapacho) is the only thing
taken from Lapacho; the fact-check logic, prompts, training and eval are new
in this repo.

## Licence

Code: MIT OR Apache-2.0, like Lapacho. Gemma 4 weights and our fine-tune:
Apache-2.0. The dataset is CC BY-SA 3.0, like VitaminC and FEVER.
