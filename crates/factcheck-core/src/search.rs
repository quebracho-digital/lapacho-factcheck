//! SerpApi Google search. Only the queries leave the device.

use anyhow::{Context, Result};
use serde::Deserialize;

#[derive(Debug, Clone)]
pub struct Hit {
    pub title: String,
    pub url: String,
    pub snippet: String,
    /// From the user's trusted sites; false = open search, unverified.
    pub trusted: bool,
}

#[derive(Deserialize)]
struct Response {
    #[serde(default)]
    organic_results: Vec<Organic>,
    error: Option<String>,
}

#[derive(Deserialize)]
struct Organic {
    #[serde(default)]
    title: String,
    #[serde(default)]
    link: String,
    #[serde(default)]
    snippet: String,
}

/// Google reads only the first 32 words of a query, and each `site:` and `OR`
/// is one: a long list goes in groups, one search each.
const SITES_PER_SEARCH: usize = 8;

/// `query` restricted to `trusted` sites, a group at a time, until one finds
/// something; if none does (or the list is empty), the open search, marked untrusted.
pub fn search(key: &str, query: &str, trusted: &[String], per_query: usize) -> Result<Vec<Hit>> {
    for group in trusted.chunks(SITES_PER_SEARCH) {
        let sites = group.iter().map(|s| format!("site:{s}")).collect::<Vec<_>>().join(" OR ");
        let hits = google(key, &format!("{query} ({sites})"), per_query, true)?;
        if !hits.is_empty() {
            return Ok(hits);
        }
    }
    google(key, query, per_query, false)
}

fn google(key: &str, q: &str, num: usize, trusted: bool) -> Result<Vec<Hit>> {
    let resp: Response = ureq::get("https://serpapi.com/search.json")
        .query("engine", "google")
        .query("q", q)
        .query("num", num.to_string())
        .query("api_key", key)
        .call()
        .context("SerpApi request")?
        .body_mut()
        .read_json()?;
    // "Google hasn't returned any results" is an error to SerpApi, not to us.
    if let Some(e) = resp.error.filter(|e| !e.contains("any results")) {
        anyhow::bail!("SerpApi: {e}");
    }
    Ok(resp
        .organic_results
        .into_iter()
        .take(num)
        .map(|o| Hit { title: o.title, url: o.link, snippet: o.snippet, trusted })
        .collect())
}

/// One domain per line; `#` comments and blank lines skipped.
pub fn parse_trusted(text: &str) -> Vec<String> {
    text.lines()
        .map(|l| l.split('#').next().unwrap_or("").trim().to_string())
        .filter(|l| !l.is_empty())
        .collect()
}
