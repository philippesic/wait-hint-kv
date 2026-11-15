# Evidence for an upstream wait-hint discussion

## Goal
Collect the measurements needed to open a vLLM discussion thread on wait-hint holds:
a measured advantage under CPU cache pressure and no material harm where hints cannot
help, against current upstream. Upstream already discards unreachable sliding-window
and recurrent chunks; the claim is the hold, not dead-first eviction.

## Authorized
2026-11-15: Philip asked for a plan of what to measure and what must change in the
benchmark. Design only. Implementation, GPU use, WSL memory changes and any public
posting are not authorized.

## Done when
Philip agrees the plan; the tooling changes are implemented and CPU-qualified; the
separately authorized acquisition has run; the result is closed through the result
profile with the claim limits the thread must state.

## State
### Why the 2080 Ti screen could not answer
- D8's GPU KV cache held 17,920 tokens (~2.5 GiB) against a 0.82 GiB time-averaged
  working set, so GPU memory alone held about 3x the working set. The 1 GiB CPU pool
  (smallest integer candidate) was 1.3x. Only 576 of 191,296 hinted tokens came from CPU.
  HM's GPU cache (85,307 tokens) has even more headroom.
- A Poisson rate derived from mean session duration gave low overlap; W1 episodes are
  short (<= 6,144 tokens, 2-8 turns) with 4 s median gaps, so returns found GPU hits.
- 16 sessions and 3 seeds left bootstrap draws without some prompt strata (BCa
  undefined); hint-off controls moved latency by about 10%, more than the effect sought.
- Its D8 data remains a valid low-pressure observation with wide intervals.

### Proposed comparisons
Frozen main e9281bd9 (2026-11-13), offload_prompt_only=True, retention interval 0.
- Primary pair: A1 stock LRU (upstream default) vs A5 LRU plus hints. Secondary pair:
  A2 ARC vs A4t ARC plus hints, at cells P and R. A1 repeat (A/A noise) and A3
  (plugin, hints off) at P.
- A6 automatic hold at P: the same hold applied by the server after every request
  without client advice. It tests whether a client hint is needed. Not implemented.
- Request-TTL delivery only (pure plugin). Post-response route, LMCache and Gemma are
  deferred; delivery shape is a question for the thread.

### Proposed cells
Pressure is defined by measured ratios to the working set, never by names.
- R regular: concurrency at which GPU KV >= working set; captured gaps. Non-inferiority.
- P pressure: GPU KV <= 0.5x and CPU pool 0.5x working set; long-wait mix. Advantage
  plus harm to unhinted returns and one-shots.
- Pool curve: 0.25x and 1.0x at P concurrency (1.0x ~5 GiB fits the 15 GiB WSL limit).
- F fast tools under pressure: P sizing, captured gaps only; little advantage expected.
- W wrong advice: P sizing, hinted sessions abandon or return after the TTL.
- H high load: 1.5x P concurrency; session throughput and SLO goodput.
- Gaps: captured release-01 agent waits (1,176 waits: median 0.24 s, p90 0.5 s, p99
  30 s). The long-wait mix adds 20% authored 20-120 s tool waits, labelled as such.
  Hint TTL comes from the tool class (fast 12 s, long 150 s), never the true gap.
- Models: D8 Qwen3-8B-AWQ (dense) and HM Qwen3.5-4B-AWQ (Mamba hybrid) on the 2080 Ti.
  Gemma and longer contexts move to the 5080 only if this phase is positive. The pinned
  hybrid-lookup loss of CPU copies caps HM gains; report it as an upstream issue.

### Proposed claims and measurements
Frozen before decision seeds; every cell is published.
- C1 advantage at P (D8, LRU pair): hinted-return recompute change CI upper < 0 and
  hinted-return TTFT benefit CI lower > 0.
- C2 protection at P: unhinted and one-shot p95 TTFT and mean ITL harm CI upper <= margin.
- C3 non-inferiority at R: all-request TTFT, ITL and session throughput harm CI upper
  <= margin. Insufficient precision is reported as unresolved, not as equivalence.
- Other cells and HM are descriptive with intervals.
- Per cell: recompute by cohort split into GPU reuse, CPU reuse, CPU-evicted before
  return and never stored; TTFT p50/p95 and ITL by cohort; session completion; sessions
  per hour, output tokens/s and SLO goodput; prefill tokens saved; holds, yields,
  refusals, store failures; RSS, GPU and host CPU.
- Seeds: 6-8 paired at P and R, sized by the pilot's precision; 3 elsewhere; fresh
  W1 pilot/confirmation partitions checked against the exposure ledger.

### Required benchmark changes
1. Closed-population concurrency in `pr-plan-w1` and `pr-client-native` (C concurrent
   sessions, the next starts when one ends, like upstream multi_turn `--num-clients`).
2. Pool size in MiB as a ratio of the measured working set (`--pool-gib` is an integer).
3. Baseline-only exposure pilot per cell: P requires GPU KV / working set <= 0.5 and at
   least 10% of hinted-return reusable tokens CPU-evicted before return under A1;
   otherwise retune concurrency. Needs the token-source split in `pr-measure-cell`.
4. Simulator precheck of W1 schedules to choose concurrency/pool on CPU and refuse
   non-discriminating cells before GPU.
5. Gap profiles and per-class TTL in the planner.
6. Stratified session assignment so every seed holds every prompt stratum; a per-cell
   verdict (advantage / not worse / worse / unresolved) from `pr-compare-cells`
   intervals; throughput and goodput metrics.
7. A6 automatic-hold arm and an A1-repeat arm label.
8. Optional: one server per arm across seeds with verified cache reset.
9. A new campaign record with budget, drop order and acquisition healthcheck.

### Cost estimate
About 14 minutes per cell. D8 ~96 cells (~22 h), HM ~48 (~11 h), pilots and
calibration ~3 h, 20% contingency: about 45 GPU hours on the 2080 Ti. D8 only with
P, R and the curve: about 18 hours. Re-quote after the pilot.

### Open decisions
- Harm margin for C2/C3: fixed 5% recommended (pending since the PR plan).
- Scope: D8 plus HM, or D8 only.
- Whether A6 automatic hold is included.
- The authored 20% long-wait share and 20-120 s range.

## Next
Philip settles the open decisions. Then implement changes 1-7, qualify them on CPU
fixtures and a simulator precheck, and request GPU authorization with a costed manifest.
