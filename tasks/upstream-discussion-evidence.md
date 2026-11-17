# Evidence for an upstream wait-hint discussion

## Goal
Produce defensible evidence for a vLLM discussion contribution on bounded CPU-offload
holds during agent tool waits. Primary target: opt-in deployments where clients send
hints (100% adoption, with one small non-hinting check session). Question: does client
knowledge (what is dead, what will change, who returns when) measurably beat a
strengthened server-only automatic hold? Upstream already discards unreachable
sliding-window and recurrent chunks, so that is not part of the claim.

## Authorized
- 2026-11-15, Philip: implementation and RTX 2080 Ti acquisition under a 16 GPU-hour
  hard ceiling; the plan is guidance, change it when needed for defensible evidence.
  Spent: pilot 1.92 h + decision 7.18 h (completed jobs). Campaign caps live in
  `tools/benchmarking/pr_jobs.py` (`discussion-2080ti`: pilot 3 h, decision 13 h).
- Later the same day Philip asked for a small screening test (about 90 minutes) of the
  revision-3 design before any further large run. A large run needs his decision after
  the screen.
- Temporary `vm.swappiness=0` is authorized for GPU runs (the committed host
  environment requires it). The native host default is 60; restore it with sudo when
  acquisition ends. If sudo is needed, ask Philip with the T3 `request_secret` tool,
  never in chat.
- No public posting, no upstream outreach.
- 2026-11-16, Philip: raise the cap and build and run revision 3 on the native host
  ("go for it"); be proactive: fix, rerun and change the benchmark when results show a
  problem; the goal is decision-ready results, the plan is only the current route.
  New campaign `discussion-native` caps: admission 0.5 h, calibration 2 h, decision
  7 h (with the 10.45 h already spent, about 20 h in total).
- 2026-11-16 08:55, Philip: fund a cache-size sweep (about 6-9 GPU-h) after the phase 1b
  gate failed. Decision cap raised by 7 h (campaign total 16.5 h, about 27 h overall).

## Done when
The revision-3 screen has run and been reported to Philip. Then either the large run
he approves is acquired and analysed, or he stops it. The evidence is closed through
`skills/close-results` with claim limits stated, FINDINGS includes a prior-art entry,
swappiness is restored and this file is deleted.

