# Risk Policy

Initial configurable policy defaults:

| Rule | Threshold |
|---|---:|
| Maximum individual-stock target weight | 10% |
| Maximum individual-sector target weight | 20% |
| Portfolio review cadence | 6 months |
| Allocation deviation review | 5 percentage points |
| Elevated drawdown review | 10% |
| Critical drawdown review | 15% |

At 10% peak-to-current drawdown: create an auditable elevated-risk event, require review, and suspend promotion of new BUY_CANDIDATE recommendations until review conditions are satisfied.

At 15%: create a critical event and suspend simulated allocation changes pending explicit review. Preserve all records.

These are review triggers, not loss limits or return guarantees. Drawdown methodology must use a consistent, documented portfolio valuation series.

Initial product scope excludes leverage, margin, short selling, and derivatives. The policy is not an individualized recommendation or a guarantee against loss.
