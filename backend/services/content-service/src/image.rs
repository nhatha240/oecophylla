use common::error::AppError;

pub const MAX_POST_IMAGE_BYTES: usize = 5 * 1024 * 1024;

pub fn validate_post_image(
    content_type: &str,
    filename: &str,
    bytes: &[u8],
) -> Result<&'static str, AppError> {
    if bytes.is_empty() || bytes.len() > MAX_POST_IMAGE_BYTES {
        return Err(invalid());
    }
    let extension = filename
        .rsplit_once('.')
        .map(|(_, ext)| ext.to_ascii_lowercase())
        .ok_or_else(invalid)?;
    match (content_type, extension.as_str()) {
        ("image/jpeg", "jpg" | "jpeg") if bytes.starts_with(&[0xff, 0xd8, 0xff]) => {
            Ok("image/jpeg")
        }
        ("image/png", "png") if bytes.starts_with(b"\x89PNG\r\n\x1a\n") => Ok("image/png"),
        ("image/webp", "webp")
            if bytes.len() >= 12
                && bytes.starts_with(b"RIFF")
                && bytes.get(8..12) == Some(b"WEBP") =>
        {
            Ok("image/webp")
        }
        _ => Err(invalid()),
    }
}

fn invalid() -> AppError {
    AppError::Validation {
        field: "image".into(),
        message: "image must be a JPEG, PNG, or WebP up to 5 MiB".into(),
    }
}
