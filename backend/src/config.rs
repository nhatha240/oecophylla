use figment::{providers::Env, Figment};
use serde::Deserialize;

#[derive(Debug, Deserialize)]
pub struct AppConfig {
    pub database_url: String,
    #[serde(default = "default_port")]
    pub port: u16,
    #[serde(default = "default_max_connections")]
    pub db_max_connections: u32,
}

fn default_port() -> u16 {
    3000
}

fn default_max_connections() -> u32 {
    10
}

impl AppConfig {
    pub fn from_env() -> Result<Self, figment::Error> {
        Figment::new().merge(Env::raw()).extract()
    }
}
