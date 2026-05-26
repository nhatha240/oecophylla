pub fn infer_topics(content: &str, tags: &[String], explicit: &[String]) -> Vec<String> {
    if !explicit.is_empty() {
        return explicit.to_vec();
    }

    let lower = content.to_lowercase();
    let mut topics = Vec::new();
    let rules = [
        (
            "ai",
            [
                "ai",
                "trí tuệ nhân tạo",
                "mô hình",
                "llm",
                "machine learning",
            ]
            .as_slice(),
        ),
        (
            "tech",
            ["công nghệ", "phần mềm", "dữ liệu", "bảo mật", "điện toán"].as_slice(),
        ),
        (
            "econ",
            [
                "kinh tế",
                "lãi suất",
                "chứng khoán",
                "doanh nghiệp",
                "ngân hàng",
            ]
            .as_slice(),
        ),
        (
            "edu",
            ["giáo dục", "học sinh", "trường", "kỹ năng", "edtech"].as_slice(),
        ),
        (
            "life",
            ["đời sống", "đô thị", "văn hoá", "du lịch", "ẩm thực"].as_slice(),
        ),
        (
            "health",
            ["y tế", "sức khỏe", "vacxin", "dinh dưỡng"].as_slice(),
        ),
        (
            "soc",
            ["chính sách", "xã hội", "chính trị", "cộng đồng"].as_slice(),
        ),
        (
            "code",
            ["lập trình", "rust", "svelte", "backend", "frontend"].as_slice(),
        ),
    ];
    for (topic, keywords) in rules {
        if keywords.iter().any(|kw| lower.contains(kw)) {
            topics.push(topic.to_string());
        }
    }
    if topics.is_empty() && !tags.is_empty() {
        topics.extend(tags.iter().take(3).cloned());
    }
    if topics.is_empty() {
        topics.push("general".to_string());
    }
    topics.sort();
    topics.dedup();
    topics
}

#[cfg(test)]
mod tests {
    use super::infer_topics;

    #[test]
    fn infers_ai_from_content() {
        let topics = infer_topics("AI đang thay đổi dữ liệu", &[], &[]);

        assert!(topics.contains(&"ai".to_string()));
    }

    #[test]
    fn preserves_explicit_topics() {
        let explicit = vec!["custom".to_string()];
        let topics = infer_topics("AI", &[], &explicit);

        assert_eq!(topics, explicit);
    }
}
