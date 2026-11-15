# Evidence for an upstream wait-hint discussion

## Goal
Collect the measurements needed to open a vLLM discussion thread on wait-hint holds:
a measured advantage under CPU cache pressure and no material harm where hints cannot
help, against current upstream. Upstream already discards unreachable sliding-window
and recurrent chunks; the claim is the hold, not dead-first eviction.

## Authorized
2026-11-15: Philip asked for a plan and accepted a fixed 5% harm margin, an automatic
hold comparison and a 5% long-wait share. He asked for a smaller GPU budget that reuses
earlier benchmarks. Design only so far. Implementation, GPU use, WSL memory changes and
any public posting are not authorized.

## Done when
Philip agrees the plan; the tooling changes are implemented and CPU-qualified; the
separately authorized acquisition has run; the result is closed through the result
profile with the claim limits the thread must state.

## State
### Why the 2080 Ti screen could not answer
- D8's GPU KV cache held 17,920 tokens (~2.5 GiB) against a 0.82 GiB time-averaged
  working set, so GPU memory alone held about 3x the working set. The 1 GiB CPU pool
  was 1.3x. Only 576 of 191,296 hinted tokens came from CPU.
- It is therefore a valid regular-case (no CPU pressure) observation, with three seeds.

### Reduced plan (proposed, ~10-12 GPU hours)
Reuse two existing instruments, each for the question it can answer.
- Regular case: finish the frozen D8 W1 screen. Seeds 12104-12108 are already
  scheduled under the frozen calibration; run them with A1 LRU, A2 ARC, A3 hints off,
  A4t ARC plus hints and A5 LRU plus hints, giving eight seeds with 12101-12103. No
  tooling changes. Claim C3: all-request TTFT, ITL and unhinted recompute harm CI
  upper <= 5%. The 3-seed data showed unhinted ITL +10% for both hinted arms and +7.7%
  for hints-off A3; more seeds decide whether that is plugin cost or noise. Plugin code
  for A4t/A5 must stay hash-identical to the screen, or those seeds rerun.
- Pressure case: the `pressure` benchmark, whose validity gates already require CPU
  evictions and restores, discriminating gpu-only/oracle controls and a simulator
  precheck. Run it on frozen main with stock arms: A1, A1 repeat, A5, A2, A4t, A6
  automatic hold, gpu-only and oracle. Models HM and D8; Gemma only if it admits on
  frozen main. Six to eight seeds. Claims C1 (hinted recompute and hinted-return TTFT
  improve, CIs exclude zero, LRU pair) and C2 (unhinted and one-shot TTFT and ITL harm
  CI upper <= 5%). The workload already includes 40% unhinted sessions, 34% abandoned
  hints and one-shot competitors.
- Long waits: 5% of tool waits drawn from 20-120 s with hint TTL by tool class (fast
  12 s, long 150 s), added to the existing LogNormal(4 s, 0.8) gaps. Captured agent
  waits had median 0.24 s and p99 30 s; the existing gaps already put ~2% above 20 s.
- Earlier campaign results (July vLLM, non-stock baseline, dead-first included) may be
  cited only as labelled history, not as current evidence.

### Required changes
1. Port `pressure` to the frozen-main runtime and stock OffloadingConnector arms with
   request-TTL hints (largest piece).
2. A6 automatic-hold arm in the frozen-main plugin.
3. D8 pressure model definition and simulator precheck.
4. Long-wait class and per-class TTL in the pressure workload.
5. Paired-seed bootstrap intervals and a per-claim verdict (advantage / not worse /
   worse / unresolved) for pressure results.

### Deferred from the full plan
Closed-population W1 under pressure, pool curve, high-load throughput, separate
wrong-advice cell, HM regular case, 5080 and Gemma at longer context. The thread
would report recompute and TTFT, not throughput.

### Risks
- Pressure evidence is synthetic, with Qwen's GPU cache capped at 36 blocks and two
  running requests; it must be labelled as such beside the realistic regular case.
- Hold without dead-first tied recency on Qwen in the old promote-hold round; the
  hold-only gain on frozen main may be much smaller than the earlier campaign.
- Upstream's hybrid lookup discards complete CPU copies, capping HM gains.

### Open decisions
- Accept the reduced plan and its ~10-12 GPU hour estimate.

## Next
After Philip accepts: implement changes 1-5, qualify on CPU fixtures and the simulator
precheck, then request GPU authorization with a costed manifest.
