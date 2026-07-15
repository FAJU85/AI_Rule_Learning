"""Regression checks for GitHub labeler configuration."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pytest
import yaml


class UniqueKeyLoader(yaml.SafeLoader):
    """YAML loader that rejects duplicate mapping keys."""


def _construct_mapping(loader: UniqueKeyLoader, node: yaml.MappingNode, deep: bool = False) -> dict[str, Any]:
    mapping: dict[str, Any] = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if key in mapping:
            raise ValueError(f"duplicate YAML key: {key}")
        mapping[key] = loader.construct_object(value_node, deep=deep)
    return mapping


UniqueKeyLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _construct_mapping)


def _load_labeler_config() -> dict[str, Any]:
    config_path = Path(".github/labeler.yml")
    return yaml.load(config_path.read_text(), Loader=UniqueKeyLoader)


def test_labeler_config_has_unique_top_level_labels() -> None:
    config = _load_labeler_config()

    assert "enhancement" in config
    assert "bug" in config


@pytest.mark.parametrize("label", ["bug", "enhancement"])
def test_labeler_head_branch_patterns_are_valid_regexes(label: str) -> None:
    config = _load_labeler_config()
    branch_patterns = [pattern for rule in config[label] for pattern in rule.get("head-branch", [])]

    assert branch_patterns
    for pattern in branch_patterns:
        assert "**" not in pattern
        re.compile(pattern)
