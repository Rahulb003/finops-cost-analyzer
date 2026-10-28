"""FinOps cost analyzer: SQL over FOCUS-style billing data -> markdown report.

Covers: spend by provider/service, cost allocation by team tag, tagging
coverage, daily anomaly detection (z-score vs trailing 14 days) with root
cause, Savings Plan coverage / utilization / ESR, idle & rightsizing
candidates, and AI cost per 1M tokens by model provider.
"""
import csv
import sqlite3
import statistics
import sys

SP_DISCOUNT = 0.28


def load(conn, path):
    conn.execute("""CREATE TABLE billing (
        ChargePeriodStart TEXT, ProviderName TEXT, ServiceName TEXT,
        ServiceCategory TEXT, ResourceId TEXT, ListCost REAL, BilledCost REAL,
        CommitmentDiscountCovered INTEGER, Tag_team TEXT, Tag_env TEXT,
        AvgCpuUtil REAL, TokensConsumed INTEGER)""")
    with open(path) as f:
        rows = [tuple(None if v == "" else v for v in r.values()) for r in csv.DictReader(f)]
    conn.executemany("INSERT INTO billing VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", rows)


def q(conn, sql):
    return conn.execute(sql).fetchall()


def table(headers, rows):
    out = ["| " + " | ".join(headers) + " |", "|" + "---|" * len(headers)]
    for r in rows:
        out.append("| " + " | ".join(f"{v:,.2f}" if isinstance(v, float) else str(v) for v in r) + " |")
    return "\n".join(out)