## State
- Terms are fixed in [docs/benchmarks.md](../docs/benchmarks.md#terms): LRU (A1), ARC (A2),
  automatic (A6s), candidate (A9, revision 3, not yet built) and wait-hint (old
  reachable-hold). A6, A7 and A9s are deprecated; `pr-gpu-job` refuses them.
### What exists (committed)
- Campaign tooling (see the "Upstream discussion campaign" section of
  `docs/benchmarks.md`):
  - `pr-plan-pressure` writes pressure schedules with profiles `mixed`, `adopt` and
    `adopt-long`.
  - `pr-gpu-job` takes `--pool-mib` and `--gpu-blocks`.
  - `pr-discussion-run` is the sequential driver: retry once, STOP file, metrics.
  - `pr-discussion-report` gives paired BCa comparisons per pool and profile group.
  - The client closes keep-alive connections after 2 s. Mixed-profile schedules are
    byte-identical to before.
- Policy variants live in `wait_hint_offload/vllm_adapter/policy_variants.py`;
  the frozen `policy.py` is untouched:
  - `ReturnAwareHold` keeps a live hold through queueing until the returning request
    loads, for up to 120 s, and clamps hint TTLs at 300 s.
  - `AutomaticHoldLRU` (A6) puts a 12 s hold on every finish.
  - `PostResponseLRU` (A7) applies post-response hints.
  - CPU fixture checks run with `pr-feasibility-native --variants`.
- The never-run A8 arm was replaced by the screen arms A6s and A9s.
- Calibration is in `benchmarks/pr-evidence/pressure/{D8,HM}.json`:
  - D8: GPU KV 195 blocks (12,480 tokens; 64-token blocks), pools 2,048 and 1,254 MiB,
    large pool 6,144 MiB;
  - HM: 48 blocks, pool 428 MiB, large pool 2,048 MiB.

### Runs and results so far (mixed profile: 5 of 8 sessions hint)
- Where things are: GPU jobs run from the detached worktree
  `artifacts/checkouts/discussion-runner` (checked out at the screen commit). Campaign:
  `.../discussion-runner/artifacts/runs/discussion-2080ti` (jobs/, metrics/,
  metrics-invalid/, driver.jsonl). Manifests are in `artifacts/runs/discussion-plan/`.
- The decision manifest (83 jobs) is complete. Only the rerun of the invalid HM 22004
  A7 cell was not run (stopped at 12:35 for the screen).
- `manifest-extension.json` and `chain.sh` are obsolete; do not run them.
- Interim (4-5 seeds, D8, 2,048 MiB), versus stock LRU:
  - hinted recompute: A7 -20 points, A6 -19;
  - hinted TTFT: A7 9% faster, A6 13% faster; one-shot TTFT 19-29% faster for both;
  - A7 versus A6: a tie on hinted reuse, A6 better on unhinted (it holds them too);
  - long-wait returns favour A7, but there are too few to bound.
  - D8 at 1,254 MiB: similar. One unhinted-ITL comparison exceeds the 5% margin
    (point estimate +5.5%).
  - D8 A1 repeats (A/A): 0-2%.
  - HM: A6 hinted recompute -18; A7 pending reruns.
- Regular case (W1, 8 seeds): pooled-strata estimates. One-shot TTFT is not worse;
  other harm comparisons are likely unresolved.
- Pilot lesson: the frozen release-on-arrival rule makes holds useless under
  queueing. Event traces show prefixes evicted between arrival and lookup.
- Attribution (Claude Fable 5.2, unreviewed quick tabulation of A7 cells):
  - 764 of 1,125 lost held chunks were evicted while the session's own request ran, and
    350 between arrival and first token; 9 during the wait.
  - Leases covering the full prefix lost nothing.
  - Timing advice can recover at most about 9 of A7's 26.6 recompute points.
- Prior art:
  - Dynamo `cache_control` with SGLang HiCache pinning: client TTL 300-3600 s, demotes
    to host memory, refresh-on-hit, priority hints.
  - Continuum: server-side GPU TTL per tool call.
  - InferCept: preserve, discard or swap.
  - Open vLLM RFCs #52113, #57103, #64150 and #51428.
  - The repo plan already listed HiCache (`docs/pr-evidence-plan.md:521`) but never
    reported the overlap.
  - Novelty must be claimed narrowly.

### Revision-3 design (agreed unanimously by Claude Fable 5.2, GPT-6 Astra, Claude Opus 5.5)
Implement these as new policy variants only.

Server mechanism, in every new hold arm:
- S1, lease continuity: when a session's next request arrives, keep its prefix protected
  through queueing and the request's own run until that request finishes and becomes
  the next observation.
- S1b, partial holds: if the 50% cap cannot fit a prefix, hold the longest leading part
  that fits.
- S2, precedence for yield, displacement and admission:
  - arrived (queued or running) sessions come before waiting ones;
  - among waiting holds, rank by estimated remaining wait and yield or displace the
    largest first;
  - unadvised holds use age (longest-waiting is largest);
  - advised holds use expected return minus now;
  - once a hold is overdue, rank it by age;
  - expected return is used for ordering only and never sets expiry.
- The rest is unchanged: still yield before any store would fail, and never start a
  transfer.

Arms:
- A1: stock LRU.
- A6s, strengthened automatic: a 30 s hold on every finish (preregistered from the
  captured-trace p99; not tuned on GPU), plus S1/S1b/S2 with age ordering. It gets no
  client knowledge.
- A9, causal hints: A6s plus four client signals, each from information the caller
  has at that time.
  - (a) `ephemeral` request flag on one-shot calls: no hold, and at finish demote its
    chunks to the evict-first end.
  - (b) `done` after a final turn, only when the client knows the session ended:
    release and demote.
  - (c) `keep_tokens` on compaction turns: hold only chunks wholly before the
    boundary and demote the rest.
  - (d) `expected_return_ms` for long tools, used for ordering. Expiry is the class
    upper bound, clamped at 300 s.
  - Demotion skips chunks shared with a live session. It writes the native LRU's
    private `_ranks` and heap (`vllm/v1/kv_offload/cpu/policies/lru.py` in the
    `pr-evidence` venv), which ties it to this vLLM revision.
  - The new fields need a closed-schema version bump in
    `wait_hint_offload/policy_protocol.py` and the client.
- A9o, oracle-information diagnostic: A9 given the exact next-use time, whether reuse
  happens and the reusable prefix extent, all from the schedule. It is not a
  performance ceiling.
- Reserve: A6s with native `store_threshold=2`.

Primary metric and rules:
- Metric: total recomputed tokens over all returns divided by total eligible tokens,
  in percentage points; paired BCa with seeds as the unit.
- Benefit is A6s minus the arm. The meaningful threshold is 3 points.
- Outcomes:
  - "helps" if the lower bound is above 0;
  - "real but below threshold" if the interval lies within (0, 3);
  - "no meaningful case" if the upper bound is below 3;
  - otherwise "unresolved".
- If A9o helps but A9 does not, the open problem is information availability.

### Screening test (done 2026-11-15, 12:47-13:37; reviewed with GPT-6 Astra, both AGREE)
- Arms: A1; A6s `StrengthenedHoldLRU` (30 s automatic hold, S1, S1b, S2 age ordering);
  A9s = same policy on the post-response runtime with `cancel` after one-shots and
  known-final turns plus long-class hints, no fast-class hints. A9o and full A9 were
  deferred (A9's protocol bump trips the Stage 1 freeze check).
- 9 of 9 cells complete, no interference flags, no failures. Manifest
  `artifacts/runs/discussion-plan/manifest-screen.json`; descriptive summary
  `artifacts/runs/discussion-plan/screen-summary.json`. One seed per workload.
- Hinted-return recompute, A1 / A6s / A9s:
  - adopt 23001, 2,048 MiB: 49.8 / 32.2 / 33.3%.
  - adopt-long 23003, 2,048 MiB: 22.2 / 22.2 / 22.3%. All of it is the 7 long returns
    (100% recomputed in every arm); short returns had no pressure.
  - adopt 23001, 1,254 MiB: 67.3 / 44.4 / 47.7%.
  - Long-class returns were 100% recomputed in every arm and workload.
- No harm seen against A1. The non-hinting session's recompute was never above A1's,
  and one-shot median TTFT was not worse (5 non-hinting returns per cell).
- Why long hints did nothing: each long hint extended its hold to 150-300 s, but newer
  automatic holds displaced it within 3-30 s. Age ordering puts the longest-waiting
  hold first in line, and the 50% cap is 113 chunks at 2,048 MiB (69 at 1,254 MiB)
  against prefixes of up to 78.
- Gap: A9s did not test the design. Per-hint hold time (ttl_ms, already in the
  protocol) was suppressed and expected-return ordering was deferred, so A9s equalled
  A6s on about 95% of waits. Philip had asked for the new design; the screen measures
  release messages over a strengthened automatic hold only.
- Typical 2,048 MiB A6s recompute by source: about 45% from short-wait holds displaced
  before return, 22-30% held at return (cap-trimmed), 14-22% never held, about 11% from
  long waits.
- Cap check: arrived leases truncated by the cap were 4 of 26 at 2,048 MiB but 12 of
  21 (A6s) and 13 of 25 (A9s) at 1,254 MiB, above the 25% rule. This is a decision for
  Philip.

### Large run (only if Philip approves after the screen)
- `adopt` first: 8 paired seeds x A6s, A9 and A9o (about 120 min).
- Then A6s+st2 on 4 `adopt` seeds (about 20 min).
- Then `adopt-long`: 3 descriptive seeds (about 135 min).
- If the cap binds, cut whole `adopt-long` seeds.
- Remaining budget before the screen: about 5.8 h under the decision cap, about 6.9 h
  under the 16 h ceiling.

### Operating notes
- Session interrupts kill processes started from the agent shell, even with
  setsid/nohup. Launch drivers with
  `systemd-run --user --unit=NAME --collect --working-directory=<runner>
  --setenv=PATH="$PATH" --setenv=HOME="$HOME" /bin/bash -c '<driver> > LOG 2>&1'`.
- Before launching, check out the committed commit in the runner worktree (detached,
  clean) and check that the GPU is idle.
- Since 2026-11-15 the host is native Ubuntu 26.04 (driver 595.99, 91 GB RAM, PCIe 3
  x16 at about 7.5 GB/s pinned). All earlier screen and decision runs were on WSL2;
  do not pool them with native runs. The GNOME desktop runs on the same GPU (about
  260 MiB); keep the desktop idle during cells.
- To stop between jobs, touch `<campaign>/STOP`.
- For long jobs, keep an hourly healthcheck (a background wait that exits on driver exit
  or after about 55 min) and stop it when acquisition ends.
- Interrupted or invalid attempts stay on record. Rerun under a new job name; set
  invalid metrics aside in `metrics-invalid/` with a README.
- The debate record is in `artifacts/runs/discussion-debate/` (brief, revisions 1-3,
  and `proposal-final.md`).

### Open decisions for Philip
- After the screen, whether to run the large run and which follow-up comes first.
- Framing of the thread: hints as information on top of automatic hold, or a
  server-side return-aware hold with optional release and compaction hints.
- The cap, if the exit check reaches 25%.

## Next
Revision 3 is built and committed (see docs/benchmarks.md, "Native agent-mix campaign").
Runner: `artifacts/checkouts/discussion-runner`, campaign
`artifacts/runs/discussion-native` there, job helper `run-job.sh NAME ARM PHASE MIB SECONDS
SCHEDULE`. `vm.swappiness` is 0 since 2026-11-16 00:05 (original 60 recorded in the
campaign directory); restore it when acquisition ends.

Done on the GPU (2026-11-16):
- Admission `q7-admission-a2`: byte-identical restore, same boundary, token identity;
  GPU KV 55,296 tokens; CPU chunk 64 tokens (3.67 MB).
- Smoke, 8 sessions, 2 GiB, seed 31001, one seed (not evidence): every advice mechanism
  fired (planned 57, arrived held 73, displaced 125, partial 167, readmitted 118, keep 5,
  done 6, ephemeral 13, demoted evictions 1,273, shared prefix kept 608). Oracle 4.3%
  versus LRU 12.3% opt-in recompute, but the LRU cell ran with CUDA graphs (46k GPU KV
  tokens) and is not paired. CUDA graphs gave no speedup and were reverted.
- The engine is slow on this card (about 130 ms per decode step with 6 running, prefill
  about 2.8 s median); at 8 sessions the queue share of TTFT was 24-35%. Stage A sets
  the session count by the 20% rule on a roomy LRU run.

Plan (Philip's order): Stage A (session count, GPU-only and LRU pool sizes, retention
horizon) -> phase 1 oracle gate on LRU (typical x3, roomy, uncapped, automatic 300 s and
store_threshold=2) -> phase 2 ARC and tight -> phase 3 candidate on passing bases.

### Stage A result (2026-11-16, seeds 31003-31004, LRU)
| Sessions | Pool | Opt-in recompute | Queue share of TTFT | Note |
|---|---|---|---|---|
| 9 | 24 GiB | 0% | 9.6% | eviction-free (roomy) |
| 9 | 8 GiB | 0% | 8.9% | 11 evictions |
| 9 | 4 GiB | 4.7% | 6.9% | horizon about 120 s |
| 9 | 2 GiB | 11.1% | 11.5% | horizon about 60 s; equals GPU-only |
| 9 | 256 MiB | 11.1% | 9.6% | GPU-only proxy |
| 12 | 24 GiB | 0% | 27.4% | overloaded |
| 12 | 2 GiB | 14.7% | 55.8% | overloaded |
At 9 sessions all LRU recompute comes from the 7 long-wait returns per cell; instant and
tool waits are served by the GPU prefix cache. Frozen choices: 9 sessions, window 480 s,
one-shot mean 20 s, 6 running; typical 2 GiB, roomy 24 GiB, tight 1 GiB. A 12-session
4 GiB job was refused by the calibration cap (no GPU time spent).

### Preflight: phase 1 (oracle gate on LRU, about 2.7 GPU-h)
- Question: does exact client information beat the best server-only policy on LRU, so
  that the candidate is worth running on LRU?
- Decision-changing result: `oracle-lru` opt-in recompute at least 3 points below the
  best of `lru`, `auto-lru`, `auto300-lru`, `auto-st2-lru` in each of 3 seeds (typical,
  2 GiB). Otherwise no candidate run on LRU; if only `oracle-uncapped-lru` passes, the
  cap is the finding and Philip decides.
- Preconditions and checks: pressure (Stage A LRU 11.1% at typical, so the ceiling on the
  gain is about 11 points, above the 3-point bar); room to hold (cap 1 GiB, about 18k
  tokens, one or two idle long-wait prefixes); mechanisms fire (smoke counters); no
  overload (11.5% queue share at typical). Unverified: per-seed noise with about 7 long
  returns per cell.
- Order and early milestone: seed 32001 `lru`, `auto-lru`, `oracle-lru` first. If
  `oracle-lru` is not at least 1 point below `lru` there, stop and investigate before the
  remaining 14 jobs.
- Expectations: each job about 9-10 min, `client_complete`, no session or store
  failures, every advice accepted, queue share under 25%, no material interference.
  Kill: any failed job, store failures, advice delivery errors over 1%, swap growth.

### Phase 1 result (15% long mix, typical 2 GiB, LRU): gate failed
Opt-in recompute per seed: 32001 LRU 8.5%, auto 8.2%, auto300 8.5%, auto-st2 7.0%,
oracle 4.2% (4.3 points versus the gate comparators, 2.8 versus st2, which is descriptive
only); 32002 LRU 2.7%, oracle 2.7%; 32003 LRU 3.1%, oracle 1.6%. Two causes, both
verified in the receipts:
- Ceiling: instant and tool waits never recompute (the GPU prefix cache keeps them; GPU
  retention is about 60 s at 9 sessions), so LRU recompute comes only from the 5-9 long
  returns per cell and was 2.7-3.1% on two seeds, below the 3-point bar.
- Ranking flaw: "largest remaining wait loses first" spends the 50% hold budget on
  short waits the GPU already covers and pushes out the long waits. In seed 32002 a
  227 s wait's hold fell from 110 chunks to the 32-chunk system prefix while the hold
  budget stayed full (292 of 292 chunks). The candidate inherits this (tool median 4 s
  outranks long 135 s).

### Phase 1b (pre-registered 2026-11-16 before any phase 1b data)
Changes, all declared in reports:
- GPU-aware advised holds (`oracle-gpu-*`, `cand-gpu-*`): a hint whose expected wait is
  under the measured GPU retention (60 s, Stage A) gets no CPU hold; unhinted sessions
  get no automatic hold in these arms; arrivals are still protected; ranking among the
  remaining holds is unchanged. Original arms stay on record.
- Fairer server-only comparator `auto300old-*`: 300 s automatic hold that keeps the
  oldest holds (new finishes cannot displace older ones; yield takes the youngest).
- Long-heavy wait mix (`--wait-mix long`: instant 35%, tool 25%, long 40%), authored
  as the workload where holds should matter; the 15% mix and roomy cells remain the
  "should not matter" checks.
- Matrix (typical 2 GiB, 9 sessions, seeds 33001-33003): `lru`, `auto-lru`,
  `auto300old-lru`, `oracle-gpu-lru` (12 runs, about 2.8 GPU-h).
- Gate unchanged in form: `oracle-gpu-lru` opt-in recompute at least 3 points below the
  best of `lru`, `auto-lru`, `auto300old-lru` in each seed. Pass: `cand-gpu-lru` on the
  same 3 seeds (about 0.7 GPU-h). The ARC phase needs a cap raise from Philip.
- Ceiling check after seed 33001's `lru`: if its opt-in recompute is under 6%, stop and
  replan before the other runs.
- Amended before any valid phase 1b cell (2026-11-16 06:05): the first attempt hit the
  1,000 s job ceiling (long-mix cells take 17-20 min; `l-p2048-lru-s33001-a1` timed out,
  `l-p2048-auto-lru-s33001-a1` was stopped during model load, terminal reconstructed,
  58 s charged). Ceiling raised to 1,500 s. `auto-lru` dropped from phase 1b: in phase 1
  it matched LRU within 0.3 points on every seed and its 30 s holds expire before any
  long return. Unused admission and calibration caps moved to the decision phase (total
  campaign cap unchanged at 9.5 h). Matrix: `lru`, `auto300old-lru`, `oracle-gpu-lru`
  x 3 seeds; gate comparators `lru` and `auto300old-lru`.

### Phase 1b first seed and the exploratory 4 GiB point (decided 07:45, before 4 GiB data)
Seed 33001 (long mix, 2 GiB): LRU 10.9%, `auto300old-lru` 10.7%, `oracle-gpu-lru` 10.8%
opt-in recompute; long-return recompute 23% in all three. Most long returns are served by
the GPU prefix cache at this light load (queue share 1%). The recomputed ones are the
same in every arm: the oracle did hold them at finish (session 0005: 187 chunks, about
12k tokens) but other long-wait holds with nearer returns displaced them down to the
32-chunk system prefix. The 2 GiB pool's hold budget (292 chunks, about 18.7k tokens)
fits about one long-wait prefix while 3-4 sessions wait at once, so selection cannot
change much. Seeds 33002-33003 at 2 GiB finish as pre-registered. Exploratory, not part of
the gate: the same trio at 4 GiB on seed 33001, to see whether information helps when the
pool can hold 2-3 waiting prefixes.

### Phase 1b result (long mix, 2 GiB, LRU, 3 seeds): gate failed
| Seed | LRU | auto300old | oracle-gpu | Gate points | All returns LRU / best server / oracle |
|---|---|---|---|---|---|
| 33001 | 10.9% | 10.7% | 10.8% | -0.1 | 11.3 / 10.9 / 10.0 |
| 33002 | 12.2% | 9.2% | 3.9% | 5.3 | 14.4 / 11.2 / 5.5 |
| 33003 | 16.1% | 15.8% | 13.7% | 2.1 | 15.6 / 15.4 / 11.4 |
Opt-in recompute; "all returns" adds the non-hinting sessions, which gain from the
oracle's `done` and `ephemeral` releases (seed 33003: 13.1% to 0%). No failures, queue
share at most 8%, no interference flags, every advice accepted. Exploratory 4 GiB seed
33001: LRU recomputes nothing, so the other two 4 GiB cells were stopped (22 s charged).
Phase 1 (15% mix) and phase 1b agree: the benefit of client information over the best
server-only policy is 0-5 points per seed (mean about 2 opt-in, about 3 for all returns),
not consistently 3 or more. Short waits are covered by the GPU prefix cache; long waits
compete for a hold budget that fits about one waiting prefix at 2 GiB; at 4 GiB and above
LRU already keeps everything. The candidate was not run (gate rule). Roomy cells show no
harm (equal TTFT). `vm.swappiness` and `vm.compaction_proactiveness` were restored to 60
and 20 at 08:45. Budget: calibration 1.85 h, decision about 6.2 h of 7.56 h.

### Preflight: cache-size sweep (pre-registered 2026-11-16 08:55, before sweep data)
- Question: is there a CPU pool size where client information clearly beats the best
  server-only policy on LRU, so the candidate is worth testing there?
- Workload and arms: long mix, 9 sessions, window 480 s, one-shot mean 20 s, 6 running;
  `lru`, `auto300old-lru`, `oracle-gpu-lru`.
- Matrix: 3 GiB x seeds 33001-33005 (15 runs); 2 GiB x seeds 33004-33005 (6 runs; with
  33001-33003 already run, 5 seeds). About 21 x 17.5 min = 6.1 GPU-h.
- Decision rule per size (5 paired seeds; replaces the all-seeds rule for this sweep
  because per-seed differences range from -0.1 to 5.3 points): `oracle-gpu-lru`
  opt-in recompute below the best of `lru` and `auto300old-lru` by a mean of at least 3
  points, and lower in at least 4 of 5 seeds. All-returns recompute is reported next to
  it. Pass at a size: `cand-gpu-lru` on the same 5 seeds at that size (about 1.5 GPU-h).
- Preconditions and checks: opportunity at 3 GiB is unverified (2 GiB LRU 10.9-16.1%,
  4 GiB 0%). Early milestone: if `lru` at 3 GiB seed 33001 recomputes under 3% opt-in,
  replace 3 GiB with 2.5 GiB before the other runs.
- Expectations and kill: each cell about 15-20 min, `client_complete`, no failures, all
  advice accepted, queue share under 20%; kill on any failed or timed-out job.

### Cache-size sweep result (2026-11-16, long mix, LRU, 5 seeds, rule passed at 3 GiB)
Opt-in recompute; lead = best of `lru` and `auto300old-lru` minus the arm.
| Seed | LRU 3G | auto300old 3G | oracle-gpu 3G | cand-gpu 3G | oracle lead 2G |
|---|---|---|---|---|---|
| 33001 | 12.2% | 5.4% | 0.0% | 0.0% | -0.1 |
| 33002 | 12.1% | 7.3% | 0.0% | 0.0% | 5.3 |
| 33003 | 14.4% | 14.3% | 2.7% | 2.8% | 2.2 |
| 33004 | 6.3% | 3.5% | 0.0% | 0.0% | 4.1 |
| 33005 | 11.7% | 8.5% | 2.5% | 4.5% | 4.0 |
- 3 GiB: oracle lead mean 6.8 points, better in 5 of 5; candidate lead mean 6.3, better
  in 5 of 5 (keeps about 93% of the oracle's gain using only tool-type medians).
  Long-wait recompute falls from 14-31% (LRU) to 0-10% (candidate). Non-hinting sessions
  also improve (0-4.6% versus 8.5-26.1% under LRU) through `done` and `ephemeral`
  releases.
- 2 GiB with 5 seeds: oracle lead mean 3.1, better in 4 of 5 (passes the sweep rule
  narrowly; the earlier 3-seed all-seeds rule failed). 4 GiB: LRU recomputes nothing.
- Candidate counters per seed: 70-79 advice, all accepted; `gpu_covered` 88-100, done
  4-5, ephemeral 17-27, keep 2-8, demoted evictions 926-1,592, shared prefix kept
  704-1,024 chunks. No failures; queue share at most 8% except LRU and auto300old at
  seed 33005 (23% and 19%, LRU's own recompute load); no interference flags.
- Caveats: authored long-heavy mix (40% waits of 30-240 s), one model and GPU, 9
  sessions, LRU only; the benefit appears in a pool-size window (about 2-3 GiB here)
  where the hold budget fits some but not all waiting sessions. ARC and tight were not
  run. `vm.swappiness` and `vm.compaction_proactiveness` restored to 60 and 20 at 17:12.
- GPU time: calibration 1.85 h, decision 13.45 h, admission 0.02 h (15.32 h in this
  campaign, about 25.8 h overall with the WSL campaigns).

### Result and RFC (2026-11-16)
- Result record: `results/agent-wait-advice/` (evidence at fcf62b31: 60 cells, gates,
  excluded attempts, budget).
- RFC drafted for Philip: CPU-offload policy layer with measurements, asking which
  interface (#52113, #51428, #57103) should carry the advice; companion comments on
  #52113 and #57103. CC from CODEOWNERS: @ApostaC, @orozery (`vllm/v1/kv_offload`),
  @njhill (`vllm/v1/engine`). GPT-6 Astra reviews claims, links and omissions before
  Philip posts. Posting is Philip's decision.

### ARC spot check (decided 2026-11-16 19:20, before data; Philip: one seed)
Descriptive only, no gate: `arc`, `auto300old-arc`, `cand-gpu-arc` at 3 GiB on seed 33001
(long mix), paired with the known LRU cells (12.2%, 5.4%, 0.0% opt-in recompute). Seed
33001 is the first seed, chosen by the earlier convention, not by its result. Question: is
ARC materially better than LRU here, for the base policy or with advice? About 0.9 GPU-h
within the remaining decision cap.

### Audit: every mechanism and its proof
| Mechanism | Workload trigger | Proof (counter or check) |
|---|---|---|
| Automatic hold at finish | every turn | `finish_planned`; CPU fixture on LRU and ARC |
| Expected-return ranking | holds over the 50% cap | `hold_displaced`; fixture ranking-LRU/ARC |
| Partial head hold | hold larger than free budget | `partial_hold`; fixture |
| Intentions, re-admission | displaced or yielded holds | `readmitted`; fixture (never inside eviction) |
| Yield before store failure | stores with holds full | `hold_yield`, store failures 0; fixture |
| Arrived protection | any return while planned | `arrived_held`/`arrived_unheld`; fixture (120 s bound) |
| `done` | final turn (candidate: complete only) | `done_released`; client test |
| `ephemeral` | every one-shot | `pending` + `ephemeral_released` |
| `keep_tokens` | compaction (ceiling or 10%) | `keep_applied`, `demoted_chunks` |
| Shared-prefix safety | 2,048-token system prefix everywhere | `shared_kept_chunks` |
| Demoted evicted first | done, ephemeral, compacted suffix | `demoted_evictions` |
| Lost protection | evicted after displacement or yield | `lost_protection_evictions` |
| Candidate uses only causal information | per-turn type median, fixed expiry | `test_advice_differs_only_in_information` |

Pre-mortem guards: overload (queue share < 20% of TTFT in roomy and typical LRU); cap
binding (uncapped oracle); unmatched arms (identical server command except policy,
same schedule and seed; test); one-shot counts (fixed list, drained); interference
(resource monitor, desktop idle, desktop GPU client excluded); advice delivery (advice
outcomes in the report must all be accepted); a feature not firing (counters above
checked in every cell); budget (cut tight first, then ask).

Also record the final mixed WSL results with `pr-discussion-report`.
