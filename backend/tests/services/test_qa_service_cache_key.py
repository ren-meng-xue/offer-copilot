"""F3 测试：L1 cache key 不应依赖 conv_id。"""

import pytest


def test_l1_cache_key_independent_of_conv_id():
    """不同 conv_id 但相同 (scope, question) 应该产生相同 key。"""
    from backend.app.services.qa_service import _build_l1_cache_key

    key_a = _build_l1_cache_key(scope_hash="s1", q_hash="q1")
    key_b = _build_l1_cache_key(scope_hash="s1", q_hash="q1")
    assert key_a == key_b
    assert "conv" not in key_a.lower()


def test_l1_cache_key_different_scope_produces_different_key():
    from backend.app.services.qa_service import _build_l1_cache_key

    assert _build_l1_cache_key(scope_hash="s1", q_hash="q1") != _build_l1_cache_key(
        scope_hash="s2", q_hash="q1"
    )
    assert _build_l1_cache_key(scope_hash="s1", q_hash="q1") != _build_l1_cache_key(
        scope_hash="s1", q_hash="q2"
    )
