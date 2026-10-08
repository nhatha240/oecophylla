use common::error::AppError;
use serde::Deserialize;

#[derive(Debug, Deserialize)]
pub struct UpdatePostInput {
    pub content: Option<String>,
    pub media_urls: Option<Vec<String>>,
    pub tags: Option<Vec<String>>,
    pub topics: Option<Vec<String>>,
}

pub fn validate_update_post(mut input: UpdatePostInput) -> Result<UpdatePostInput, AppError> {
    if input.content.is_none()
        && input.media_urls.is_none()
        && input.tags.is_none()
        && input.topics.is_none()
    {
        return Err(invalid("body", "at least one editable field is required"));
    }
    if let Some(content) = input.content.as_mut() {
        *content = content.trim().to_owned();
        if content.is_empty() || content.chars().count() > 4000 {
            return Err(invalid("content", "1..=4000 chars"));
        }
        if input.topics.is_none() {
            input.topics = Some(Vec::new());
        }
    }
    if input.media_urls.as_ref().is_some_and(|urls| {
        urls.len() > 6
            || urls
                .iter()
                .any(|url| !url.starts_with("https://") && !url.starts_with("/api/v1/posts/"))
    }) {
        return Err(invalid("media_urls", "<=6 https urls or owned uploads"));
    }
    if input.tags.as_ref().is_some_and(|tags| tags.len() > 8) {
        return Err(invalid("tags", "<=8 tags"));
    }
    if input.topics.as_ref().is_some_and(|topics| topics.len() > 8) {
        return Err(invalid("topics", "<=8 topics"));
    }
    Ok(input)
}

pub fn validate_owned_uploads(
    media_urls: Option<&[String]>,
    existing: &[String],
) -> Result<(), AppError> {
    if media_urls.is_some_and(|urls| {
        urls.iter()
            .any(|url| url.starts_with("/api/v1/posts/") && !existing.contains(url))
    }) {
        return Err(invalid(
            "media_urls",
            "uploaded images must belong to this post",
        ));
    }
    Ok(())
}

fn invalid(field: &str, message: &str) -> AppError {
    AppError::Validation {
        field: field.into(),
        message: message.into(),
    }
}

#[cfg(test)]
mod tests {
    use super::super::update::{validate_owned_uploads, validate_update_post, UpdatePostInput};

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

    #[test]
    fn accepts_existing_post_uploads_and_rejects_other_posts_uploads() {
        let own = "/api/v1/posts/post-a/images/image-a".to_string();
        let other = "/api/v1/posts/post-b/images/image-b".to_string();
        assert!(validate_owned_uploads(Some(&[own.clone()]), &[own]).is_ok());
        assert!(validate_owned_uploads(Some(&[other]), &[]).is_err());
        assert!(
            validate_owned_uploads(Some(&["https://cdn.example.test/photo.jpg".into()]), &[])
                .is_ok()
        );
    }
}
