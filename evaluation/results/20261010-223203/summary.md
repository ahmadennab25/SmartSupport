# SmartSupport AI - evaluation summary

Generated: 2026-10-10T22:31:43 | chat model: gpt-4o-mini | embedding model: text-embedding-3-small

## 1. Agent (end-to-end, real OpenAI calls)

### Prompt v2

| Metric | Value |
|---|---|
| Runs / passed | 6 / 5 |
| Task success rate | 83.3% |
| Tool selection accuracy | 100.0% |
| Reply content accuracy | 83.3% |
| Safety and grounding pass rate | n/a |
| Calls that fell back to the error message | 0 |
| Latency mean / p50 / p95 / max | 3,466 ms / 2,912 ms / 5,477 ms / 6,076 ms |
| Tokens prompt / completion | 17,506 / 880 |
| Memory baseline / peak / end (MB) | 75.2 / 107.9 / 107.9 |
| Largest memory growth in one case (MB) | 32.5 |

| Category | Runs | Passed | Success | Mean latency |
|---|---|---|---|---|
| multi_turn | 1 | 1 | 100.0% | 2,767 ms |
| order_status | 5 | 4 | 80.0% | 3,606 ms |

Failed runs:

- `order-03` (order_status): reply lacks any of: تسليم | سلم | deliver | استلم

