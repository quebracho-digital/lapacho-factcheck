//! The core's own prompts for train/ (Python), so the dataset and the eval
//! use exactly what the app sends.
//!
//! JSON lines in, JSON lines out, each line gets fields added:
//!   {"clip": "...", "passages": ["..."]?}
//!   → + "queries_prompt", "verdict_prompt" (if passages)
//! With a model path as argument, also runs it (greedy, like the app):
//!   → + "queries_raw", "queries", "verdict_raw" (if passages)
//!
//!   cargo run --release -p factcheck-core --example train_io [model.gguf] < in.jsonl > out.jsonl

use std::io::{BufRead, Write};

use factcheck_core::{Hit, Llm, parse_queries, queries_prompt, verdict_prompt};
use serde_json::{Value, json};

fn main() -> anyhow::Result<()> {
    let llm = std::env::args().nth(1).map(|p| Llm::load(p.as_ref())).transpose()?;
    let mut out = std::io::stdout().lock();
    for line in std::io::stdin().lock().lines() {
        let mut v: Value = serde_json::from_str(&line?)?;
        let clip = v["clip"].as_str().unwrap_or_default().to_string();
        let hits: Option<Vec<Hit>> = v["passages"].as_array().map(|ps| {
            ps.iter()
                .map(|p| Hit {
                    title: String::new(),
                    url: String::new(),
                    snippet: p.as_str().unwrap_or_default().into(),
                    trusted: true,
                })
                .collect()
        });
        v["queries_prompt"] = json!(queries_prompt(&clip));
        if let Some(h) = &hits {
            v["verdict_prompt"] = json!(verdict_prompt(&clip, h));
        }
        if let Some(llm) = &llm {
            let t = std::time::Instant::now();
            let raw = llm.chat(&queries_prompt(&clip), 128)?;
            v["queries"] = json!(parse_queries(&raw));
            v["queries_raw"] = json!(raw);
            v["queries_secs"] = json!(t.elapsed().as_secs_f32());
            if let Some(h) = &hits {
                let t = std::time::Instant::now();
                v["verdict_raw"] = json!(llm.chat(&verdict_prompt(&clip, h), 768)?);
                v["verdict_secs"] = json!(t.elapsed().as_secs_f32());
            }
        }
        writeln!(out, "{v}")?;
        out.flush()?;
    }
    Ok(())
}
