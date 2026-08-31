#[cfg(test)]
mod tests {
    use super::super::avatar::{validate_avatar_upload, AvatarFormat, MAX_AVATAR_BYTES};

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
        assert!(validate_avatar_upload(
            "image/png",
            "avatar.png",
            &vec![0; MAX_AVATAR_BYTES + 1]
        )
        .is_err());
    }

    #[test]
    fn rejects_svg_spoofed_mime_and_extension_mismatches() {
        assert!(validate_avatar_upload("image/svg+xml", "avatar.svg", b"<svg/>").is_err());
        assert!(validate_avatar_upload("image/png", "avatar.png", b"<script>").is_err());
        assert!(validate_avatar_upload("image/png", "avatar.jpg", PNG).is_err());
    }
}
