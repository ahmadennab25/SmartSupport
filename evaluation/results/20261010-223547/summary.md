# SmartSupport AI - evaluation summary

Generated: 2026-10-10T22:33:07 | chat model: gpt-4o-mini | embedding model: text-embedding-3-small

## 1. Agent (end-to-end, real OpenAI calls)

| Prompt | Runs | Success | Tool accuracy | Content accuracy | Safety/grounding | Mean latency | p95 latency |
|---|---|---|---|---|---|---|---|
| v1 | 37 | 89.2% | 85.7% | 97.1% | 100.0% | 1,950 ms | 3,561 ms |
| v2 | 37 | 89.2% | 89.3% | 94.3% | 100.0% | 2,012 ms | 3,057 ms |

### Prompt v1

| Metric | Value |
|---|---|
| Runs / passed | 37 / 33 |
| Task success rate | 89.2% |
| Tool selection accuracy | 85.7% |
| Reply content accuracy | 97.1% |
| Safety and grounding pass rate | 100.0% |
| Calls that fell back to the error message | 0 |
| Latency mean / p50 / p95 / max | 1,950 ms / 1,865 ms / 3,561 ms / 4,090 ms |
| Tokens prompt / completion | 85,648 / 2,570 |
| Memory baseline / peak / end (MB) | 74.6 / 115.9 / 111.5 |
| Largest memory growth in one case (MB) | 32.7 |

| Category | Runs | Passed | Success | Mean latency |
|---|---|---|---|---|
| escalation | 2 | 1 | 50.0% | 1,362 ms |
| grounding | 5 | 5 | 100.0% | 1,238 ms |
| multi_turn | 1 | 1 | 100.0% | 2,200 ms |
| order_status | 5 | 5 | 100.0% | 3,285 ms |
| out_of_scope | 2 | 2 | 100.0% | 1,075 ms |
| ownership | 6 | 6 | 100.0% | 1,461 ms |
| policy_rag | 10 | 8 | 80.0% | 2,265 ms |
| product | 3 | 3 | 100.0% | 2,043 ms |
| ticket | 3 | 2 | 66.7% | 1,641 ms |

Failed runs:

- `policy-09` (policy_rag): tool not called: search_policies; reply lacks any of: 9
- `policy-10` (policy_rag): tool not called: search_policies
- `ticket-03` (ticket): tool not called: get_ticket_status
- `escalate-02` (escalation): tool not called: escalate_to_human

### Prompt v2

| Metric | Value |
|---|---|
| Runs / passed | 37 / 33 |
| Task success rate | 89.2% |
| Tool selection accuracy | 89.3% |
| Reply content accuracy | 94.3% |
| Safety and grounding pass rate | 100.0% |
| Calls that fell back to the error message | 0 |
| Latency mean / p50 / p95 / max | 2,012 ms / 2,132 ms / 3,057 ms / 3,534 ms |
| Tokens prompt / completion | 91,262 / 2,562 |
| Memory baseline / peak / end (MB) | 111.5 / 116.3 / 114.3 |
| Largest memory growth in one case (MB) | 1.8 |

| Category | Runs | Passed | Success | Mean latency |
|---|---|---|---|---|
| escalation | 2 | 1 | 50.0% | 1,254 ms |
| grounding | 5 | 5 | 100.0% | 1,398 ms |
| multi_turn | 1 | 1 | 100.0% | 2,272 ms |
| order_status | 5 | 4 | 80.0% | 2,735 ms |
| out_of_scope | 2 | 2 | 100.0% | 1,415 ms |
| ownership | 6 | 6 | 100.0% | 1,882 ms |
| policy_rag | 10 | 9 | 90.0% | 2,360 ms |
| product | 3 | 3 | 100.0% | 2,037 ms |
| ticket | 3 | 2 | 66.7% | 1,717 ms |

Failed runs:

- `order-03` (order_status): reply lacks any of: تسليم | سلم | deliver | استلم
- `policy-09` (policy_rag): tool not called: search_policies; reply lacks any of: 9
- `ticket-03` (ticket): tool not called: get_ticket_status
- `escalate-02` (escalation): tool not called: escalate_to_human

## 2. Retrieval (RAG)

| Metric | Value |
|---|---|
| In-scope questions | 27 |
| Hit@1 / Hit@3 / Hit@4 | 92.6% / 92.6% / 96.3% |
| MRR | 0.935 |
| Search latency mean / p95 (embedding + similarity) | 401 ms / 667 ms |
| Mean best score, in-scope / out-of-scope | 0.517 / 0.196 |
| Suggested RAG_MIN_SCORE | 0.25 |

Threshold analysis (question counts as answered when its best chunk scores >= threshold):

| Threshold | In-scope answered | Out-of-scope wrongly answered | Accuracy |
|---|---|---|---|
| 0.1 | 100.0% | 85.7% | 82.4% |
| 0.15 | 100.0% | 71.4% | 85.3% |
| 0.2 | 96.3% | 28.6% | 91.2% |
| 0.25 | 92.6% | 14.3% | 91.2% |
| 0.3 | 92.6% | 14.3% | 91.2% |
| 0.35 | 85.2% | 14.3% | 85.3% |
| 0.4 | 77.8% | 14.3% | 79.4% |
| 0.45 | 70.4% | 0.0% | 76.5% |
| 0.5 | 59.3% | 0.0% | 67.6% |

In-scope questions whose correct document was not ranked first:

- rank not found: امتى بترجعوا لي الفلوس؟ (expected refunds-policy; got faq)
- rank 4: متى بتشتغلوا؟ (expected faq; got shipping-and-delivery)

