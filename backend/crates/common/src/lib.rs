//! Shared infrastructure crate for Oecophylla Rust services.
//!
//! Public modules are filled in across subsequent tasks. This stub exists so
//! the workspace compiles end-to-end from the start.

pub mod config;
pub mod error;
pub mod db;
pub mod redis;
pub mod kafka;
pub mod auth;
pub mod ids;
pub mod time;
pub mod events;
pub mod models;
pub mod middleware;
