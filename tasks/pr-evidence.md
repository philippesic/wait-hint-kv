# PR evidence on frozen vLLM main

## Goal
Complete Stage 1 and the authorized 2080 Ti admission/screen under the accepted plan,
then close results for Philip's 5080 decision. Do not stop at acquisition alone.

## Authorized
Admission at most 3,600 GPU seconds; screen at most 28,800, including every failed
attempt and cleanup. Fresh idle nvidia-smi before each job; wait if busy. Frozen
mechanism/settings/decision rules, complete paired blocks in priority order. No
Stage 2b posting, Stage 3, 5080/rental, WSL memory increase, harm-limit change or
check exceptions. Commit coherent milestones after full acceptance and push.

When genuinely finished and GPU free, send Philip's exact two-task authorization
message from this conversation to thread 4dd4323d-196a-4973-a4cb-3e985a47c982.
It has not been sent. No other thread messaging is authorized.

## Done when
Close through skills/close-results/SKILL.md: per-route/model/workload verdicts,
whole-route difference, harms, opportunity, failed/not-run coverage, current docs,
FINDINGS and committed/pushed evidence. Restore machine setting and remove the
healthcheck; delete this task only with final closure.

## State
Stage 1 is frozen and pushed; both A4t and A4p are feasible with hold-only policy.
The public-callback-only infeasibility conclusion was corrected in the earlier
result. Private read-only scheduler access is allowed and CPU-qualified.
benchmarks/pr-evidence/stage1-freeze.json owns runtime, protocol, patch, mechanism,
metadata/hold limits and W1 identities. docs/pr-evidence-screen.md is hash-frozen.

D8 has three valid complete W1 decision blocks: seeds 12101/12102/12103, all seven arms,
21 cells and 1,603 requests, every request complete. No failed stores/transfers,
swap/resource violation, capture failure or material interference. Both routes
actively held chunks. Native allocation refusals remain separate outcomes needing
paired reporting/attribution. No treatment speedup or harm ratio has been inspected.
benchmarks/pr-evidence/2080ti-d8-screen.json indexes every valid cell, verification,
source and resource record, the first-valid-block re-quote and budget stop.
Seeds 12104–12108 are not run: their next complete 4,389-second reservation cannot fit.

Admission charged 1,905.025330883 seconds; screen charged 27,048.439091714 seconds.
Remaining screen 1,751.560908286 seconds. No active GPU job at this checkpoint.
The D8 campaign loop exited normally; its session 15549 is closed. Logs/metrics:
artifacts/runs/pr-evidence-runtime-03/d8-decision-campaign-03.log.

HM baseline-only sizing is next under the frozen algorithm. Its1 GiB reference pool
contains the conservative 838,860,800-byte maximum-conversation bound from admitted
four-group geometry. benchmarks/pr-evidence/hm-sizing-quote.json freezes three schedules
(seeds 12001–12003, A2, rate 0.2, no one-shots, 240-second horizon), job ceiling 840 plus
60 cleanup. Admit each successive sizing job only if its 900-second reservation fits
the actual ledger. The all-three upper quote 2,700 does not fit initially; this is
not a paired treatment block. Partial calibration must remain explicit. Derive a
rate only if all three sizing observations are valid, then assess the next A2 working-set
job using that frozen result. Any all-arm comparison still needs its whole block.
W2's shortest historical seven-arm block needs at least 4,200 seconds before startup,
cleanup or calibration, so neither W2 variant can fit. HS is not admitted.

### Retained attempts and qualification limits
All GPU attempts share artifacts/runs/pr-evidence-2080ti. Admission index:
benchmarks/pr-evidence/2080ti-admission.json. D8/HM all seven arms pass poisoned-destination
bytes, provenance, same-boundary continuation and output identity. D8 admission's
4,096-token prefix exceeded the 50% hold cap, so it did not exercise active holds;
HM active 15-chunk holds passed byte tests. D8 active holds are observed in the screen.
HS weights leave 0.20 GiB native GPU cache versus 0.74 GiB required at the frozen 6144
context/.85 memory fraction; remaining HS arms and workload are not run.

