# FinOps Cost Report (90 days)

**Total billed cost:** $41,387.72

## Spend by provider and service
| Provider | Service | Billed $ |
|---|---|---|
| AWS | Amazon EC2 | 6,543.60 |
| AWS | Savings Plans | 6,300.00 |
| GCP | Compute Engine | 6,064.70 |
| AWS | Amazon RDS | 5,501.75 |
| GCP | Kubernetes Engine | 4,787.26 |
| Azure | Virtual Machines | 3,449.14 |
| AWS | Amazon Bedrock | 3,075.13 |
| Azure | Azure OpenAI | 2,240.33 |
| GCP | Vertex AI | 1,297.57 |
| AWS | Amazon S3 | 1,030.66 |
| AWS | Amazon VPC | 823.18 |
| AWS | Amazon EBS | 274.38 |

## Cost allocation by team (showback)
| Team | Billed $ | % of total |
|---|---|---|
| ml | 12,149.53 | 29.40 |
| platform | 8,153.84 | 19.70 |
| payments | 7,042.21 | 17.00 |
| data | 6,571.78 | 15.90 |
| support-bot | 3,075.13 | 7.40 |
| search | 2,240.33 | 5.40 |
| (untagged) | 2,154.88 | 5.20 |

**Tagging coverage:** 94.8% of spend is fully tagged; $2,154.88 has a missing team/env tag.

## Cost anomalies (z-score > 3 vs trailing 14 days)
| Day | Service | Cost $ | Expected $ | z | Excess $ | Root cause |
|---|---|---|---|---|---|---|
| 2026-08-31 | Amazon Bedrock | 189.37 | 28.80 | 57.70 | 160.57 | token usage 6.6x baseline (likely runaway agent / loop) |
| 2026-09-01 | Amazon Bedrock | 195.80 | 28.74 | 60.20 | 167.06 | token usage 6.8x baseline (likely runaway agent / loop) |
| 2026-09-02 | Amazon Bedrock | 205.79 | 28.55 | 66.50 | 177.25 | token usage 7.2x baseline (likely runaway agent / loop) |

**$ lost to anomalies:** $504.88

## Rate optimization (AWS Savings Plan)
| Metric | Value |
|---|---|
| Eligible on-demand cost $ | 14,849.40 |
| Covered on-demand cost $ | 8,305.80 |
| Coverage % | 55.93 |
| Utilization % | 94.92 |
| Net savings $ | 2,005.80 |
| Effective savings rate (ESR) % | 13.51 |

Steady uncovered EC2 on-demand ($6,543.60) is a candidate for additional Savings Plan commitment (~$1,282.55 potential savings at 70% coverage of it), after idle resources below are removed.

## Idle and rightsizing candidates (avg CPU < 20%)
| Resource | Service | Team | Avg CPU % | 90-day cost $ | Action |
|---|---|---|---|---|---|
| gpu-a100-1 | Compute Engine | ml | 11.90 | 6,064.70 | Rightsize down one size |
| db-orders | Amazon RDS | payments | 18.20 | 5,501.75 | Rightsize down one size |
| i-old-test | Amazon EC2 | (untagged) | 0.80 | 1,880.49 | Stop / delete |
| i-staging-01 | Amazon EC2 | payments | 4.00 | 1,540.47 | Stop / delete |
| vol-orphan-7 | Amazon EBS | (untagged) | 0.00 | 274.38 | Stop / delete |

Orphaned storage: `vol-orphan-7` (unattached, untagged) cost $274.38; delete after snapshot check.

## AI / LLM cost (unit economics)
| Provider | Service | Team | Billed $ | Tokens (M) | $ per 1M tokens |
|---|---|---|---|---|---|
| AWS | Amazon Bedrock | support-bot | 3,075.13 | 341.70 | 9.00 |
| Azure | Azure OpenAI | search | 2,240.33 | 344.70 | 6.50 |
| GCP | Vertex AI | ml | 1,297.57 | 370.70 | 3.50 |
