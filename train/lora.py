#!/usr/bin/env python3
"""LoRA on Gemma 4 E2B with transformers + PEFT (ROCm on minisforum's 890M).

Loss only on the answer (and its <turn|>), the prompt is masked. The chat
template is Gemma's own, which is byte for byte what llm.rs writes.

  python lora.py train data/train.jsonl out/      # adapter in out/adapter
  python lora.py merge out/                       # out/merged (full HF model)
then: convert_hf_to_gguf.py out/merged → llama-quantize Q4_K_M (see night.sh)
"""
import json
import os
import math
import random
import sys
import time
from pathlib import Path

import torch
from peft import LoraConfig, PeftModel, get_peft_model
from transformers import AutoModelForImageTextToText, AutoTokenizer

BASE = "google/gemma-4-E2B-it"
MAX_LEN = 2048
EPOCHS = int(os.environ.get("EPOCHS", 2))
BATCH = 16  # sequences per optimizer step
MICRO = int(os.environ.get("MICRO", 4))  # sequences per forward, padded
LR = 2e-4
# Text decoder only; the audio and vision towers stay as they are.
TARGETS = r".*language_model.*\.(q_proj|k_proj|v_proj|o_proj|gate_proj|up_proj|down_proj)"


def encode(tok, row):
    prompt = tok.apply_chat_template(row["messages"][:1], tokenize=False, add_generation_prompt=True)
    full = tok.apply_chat_template(row["messages"], tokenize=False)
    assert full.startswith(prompt), "template changed"
    p = tok(prompt, add_special_tokens=False)["input_ids"]
    ids = tok(full, add_special_tokens=False)["input_ids"][:MAX_LEN]
    return ids, [-100] * len(p) + ids[len(p):]


def train(data, out):
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    tok = AutoTokenizer.from_pretrained(BASE)
    rows = [json.loads(l) for l in open(data)][: int(os.environ.get("LIMIT", 10**9))]  # LIMIT: smoke test
    random.Random(25).shuffle(rows)
    seqs = [encode(tok, r) for r in rows]
    n_val = min(60, max(20, len(seqs) // 40))
    val, seqs = seqs[:n_val], seqs[n_val:]
    print(f"train {len(seqs)} val {len(val)} max_len {max(len(s[0]) for s in seqs)}", flush=True)

    model = AutoModelForImageTextToText.from_pretrained(BASE, dtype=torch.bfloat16, device_map={"": 0})
    model.gradient_checkpointing_enable()
    model.enable_input_require_grads()
    model = get_peft_model(model, LoraConfig(r=16, lora_alpha=32, lora_dropout=0.05, target_modules=TARGETS,
                                             task_type="CAUSAL_LM"))
    model.print_trainable_parameters()

    params = [p for p in model.parameters() if p.requires_grad]
    opt = torch.optim.AdamW(params, lr=LR, weight_decay=0.0)
    steps = EPOCHS * math.ceil(len(seqs) / BATCH)
    sched = torch.optim.lr_scheduler.LambdaLR(
        opt, lambda s: min(1, (s + 1) / 20) * 0.5 * (1 + math.cos(math.pi * min(s, steps) / steps)))

    pad = tok.pad_token_id

    def loss_of(micro):
        n = max(len(ids) for ids, _ in micro)
        t = lambda xs: torch.tensor(xs, device=model.device)
        return model(input_ids=t([ids + [pad] * (n - len(ids)) for ids, _ in micro]),
                     attention_mask=t([[1] * len(ids) + [0] * (n - len(ids)) for ids, _ in micro]),
                     labels=t([lab + [-100] * (n - len(lab)) for _, lab in micro])).loss

    def micros(batch):  # similar lengths together, so little padding
        batch = sorted(batch, key=lambda s: len(s[0]))
        return [batch[j:j + MICRO] for j in range(0, len(batch), MICRO)]

    def val_loss():
        model.eval()
        with torch.no_grad():
            l = sum(loss_of(m).item() * len(m) for m in micros(val)) / len(val)
        model.train()
        return l

    print(f"steps {steps}, val loss before {val_loss():.4f}", flush=True)
    model.train()
    step, t0 = 0, time.time()
    for epoch in range(EPOCHS):
        random.Random(epoch).shuffle(seqs)
        for i in range(0, len(seqs), BATCH):
            batch = seqs[i:i + BATCH]
            total = 0.0
            for m in micros(batch):
                loss = loss_of(m) * len(m) / len(batch)
                loss.backward()
                total += loss.item()
            torch.nn.utils.clip_grad_norm_(params, 1.0)
            opt.step()
            sched.step()
            opt.zero_grad()
            step += 1
            if step % 10 == 0 or step == 2:
                el = time.time() - t0
                print(f"step {step}/{steps} loss {total:.4f} lr {sched.get_last_lr()[0]:.2e} "
                      f"{el / step:.1f}s/step eta {(steps - step) * el / step / 60:.0f} min", flush=True)
            if step % 100 == 0:
                model.save_pretrained(out / "adapter")
                print(f"val loss {val_loss():.4f} (saved)", flush=True)
    model.save_pretrained(out / "adapter")
    print(f"done, val loss {val_loss():.4f}, {(time.time() - t0) / 60:.0f} min", flush=True)


def merge(out):
    out = Path(out)
    model = AutoModelForImageTextToText.from_pretrained(BASE, dtype=torch.bfloat16)
    model = PeftModel.from_pretrained(model, out / "adapter").merge_and_unload()
    model.save_pretrained(out / "merged")
    AutoTokenizer.from_pretrained(BASE).save_pretrained(out / "merged")
    print(f"merged → {out / 'merged'}")


if __name__ == "__main__":
    {"train": train, "merge": merge}[sys.argv[1]](*sys.argv[2:])