Five initial admission jobs stopped on host swap growth despite zero owned swap.
Philip approved temporary swappiness 0 and corrected the unnecessary overnight
approval stop. Runtime repairs (client path, mapped-host-pointer CUDA alias and
post-response lifetime snapshots) precede performance comparison. Exact wheel
0.34.0rc1.dev465+ge9281bd93 / torch 2.14+cu130 is installed in matched base/post envs.
Both include common Gemma/Turing and mapped-pointer compatibility patches; A3p/A4p
also include the hashed delivery patch. No local CUDA source-build claim.

Decision 12101 attempt 01 completed all seven arms but A1's final resource sample missed
the cutoff by 32 ms. Capture repair 921318e8 polls client exit before sampling, with a
real-process regression test; coverage checks are unchanged. Attempt 02 stopped after
A5/A3/A3p: A3 had 18.38% average outside CPU and 44.09 s continuously above 25%. A separate
thread's completed filesystem search correlates; exact exited PID command is unknown.
Its remaining four arms are not run. All invalid costs remain charged; neither attempt
contributes any cell to primary estimates. Attempt 03 is the valid full rerun.
benchmarks/pr-evidence/2080ti-screen-invalid-attempts.json retains both diagnoses.

The staged implementation estimate is recorded in docs/pr-evidence-execution.md.
CPU receipts: pr-policy-feasibility-11, pr-post-feasibility-03, pr-bookkeeping-01,
pr-instrument-10/11, pr-w1-admission-01. Latest full acceptance 137 portable tests plus
105 rule proofs. No checks weakened/tests removed/exceptions added. Bookkeeping at
1M chunks/1k holds has p99 ARC 14.9 ms / LRU 81.5 ms and 18.2 MB metadata. LMCache 0.5.6 is
incompatible. Qwen diverged-hit component reproduces; full-scheduler probe remains
unqualified. W1 is semi-synthetic prompt replay, mostly truncated, not live task success.
Final D8 calibration: benchmarks/pr-evidence/calibration/D8.json, native ARC baseline,
1 GiB,428 s, rate 0.13696109776373452, shots 0.024583333333333332. Configured/usable pool
ratios 1.31554/1.30654 against finite-horizon mean; report peak and actual overlap too.

### Machine restoration and reporting
vm.swappiness is 0; restore original 60 after acquisition. Backup/boot ID:
artifacts/runs/pr-evidence-runtime-02/swappiness-original.json. Same-machine root:
/mnt/c/Windows/System32/wsl.exe -d Ubuntu-24.04 -u root /usr/sbin/sysctl -w vm.swappiness=60
Do not change WSL memory or resource gates. Five-minute healthcheck remains active:
scheduled-task:b9d30075-3c8f-4060-93da-acb406cfb8d2; delete after acquisition/restoration.

Read artifacts/runs/pr-evidence-runtime-02/reporting-notes.txt and runtime-03/
reporting-design-notes.txt before analysis. They cover first-task sensitivity,
cross-session reuse, lease lifetime limits, refusal-capacity replay, resources/faults,
all A/A metrics and missing/degenerate intervals. Systematic statistic labels are
frozen in D8 calibration. Do not inspect benefits to choose more coverage/settings.

## Next
Commit/push D8 acquisition and HM sizing quote after full acceptance. Run affordable
HM A2 sizing jobs sequentially with fresh idle checks, preserving all attempts.
Freeze derived settings only after three valid observations; assess subsequent jobs and
record every budget-not-run cell. Then restore swappiness, stop healthcheck, complete
maintained reporting/diagnostic extensions and analysis, CPU identity re-verification
if A/A demands it, per-route verdicts and close-results. Preserve every failed and
unfavorable attempt. Finish docs/FINDINGS, commit/push, verify GPU free, send exact
handoff, and give Philip the plain-language result and next decisions.
