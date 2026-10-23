#!/bin/bash
# Ablation on minisforum: same LoRA, same size sample (N rows, seed 0), once
# from the original rows and once from the repaired rows. Only the rows differ.
#   rsync -a train/lora.py train/ablate.sh train/data/train.jsonl train/data/train_repaired.jsonl minisforum:factcheck-train/work/
#   ssh minisforum 'cd factcheck-train/work && nohup sh ablate.sh > ablate.log 2>&1 &'
set -e
cd "$(dirname "$0")"
PY=../bin/python
LLAMA=~/Proyects/llama.cpp/llama.cpp
N=${N:-600}

systemctl --user stop llama-router
trap 'systemctl --user start llama-router' EXIT

for arm in original repaired; do
  src=train.jsonl; [ $arm = repaired ] && src=train_repaired.jsonl
  shuf -n $N --random-source=<(yes 0) $src > abl-$arm.jsonl
  rm -rf out-abl-$arm
  $PY lora.py train abl-$arm.jsonl out-abl-$arm
  $PY lora.py merge out-abl-$arm
  PYTHONPATH=$LLAMA/gguf-py $PY $LLAMA/convert_hf_to_gguf.py out-abl-$arm/merged --outtype bf16 --outfile out-abl-$arm/bf16.gguf
  $LLAMA/build/bin/llama-quantize out-abl-$arm/bf16.gguf abl-$arm-Q4_K_M.gguf Q4_K_M
  rm -rf out-abl-$arm/merged out-abl-$arm/bf16.gguf   # 19 GB each; the disk is at 85%
  date; echo "arm $arm done"
done
