//! Gemma through llama.cpp: one GGUF file, the same on desktop and phone.

use std::num::NonZeroU32;
use std::path::Path;

use anyhow::{Context, Result};
use llama_cpp_2::context::params::LlamaContextParams;
use llama_cpp_2::llama_backend::LlamaBackend;
use llama_cpp_2::llama_batch::LlamaBatch;
use llama_cpp_2::model::params::LlamaModelParams;
use llama_cpp_2::model::LlamaModel;
use llama_cpp_2::sampling::LlamaSampler;

const N_CTX: u32 = 8192;

pub struct Llm {
    backend: LlamaBackend,
    model: LlamaModel,
}

impl Llm {
    pub fn load(path: &Path) -> Result<Self> {
        let mut backend = LlamaBackend::init()?;
        backend.void_logs();
        let model = LlamaModel::load_from_file(&backend, path, &LlamaModelParams::default())
            .with_context(|| format!("loading {}", path.display()))?;
        Ok(Self { backend, model })
    }

    /// One user turn, greedy, so the same clip gives the same answer.
    pub fn chat(&self, user: &str, max_tokens: usize) -> Result<String> {
        // ponytail: Gemma 4's turn format written out; llama.cpp's built-in
        // templater doesn't know it and the Jinja path needs the `common` C++ API.
        let prompt = format!("<|turn>user\n{user}<turn|>\n<|turn>model\n");
        let vocab = self.model.vocab();
        let tokens = vocab.tokenize(prompt.as_bytes(), true, true);
        anyhow::ensure!(
            tokens.len() + max_tokens <= N_CTX as usize,
            "prompt too long: {} tokens",
            tokens.len()
        );

        let params = LlamaContextParams::default()
            .with_n_ctx(NonZeroU32::new(N_CTX))
            .with_n_batch(N_CTX);
        let mut ctx = self.model.new_context(&self.backend, params)?;
        let mut batch = LlamaBatch::new(N_CTX as usize, 1);
        let last = tokens.len() - 1;
        for (i, t) in tokens.iter().enumerate() {
            batch.add(*t, i as i32, &[0], i == last)?;
        }
        ctx.decode(&mut batch)?;

        let mut sampler = LlamaSampler::greedy();
        let mut out = Vec::new();
        let mut pos = tokens.len() as i32;
        for _ in 0..max_tokens {
            let token = sampler.sample(&ctx, batch.n_tokens() - 1);
            sampler.accept(token);
            if vocab.is_eog(token) {
                break;
            }
            out.extend(vocab.token_to_piece(token, false, None));
            batch.clear();
            batch.add(token, pos, &[0], true)?;
            pos += 1;
            ctx.decode(&mut batch)?;
        }
        Ok(String::from_utf8_lossy(&out).into_owned())
    }
}
