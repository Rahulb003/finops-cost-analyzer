"""Generate a synthetic, FOCUS-style cloud + AI billing dataset (90 days).

Columns follow the FinOps FOCUS spec naming so the SQL works on real exports
after a light column mapping (AWS CUR 2.0 / Azure / GCP billing export).
Includes deliberate problems to find: untagged spend, idle resources,
a token-usage spike (runaway agent), and on-demand compute that a
Savings Plan could cover.
"""
import csv
import random
from datetime import date, timedelta

random.seed(42)
START = date(2026, 7, 1)
DAYS = 90

RESOURCES = [
    # id, provider, service, category, team, env, daily_cost, avg_cpu, commit_covered
    ("i-api-01", "AWS", "Amazon EC2", "Compute", "payments", "prod", 48.0, 0.55, True),
    ("i-api-02", "AWS", "Amazon EC2", "Compute", "payments", "prod", 48.0, 0.52, True),
    ("i-batch-01", "AWS", "Amazon EC2", "Compute", "data", "prod", 36.0, 0.61, False),
    ("i-old-test", "AWS", "Amazon EC2", "Compute", "", "", 22.0, 0.008, False),  # idle + untagged
    ("i-staging-01", "AWS", "Amazon EC2", "Compute", "payments", "staging", 18.0, 0.04, False),  # idle
    ("db-orders", "AWS", "Amazon RDS", "Databases", "payments", "prod", 64.0, 0.18, False),  # oversized
    ("vol-orphan-7", "AWS", "Amazon EBS", "Storage", "", "", 3.2, 0.0, False),  # unattached
    ("s3-logs", "AWS", "Amazon S3", "Storage", "platform", "prod", 12.0, None, False),
    ("nat-gw-1", "AWS", "Amazon VPC", "Networking", "platform", "prod", 9.5, None, False),
    ("bedrock-claude", "AWS", "Amazon Bedrock", "AI and Machine Learning", "support-bot", "prod", 30.0, None, False),
    ("vm-analytics", "Azure", "Virtual Machines", "Compute", "data", "prod", 40.0, 0.47, False),
    ("aoai-gpt", "Azure", "Azure OpenAI", "AI and Machine Learning", "search", "prod", 26.0, None, False),
    ("gke-cluster", "GCP", "Kubernetes Engine", "Compute", "ml", "prod", 55.0, 0.35, False),
    ("vertex-gemini", "GCP", "Vertex AI", "AI and Machine Learning", "ml", "dev", 15.0, None, False),
    ("gpu-a100-1", "GCP", "Compute Engine", "Compute", "ml", "dev", 70.0, 0.12, False),  # under-used GPU
]

SAVINGS_PLAN_DISCOUNT = 0.28  # covered EC2 billed at 72% of on-demand
SP_HOURLY_COMMIT_DAILY = 70.0  # commitment fee per day


def main(path="billing_focus.csv"):
    rows = []
    for d in range(DAYS):
        day = START + timedelta(days=d)
        weekday_factor = 0.85 if day.weekday() >= 5 else 1.0
        for rid, prov, svc, cat, team, env, base, cpu, covered in RESOURCES:
            cost = base * weekday_factor * random.uniform(0.92, 1.08)
            tokens = None
            if cat == "AI and Machine Learning":
                # blended $ per token differs by model/provider
                price = {"bedrock-claude": 9.0, "aoai-gpt": 6.5, "vertex-gemini": 3.5}[rid] / 1e6
                tokens = int(cost / price)
                # runaway agent: token spike on Bedrock for 3 days
                if rid == "bedrock-claude" and 61 <= d <= 63:
                    cost *= 6.5
                    tokens = int(tokens * 6.5)
            list_cost = cost
            # covered usage is paid by the Savings Plan fee line, so billed = 0
            billed = 0.0 if covered else cost
            rows.append({
                "ChargePeriodStart": day.isoformat(),
                "ProviderName": prov,
                "ServiceName": svc,
                "ServiceCategory": cat,
                "ResourceId": rid,
                "ListCost": round(list_cost, 4),
                "BilledCost": round(billed, 4),
                "CommitmentDiscountCovered": int(covered),
                "Tag_team": team,
                "Tag_env": env,
                "AvgCpuUtil": "" if cpu is None else round(max(0, cpu * random.uniform(0.8, 1.2)), 4),
                "TokensConsumed": "" if tokens is None else tokens,
            })
        # Savings Plan commitment fee line
        rows.append({
            "ChargePeriodStart": day.isoformat(), "ProviderName": "AWS",
            "ServiceName": "Savings Plans", "ServiceCategory": "Commitment",
            "ResourceId": "sp-compute-1yr", "ListCost": 0,
            "BilledCost": SP_HOURLY_COMMIT_DAILY, "CommitmentDiscountCovered": 0,
            "Tag_team": "platform", "Tag_env": "prod", "AvgCpuUtil": "", "TokensConsumed": "",
        })
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print(f"Wrote {len(rows)} billing rows to {path}")


if __name__ == "__main__":
    main()
