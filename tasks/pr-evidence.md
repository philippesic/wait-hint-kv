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
Current agent owns main. Stage 1 is frozen/pushed; both routes use the same hold-only
mechanism. The public-callback-only infeasibility conclusion was corrected in
results/pr-evidence-feasibility. Read-only private scheduler access is allowed and
CPU-qualified. No GPU performance/benefit cells have run.

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

Admission is complete: 1,905.025330883 seconds (0.529174 hours), leaving
1,694.974669117 seconds unused. Screen sizing used 862.432028090 seconds. GPU currently idle.
benchmarks/pr-evidence/2080ti-admission.json indexes every charged attempt.

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
Resource summaries are now being added to pr-measure-cell with a regression test;
finish full acceptance before further jobs.

## Next
Commit resource reporting and sizing checkpoint, then A2 working-set calibration
seeds 12001–12003 at the derived rates/horizon and reference pool 1 GiB, per-job
ceiling 567 seconds plus 60 cleanup. Rank pool candidates from that working set,
then three complete seven-arm calibration blocks at the selected candidate.
Complete-block initial reserve is 4,389 seconds; 27,937.568 screen seconds remain.
Commit final model calibration before any decision seed. Continue D8 blocks in
priority order, re-quote after the first, then HM/W2 only if budget permits. Restore
swappiness, delete healthcheck, close results, push and send the handoff at completion.
