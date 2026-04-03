"""Tests for category normalization."""
from app.crawl.category import normalize_category, STANDARD_CATEGORIES


class TestDirectMatch:
    """Standard categories should pass through unchanged."""

    def test_exact_match(self):
        for cat in STANDARD_CATEGORIES:
            assert normalize_category(cat) == cat

    def test_empty_returns_none(self):
        assert normalize_category("") is None
        assert normalize_category("  ") is None


class TestKeywordMap:
    """Known variants should map correctly."""

    def test_backend_variants(self):
        assert normalize_category("后端开发") == "后端"
        assert normalize_category("基础后端") == "后端"
        assert normalize_category("服务端") == "后端"
        assert normalize_category("Java开发") == "后端"

    def test_frontend_variants(self):
        assert normalize_category("前端开发") == "前端"
        assert normalize_category("Web开发") == "前端"

    def test_client_variants(self):
        assert normalize_category("客户端开发") == "客户端"
        assert normalize_category("Android") == "客户端"
        assert normalize_category("iOS") == "客户端"

    def test_algorithm_variants(self):
        assert normalize_category("策略算法") == "算法"
        assert normalize_category("风控算法") == "算法"
        assert normalize_category("AIGC算法") == "算法"

    def test_ml_variants(self):
        assert normalize_category("大模型") == "机器学习"
        assert normalize_category("机器学习平台") == "机器学习"
        assert normalize_category("深度学习") == "机器学习"

    def test_security_variants(self):
        assert normalize_category("基础安全") == "安全"
        assert normalize_category("端点防护") == "安全"

    def test_multimedia_variants(self):
        assert normalize_category("多媒体技术") == "多媒体"
        assert normalize_category("多媒体算法") == "多媒体"
        assert normalize_category("图形图像渲染") == "多媒体"
        assert normalize_category("音视频") == "多媒体"

    def test_cv_variants(self):
        assert normalize_category("内容理解") == "计算机视觉"
        assert normalize_category("图像算法") == "计算机视觉"

    def test_data_mining_variants(self):
        assert normalize_category("数据分析") == "数据挖掘"
        assert normalize_category("数据科学") == "数据挖掘"

    def test_bigdata_variants(self):
        assert normalize_category("数据引擎") == "大数据"
        assert normalize_category("数据工程") == "大数据"

    def test_test_variants(self):
        assert normalize_category("测试开发") == "测试"

    def test_case_insensitive(self):
        assert normalize_category("ios") == "客户端"
        assert normalize_category("NLP") == "自然语言处理"
        assert normalize_category("DevOps") == "基础架构"
        assert normalize_category("AIGC算法") == "算法"
