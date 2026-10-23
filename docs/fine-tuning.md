# Fine-tuning tier (Phase 4) — optional and opt-in

This is the roadmap's "lever 2": instead of injecting rules into a model's
context at runtime, bake the user's learned guardrails into the weights of a
local, open-weights model. It is **optional, opt-in, and external** — it is not
part of the default product and adds no machine-learning dependencies to the MCP
package.

## What lives in this repo vs. outside it

- **In the repo (this PR):** a dataset exporter. `ai-rule-learning export-dataset`
  (or the `dataset.export_sft_jsonl` function) turns the learned rules corpus into
  a standard SFT JSONL file. Pure data transformation — no `torch`, no
  `transformers`, no `unsloth`, no GPU, nothing runs in CI.
- **Outside the repo (you run it):** the actual training, on a GPU or a free
  Colab T4, using Unsloth against the exported JSONL.

Keeping the heavy stack out of the package is deliberate: the tool stays
lightweight and model-agnostic, and training is a separate, consenting step.

## Honest limits (read before relying on this)

- **This changes the product's character.** Fine-tuning only works on
  open-weights models; it cannot be applied to Claude, GPT, Copilot or Cursor —
  the tool's primary targets. It also loses instant updates and citeability. Use
  it as a per-user personalization tier, not a replacement for rule injection.
- **The dataset is instruction-style, not preference pairs.** The corpus stores
  each rule's directive and, where captured, the user's grounded correction
  (`evidence`). That is enough for an SFT dataset that teaches standing
  preferences. It is **not** a DPO/preference dataset: the corpus does not store
  full before/after transcripts (task → bad completion → good completion), so
  chosen-vs-rejected pairs are not fabricated here. Building a real preference
  dataset first requires before/after capture — a data-collection enhancement,
  not something to invent from thin data.
- **Validate first.** Per the roadmap, this tier is only worth training on once
  Phases 1–3 show the corpus carries real signal. Export and inspect the dataset
  before spending GPU time.

## Export

```bash
ai-rule-learning export-dataset --out arl_dataset.jsonl
```

Each line is a chat-format SFT example:

```json
{
  "messages": [
    {
      "role": "system",
      "content": "You are a coding assistant. Follow the user's established guardrail preferences in every response."
    },
    { "role": "user", "content": "<the grounded correction, or a question about the preference>" },
    { "role": "assistant", "content": "<the directive>" }
  ]
}
```

## Training recipe (external, Unsloth)

Run this in a GPU environment (e.g. Colab T4), not in this repo. Pin versions in
your own environment; this is illustrative, not a maintained dependency.

```python
# pip install unsloth
from unsloth import FastLanguageModel
from trl import SFTTrainer, SFTConfig
from datasets import load_dataset

model, tokenizer = FastLanguageModel.from_pretrained(
    model_name="unsloth/Qwen2.5-Coder-1.5B-Instruct",
    load_in_4bit=True,
)
model = FastLanguageModel.get_peft_model(model, r=16, lora_alpha=16)

ds = load_dataset("json", data_files="arl_dataset.jsonl", split="train")
ds = ds.map(lambda ex: {"text": tokenizer.apply_chat_template(ex["messages"], tokenize=False)})

SFTTrainer(
    model=model,
    tokenizer=tokenizer,
    train_dataset=ds,
    args=SFTConfig(dataset_text_field="text", max_steps=60, output_dir="arl-lora"),
).train()

model.save_pretrained("arl-lora")  # LoRA adapter
```

The result is a small LoRA adapter personalized to the user's guardrails. Measure
it against the behaviour harness (cold vs this adapter) before trusting it — the
same honest-evaluation discipline used for the rule-injection path.
