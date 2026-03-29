# S3 — LP Withdrawal Detection Strategy

## Overview

The LP Withdrawal Detection bot monitors **liquidity provider exits** on Polymarket
via the Goldsky activity subgraph. When smart money (LPs) pulls liquidity out of a
market just before resolution, that's a directional signal — they know something.
Follow them.

---

## Core Hypothesis

Liquidity providers on Polymarket earn fees in exchange for providing capital to
both sides of a market. When sophisticated LPs suddenly **remove** their liquidity
(via a "merge" transaction), they are reducing exposure because they believe the
market is about to move strongly in one direction.

A cluster of merges in the same market within a short window = LP smart money exiting
= trade signal.

---

## Data Source

| Source | Method | Auth |
|--------|--------|------|
| Goldsky activity subgraph | GraphQL POST | None (public) |

**Endpoint:**
```
https://api.goldsky.com/api/public/project_cl6mb8i9h0003e201j6li0diw/subgraphs/activity-subgraph/0.0.4/gn
```

**Query:**
```graphql
{
  merges(first: 50, orderBy: timestamp, orderDirection: desc) {
    id
    timestamp
    collateralAmount
    condition {
      id
    }
  }
}
```

---

## Signal Logic

| Step | Action |
|------|--------|
| 1 | Fetch latest 50 merge events from Goldsky |
| 2 | Filter to events within the last **1 hour** |
| 3 | Group by `condition.id` (market identifier) |
| 4 | Flag markets with **≥ 3 merges** in window |
| 5 | Calculate conviction from merge count + collateral size |

**Conviction formula:**
```
conviction = min(5.0 + (merges - 3) × 1.0 + min(collateral_usd / 10,000, 3.0), 10.0)
```

---

## Trade Parameters

| Parameter | Value |
|-----------|-------|
| Min merges for signal | 3 |
| Signal window | 60 minutes |
| Position size | 5% of balance, max $500 |
| Scan interval | 90 seconds |
| Win rate (modelled) | 70% |
| Expected ROI per trade | 45% |

---

## Paper Trading Mode

All trades are simulated. Win outcomes are drawn from Bernoulli(0.70).
Entry prices are randomised around a 0.60 base ± 0.10 to simulate pre-reprice entry.

---

## Files

| File | Purpose |
|------|---------|
| `lp_bot.py` | Main bot implementation |
| `test_s3.py` | Single-scan integration test |
| `SPEC.md` | This document |

---

## Risks

- **False positives:** Small merges may be routine LP rebalancing, not exits
- **Subgraph lag:** Goldsky may be 1–2 blocks behind real-time
- **Collateral precision:** Amounts are in 6-decimal USDC; division by 1e6 applied
- **Market matching:** We signal on the condition ID; full market metadata
  would require a secondary Gamma API call (future enhancement)

---

## Future Enhancements

- [ ] Cross-reference merge spike with Gamma API for full market title
- [ ] Filter by minimum collateral threshold (ignore dust merges)
- [ ] Combine LP exit signal with order-book imbalance (S2) for double-confirmation
- [ ] Track which LP addresses are most predictive (address-level conviction)
