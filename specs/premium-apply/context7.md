# Context7 MCP wiring for CP Compass (premium-apply batch)

## What it is

Context7 serves current library documentation to the coding agent, instead of
relying on training data. The MCP server exposes two tools:

- `resolve-library-id` — find a library's Context7 ID by name (+ a query to
  rank relevance).
- `query-docs` — fetch docs for one concept from that library, optionally
  pinned to the version the project uses.

## Config

Repo-root `.mcp.json` (stdio server, no key needed):

```json
{
  "mcpServers": {
    "context7": {
      "command": "npx",
      "args": ["-y", "@upstash/context7-mcp@4.0.3"],
      "env": {}
    }
  }
}
```

Any MCP client that reads `.mcp.json` (Claude Code, VS Code, Cursor, …)
picks this up for the project. No API key is stored in the repo — the
server works without one on the free tier. If rate limits bite, a free key
comes from https://context7.com/dashboard and goes in the client's own
secret storage, never in this file.

## How to use it for CP Compass deps

Per the `context7-mcp` skill: resolve the ID once, then one `query-docs`
call per concept, passing the pinned version.

| Dependency | Pinned version | Example query |
|---|---|---|
| React | 19.3.1 | "use() hook and Suspense" |
| Tailwind CSS | 4.3.5 | "@theme inline tokens" |
| motion (Motion) | 14.14.0 | "AnimatePresence exit animations" |
| Recharts | 3.2.0 | "ResponsiveContainer sizing" |
| FastAPI | (see backend/requirements.txt) | "dependency overrides in tests" |
| scikit-learn | (see backend/requirements.txt) | "CalibratedClassifierCV" |

## Verification (2026-11-27)

- `.mcp.json` is valid JSON (checked with `python -m json.tool`).
- The server package resolves: `npm view @upstash/context7-mcp@4.0.3
  version` returns 4.0.3 with a registry tarball (latest published is
  4.9.1; the pin stays at 4.0.3, the version the installed skill documents).
  No interactive setup was run; `npx -y` downloads the server on first use.
