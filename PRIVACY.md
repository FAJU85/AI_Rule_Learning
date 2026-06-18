# Privacy Policy

**AI Rule Learning** — effective 18 June 2026

## What data is collected

When you use this project, conversation turns from your AI sessions may be
exported to a Hugging Face dataset that you control. The following fields are
stored per conversation turn:

| Field                      | Purpose                                                         |
| -------------------------- | --------------------------------------------------------------- |
| `user_input`               | The message you sent to the AI                                  |
| `agent_response`           | The AI's reply                                                  |
| `turn_number`, `timestamp` | Ordering and timing metadata                                    |
| `gaps_detected`            | Automatically detected failure signals                          |
| `session_id`               | A random UUID — not tied to your identity                       |
| `project_context`          | The relative project folder name only (e.g. `AI_Rule_Learning`) |
| `git_branch`               | The active branch name at export time                           |

## What is automatically scrubbed

Before any data leaves your machine or reaches the dataset, the following
patterns are replaced with safe placeholders:

| Pattern                                           | Replaced with |
| ------------------------------------------------- | ------------- |
| Email addresses                                   | `[EMAIL]`     |
| Home directory paths (`/home/user/…`, `/Users/…`) | `[HOME]`      |
| IP addresses                                      | `[IP]`        |
| Phone numbers                                     | `[PHONE]`     |
| API tokens (`hf_`, `sk-`, `ghp_`, etc.)           | `[TOKEN]`     |

## Where data is stored

Data is written to your own Hugging Face dataset repository
(`<your-username>/AI_Rule_Learning`). You are the data controller.
The project maintainer does **not** have access to your private dataset.

For the community/federated dataset (`vooom/AI_Rule_Learning`), only
anonymised, PII-scrubbed conversation metadata is accepted.

## Data you can delete

You can delete any conversation from your dataset at any time via the
Hugging Face dataset viewer or by removing records from `conversations.jsonl`
and re-uploading.

## Third-party services

- **Hugging Face Hub** — dataset and Space hosting. Subject to
  [HF Privacy Policy](https://huggingface.co/privacy).
- **Qwen/Qwen2.5-72B-Instruct** via HF Inference API — used for rule
  generation. Only the gap-type label and anonymised example snippets are
  sent; full conversation text is not transmitted.

## Contact

For privacy concerns: <info@tococolors.com>
