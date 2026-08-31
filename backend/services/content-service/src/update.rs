#[cfg(test)]
mod tests {
    use super::super::update::{validate_update_post, UpdatePostInput};

    fn empty_update() -> UpdatePostInput {
        UpdatePostInput {
            content: None,
            media_urls: None,
            tags: None,
            topics: None,
        }
    }

    #[test]
    fn rejects_an_update_without_any_fields() {
        assert!(validate_update_post(empty_update()).is_err());
    }

    #[test]
    fn trims_content_and_accepts_valid_fields() {
        let validated = validate_update_post(UpdatePostInput {
            content: Some("  Nội dung mới  ".into()),
            media_urls: Some(vec!["https://cdn.example.test/image.jpg".into()]),
            tags: Some(vec!["news".into()]),
            topics: None,
        })
        .unwrap();

        assert_eq!(validated.content.as_deref(), Some("Nội dung mới"));
    }

    #[test]
    fn rejects_invalid_content_media_and_tag_boundaries() {
        let mut input = empty_update();
        input.content = Some("   ".into());
        assert!(validate_update_post(input).is_err());

        let mut input = empty_update();
        input.media_urls = Some(vec!["http://insecure.example.test/image.jpg".into()]);
        assert!(validate_update_post(input).is_err());

        let mut input = empty_update();
        input.tags = Some((0..9).map(|index| format!("tag-{index}")).collect());
        assert!(validate_update_post(input).is_err());
    }
}
