# Roadmap

## Hackathon (Oct 22–25, 2026)

Order matters: each step works on its own, so whatever we reach by Sunday is
a complete entry.

1. **Core on desktop** — `factcheck-core` with Gemma 4 E2B (stock, GGUF) via
   llama.cpp: clip → queries → SerpApi → verdict. The stdin binary works as a
   Lapacho external plugin. *This alone is a valid entry.*
2. **Android plugin app** — the same core through uniffi; RUN_PLUGIN in,
   verdict out. Model downloaded on first run, not shipped in the APK.
3. **Eval set** — ~100 held-out claims with expected verdicts and sources.
   Numbers for stock E2B and E4B, so the fine-tune has something to beat.
4. **Fine-tune** — LoRA on E2B from teacher-labelled data, merged and
   exported to GGUF q4; eval again; publish on Hugging Face.
   If the LoRA doesn't make it, the quantization and E2B/E4B comparison is
   the work on the weights we show.
5. **Post and video** — 45–60 s phone recording; "Lazy Payoff" with measured
   numbers (seconds per check, RAM, model size, before/after eval).

If step 4 doesn't beat stock on the eval, we ship stock and say so in the post,
with the numbers. A fine-tune that's worse isn't a feature.

## Open questions

- **Where we train.** Does minisforum's GPU fit a LoRA on E2B (Unsloth
  claims ~8 GB for E2B in 4-bit, 8–16 GB in practice)? Otherwise Colab or
  a rented GPU for a couple of hours.
- **Prize category.** One project wins once: Best Use of Gemma ($200) over
  Tinker's fine-tuning category.
- **Phone runtime.** llama.cpp via the NDK keeps one model file for both
  platforms; LiteRT is lighter to integrate on Android but needs a second
  format. Decide on day 1 by trying llama.cpp first.
- **SerpApi free quota** (serpapi.com/pricing): enough for the eval set plus
  the demo? If not, cache results during the eval.
- **Default `trusted.txt`:** ship it empty with a few lists to pick from on
  first run, or the user's own? The demo uses Leo's list.
- **Team:** Leo alone or with fluuix; who publishes the post.

## After the hackathon

- **Trusted sites as rich as `ai_provider_universal_factcheck`:** include and
  exclude lists, an imported bias list (MBFC), domains per topic, the local
  index before the web.
- **Other search backends** (SearXNG self-hosted, so no key is needed).
- **One Gemma on the phone for several Lapacho plugins**, each measured
  before it moves:
  - **Translate:** plain Gemma 4. Not TranslateGemma: it is based on Gemma 3,
    under the Gemma licence, which Lapacho's licence rule leaves out.
  - **Dictation (ASR):** the E models take audio; check that Gemma 4 E2B keeps
    transcription and that the phone runtime supports it (audio in llama.cpp
    is less mature than text). If so, it could replace sherpa-onnx in
    Lapacho Voice; compare against Parakeet with `speech-eval` first.
  - **Text to speech:** no; Gemma doesn't generate audio (Piper or Kokoro).
  - **Terms, Fabric patterns:** measured with `terms-eval` first.
