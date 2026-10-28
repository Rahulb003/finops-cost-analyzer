# FinOps Cost Analyzer

SQL + Python analysis of multi-cloud (AWS, Azure, GCP) and AI/LLM billing data in the
[FinOps FOCUS](https://focus.finops.org/) format. It turns a raw billing export into a
FinOps report: where money goes, who owns it, what's wasted, and what spiked.

## What it finds
| Analysis | How |
|---|---|
| Spend by provider / service | SQL `GROUP BY` over `BilledCost` |
| Cost allocation (showback) by team | `Tag_team`, with untagged spend surfaced |
| Tagging coverage | % of spend with both `team` and `env` tags |
| Cost anomaly detection + root cause | z-score > 3 vs trailing 14-day baseline (flagged days excluded from baseline); token usage vs baseline to explain AI spikes |
| Savings Plan rate optimization | Coverage, Utilization, Net savings, Effective Savings Rate (ESR) |
| Idle / rightsizing candidates | Avg CPU < 5% → stop/delete; < 20% → rightsize; unattached untagged storage |
| AI unit economics | $ per 1M tokens by provider/model (Bedrock, Azure OpenAI, Vertex AI) |

Formulas used (same definitions FinOps platforms use):
- **Coverage** = covered on-demand cost ÷ eligible on-demand cost
- **Utilization** = commitment consumed ÷ commitment fee
- **Net savings** = covered on-demand cost − commitment fees
- **ESR** = net savings ÷ eligible on-demand cost

## Run it
```bash
python3 generate_data.py   # writes billing_focus.csv (90 days, synthetic)
python3 analyze.py         # writes report.md
```
No dependencies beyond the Python standard library (sqlite3). To use a real export,
map your AWS CUR 2.0 / Azure cost export / GCP BigQuery billing export columns to
the FOCUS names in `generate_data.py` and pass the CSV path: `python3 analyze.py my_export.csv`.

## Tests
```bash
python3 -m unittest -v
```
Checks that all three spike days are caught with no false alarms, idle resources are flagged
(and busy production boxes aren't), untagged spend is surfaced, and the rate metrics are present.
GitHub Actions runs the tests on every push (`.github/workflows/ci.yml`).

## Project layout
| File | Purpose |
|---|---|
| `generate_data.py` | Builds a 90-day synthetic FOCUS-style billing dataset with planted waste and a token spike |
| `analyze.py` | Loads the CSV into SQLite and runs the FinOps SQL analyses → `report.md` |
| `test_analyze.py` | Unit tests |
| `report.md` | Sample output |

## Sample results (synthetic 90-day dataset, $41.4K spend)
- Caught a 3-day Amazon Bedrock spike (token usage ~7x baseline, a runaway agent pattern): **$505 lost**
- Flagged **$15.3K** of 90-day spend on idle or oversized resources (idle EC2, staging box, oversized RDS, under-used GPU, orphaned EBS)
- Savings Plan: 56% coverage, 95% utilization, 13.5% ESR; ~$1.3K more savings available from extra commitment
- 5.2% of spend untagged → tagging policy fix
