# Evidence for an upstream wait-hint discussion

## Goal
Collect the measurements needed to open a vLLM discussion thread on wait-hint holds:
a measured advantage under CPU cache pressure and no material harm where hints cannot
help, against current upstream. Upstream already discards unreachable sliding-window
and recurrent chunks; the claim is the hold, not dead-first eviction.

## Authorized
2026-11-15: Philip accepted revision 4 and authorized implementation and the RTX 2080 Ti
acquisition: estimate 10-12 GPU hours, hard ceiling 16 GPU hours. Spare budget goes to
more seeds on existing claims first. The plan is guidance, not fixed: change it when
needed for defensible evidence for an upstream discussion. Temporary vm.swappiness=0 is
authorized (backup artifacts/runs/discussion-host/swappiness-original.json); restore 60
at the end. No WSL memory change and no public posting.

## Done when
Philip agrees the plan; the tooling changes are implemented and CPU-qualified; the
separately authorized acquisition has run; the result is closed through the result
profile with the claim limits the thread must state.

## State
### Execution (2026-11-15)
- Tooling committed: pressure schedules, A6/A7 variant arms, discussion campaign caps
  (pilot 3 h, decision 13 h, total 16 h), `pr-discussion-run` driver and
  `pr-discussion-report`. GPU jobs run from the detached worktree
  `artifacts/checkouts/discussion-runner`; its campaign is
  `artifacts/checkouts/discussion-runner/artifacts/runs/discussion-2080ti`.
- Pilot facts: D8 GPU KV capped at 195 blocks (12,480 tokens; D8 uses 64-token blocks,
  a 780-block attempt oversubscribed and was interrupted and retained); HM at 48 blocks
  (11,342 tokens). Mean working set D8 2.45/1.53 GiB (seeds 21001/21002), HM 0.46/0.38
  GiB. At half-working-set pools, A1 recomputed 83% (D8) and 90% (HM) of hinted
  prefixes; a 6 GiB D8 pool recomputed 0%.
- Pilot finding: with the frozen release rule, A6/A7 matched A1 (D8 82%/81%, HM 90%).
  Event traces show every hold released within 0.3-2.6 s of the returning request's
  arrival, then evicted during 6-24 s of queueing before lookup. Fixed only in
  `policy_variants.py` (return-aware release, commit c87aeb77); frozen files unchanged.
- Pilot round 3 (seed 21002, single observations): with the fix, D8 at 2,048 MiB cut
  hinted recompute 71%->41% and unhinted 46%->34%; at 1,254 MiB hinted 83%->60% but
  unhinted 46%->57%; HM at 256 MiB showed no benefit (90%->94%). Calibration frozen in
  `benchmarks/pr-evidence/pressure/` (primary pool 1.0x working set; D8 secondary
  1,254 MiB), with the change from the planned 0.5x recorded there.
- Decision run started 2026-11-15 ~10:15 UTC: manifest
  `artifacts/runs/discussion-plan/manifest-decision.json` (83 jobs: D8/HM 1.0x pools
  A1/A6/A7 x 8 seeds, D8 1,254 MiB x 4 seeds, A1 repeats x 3, large pools x 2, 13 W1
  regular cells), detached driver PID in `decision-driver.pid`. Pilot used 1.9 GPU h;
  decision estimate ~11.8 h. Touch the campaign's `STOP` file to stop between jobs.
- Spare budget, declared after 20 decision cells and before any comparison was
  computed (cells ran ~5 min, so ~9 h total was projected): `manifest-extension.json`
  adds pressure seeds 22009-22016 (D8 2,048 MiB and HM 428 MiB, A1/A6/A7), then W1
  regular seeds 12109-12116 (A1/A7; W1 schedule seed range widened to 12101-12116,
  same frozen calibration and generator). It starts automatically after the decision
  driver exits and stops when the 13 h decision cap refuses a job; unpaired cells are
  excluded from paired comparisons.
- Two HM cells (22003 A1, 22004 A7) had one client `transport_error` each: a connection
  reset 1-3 ms after submission that the server never received (keep-alive race after
  long waits). Commit d4dc272f closes idle client connections after 2 s (server 5 s);
  the cells are set aside in the campaign's `metrics-invalid/` and rerun first in the
  extension. All other cells had no failed requests.

### Plan (revision 4, after debate with GPT-6.1 Sol)
- Claims: C1 hints cut hinted-return recompute and TTFT under pressure (LRU pair);
  C2 no harm to other cohorts under pressure; C3 not worse in the low-opportunity
  regular case; client hints versus automatic hold is descriptive.
