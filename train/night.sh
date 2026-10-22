#!/bin/sh
# Overnight on minisforum: free the GPU, LoRA, merge, GGUF Q4_K_M.
#   rsync -a train/lora.py train/night.sh train/data/train.jsonl minisforum:factcheck-train/work/
#   ssh minisforum 'cd factcheck-train/work && nohup sh night.sh > night.log 2>&1 &'
set -e
cd "$(dirname "$0")"
PY=../bin/python
LLAMA=~/Proyects/llama.cpp/llama.cpp

# The router (teacher and any other model) off the shared memory while training;
# back on when this script ends, however it ends.
systemctl --user stop llama-router
trap 'systemctl --user start llama-router' EXIT

$PY lora.py train train.jsonl out
$PY lora.py merge out
PYTHONPATH=$LLAMA/gguf-py $PY $LLAMA/convert_hf_to_gguf.py out/merged --outtype bf16 --outfile out/e2b-ft-bf16.gguf
$LLAMA/build/bin/llama-quantize out/e2b-ft-bf16.gguf out/gemma-4-E2B-it-factcheck-Q4_K_M.gguf Q4_K_M
ls -la out/
