# Phase 3 (deep history) — Trend-v2 through 2008 & 2010

**What:** re-evaluation of trend-v2 (chandelier 4×ATR) on **2005–2026** Yahoo
data (283 survivor names), finally including the **2008 GFC** and **2010 flash
crash** the sandbox lacked.
**Status:** complete. **Awaiting review.**
**Date:** 2026-07-01 · **Reproduce:** `python3 research/run_phase3_deep.py`
(`_phase3_deep_results.json`).

> **Still survivorship-biased.** Yahoo has no delisted names, so the 2008 tail
> here is a **lower bound** on true pain — the real GFC (with Lehman/Bear/WaMu
> going to zero) was worse for a naive long book. But because the strategy goes
> **defensive/flat** in the GFC (below), it largely sidesteps single-name
> blowups anyway, which limits how much the bias flatters this particular test.
> True survivorship-free validation still needs a paid source.

---

## 1. The headline: 2008 behavior validates the "survive stress" intent

| Stress window | Strategy | Strategy maxDD | Eq-wt market |
|---|---|---|---|
| **2008 GFC** (Sep08–Mar09) | **−0.3%** | **−0.4%** | **−30.6%** |
| 2010 flash crash | −11.1% | −13.8% | −11.4% |
| 2011 euro crisis | −3.9% | −5.5% | −4.8% |
| 2015–16 selloff | **−9.8%** | −11.3% | **−6.2%** |
| 2018-Q4 selloff | −11.0% | −11.6% | −12.1% |
| 2020 COVID crash | −11.4% | −12.1% | −14.4% |
| 2022 bear | −6.5% | −10.3% | −7.8% |

**In the 2008 GFC the strategy was essentially flat (−0.3%) while the market
fell −30.6%.** The regime governor (index < 200d MA + elevated vol) halted new
entries and the chandelier stops exited longs, moving the book to cash. This is
the single most important piece of new evidence: **the design does what it was
built to do in the worst modern crisis.**

Equally honest: in the **2015–16 choppy selloff it did WORSE than the market
(−9.8% vs −6.2%)** — the classic trend whipsaw in a non-trending decline. That
is expected trend-following behavior and actually *supports* the "map to
market" negative control (trend underperforms in chop) that was inconclusive on
the short sample. The 2010 flash crash it roughly matched the market (too fast
for stops).

---

## 2. Full-cycle metrics (2005–2026) — more sober than the sandbox

| Metric | Deep (2005–26) | Sandbox (2016–26) |
|---|---|---|
| CAGR | +3.9% | +2.8% |
| Sharpe | 0.40 | 0.31 |
| Max drawdown | −18.1% | −16.1% |
| **Longest underwater** | **~1,546 days (~6y)** | ~578 days |
| **Monthly skew** | **−0.03 (neutral)** | +0.28 |
| Trade-R skew (let winners run) | **strongly + (best +14R)** | strongly + |
| Expectancy / payoff | +0.11R / 1.81 | +0.07R / 1.78 |
| Win rate | 41% | 40% |
| Turnover | 11×/yr | 10×/yr |

Two honest corrections to the earlier (short-sample) story:

1. **Monthly-return skew is ~0 over the full cycle** (not +0.28). The positive
   monthly skew was partly a 2016–2026 artifact. The **trade-level** positive
   skew (many small losses, rare +14R winners; expectancy +0.11R) **is** robust
   across the full history — that is the durable "let winners run" signature.
2. **~6-year longest underwater stretch.** Modest returns + periodic trend
   drawdowns mean long periods below high-water mark. For an absolute-return
   product this is a serious investor-experience problem and the **main
   remaining weakness.**

---

## 3. Updated scorecard vs design intent

| Goal | Verdict (deep history) |
|---|---|
| Survive all regimes | **✅ strong** — flat in 2008 (−0.3% vs −31%), cushioned most crises |
| Positive skew | **Mixed** — trade-level ✅ robust; monthly-return ≈ neutral over full cycle |
| Small bounded losses | **✅** avg loss ~−0.7R, worst −3.6R |
| Trend behaves as trend | **✅** underperforms in 2015–16 chop (good negative-control sign) |
| Absolute return | **Weak** — +3.9% CAGR, ~6y underwater |
| Two neg-correlated sleeves | **✗** single sleeve (MR rejected) |

---

## 4. Part A status & remaining gaps

Part A (post-Phase-3 "A" path) is now largely done:
- ✅ **Deeper data**: 2005–2026 incl. 2008/2010 (survivor-only).
- ✅ **LEAN algo rewritten** to trend-v2 (`algorithm/main.py`, direct-position).
- ⏳ **True survivorship-free data** still needs a paid source (funded QC org /
  CRSP / Norgate) — unavailable here. The 2008 result is a lower bound.
- ⏳ **LEAN algo remains UNTESTED** (no engine / free QC account).

**Open weaknesses to weigh before any live decision:** (a) ~6-year underwater
duration, (b) neutral full-cycle monthly skew, (c) modest CAGR, (d) single
sleeve, (e) survivor bias not fully removed.

---

## 5. Gate

**STOP — awaiting review.** Net of everything: trend-v2 is a **genuinely
crash-resilient, trade-level-positive-skew, modest-return trend sleeve** whose
biggest flaws are long underwater periods and a return profile that honors the
risk philosophy more than the return ambition.

Options from here:
- **(B)** Proceed to Phase 4 paper-staging scaffolding (monitoring, kill-switch,
  go/no-go checklist) on trend-v2 — now better justified given the 2008 result.
- **(C)** Attack the ~6y-underwater / modest-return problem first (add a genuine
  diversifier sleeve — managed-futures trend / small-cap reversion — or modest
  leverage to the vol target) before staging.
- **Data:** if you can provide a funded QC org or CRSP/Norgate access, I'd run
  the true survivorship-free validation, which is the last big unknown.

My recommendation: **(B)** build the Phase 4 scaffolding (it's staging, not real
money) while flagging (C) and the survivorship-free re-run as explicit
pre-live gates.
