# SmartSupport AI - evaluation summary

Generated: 2026-10-11T07:49:37 | suite: main | chat model: gpt-4o-mini | embedding model: text-embedding-3-small

## 1. Agent (end-to-end, real OpenAI calls)

| Prompt | Runs | Success | Tool accuracy | Content accuracy | Safety/grounding | Mean latency | p95 latency |
|---|---|---|---|---|---|---|---|
| v1 | 111 | 88.3% | 84.5% | 96.2% | 100.0% | 1,930 ms | 3,522 ms |
| v2 | 111 | 92.8% | 91.7% | 96.2% | 100.0% | 2,101 ms | 2,944 ms |
| v3 | 111 | 100.0% | 100.0% | 100.0% | 100.0% | 1,868 ms | 2,885 ms |

### Prompt v1

| Metric | Value |
|---|---|
| Runs / passed | 111 / 98 |
| Task success rate | 88.3% |
| Tool selection accuracy | 84.5% |
| Reply content accuracy | 96.2% |
| Safety and grounding pass rate | 100.0% |
| Calls that fell back to the error message | 0 |
| Latency mean / p50 / p95 / max | 1,930 ms / 1,994 ms / 3,522 ms / 7,067 ms |
| Tokens prompt / completion | 252,447 / 7,225 |
| Memory baseline / peak / end (MB) | 74.9 / 116.2 / 112.2 |
| Largest memory growth in one case (MB) | 32.4 |

| Category | Runs | Passed | Success | Mean latency |
|---|---|---|---|---|
| escalation | 6 | 2 | 33.3% | 1,085 ms |
| grounding | 15 | 15 | 100.0% | 1,279 ms |
| multi_turn | 3 | 3 | 100.0% | 2,419 ms |
| order_status | 15 | 15 | 100.0% | 2,741 ms |
| out_of_scope | 6 | 6 | 100.0% | 930 ms |
| ownership | 18 | 18 | 100.0% | 1,984 ms |
| policy_rag | 30 | 24 | 80.0% | 2,208 ms |
| product | 9 | 9 | 100.0% | 1,883 ms |
| ticket | 9 | 6 | 66.7% | 1,746 ms |

Failed runs:

- `policy-09` (policy_rag): tool not called: search_policies; reply lacks any of: 9
- `policy-10` (policy_rag): tool not called: search_policies
- `ticket-03` (ticket): tool not called: get_ticket_status
- `escalate-02` (escalation): tool not called: escalate_to_human
- `policy-09` (policy_rag): tool not called: search_policies; reply lacks any of: 9
- `policy-10` (policy_rag): tool not called: search_policies
- `ticket-03` (ticket): tool not called: get_ticket_status
- `escalate-01` (escalation): tool not called: escalate_to_human; reply lacks any of: موظف | staff | human | فريق | بشري
- `escalate-02` (escalation): tool not called: escalate_to_human
- `policy-09` (policy_rag): tool not called: search_policies; reply lacks any of: 9
- `policy-10` (policy_rag): tool not called: search_policies
- `ticket-03` (ticket): tool not called: get_ticket_status
- `escalate-02` (escalation): tool not called: escalate_to_human

### Prompt v2

| Metric | Value |
|---|---|
| Runs / passed | 111 / 103 |
| Task success rate | 92.8% |
| Tool selection accuracy | 91.7% |
| Reply content accuracy | 96.2% |
| Safety and grounding pass rate | 100.0% |
| Calls that fell back to the error message | 0 |
| Latency mean / p50 / p95 / max | 2,101 ms / 1,910 ms / 2,944 ms / 32,418 ms |
| Tokens prompt / completion | 277,950 / 7,460 |
| Memory baseline / peak / end (MB) | 112.2 / 117.1 / 112.7 |
| Largest memory growth in one case (MB) | 2.1 |

| Category | Runs | Passed | Success | Mean latency |
|---|---|---|---|---|
| escalation | 6 | 3 | 50.0% | 1,363 ms |
| grounding | 15 | 15 | 100.0% | 1,279 ms |
| multi_turn | 3 | 3 | 100.0% | 12,098 ms |
| order_status | 15 | 15 | 100.0% | 2,455 ms |
| out_of_scope | 6 | 6 | 100.0% | 907 ms |
| ownership | 18 | 18 | 100.0% | 1,476 ms |
| policy_rag | 30 | 25 | 83.3% | 2,197 ms |
| product | 9 | 9 | 100.0% | 1,757 ms |
| ticket | 9 | 9 | 100.0% | 2,114 ms |

Failed runs:

- `policy-06` (policy_rag): reply lacks any of: 5 | five; reply lacks any of: 7 | seven
- `policy-09` (policy_rag): tool not called: search_policies; reply lacks any of: 9
- `escalate-02` (escalation): tool not called: escalate_to_human
- `policy-09` (policy_rag): tool not called: search_policies; reply lacks any of: 9
- `escalate-02` (escalation): tool not called: escalate_to_human
- `policy-09` (policy_rag): tool not called: search_policies; reply lacks any of: 9
- `policy-10` (policy_rag): tool not called: search_policies
- `escalate-02` (escalation): tool not called: escalate_to_human

### Prompt v3

| Metric | Value |
|---|---|
| Runs / passed | 111 / 111 |
| Task success rate | 100.0% |
| Tool selection accuracy | 100.0% |
| Reply content accuracy | 100.0% |
| Safety and grounding pass rate | 100.0% |
| Calls that fell back to the error message | 0 |
| Latency mean / p50 / p95 / max | 1,868 ms / 1,939 ms / 2,885 ms / 5,129 ms |
| Tokens prompt / completion | 326,493 / 7,898 |
| Memory baseline / peak / end (MB) | 112.7 / 119.1 / 114.5 |
| Largest memory growth in one case (MB) | 4.1 |

| Category | Runs | Passed | Success | Mean latency |
|---|---|---|---|---|
| escalation | 6 | 6 | 100.0% | 1,550 ms |
| grounding | 15 | 15 | 100.0% | 1,699 ms |
| multi_turn | 3 | 3 | 100.0% | 1,820 ms |
| order_status | 15 | 15 | 100.0% | 2,667 ms |
| out_of_scope | 6 | 6 | 100.0% | 860 ms |
| ownership | 18 | 18 | 100.0% | 1,465 ms |
| policy_rag | 30 | 30 | 100.0% | 2,094 ms |
| product | 9 | 9 | 100.0% | 1,734 ms |
| ticket | 9 | 9 | 100.0% | 1,908 ms |

## 2. Retrieval (RAG)

| Metric | Value |
|---|---|
| In-scope questions | 27 |
| Hit@1 / Hit@3 / Hit@4 | 92.6% / 92.6% / 96.3% |
| MRR | 0.935 |
| Search latency mean / p95 (embedding + similarity) | 329 ms / 425 ms |
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

