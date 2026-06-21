"""Tests for embeddings utility — verifying real mathematical behavior."""

from __future__ import annotations

import math
from unittest.mock import MagicMock
from unittest.mock import patch

import numpy as np
import pytest

import src.utils.embeddings as embeddings_module
from src.utils.embeddings import cosine_similarity
from src.utils.embeddings import embed
from src.utils.embeddings import embed_batch

# ---------------------------------------------------------------------------
# cosine_similarity — pure numpy, no mocking needed
# ---------------------------------------------------------------------------


class TestCosineSimilarity:
    def test_identical_vectors_return_one(self):
        v = [1.0, 2.0, 3.0]
        result = cosine_similarity(v, v)
        assert result == pytest.approx(1.0, abs=1e-6)

    def test_orthogonal_vectors_return_zero(self):
        a = [1.0, 0.0, 0.0]
        b = [0.0, 1.0, 0.0]
        assert cosine_similarity(a, b) == pytest.approx(0.0, abs=1e-6)

    def test_opposite_vectors_return_negative_one(self):
        a = [1.0, 0.0]
        b = [-1.0, 0.0]
        assert cosine_similarity(a, b) == pytest.approx(-1.0, abs=1e-6)

    def test_partial_similarity(self):
        a = [1.0, 0.0, 0.0]
        b = [1.0, 1.0, 0.0]
        # cos(45°) = 1/sqrt(2)
        expected = 1.0 / math.sqrt(2)
        assert cosine_similarity(a, b) == pytest.approx(expected, abs=1e-5)

    def test_empty_vec_a_returns_zero(self):
        assert cosine_similarity([], [1.0, 2.0]) == 0.0

    def test_empty_vec_b_returns_zero(self):
        assert cosine_similarity([1.0, 2.0], []) == 0.0

    def test_both_empty_returns_zero(self):
        assert cosine_similarity([], []) == 0.0

    def test_zero_vector_a_returns_zero(self):
        assert cosine_similarity([0.0, 0.0], [1.0, 2.0]) == pytest.approx(0.0)

    def test_zero_vector_b_returns_zero(self):
        assert cosine_similarity([1.0, 2.0], [0.0, 0.0]) == pytest.approx(0.0)

    def test_scalar_scaling_does_not_affect_result(self):
        a = [1.0, 1.0]
        b = [2.0, 2.0]
        # Same direction — should be exactly 1.0
        assert cosine_similarity(a, b) == pytest.approx(1.0, abs=1e-6)

    def test_high_dimensional_vectors(self):
        # All-ones vs all-ones in 100 dimensions → 1.0
        v = [1.0] * 100
        assert cosine_similarity(v, v) == pytest.approx(1.0, abs=1e-5)

    def test_returns_float_not_numpy_scalar(self):
        result = cosine_similarity([1.0, 0.0], [1.0, 0.0])
        assert isinstance(result, float)


# ---------------------------------------------------------------------------
# _get_model — lazy loading behavior
# ---------------------------------------------------------------------------


class TestGetModel:
    def setup_method(self):
        embeddings_module._model = None

    def test_loads_sentence_transformer(self):
        mock_model = MagicMock()
        mock_st_class = MagicMock(return_value=mock_model)
        mock_st_module = MagicMock(SentenceTransformer=mock_st_class)
        with patch("src.utils.embeddings.settings") as ms:
            ms.EMBEDDING_MODEL = "test-model"
            with patch.dict("sys.modules", {"sentence_transformers": mock_st_module}):
                model = embeddings_module._get_model()
        assert model is mock_model
        mock_st_class.assert_called_once_with("test-model")

    def test_caches_model_on_second_call(self):
        mock_model = MagicMock()
        mock_st_class = MagicMock(return_value=mock_model)
        mock_st_module = MagicMock(SentenceTransformer=mock_st_class)
        with patch("src.utils.embeddings.settings") as ms:
            ms.EMBEDDING_MODEL = "test-model"
            with patch.dict("sys.modules", {"sentence_transformers": mock_st_module}):
                embeddings_module._get_model()
                embeddings_module._get_model()
        assert mock_st_class.call_count == 1

    def test_raises_when_import_fails(self):
        embeddings_module._model = None
        with patch.dict("sys.modules", {"sentence_transformers": None}):
            with pytest.raises(Exception):
                embeddings_module._get_model()

    def test_returns_cached_model_without_import(self):
        sentinel = object()
        embeddings_module._model = sentinel
        result = embeddings_module._get_model()
        assert result is sentinel


