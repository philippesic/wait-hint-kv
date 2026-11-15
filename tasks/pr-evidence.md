# PR evidence on frozen vLLM main

## Goal
Complete Stage 1 and the 2080 Ti admission/screen under the accepted plan, then
close results for Philip’s 5080 decision.

## Authorized
Maximum admission 1 GPU hour, screen 8,
including failed attempts and cleanup. Check idle before every job. Freeze inputs
before dependent GPU; complete paired blocks in priority order; re-quote after the
first. Retain all evidence. No Stage 2b posting, Stage 3, 5080/rental, WSL memory
increase, changed decision rules or check exceptions. Push milestones.

When genuinely finished and GPU free, send Philip’s exact two-task authorization
message from this conversation to thread 4dd4323d-196a-4973-a4cb-3e985a47c982.
The message has not been sent.

## Done when
Close-results must retain per-route/model verdicts,
harms, opportunity, failed/not-run coverage and update docs/FINDINGS; delete this
task only after closure and push.

## State
Capture repair 921318e8 is accepted and pushed (137 portable tests, 105 rule proofs).
Decision seed 12101 attempt02 is invalid because A3 had outside CPU activity:
18.38% of one core averaged across the cell and 44.09 seconds continuously above
25%. A separate thread's filesystem-wide search correlates in time and duration;
its exited PID command was not captured, so exact attribution remains an inference.
That thread finished normally. All three acquired cells (A5/A3/A3p) are retained;
the four remaining arms were stopped before launch. The task-only checkpoint
invoked the existing clean-source gate after A3p closed. No active GPU job remains.
The complete seven-arm rerun is attempt03; no previous-attempt cell is substituted.
Compact accounting is benchmarks/pr-evidence/2080ti-screen-invalid-attempts.json.

Current agent owns main. Stage 1 is frozen/pushed; both routes use the same hold-only
mechanism. The public-callback-only infeasibility conclusion was corrected in
results/pr-evidence-feasibility. Read-only private scheduler access is allowed and
CPU-qualified. D8 calibration is complete and frozen at 1a2b2e6b. The first decision
block completed but is invalid because of a resource-capture race. No valid
decision block is available yet; no treatment speedup has been used to choose
settings, coverage or the repair.

Exact runtime 0.34.0rc1.dev465+ge9281bd93 / torch 2.14+cu130 lives in
artifacts/venvs/pr-evidence and matched pr-evidence-post. Both have the common
Gemma Turing and mapped-host-pointer compatibility patches. Only A3p/A4p have
the hashed delivery patch. The clean checkout is artifacts/checkouts/vllm-pr-evidence.
benchmarks/pr-evidence/stage1-freeze.json identifies dependencies, mechanisms,
limits, models, patches and protocol. Original supported runtime is unchanged.

CPU receipts: pr-policy-feasibility-11, pr-post-feasibility-01/02/03,
pr-bookkeeping-01 and pr-instrument-10/11 under artifacts/runs. Instrument qualification
covers all 21 model/arm configurations, poisoned-destination fixtures, HTTP faults,
paired schedules, metric regeneration and working-set accounting. Bookkeeping at
1M chunks/1k holds has p99 14.9 ms ARC / 81.5 ms LRU, 18.2 MB owned metadata; retain
this scale limitation. LMCache 0.5.6 dependency admission fails. The Qwen diverged-hit
component reproduces; full scheduler probe remains unqualified.

W1 admission pr-w1-admission-01 is verified; compact identity is
benchmarks/pr-evidence/w1-freeze.json. Manifest SHA:
d993b516214bd534e198c7122fe470407b011f974c080a42bb8cc650cd0d40da.
No source-success filter. Pilot D8/HM/HS: 1,691/1,689/1,562 tasks across 28 repositories;
mostly truncated. Confirmation performance is held out. Statistical tools implement
frozen pooled BCa/delta sensitivity and verdict rules; arithmetic does not certify
resource or attribution evidence.

