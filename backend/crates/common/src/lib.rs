//! Shared infrastructure crate for Oecophylla Rust services.
//!
//! Public modules are filled in across subsequent tasks. This stub exists so
//! the workspace compiles end-to-end from the start.

pub mod auth;
pub mod config;
pub mod db;
pub mod error;
pub mod events;
pub mod ids;
pub mod kafka;
pub mod middleware;
pub mod models;
pub mod redis;
pub mod time;
