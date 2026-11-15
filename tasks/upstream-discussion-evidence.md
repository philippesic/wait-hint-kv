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
- Temporary `vm.swappiness=0` is authorized. Restore it to 60 with sudo at the end; the
  backup is `artifacts/runs/discussion-host/swappiness-original.json`. If sudo is
  needed, ask Philip with the T3 `request_secret` tool, never in chat.
- No WSL memory change, no public posting, no upstream outreach.

## Done when
The revision-3 screen has run and been reported to Philip. Then either the large run
he approves is acquired and analysed, or he stops it. The evidence is closed through
`skills/close-results` with claim limits stated, FINDINGS includes a prior-art entry,
swappiness is restored and this file is deleted.

## State
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
  PATH must include `/usr/lib/wsl/lib` for nvidia-smi.
- Before launching, check out the committed commit in the runner worktree (detached,
  clean) and check that the GPU is idle.
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
Philip decides the follow-up after the screen report: an advised-hold precedence fix
so long hints get a fair test, the cap at the tight pool, or the server-side framing.
Record the final mixed results with `pr-discussion-report` as well.
