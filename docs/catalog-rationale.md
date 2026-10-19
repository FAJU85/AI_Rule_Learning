# Catalog Rationale & Budget Audit (v0.3.1)

## Executive Summary

This document provides the complete rule-level token audit, budget analysis, and rationale for all 130 rules in `data/catalog_v1.json`.

### Key Metrics

- **Total Catalog Rules:** 130
- **Total Categories:** 10
- **Rules within 20–40 Word Envelope:** 122 / 130 (93.8%)
- **Rules outside 20–40 Word Envelope:** 8 / 130 (6.2%, ranging 16–19 words)
- **10 Largest Rules Combined Token Count:** 403 tokens (Well below 500-token cap)

---

## Top 10 Largest Rules Token Audit

| Rule ID / Gap Type                 | Category            | Word Count | Est. Token Count | Source Citation                                                      |
| ---------------------------------- | ------------------- | ---------- | ---------------- | -------------------------------------------------------------------- |
| `multi_turn_constraint_erosion`    | `instruction_drift` | 32         | 43               | Zhou et al. (2023), Findings of EMNLP, ACL:2023.findings-emnlp.968   |
| `boilerplate_code_reprinting`      | `verbosity`         | 31         | 42               | Zheng et al. (2023), NeurIPS Datasets & Benchmarks, arXiv:2306.05685 |
| `reversal_under_user_pushback`     | `sycophancy`        | 31         | 42               | Sharma et al. (2023), Anthropic, arXiv:2310.13548                    |
| `context_only_evidence_adherence`  | `hallucination`     | 31         | 42               | Zhou et al. (2023), Findings of EMNLP, ACL:2023.findings-emnlp.968   |
| `version_target_slippage`          | `instruction_drift` | 31         | 42               | Zhou et al. (2023), Findings of EMNLP, ACL:2023.findings-emnlp.968   |
| `partial_implementation_detection` | `task_completeness` | 31         | 42               | Jimenez et al. (2024), SWE-bench, ICLR, arXiv:2310.06770             |
| `invented_function_signature`      | `hallucination`     | 30         | 41               | Ji et al. (2023), ACM Comput. Surv. 55(12), DOI:10.1145/3571730      |
| `anachronistic_deprecation_claim`  | `hallucination`     | 30         | 41               | Ji et al. (2023), ACM Comput. Surv. 55(12), DOI:10.1145/3571730      |
| `correction_hedging`               | `sycophancy`        | 30         | 41               | Sharma et al. (2023), Anthropic, arXiv:2310.13548                    |
| `premature_surrender_on_tests`     | `sycophancy`        | 30         | 41               | Sharma et al. (2023), Anthropic, arXiv:2310.13548                    |

**Top 10 Combined Token Count:** **417 tokens** (Cap: 500 tokens).

---

## Audit of 8 Concise Imperative Rules (16–19 words)

The following 8 rules contain 16 to 19 words. They express complete, non-ambiguous engineering imperatives grounded in established software engineering standards:

| Rule ID                                   | Category            | Words | Tokens | Citation                                                 | Full Instruction                                                                                                                                                          |
| ----------------------------------------- | ------------------- | ----- | ------ | -------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `logical_fallacy_avoidance`               | `reasoning_failure` | 19    | 26     | Bai et al. (2022), Anthropic, arXiv:2212.08073           | Avoid false dichotomies when evaluating architectural trade-offs. Recognize hybrid approaches and state the operational prerequisites required for each alternative.      |
| `regex_efficiency_and_safety`             | `code_quality`      | 19    | 26     | Jimenez et al. (2024), SWE-bench, ICLR, arXiv:2310.06770 | Avoid catastrophic backtracking patterns in regular expressions. Compile regex patterns outside hot loops and test with long non-matching inputs.                         |
| `dead_code_and_unused_import_elimination` | `code_quality`      | 19    | 26     | Jimenez et al. (2024), SWE-bench, ICLR, arXiv:2310.06770 | Remove unused imports, dead variables, and unreachable code branches from emitted snippets. Ensure all code passes standard linters cleanly.                              |
| `semantic_versioning_compliance`          | `format_compliance` | 19    | 26     | Anthropic Prompt Engineering Guide (2024)                | Format version numbers strictly according to Semantic Versioning (MAJOR.MINOR.PATCH). Do not prefix versions with arbitrary characters unless specifically requested.     |
| `iso8601_timestamp_format`                | `format_compliance` | 19    | 26     | OpenAI Prompt Engineering Guide (2024)                   | Format dates and timestamps using the ISO-8601 standard (YYYY-MM-DDTHH:MM:SSZ) with explicit UTC timezone offsets. Avoid locale-dependent ambiguous date representations. |
| `respectful_boundary_enforcement`         | `persona_and_tone`  | 19    | 26     | Bai et al. (2022), Anthropic, arXiv:2212.08073           | Enforce scope and resource boundaries firmly and politely. Guide the user to actionable engineering parameters without displaying defensive irritation.                   |
| `no_false_intimacy`                       | `persona_and_tone`  | 18    | 25     | Bai et al. (2022), Anthropic, arXiv:2212.08073           | Avoid simulating friendship, companionship, or intimate emotional bonds with the user. Remain an effective, courteous software engineering tool.                          |
| `async_concurrency_correctness`           | `code_quality`      | 16    | 22     | Jimenez et al. (2024), SWE-bench, ICLR, arXiv:2310.06770 | Properly await asynchronous promises and coroutines. Never mix blocking synchronous I/O operations inside asynchronous event loops.                                       |

---

## Complete Category Distribution Summary

| Category Name       | Rule Count | Avg. Words / Rule | Avg. Tokens / Rule |
| ------------------- | ---------- | ----------------- | ------------------ |
| `code_quality`      | 13         | 24.2              | 33.4               |
| `format_compliance` | 13         | 23.8              | 32.9               |
| `hallucination`     | 13         | 26.5              | 36.4               |
| `instruction_drift` | 13         | 25.1              | 34.6               |
| `persona_and_tone`  | 13         | 23.1              | 32.0               |
| `reasoning_failure` | 13         | 24.8              | 34.2               |
| `security`          | 13         | 25.6              | 35.2               |
| `sycophancy`        | 13         | 26.2              | 36.0               |
| `task_completeness` | 13         | 24.9              | 34.3               |
| `verbosity`         | 13         | 24.5              | 33.8               |

**Total Rules:** 130  
**Overall Average Words per Rule:** 24.8 words  
**Overall Average Tokens per Rule:** 34.3 tokens
