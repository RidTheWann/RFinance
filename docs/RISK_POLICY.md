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

## Implemented methodology (`risk-controls-v1`)

Drawdown is computed from the append-only `portfolio_valuation_history` series
written by `PortfolioValuationService.value()` through
`RiskMonitoringService.evaluate_valuation()`:

```
drawdown = max(0, (peak_complete_total_value - current_complete_total_value)
                  / peak_complete_total_value)
```

- `portfolio-valuation-v1` supplies every total in the series; only complete
  valuations (no unvalued positions) can enter the peak or current value.
- A new portfolio high produces zero drawdown. A zero or missing peak, an
  incomplete valuation, or no valuation history produces **no drawdown value**
  and an explicit `VALUATION_INCOMPLETE` finding. Missing data is never coerced
  to zero as if it were a measured decline.
- Instrument weights come from valued position market values divided by the
  current complete total. Sector weights are `{}` until verified instrument
  sector evidence exists; category labels are never treated as sectors.
- Allocation deviations are the absolute differences reported by
  `portfolio-valuation-v1`. Concentration breaches suspend new buy candidates;
  a critical drawdown or a prohibited activity also suspends simulated
  allocation changes.

## Event and review semantics

- Each triggered rule becomes an append-only `risk_events` row. The event ID is
  a SHA-256 digest of rule, severity, UTC date, valuation methodology and
  evidence reference, so repeated evaluation on the same UTC date is
  idempotent. A worsening severity creates a distinct event.
- An event is active until an explicit `risk_reviews` row records a reviewer,
  notes and an evidence reference. Reviews are append-only and one per event.
  A review resolves that event for its UTC date; a continuing condition on a
  later UTC date raises a new event.
- Active events determine the suspension flags returned to screening and to
  the Risk Management page. No AI output, imported document or price
  observation can create or resolve an event automatically.
- `RiskMonitoringService.screening_controls()` projects those events, plus the
  drawdown derived from complete stored valuations, into
  `RiskControlEvidence`. `ScreeningEvaluationService` supplies it to the
  deterministic engine on every desktop evaluation. A buy-suspending rule
  raises `RISK_REVIEW_REQUIRED` and cites `risk:<event_id>`; a critical event
  produces `AVOID`. Recording an explicit review lifts the block on the next
  evaluation while the valuation-based drawdown remains available.
- Risk events are simulated portfolio controls, not brokerage records or
  evidence of realised loss.
