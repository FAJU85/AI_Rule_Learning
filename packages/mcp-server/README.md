# ai-rule-learning-mcp

MCP server for AI Rule Learning. Gives Claude access to your personalised rules — it reads them at
the start of each session, applies them to responses, and helps you grow the rule set over time.

## Installation

```bash
npm install -g ai-rule-learning-mcp
```

Or run directly with npx:

```bash
npx ai-rule-learning-mcp
```

## Claude Desktop Configuration

Add the server to your Claude Desktop config file:

- **macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Windows**: `%APPDATA%\Claude\claude_desktop_config.json`

```json
{
  "mcpServers": {
    "ai-rule-learning": {
      "command": "npx",
      "args": ["ai-rule-learning-mcp"],
      "env": {}
    }
  }
}
```

If you installed globally with `npm install -g`, you can use the binary directly:

```json
{
  "mcpServers": {
    "ai-rule-learning": {
      "command": "ai-rule-learning-mcp"
    }
  }
}
```

## Tools

| Tool             | Description                                                         |
| ---------------- | ------------------------------------------------------------------- |
| `list_rules`     | List all personalisation rules (optionally including inactive ones) |
| `apply_rules`    | Check which rules are triggered by a given piece of text            |
| `add_rule`       | Add a new rule with a name, description, and trigger keywords       |
| `record_session` | Save a conversation session for gap analysis                        |
| `analyze_gaps`   | Find conversation patterns not covered by any existing rule         |

## Data Storage

Rules and sessions are stored as JSONL files in `~/.ai-rule-learning/`:

- `~/.ai-rule-learning/rules.jsonl` — your personalisation rules
- `~/.ai-rule-learning/sessions.jsonl` — recorded sessions for gap analysis

To use a custom data directory, set the `ARL_DATA_DIR` environment variable:

```json
{
  "mcpServers": {
    "ai-rule-learning": {
      "command": "ai-rule-learning-mcp",
      "env": {
        "ARL_DATA_DIR": "/path/to/your/data"
      }
    }
  }
}
```

## Usage Example

Once connected, Claude will automatically use `list_rules` and `apply_rules` to personalise its
responses. You can also ask Claude to:

- "Add a rule that reminds you to always use British English"
- "What gaps exist in my rule coverage?"
- "Record this session so you can learn from it"

## Development

```bash
git clone <repo>
cd packages/mcp-server
npm install
npm run dev    # run with tsx (no build step)
npm run build  # compile TypeScript to dist/
npm start      # run compiled output
```

## License

MIT
