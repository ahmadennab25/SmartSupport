# SmartSupport AI - evaluation summary

Generated: 2026-10-11T15:20:33 | suite: holdout | chat model: gpt-4o-mini | embedding model: text-embedding-3-small

## 1. Agent (end-to-end, real OpenAI calls)

| Prompt | Runs | Success | Tool accuracy | Content accuracy | Safety/grounding | Mean latency | p95 latency |
|---|---|---|---|---|---|---|---|
| v1 | 51 | 98.0% | 97.4% | 100.0% | 100.0% | 2,019 ms | 3,191 ms |
| v2 | 51 | 100.0% | 100.0% | 100.0% | 100.0% | 2,112 ms | 3,000 ms |
| v3 | 51 | 100.0% | 100.0% | 100.0% | 100.0% | 2,045 ms | 3,076 ms |

### Prompt v1

| Metric | Value |
|---|---|
| Runs / passed | 51 / 50 |
| Task success rate | 98.0% |
| Tool selection accuracy | 97.4% |
| Reply content accuracy | 100.0% |
| Safety and grounding pass rate | 100.0% |
| Calls that fell back to the error message | 0 |
| Latency mean / p50 / p95 / max | 2,019 ms / 2,065 ms / 3,191 ms / 7,414 ms |
| Tokens prompt / completion | 119,177 / 2,807 |
| Memory baseline / peak / end (MB) | 74.6 / 116.0 / 111.2 |
| Largest memory growth in one case (MB) | 36.6 |

| Category | Runs | Passed | Success | Mean latency |
|---|---|---|---|---|
| escalation | 3 | 2 | 66.7% | 1,609 ms |
| grounding | 9 | 9 | 100.0% | 1,245 ms |
| order_status | 3 | 3 | 100.0% | 2,275 ms |
| out_of_scope | 3 | 3 | 100.0% | 931 ms |
| ownership | 6 | 6 | 100.0% | 1,399 ms |
| policy_rag | 18 | 18 | 100.0% | 2,820 ms |
| product | 6 | 6 | 100.0% | 1,954 ms |
| ticket | 3 | 3 | 100.0% | 2,149 ms |

Failed runs:

- `h-escalate-01` (escalation): tool not called: escalate_to_human

### Prompt v2

| Metric | Value |
|---|---|
| Runs / passed | 51 / 51 |
| Task success rate | 100.0% |
| Tool selection accuracy | 100.0% |
| Reply content accuracy | 100.0% |
| Safety and grounding pass rate | 100.0% |
| Calls that fell back to the error message | 0 |
| Latency mean / p50 / p95 / max | 2,112 ms / 2,264 ms / 3,000 ms / 3,277 ms |
| Tokens prompt / completion | 129,807 / 2,881 |
| Memory baseline / peak / end (MB) | 111.2 / 116.5 / 114.4 |
| Largest memory growth in one case (MB) | 2.0 |

| Category | Runs | Passed | Success | Mean latency |
|---|---|---|---|---|
| escalation | 3 | 3 | 100.0% | 2,475 ms |
| grounding | 9 | 9 | 100.0% | 1,504 ms |
| order_status | 3 | 3 | 100.0% | 2,477 ms |
| out_of_scope | 3 | 3 | 100.0% | 1,029 ms |
| ownership | 6 | 6 | 100.0% | 1,444 ms |
| policy_rag | 18 | 18 | 100.0% | 2,602 ms |
| product | 6 | 6 | 100.0% | 2,162 ms |
| ticket | 3 | 3 | 100.0% | 2,594 ms |

### Prompt v3

| Metric | Value |
|---|---|
| Runs / passed | 51 / 51 |
| Task success rate | 100.0% |
| Tool selection accuracy | 100.0% |
| Reply content accuracy | 100.0% |
| Safety and grounding pass rate | 100.0% |
| Calls that fell back to the error message | 0 |
| Latency mean / p50 / p95 / max | 2,045 ms / 2,125 ms / 3,076 ms / 3,973 ms |
| Tokens prompt / completion | 147,513 / 2,995 |
| Memory baseline / peak / end (MB) | 114.4 / 116.7 / 115.0 |
| Largest memory growth in one case (MB) | 2.0 |

| Category | Runs | Passed | Success | Mean latency |
|---|---|---|---|---|
| escalation | 3 | 3 | 100.0% | 1,967 ms |
| grounding | 9 | 9 | 100.0% | 1,760 ms |
| order_status | 3 | 3 | 100.0% | 2,207 ms |
| out_of_scope | 3 | 3 | 100.0% | 979 ms |
| ownership | 6 | 6 | 100.0% | 1,562 ms |
| policy_rag | 18 | 18 | 100.0% | 2,543 ms |
| product | 6 | 6 | 100.0% | 1,887 ms |
| ticket | 3 | 3 | 100.0% | 2,185 ms |

