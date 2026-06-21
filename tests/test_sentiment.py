"""Tests for the sentiment analysis utility."""

from __future__ import annotations

from unittest.mock import MagicMock
from unittest.mock import patch

import pytest

import src.utils.sentiment as sentiment_module
from src.utils.sentiment import analyze
from src.utils.sentiment import sentiment_delta


class TestAnalyze:
    def setup_method(self):
        sentiment_module._pipeline = None

    def _make_pipeline(self, label: str, score: float):
        pipe = MagicMock(return_value=[{"label": label, "score": score}])
        return pipe

    def test_empty_string_returns_zero(self):
        assert analyze("") == 0.0

    def test_whitespace_only_returns_zero(self):
        assert analyze("   ") == 0.0

    def test_positive_sentiment(self):
        pipe = self._make_pipeline("POSITIVE", 0.9)
        with patch.object(sentiment_module, "_get_pipeline", return_value=pipe):
            result = analyze("This is great!")
            assert result == pytest.approx(0.9)

    def test_negative_sentiment(self):
        pipe = self._make_pipeline("NEGATIVE", 0.8)
        with patch.object(sentiment_module, "_get_pipeline", return_value=pipe):
            result = analyze("This is terrible!")
            assert result == pytest.approx(-0.8)

    def test_case_insensitive_label(self):
        pipe = self._make_pipeline("positive", 0.7)
        with patch.object(sentiment_module, "_get_pipeline", return_value=pipe):
            result = analyze("good")
            assert result == pytest.approx(0.7)

    def test_pipeline_failure_returns_zero(self):
        with patch.object(sentiment_module, "_get_pipeline", side_effect=RuntimeError("model unavailable")):
            result = analyze("any text")
            assert result == 0.0

    def test_truncates_to_512_chars(self):
        long_text = "a" * 600
        pipe = self._make_pipeline("POSITIVE", 0.5)
        with patch.object(sentiment_module, "_get_pipeline", return_value=pipe):
            analyze(long_text)
            pipe.assert_called_once_with("a" * 512)

    def test_get_pipeline_loads_once(self):
        sentiment_module._pipeline = None
        mock_pipeline_fn = MagicMock(return_value=self._make_pipeline("POSITIVE", 0.6))
        mock_transformers = MagicMock(pipeline=mock_pipeline_fn)
        with patch.dict("sys.modules", {"transformers": mock_transformers}):
            sentiment_module._get_pipeline()
            sentiment_module._get_pipeline()
            assert mock_pipeline_fn.call_count == 1

    def test_get_pipeline_raises_on_import_error(self):
        sentiment_module._pipeline = None
        with patch.dict("sys.modules", {"transformers": None}):
            with pytest.raises(Exception):
                sentiment_module._get_pipeline()


class TestSentimentDelta:
    def test_positive_improvement(self):
        assert sentiment_delta(0.1, 0.8) == pytest.approx(0.7)

    def test_negative_decline(self):
        assert sentiment_delta(0.8, 0.1) == pytest.approx(-0.7)

    def test_clamped_at_positive_two(self):
        assert sentiment_delta(-1.0, 1.5) == pytest.approx(2.0)

    def test_clamped_at_negative_two(self):
        assert sentiment_delta(1.0, -1.5) == pytest.approx(-2.0)

    def test_zero_delta(self):
        assert sentiment_delta(0.5, 0.5) == pytest.approx(0.0)