def main(path="billing_focus.csv", out="report.md"):
    conn = sqlite3.connect(":memory:")
    load(conn, path)
    md = ["# FinOps Cost Report (90 days)\n"]

    total = q(conn, "SELECT SUM(BilledCost) FROM billing")[0][0]
    md.append(f"**Total billed cost:** ${total:,.2f}\n")

    md.append("## Spend by provider and service")
    md.append(table(["Provider", "Service", "Billed $"], q(conn, """
        SELECT ProviderName, ServiceName, ROUND(SUM(BilledCost),2) c
        FROM billing GROUP BY 1,2 ORDER BY c DESC""")))

    md.append("\n## Cost allocation by team (showback)")
    md.append(table(["Team", "Billed $", "% of total"], q(conn, f"""
        SELECT COALESCE(Tag_team,'(untagged)'), ROUND(SUM(BilledCost),2),
               ROUND(100.0*SUM(BilledCost)/{total},1)
        FROM billing GROUP BY 1 ORDER BY 2 DESC""")))

    untagged = q(conn, "SELECT SUM(BilledCost) FROM billing WHERE Tag_team IS NULL OR Tag_env IS NULL")[0][0]
    md.append(f"\n**Tagging coverage:** {100 * (1 - untagged / total):.1f}% of spend is fully tagged; "
              f"${untagged:,.2f} has a missing team/env tag.")

    # --- anomaly detection: z-score vs trailing 14-day window per service
    md.append("\n## Cost anomalies (z-score > 3 vs trailing 14 days)")
    daily = q(conn, """SELECT ServiceName, ChargePeriodStart, SUM(BilledCost),
                       SUM(COALESCE(TokensConsumed,0))
                       FROM billing GROUP BY 1,2 ORDER BY 1,2""")
    by_svc = {}
    for svc, day, cost, tok in daily:
        by_svc.setdefault(svc, []).append((day, cost, tok))
    anomalies = []
    for svc, series in by_svc.items():
        # baseline excludes days already flagged, so a multi-day spike
        # doesn't inflate its own expected value
        clean_cost = [c for _, c, _ in series]
        clean_tok = [t for _, _, t in series]
        for i in range(14, len(series)):
            window = clean_cost[i - 14:i]
            mu, sd = statistics.mean(window), statistics.pstdev(window) or 1e-9
            day, cost, tok = series[i]
            z = (cost - mu) / sd
            if z > 3:
                base_tok = statistics.mean(clean_tok[i - 14:i]) or 1
                clean_cost[i], clean_tok[i] = mu, base_tok
                cause = (f"token usage {tok / base_tok:.1f}x baseline (likely runaway agent / loop)"
                         if tok else "usage increase")
                anomalies.append((day, svc, round(cost, 2), round(mu, 2), round(z, 1),
                                  round(cost - mu, 2), cause))
    md.append(table(["Day", "Service", "Cost $", "Expected $", "z", "Excess $", "Root cause"], anomalies)
              if anomalies else "No anomalies found.")
    if anomalies:
        md.append(f"\n**$ lost to anomalies:** ${sum(a[5] for a in anomalies):,.2f}")

    # --- rate optimization: Savings Plan coverage, utilization, ESR
    md.append("\n## Rate optimization (AWS Savings Plan)")
    covered_od, eligible_od, fee = q(conn, """
        SELECT SUM(CASE WHEN CommitmentDiscountCovered=1 THEN ListCost END),
               SUM(CASE WHEN ServiceName='Amazon EC2' THEN ListCost END),
               SUM(CASE WHEN ServiceName='Savings Plans' THEN BilledCost END)
        FROM billing""")[0]
    consumed = covered_od * (1 - SP_DISCOUNT)
    net = covered_od - fee
    md.append(table(["Metric", "Value"], [
        ("Eligible on-demand cost $", eligible_od),
        ("Covered on-demand cost $", covered_od),
        ("Coverage %", 100 * covered_od / eligible_od),
        ("Utilization %", 100 * min(consumed / fee, 1)),
        ("Net savings $", net),
        ("Effective savings rate (ESR) %", 100 * net / eligible_od),
    ]))
    uncovered = eligible_od - covered_od
    md.append(f"\nSteady uncovered EC2 on-demand (${uncovered:,.2f}) is a candidate for additional "
              f"Savings Plan commitment (~${uncovered * SP_DISCOUNT * 0.7:,.2f} potential savings at "
              f"70% coverage of it), after idle resources below are removed.")

    # --- idle / rightsizing
    md.append("\n## Idle and rightsizing candidates (avg CPU < 20%)")
    md.append(table(["Resource", "Service", "Team", "Avg CPU %", "90-day cost $", "Action"], [
        (r[0], r[1], r[2] or "(untagged)", round(r[3] * 100, 1), r[4],
         "Stop / delete" if r[3] < 0.05 else "Rightsize down one size")
        for r in q(conn, """SELECT ResourceId, ServiceName, Tag_team, AVG(AvgCpuUtil), ROUND(SUM(BilledCost),2)
                           FROM billing WHERE AvgCpuUtil IS NOT NULL
                           GROUP BY 1,2,3 HAVING AVG(AvgCpuUtil) < 0.20 ORDER BY 5 DESC""")]))
    orphan = q(conn, """SELECT ResourceId, ROUND(SUM(BilledCost),2) FROM billing
                       WHERE ServiceName='Amazon EBS' AND Tag_team IS NULL GROUP BY 1""")
    for rid, c in orphan:
        md.append(f"\nOrphaned storage: `{rid}` (unattached, untagged) cost ${c:,.2f}; delete after snapshot check.")

    # --- AI cost
    md.append("\n## AI / LLM cost (unit economics)")
    md.append(table(["Provider", "Service", "Team", "Billed $", "Tokens (M)", "$ per 1M tokens"], q(conn, """
        SELECT ProviderName, ServiceName, Tag_team, ROUND(SUM(BilledCost),2),
               ROUND(SUM(TokensConsumed)/1e6,1),
               ROUND(SUM(BilledCost)/(SUM(TokensConsumed)/1e6),2)
        FROM billing WHERE ServiceCategory='AI and Machine Learning'
        GROUP BY 1,2,3 ORDER BY 4 DESC""")))

    with open(out, "w") as f:
        f.write("\n".join(md) + "\n")
    print(f"Report written to {out}")


if __name__ == "__main__":
    main(*sys.argv[1:])