### Acquisition and repairs
All jobs are retained under artifacts/runs/pr-evidence-2080ti; logs and verification
outputs under pr-evidence-runtime-02. Five initial D8/HM/HS A2 attempts stopped on
host swap growth with zero owned swap and 9.26–13.31 GiB available RAM. Philip
approved the machine repair and corrected the unnecessary overnight approval stop:
routine reversible repairs should proceed autonomously.

vm.swappiness is now 0; restore original 60 after acquisition. Backup and boot ID:
pr-evidence-runtime-02/swappiness-original.json. Committed machine scope:
benchmarks/pr-evidence/2080ti-environment.json. No WSL memory/headroom/swap rule
change. Root access: wsl.exe -d Ubuntu-24.04 -u root (same verified boot); sudo
requires a password. Active five-minute healthcheck:
scheduled-task:b9d30075-3c8f-4060-93da-acb406cfb8d2; delete when acquisition ends.

D8/A2-04 loaded without swap but the captured client output path was refused; the
runner now captures under its source artifacts and moves output before final hashing.
D8/A2-05 failed its first native CPU store with illegal CUDA access. Common
pr-mapped-host-pointer translates registered mmap CPU addresses to CUDA aliases.
All subsequent D8/HM arms pass byte/provenance/continuation admission. These repairs
precede benefit observation; original failures remain charged and retained.

D8: A2-06 and A1/A3/A4t/A3p/A4p/A5-01 pass. CPU reuse 4,096 tokens, identical
resident/restored boundary and output, group 0 byte identity, zero store failures.
1 GiB = 113 chunks of 9,437,184 bytes; GPU 280 blocks of 64 tokens. The 4,096-token
probe exceeds the 50% hold cap, so all D8 admission hint holds refuse physical_limit;
it does not qualify active holding. Remaining D8 admission job ceiling 139 seconds.

HM: A2-02 and all other arms-01 pass all four groups with 3,840 CPU reused tokens,
256 recomputed probe tokens, identical resident/restored boundary/output, zero store
failures. 1 GiB = 102 chunks of 10,485,760 bytes; GPU 360 blocks. Initial compilation
cost 396 seconds; later jobs about 60 seconds. Active 15-chunk holds in A4t pass
GPU byte checks. HM ceiling 600 seconds.

HS/A2-02 is not admitted: weights 8.44 GiB leave 0.20 GiB native GPU cache at the
frozen 0.85 fraction, below 0.74 GiB required for 6,144 tokens. No fraction/context/
sequence/block override change is allowed for W1. Remaining HS arms and W1 not run.

Admission is complete: 1905.025330883 seconds (0.529174 hours), leaving
1,694.974669117 seconds unused. Screen usage is 17048.254263326 seconds,
including all calibration and invalid attempts; 11751.745736674 seconds remain.
GPU is idle at this checkpoint. All three attempt02 cells passed capture coverage,
completed every request and had zero store/transfer failures or swap. Only A3
violated the unchanged outside CPU limit. No treatment speedup has been inspected.
benchmarks/pr-evidence/2080ti-admission.json indexes every admission attempt.

Post-response holds were acknowledged but snapshots could miss their lifetime
before the next return. The delivery utility now invokes the common read-only
observer after publication, equally for A3p/A4p, preserving policy identity. CPU
receipt pr-post-feasibility-03 checks snapshots and A3p/A3 eviction identity; p50
59.335 us / p99 97.470 us dispatch cost excludes transport/observer capture. Frozen
new patch hash at 8b49f957; D8/HM A3p/A4p-02 all pass. HM post-response snapshots
now capture 15 physical held chunks. Historical
admissions remain valid for their exact earlier patch, not silently relabeled.

D8 baseline sizing seeds 12001–12003 all completed: 48 sessions, 177 requests,
zero failures, no swap, minimum available RAM 9.995 GiB. Outside CPU averaged
3.22%/3.52%/3.65% of one core, no material interference or outside GPU processes.
The frozen formula gives arrival_rate=0.13696109776373452, one_shot_rate=
0.024583333333333332, horizon_seconds=428. Sizing metrics and derived settings are
in pr-evidence-runtime-02. These are calibration only; no hint benefit observed.
Resource reporting and sizing are committed/pushed at aa806acd; full acceptance
passes 136 portable tests and 105 rule proofs. No tests removed or checks weakened.

