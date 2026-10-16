# Business Memo: Reducing Late Deliveries and Protecting Customer Experience

**To:** Seller Experience leadership (fictional)  **From:** [Your name]  **Date:** [date]
**Data:** Olist Brazilian e-commerce dataset, [date range], [N] orders. Analysis in this repo.

> Replace every [bracket] with a real number from YOUR run on the real data.
> Delete this note. Never keep numbers from the synthetic sample.

## 1. Problem (2 to 3 sentences)
[X]% of delivered orders arrive after the promised date. Late orders score [A] on reviews versus [B] for on-time orders. We want to know where the problem is concentrated and what to do first.

## 2. Key findings
1. **Delivery vs satisfaction:** late orders average [A] stars versus [B] on time, a gap of [G] points (Welch t-test p = [p]). [Y]% of late orders get a 1-star review.
2. **Concentration by seller:** the worst 10% of sellers cause [S]% of late orders.
3. **Concentration by region:** [state 1], [state 2] and [state 3] have the highest late rates ([r1]%, [r2]%, [r3]%).
4. **Categories:** [category] has the highest late rate ([c]%) and an average review of [v].
5. **Customer text:** [T]% of 1-2 star comments mention delivery (keyword analysis of review text).
6. **Trend / timing:** [peak month or holiday effect, if any].

## 3. Recommendations (rank by impact and effort)
| # | Action | Evidence | Expected impact | Effort |
|---|---|---|---|---|
| 1 | Put Red-tier sellers on a corrective-action plan (weekly late-rate review, handling-time coaching) | Finding 2 | If they matched other sellers, about [N] fewer late orders ([P]% of all late orders) | Medium |
| 2 | Adjust delivery promises for the worst regions | Finding 3 | Fewer broken promises, fewer 1-star reviews | Low |
| 3 | Add an automated weekly seller scorecard and anomaly alert | Pipeline in this repo | Catch problems in days, not months | Low |
| 4 | [Your own idea from the data] | | | |

State clearly that impact numbers are **what-if estimates** from historical data, not forecasts.

## 4. Risks and limits
- Data is from [years]; behaviour may have changed.
- Seller late rate is not controlled for product weight, distance, or carrier.
- Correlation between lateness and reviews is strong but other factors (product quality) also affect reviews.
- Sellers with fewer than [min_orders] orders were excluded from ranking.

## 5. Next steps
1. Validate Red-tier list with the seller operations team.
2. Pilot the corrective-action plan with [N] sellers for [period] and measure the change.
3. Extend the dashboard with carrier and distance data.

## Appendix
- SQL: `sql/02_analysis_queries.sql` (Q5, Q6, Q14)
- Dashboard screenshots: `docs/screenshots/`
- Method notes: README
