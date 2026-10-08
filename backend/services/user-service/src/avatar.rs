use common::error::AppError;

pub const MAX_AVATAR_BYTES: usize = 5 * 1024 * 1024;

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum AvatarFormat {
    Jpeg,
    Png,
    Webp,
}

impl AvatarFormat {
    pub fn content_type(self) -> &'static str {
        match self {
            Self::Jpeg => "image/jpeg",
            Self::Png => "image/png",
            Self::Webp => "image/webp",
        }
    }
}

pub fn validate_avatar_upload(
    declared_content_type: &str,
    filename: &str,
    bytes: &[u8],
) -> Result<AvatarFormat, AppError> {
    if bytes.is_empty() || bytes.len() > MAX_AVATAR_BYTES {
        return Err(invalid_avatar("avatar must be between 1 byte and 5 MiB"));
    }

    let extension = filename
        .rsplit_once('.')
        .map(|(_, extension)| extension.to_ascii_lowercase())
        .ok_or_else(|| invalid_avatar("avatar filename must have a supported extension"))?;

    let format = match (declared_content_type, extension.as_str()) {
        ("image/jpeg", "jpg" | "jpeg") if bytes.starts_with(&[0xff, 0xd8, 0xff]) => {
            AvatarFormat::Jpeg
        }
        ("image/png", "png") if bytes.starts_with(b"\x89PNG\r\n\x1a\n") => AvatarFormat::Png,
        ("image/webp", "webp")
            if bytes.len() >= 12
                && bytes.starts_with(b"RIFF")
                && bytes.get(8..12) == Some(b"WEBP") =>
        {
            AvatarFormat::Webp
        }
        _ => return Err(invalid_avatar(
            "avatar must be a JPEG, PNG, or WebP with matching MIME type, extension, and signature",
        )),
    };

    Ok(format)
}

pub fn validate_cover_upload(
    declared_content_type: &str,
    filename: &str,
    bytes: &[u8],
) -> Result<AvatarFormat, AppError> {
    validate_avatar_upload(declared_content_type, filename, bytes).map_err(|_| {
        AppError::Validation {
            field: "cover".into(),
            message: "cover must be a JPEG, PNG, or WebP up to 5 MiB".into(),
        }
    })
}

pub fn validate_avatar_url(value: &str) -> Result<(), AppError> {
    if value.len() > 2048
        || !value.starts_with("https://")
        || value.chars().any(char::is_whitespace)
    {
        return Err(AppError::Validation {
            field: "avatar_url".into(),
            message: "avatar_url must be an HTTPS URL up to 2048 characters".into(),
        });
    }
    Ok(())
}

fn invalid_avatar(message: &str) -> AppError {
    AppError::Validation {
        field: "avatar".into(),
        message: message.into(),
    }
}

#[cfg(test)]
mod tests {
    use super::super::avatar::{
        validate_avatar_upload, validate_avatar_url, AvatarFormat, MAX_AVATAR_BYTES,
    };

    const PNG: &[u8] = b"\x89PNG\r\n\x1a\nrest";
    const JPEG: &[u8] = b"\xff\xd8\xff\xe0rest";
    const WEBP: &[u8] = b"RIFF\x04\x00\x00\x00WEBPrest";

    #[test]
    fn accepts_supported_images_when_mime_extension_and_signature_match() {
        assert_eq!(
            validate_avatar_upload("image/png", "avatar.png", PNG).unwrap(),
            AvatarFormat::Png
        );
        assert_eq!(
            validate_avatar_upload("image/jpeg", "avatar.JPG", JPEG).unwrap(),
            AvatarFormat::Jpeg
        );
        assert_eq!(
            validate_avatar_upload("image/webp", "avatar.webp", WEBP).unwrap(),
            AvatarFormat::Webp
        );
    }

    #[test]
    fn rejects_empty_and_oversized_uploads() {
        assert!(validate_avatar_upload("image/png", "avatar.png", &[]).is_err());
        assert!(
            validate_avatar_upload("image/png", "avatar.png", &vec![0; MAX_AVATAR_BYTES + 1])
                .is_err()
        );
    }

    #[test]
    fn rejects_svg_spoofed_mime_and_extension_mismatches() {
        assert!(validate_avatar_upload("image/svg+xml", "avatar.svg", b"<svg/>").is_err());
        assert!(validate_avatar_upload("image/png", "avatar.png", b"<script>").is_err());
        assert!(validate_avatar_upload("image/png", "avatar.jpg", PNG).is_err());
    }

    #[test]
    fn accepts_https_avatar_urls_and_rejects_unsafe_values() {
        assert!(validate_avatar_url("https://cdn.example.test/avatar.png").is_ok());
        assert!(validate_avatar_url("javascript:alert(1)").is_err());
        assert!(validate_avatar_url("http://cdn.example.test/avatar.png").is_err());
        assert!(
            validate_avatar_url(&format!("https://example.test/{}", "x".repeat(2048))).is_err()
        );
    }

    #[test]
    fn cover_upload_uses_the_same_verified_image_formats() {
        assert!(super::validate_cover_upload("image/png", "cover.png", PNG).is_ok());
        assert!(super::validate_cover_upload("image/png", "cover.png", b"<svg/>").is_err());
    }
}