- Harm criteria: per cohort (hinted return, unhinted return, one-shot), TTFT and ITL
  95% upper bound <= +5%, unhinted recompute <= +2 points. Each hinted arm is compared
  with its matching stock baseline (A5 vs A1, A4t vs A2, A6 vs A1). Any cohort failure
  fails the claim; an undefined interval is unresolved; aggregates cannot override.
- Regular case: extend the frozen D8 W1 screen with seeds 12104-12108 (already
  scheduled) for A1, A2, A3, A4t and A5, keeping A4t/A5 code hash-identical. Label the
  eight-seed analysis an extension of the screen, not fresh confirmation.
- Pressure case: the `pressure` benchmark on frozen main with stock connector arms.
  Decision arms A1, A1 repeat, A5 and A6, 12 seeds per model on HM and D8 (a budget
  choice, not demonstrated precision); gpu-only and oracle controls on 4 seeds as the
  discrimination gate (an inconclusive gate stays inconclusive). A2/A4t only if budget
  remains; without them the pressure conclusion is LRU-only. Gemma omitted. Arm order
  interleaved per seed. Per arm retain CPU-restored tokens, recompute, hold activity,
  expiry and yield, refused and failed stores, actual GPU/CPU capacities and
  working-set ratios; treatment failures stay in denominators.
- A6 automatic hold: same LRU policy, offload_prompt_only, 50% physical cap counting
  the ready-chunk union once, promotion, release on return and earliest-deadline yield
  as A5. A fixed 12 s hold starts at every request's engine finish and renews at each
  later finish, for every request including ones that never return, with no future
  knowledge. Hinted arms get class TTLs (12 s fast, 150 s long). The comparison tests
  selective retention plus class-specific duration against this rule only; a tie
  supports the simpler automatic alternative.
- Long waits: each turn independently joins the long class with probability 5%, wait
  uniform on 20-120 s, on top of the existing LogNormal(4 s, 0.8) gaps. The cell
  deadline covers every session's full scheduled sequence: arrival plus the sum of its
  scheduled waits plus a per-turn service allowance (frozen from the pilot's p95 turn
  time) plus drain. One-shot competitors and other sessions continue until that
  deadline. Report completion and censoring by arm and wait class.
- Statistics (frozen before acquisition): paired bootstrap over independent seeds
  preserving arm pairing; for hinted returns the extension estimand pools prompt-length
  strata (a disclosed population change) so a missing stratum cannot void the interval;
  the frozen post-stratified result is reported beside it. Seed count, weighting,
  interval method and stopping rule are fixed in advance. CPU fixtures test the
  implementation, not interval coverage.
- Precision forecast before any GPU request, from existing screen seeds and pressure
  A/A pairs, presented as uncertain. Expected: +5% latency non-inferiority may end
  unresolved (3-seed harm half-widths were 15-18%; Qwen pressure A/A hinted TTFT moved
  +13%, +110% and +4% per seed). Then the thread could say only "pressure benefit
  observed; latency non-inferiority unresolved", not "no material harm".
- Overhead diagnostic: a small capped run, separate from decision arms, timing live
  per-step plugin and hold bookkeeping against step time and counting eviction
  decisions that differ from the hints-off control. Supporting evidence only; it cannot
  bound end-to-end latency harm.
- Earlier campaign results (July vLLM, non-stock baseline, dead-first included) may be
  cited only as labelled history.

### Required changes
1. Port `pressure` to the frozen-main runtime and stock OffloadingConnector arms with
   request-TTL hints (largest piece).
2. A6 automatic-hold arm in the frozen-main plugin.
3. D8 pressure model definition and simulator precheck.
4. Long-wait class, class TTLs and full-schedule deadlines in the pressure workload.
5. Paired-seed intervals, the extension estimand and per-claim verdicts (advantage /
   not worse / worse / unresolved); the precision forecast.
6. The capped overhead diagnostic.

### Deferred
Closed-population W1 under pressure, pool curve, throughput, ARC pressure pair unless
budget remains, HM regular case, 5080, Gemma and longer contexts.

### Risks
- Pressure evidence is synthetic, with Qwen's GPU cache capped at 36 blocks and two
  running requests; label it beside the realistic regular case.
- Hold without dead-first tied recency on Qwen in the old promote-hold round; the
  hold-only gain on frozen main may be much smaller than the earlier campaign.
- Upstream's hybrid lookup discards complete CPU copies, capping HM gains.
- Cost: ~10-12 GPU hours is an estimate; requote from frozen-main pressure cell timings.

### Open decisions
- Philip accepts revision 4, including the likely unresolved latency outcome, or asks
  for more seeds after the precision forecast.

## Next
After Philip accepts: implement changes 1-6, run the precision forecast and CPU
qualification, then request GPU authorization with a costed manifest.
