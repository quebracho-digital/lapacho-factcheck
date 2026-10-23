//! factcheck-core for the Android plugin app. Every call blocks for seconds
//! (the model) or a network round trip (SerpApi): call it off the main thread.

use std::sync::Arc;

uniffi::setup_scaffolding!();

#[derive(Debug, thiserror::Error, uniffi::Error)]
pub enum FactcheckError {
    /// `reason` is shown to the user as is.
    #[error("{reason}")]
    Failed { reason: String },
}

fn failed(e: anyhow::Error) -> FactcheckError {
    FactcheckError::Failed { reason: format!("{e:#}") }
}

/// The model, loaded once and kept while the app runs.
#[derive(uniffi::Object)]
pub struct Checker(factcheck_core::Llm);

#[uniffi::export]
impl Checker {
    #[uniffi::constructor]
    pub fn new(model_path: String) -> Result<Arc<Self>, FactcheckError> {
        factcheck_core::Llm::load(model_path.as_ref()).map(|l| Arc::new(Self(l))).map_err(failed)
    }

    /// The 1–3 queries the model would search for; nothing is sent.
    pub fn queries(&self, clip: String) -> Result<Vec<String>, FactcheckError> {
        let raw = self.0.chat(&factcheck_core::queries_prompt(&clip), 128).map_err(failed)?;
        Ok(factcheck_core::parse_queries(&raw))
    }

    /// The whole check; the text Lapacho saves as a new clip. Empty `queries`
    /// = the model writes them. `trusted` is the trusted.txt text.
    pub fn check(
        &self,
        clip: String,
        queries: Vec<String>,
        serpapi_key: String,
        trusted: String,
    ) -> Result<String, FactcheckError> {
        let trusted = factcheck_core::parse_trusted(&trusted);
        factcheck_core::check(&self.0, &clip, Some(queries), &serpapi_key, &trusted).map_err(failed)
    }
}
