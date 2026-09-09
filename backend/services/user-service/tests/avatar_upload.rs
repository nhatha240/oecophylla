use reqwest::{Client, StatusCode};
use serde_json::json;

const AUTH: &str = "http://127.0.0.1:8001";
const USER: &str = "http://127.0.0.1:8002";

fn client() -> Client {
    Client::builder().cookie_store(true).build().unwrap()
}

async fn register(client: &Client) -> serde_json::Value {
    let unique = uuid::Uuid::now_v7().simple().to_string();
    let response = client
        .post(format!("{AUTH}/api/v1/auth/register"))
        .json(&json!({
            "username": format!("u{}", &unique[22..]),
            "email": format!("{unique}@avatar.test"),
            "password": "Password!123"
        }))
        .send()
        .await
        .unwrap();
    assert_eq!(response.status(), StatusCode::OK);
    response.json().await.unwrap()
}

fn multipart_avatar(filename: &str, content_type: &str, bytes: &[u8]) -> (String, Vec<u8>) {
    let boundary = format!("oec-avatar-{}", uuid::Uuid::now_v7().simple());
    let mut body = format!(
        "--{boundary}\r\nContent-Disposition: form-data; name=\"avatar\"; filename=\"{filename}\"\r\nContent-Type: {content_type}\r\n\r\n"
    )
    .into_bytes();
    body.extend_from_slice(bytes);
    body.extend_from_slice(format!("\r\n--{boundary}--\r\n").as_bytes());
    (boundary, body)
}

#[tokio::test]
async fn owner_uploads_versioned_avatar_and_spoofed_image_is_rejected() {
    let owner = client();
    let other = client();
    let owner_id = register(&owner).await["user"]["id"]
        .as_str()
        .unwrap()
        .to_owned();
    let _ = register(&other).await;
    let png = b"\x89PNG\r\n\x1a\nvalid-enough-browser-payload";
    let (boundary, body) = multipart_avatar("avatar.png", "image/png", png);

    let forbidden = other
        .put(format!("{USER}/api/v1/users/{owner_id}/avatar"))
        .header(
            "content-type",
            format!("multipart/form-data; boundary={boundary}"),
        )
        .body(body.clone())
        .send()
        .await
        .unwrap();
    assert_eq!(forbidden.status(), StatusCode::FORBIDDEN);

    let uploaded = owner
        .put(format!("{USER}/api/v1/users/{owner_id}/avatar"))
        .header(
            "content-type",
            format!("multipart/form-data; boundary={boundary}"),
        )
        .body(body)
        .send()
        .await
        .unwrap();
    assert_eq!(uploaded.status(), StatusCode::OK);
    let avatar_url = uploaded.json::<serde_json::Value>().await.unwrap()["avatar_url"]
        .as_str()
        .unwrap()
        .to_owned();
    assert!(avatar_url.contains("/avatar?v="));

    let served = owner
        .get(format!("{USER}{avatar_url}"))
        .send()
        .await
        .unwrap();
    assert_eq!(served.status(), StatusCode::OK);
    assert_eq!(served.headers()["content-type"], "image/png");
    assert_eq!(served.headers()["x-content-type-options"], "nosniff");
    assert_eq!(served.bytes().await.unwrap().as_ref(), png);

    let (boundary, body) = multipart_avatar("avatar.png", "image/png", b"<svg></svg>");
    let spoofed = owner
        .put(format!("{USER}/api/v1/users/{owner_id}/avatar"))
        .header(
            "content-type",
            format!("multipart/form-data; boundary={boundary}"),
        )
        .body(body)
        .send()
        .await
        .unwrap();
    assert_eq!(spoofed.status(), StatusCode::BAD_REQUEST);
}
