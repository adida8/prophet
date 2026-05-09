"""Explainer — produces the contract's `copy.title / summary / blurb`.

PR 5 will replace the templated stub with three real Haiku prompts.
For now, deterministic prose carries the verdict's editorial signal
without depending on the Anthropic API key.
"""

from desk.explainer.stub import build_copy  # noqa: F401