D8 working-set seeds 12001–12003 are complete at the calibrated rate. All 48
multi-turn sessions completed; one last-second one-shot in seed 12003 was censored.
No swap, material interference, store failure or failed transfer. Native store
refusals are 16/9/5 and remain reported. Median time-average working set is
816,199,119.311 bytes; fixed pool ranking is 1/2/4 GiB. The 1 GiB candidate is
1.31554 times that average because no smaller eligible candidate exists; peak
footprints are 2.98–3.79 GiB. benchmarks/pr-evidence/d8-pool-ranking.json freezes
ranking, source identities, schedule hashes/orders and the complete-block quote.
This is baseline calibration only; no treatment benefit observed.

All 21 full-arm D8 calibration cells are verified. All 336 multi-turn sessions
completed. Seed 12003 has one late one-shot timeout in every arm (3.347 seconds
available before the common cutoff); all seven remain in the evidence. Minimum
available RAM was 9.920 GiB; no swap, material interference, failed stores or
failed transfers. Native allocation refusals vary even in disabled controls and
remain separate evidence requiring attribution. Both routes actively held chunks.
The prescribed baseline selection is A2: pooled hinted recomputation 0.172088969,
versus A1 0.207374737. This is calibration, not the decision opportunity label.
benchmarks/pr-evidence/calibration/D8.json freezes the final pool, baseline, rates,
window, all eight decision schedule hashes/orders and systematic statistic labels.
The first calibration-block and first decision-block cost re-quotes are retained
in pr-evidence-runtime-02. Three valid decision blocks, including the required
rerun, are now expected to fit; each admission uses the actual ledger.
Reporting/attribution notes live in pr-evidence-runtime-02/reporting-notes.txt.
No tracked files should change while a GPU loop is running; CPU checks wait for
idle acquisition gaps. All raw attempts, including authoring failure 01, remain.

Decision seed 12101 attempt01 completed all seven arms in 3,331.274716183 seconds.
All requests completed; zero failed stores/transfers. A1's final resource sample
started 32,001,872 ns before the cutoff; the client exited during its 72 ms sample.
The loop previously polled the client after sampling and then stopped. The strict
coverage check correctly refuses this cell, invalidating the paired comparison.
The complete original block, native outcomes and diagnosis remain in runtime-02;
no raw receipt was edited and no old cell enters the primary comparison.

The runner now polls before sampling and uses that observed return code, ensuring
another sample if the client exits during capture. A real-process regression test
reproduces the race without sleeping. Full acceptance passes 137 portable tests
and 105 rule proofs. No coverage or resource check was weakened.
benchmarks/pr-evidence/2080ti-screen-capture.json defines capture campaign 02, which
inherits the valid committed calibration and repeats all seven arms of seed 12101.
Use artifacts/runs/pr-evidence-runtime-03 for new metrics/logs, but keep every GPU
attempt in the same cumulative pr-evidence-2080ti ledger. Mechanism, runtime,
routes, workload, thresholds and schedule hashes are unchanged.

## Next
Commit and push the interference checkpoint after full acceptance. Repeat complete
seed 12101 with attempt03, then decision seeds 12102–12108 in frozen order until
the next complete seven-arm block cannot fit. Job ceiling stays 567 seconds plus
60 cleanup reserve; reserve 4,389 seconds before each block. Re-quote after the
first valid block, retaining invalid-attempt costs. Three valid blocks are forecast
to fit, subject to actual charges. Stop newly invalid attempts after the active
cell and document unrun arms; treatment failures remain evidence, not exclusions.
Do not inspect speedups to choose coverage or change settings. Continue HM baseline
calibration if it fits after D8; report incomplete coverage honestly. W2's shortest
historical seven-arm block needs at least 4,200 seconds before startup/cleanup,
calibration and contingency. Restore swappiness, delete healthcheck, close results,
push and send the exact handoff only when genuinely finished.
