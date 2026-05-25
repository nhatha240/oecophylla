use figment::{providers::Env, Figment};
use serde::Deserialize;

#[derive(Debug, Deserialize, Clone)]
pub struct SharedConfig {
    pub database_url: String,
    pub redis_url: String,
    pub kafka_brokers: String,
    pub jwt_secret: String,
    pub jwt_access_ttl_seconds: i64,
    pub jwt_refresh_ttl_seconds: i64,
    #[serde(default = "default_m_cost")]
    pub argon2_m_cost: u32,
    #[serde(default = "default_t_cost")]
    pub argon2_t_cost: u32,
    #[serde(default = "default_p_cost")]
    pub argon2_p_cost: u32,
    #[serde(default)]
    pub auto_publish: bool,
    #[serde(default = "default_bind")]
    pub bind: String,
}

fn default_m_cost() -> u32 {
    19456
}
fn default_t_cost() -> u32 {
    2
}
fn default_p_cost() -> u32 {
    1
}
fn default_bind() -> String {
    "0.0.0.0:8001".into()
}

impl SharedConfig {
    pub fn from_env() -> anyhow::Result<Self> {
        let c: SharedConfig = Figment::new().merge(Env::raw().lowercase(true)).extract()?;
        Ok(c)
    }
}
