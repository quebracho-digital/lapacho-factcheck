//! Lapacho external plugin: the clip on stdin, the verdict on stdout.
//!
//! Settings live in `~/.config/lapacho-factcheck/`:
//! `model` (path to the GGUF), `serpapi_key`, `trusted.txt` (one domain per line).
//! `SERPAPI_KEY` and `LAPACHO_FACTCHECK_MODEL` override the files.
//! Plugin params: `preview` (flag) prints the queries without searching;
//! `queries` (text, `;`-separated) replaces the model's queries.

use std::io::Read;
use std::path::PathBuf;

use anyhow::{Context, Result};

fn main() {
    if let Err(e) = run() {
        eprintln!("{e:#}");
        std::process::exit(1);
    }
}

fn run() -> Result<()> {
    let dir = config_dir();
    let setting = |env: &str, file: &str| -> Result<String> {
        std::env::var(env).or_else(|_| {
            std::fs::read_to_string(dir.join(file))
                .map(|s| s.trim().to_string())
                .with_context(|| format!("set {env} or write {}", dir.join(file).display()))
        })
    };

    let mut clip = String::new();
    std::io::stdin().read_to_string(&mut clip)?;
    anyhow::ensure!(!clip.trim().is_empty(), "empty clip");

    let llm = factcheck_core::Llm::load(setting("LAPACHO_FACTCHECK_MODEL", "model")?.as_ref())?;

    if std::env::var("LAPACHO_PARAM_PREVIEW").as_deref() == Ok("1") {
        let raw = llm.chat(&factcheck_core::queries_prompt(&clip), 128)?;
        println!("Would search for (nothing sent):");
        for q in factcheck_core::parse_queries(&raw) {
            println!("- {q}");
        }
        return Ok(());
    }

    let queries = std::env::var("LAPACHO_PARAM_QUERIES").ok().map(|q| {
        q.split([';', '\n']).map(str::trim).filter(|q| !q.is_empty()).map(String::from).collect()
    });
    let key = setting("SERPAPI_KEY", "serpapi_key")?;
    let trusted = factcheck_core::parse_trusted(
        &std::fs::read_to_string(dir.join("trusted.txt")).unwrap_or_default(),
    );
    print!("{}", factcheck_core::check(&llm, &clip, queries, &key, &trusted)?);
    Ok(())
}

fn config_dir() -> PathBuf {
    let base = std::env::var_os("XDG_CONFIG_HOME")
        .map(PathBuf::from)
        .or_else(|| std::env::var_os("APPDATA").map(PathBuf::from))
        .unwrap_or_else(|| PathBuf::from(std::env::var_os("HOME").unwrap_or_default()).join(".config"));
    base.join("lapacho-factcheck")
}