# ---------------------------------------------------------------------------
# embed — single text
# ---------------------------------------------------------------------------


class TestEmbed:
    def setup_method(self):
        embeddings_module._model = None

    def _make_model(self, vector):
        mock_model = MagicMock()
        mock_model.encode.return_value = np.array(vector, dtype=np.float32)
        return mock_model

    def test_empty_string_returns_empty_list(self):
        result = embed("")
        assert result == []

    def test_whitespace_only_returns_empty_list(self):
        result = embed("   \t\n  ")
        assert result == []

    def test_returns_list_of_floats(self):
        vec = [0.1, 0.2, 0.3]
        mock_model = self._make_model(vec)
        with patch.object(embeddings_module, "_get_model", return_value=mock_model):
            result = embed("hello world")
        assert result == pytest.approx(vec)
        assert isinstance(result, list)
        assert all(isinstance(x, float) for x in result)

    def test_calls_encode_with_normalize(self):
        mock_model = self._make_model([0.5, 0.5])
        with patch.object(embeddings_module, "_get_model", return_value=mock_model):
            embed("some text")
        mock_model.encode.assert_called_once_with("some text", normalize_embeddings=True)

    def test_returns_empty_on_model_failure(self):
        with patch.object(embeddings_module, "_get_model", side_effect=RuntimeError("model down")):
            result = embed("any text")
        assert result == []

    def test_returns_empty_when_encode_fails(self):
        mock_model = MagicMock()
        mock_model.encode.side_effect = RuntimeError("OOM")
        with patch.object(embeddings_module, "_get_model", return_value=mock_model):
            result = embed("text")
        assert result == []


# ---------------------------------------------------------------------------
# embed_batch — multiple texts
# ---------------------------------------------------------------------------


class TestEmbedBatch:
    def setup_method(self):
        embeddings_module._model = None

    def _make_model(self, vectors):
        mock_model = MagicMock()
        mock_model.encode.return_value = np.array(vectors, dtype=np.float32)
        return mock_model

    def test_empty_list_returns_empty_list(self):
        assert embed_batch([]) == []

    def test_returns_one_vector_per_text(self):
        vecs = [[0.1, 0.2], [0.3, 0.4], [0.5, 0.6]]
        mock_model = self._make_model(vecs)
        with patch.object(embeddings_module, "_get_model", return_value=mock_model):
            result = embed_batch(["a", "b", "c"])
        assert len(result) == 3
        assert result[0] == pytest.approx([0.1, 0.2])
        assert result[2] == pytest.approx([0.5, 0.6])

    def test_calls_encode_with_normalize_and_no_progress_bar(self):
        vecs = [[0.1, 0.2]]
        mock_model = self._make_model(vecs)
        with patch.object(embeddings_module, "_get_model", return_value=mock_model):
            embed_batch(["hello"])
        mock_model.encode.assert_called_once_with(["hello"], normalize_embeddings=True, show_progress_bar=False)

    def test_returns_empty_lists_on_model_failure(self):
        with patch.object(embeddings_module, "_get_model", side_effect=RuntimeError("down")):
            result = embed_batch(["a", "b"])
        assert result == [[], []]

    def test_preserves_order(self):
        vecs = [[float(i)] for i in range(5)]
        mock_model = self._make_model(vecs)
        with patch.object(embeddings_module, "_get_model", return_value=mock_model):
            result = embed_batch(["t0", "t1", "t2", "t3", "t4"])
        for i, r in enumerate(result):
            assert r == pytest.approx([float(i)])
