use argon2::{
    password_hash::{rand_core::OsRng, PasswordHash, SaltString},
    Argon2, PasswordHasher, PasswordVerifier,
};
use axum::http::HeaderValue;
use chrono::{Duration, Utc};
use jsonwebtoken::{decode, encode, Algorithm, DecodingKey, EncodingKey, Header, Validation};
use rand::RngCore;
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use uuid::Uuid;

use crate::models::UserRole;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Claims {
    pub sub: Uuid,
    pub role: UserRole,
    pub exp: i64,
    pub iat: i64,
    pub jti: Uuid,
}

pub fn issue_access(
    secret: &[u8],
    ttl_seconds: i64,
    sub: Uuid,
    role: UserRole,
) -> anyhow::Result<String> {
    let now = Utc::now();
    let claims = Claims {
        sub,
        role,
        exp: (now + Duration::seconds(ttl_seconds)).timestamp(),
        iat: now.timestamp(),
        jti: Uuid::now_v7(),
    };
    Ok(encode(
        &Header::new(Algorithm::HS256),
        &claims,
        &EncodingKey::from_secret(secret),
    )?)
}

pub fn verify_access(secret: &[u8], token: &str) -> anyhow::Result<Claims> {
    let v = Validation::new(Algorithm::HS256);
    let data = decode::<Claims>(token, &DecodingKey::from_secret(secret), &v)?;
    Ok(data.claims)
}

/// Opaque 32-byte refresh token, base64url-encoded for cookie transport.
/// Returns `(token_for_cookie, sha256_hex_for_redis_key)`.
pub fn new_refresh_token() -> (String, String) {
    let mut bytes = [0u8; 32];
    rand::thread_rng().fill_bytes(&mut bytes);
    use base64::Engine;
    let token = base64::engine::general_purpose::URL_SAFE_NO_PAD.encode(bytes);
    let hash = sha256_hex(&token);
    (token, hash)
}

pub fn sha256_hex(s: &str) -> String {
    let mut h = Sha256::new();
    h.update(s.as_bytes());
    hex::encode(h.finalize())
}

pub fn hash_password(plain: &str, m_cost: u32, t_cost: u32, p_cost: u32) -> anyhow::Result<String> {
    let salt = SaltString::generate(&mut OsRng);
    let params = argon2::Params::new(m_cost, t_cost, p_cost, None)
        .map_err(|e| anyhow::anyhow!("argon2 params: {e}"))?;
    let argon = Argon2::new(argon2::Algorithm::Argon2id, argon2::Version::V0x13, params);
    Ok(argon
        .hash_password(plain.as_bytes(), &salt)
        .map_err(|e| anyhow::anyhow!("argon2 hash: {e}"))?
        .to_string())
}

pub fn verify_password(plain: &str, hash: &str) -> bool {
    let Ok(parsed) = PasswordHash::new(hash) else {
        return false;
    };
    Argon2::default()
        .verify_password(plain.as_bytes(), &parsed)
        .is_ok()
}

pub struct CookieOpts {
    pub name: &'static str,
    pub value: String,
    pub path: &'static str,
    pub max_age_seconds: i64,
    pub same_site: &'static str, // "Lax" | "Strict"
    pub secure: bool,
}

pub fn cookie_header(opts: CookieOpts) -> HeaderValue {
    let secure = if opts.secure { "; Secure" } else { "" };
    let v = format!(
        "{}={}; Path={}; Max-Age={}; HttpOnly; SameSite={}{}",
        opts.name, opts.value, opts.path, opts.max_age_seconds, opts.same_site, secure
    );
    HeaderValue::from_str(&v).expect("valid cookie header")
}

pub fn clear_cookie_header(name: &'static str, path: &'static str) -> HeaderValue {
    let v = format!("{}=; Path={}; Max-Age=0; HttpOnly", name, path);
    HeaderValue::from_str(&v).unwrap()
}
