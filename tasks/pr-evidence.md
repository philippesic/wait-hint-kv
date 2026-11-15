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

Acquisition is finished under the phase budgets. Admission charged 1,905.025330883
seconds; screen charged 27,922.292034527 seconds; total 8.285365935 GPU hours.
Remaining screen 877.707965473 seconds cannot fit the next required job. No GPU
job is active. Both campaign sessions 15549 and 94897 closed normally.
benchmarks/pr-evidence/2080ti-acquisition-close.json owns final accounting and every
not-run family. Runtime-03 retains both campaign logs and all derived observations.

HM's three baseline-only sizing cells are valid: 48 sessions, 173 requests, every
request complete, no allocation refusals, failed stores/transfers, swap, capture
failure or interference violation. benchmarks/pr-evidence/hm-sizing.json freezes
the formula-derived rate 0.20189157519737003, one-shot rate 0.02402777777777778 and
308-second horizon. This is sizing only, with no efficacy or opportunity verdict.
Its next A2 working-set job reserves 308 + 600 + 60 = 968 seconds, exceeding the
remaining 877.708 seconds. Working-set and all-arm calibration plus every HM decision
cell are not run. No reduced allowance, shorter workload or selected treatment arm.
W2's minimum seven-arm measured window is 4,200 seconds before overhead; both
variants are not run. HS remains not admitted. No treatment speedup inspected yet.

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
vm.swappiness was restored to the original 60 on the same verified boot after
acquisition; GPU idle was confirmed. Record:
artifacts/runs/pr-evidence-runtime-03/swappiness-restored-01.json.
The five-minute healthcheck scheduled-task:b9d30075-3c8f-4060-93da-acb406cfb8d2 was
deleted successfully. No machine setting remains to restore and no GPU job remains.
The requested other-thread handoff is still pending until final closeout.

Read artifacts/runs/pr-evidence-runtime-02/reporting-notes.txt and runtime-03/
reporting-design-notes.txt before analysis. They cover first-task sensitivity,
cross-session reuse, lease lifetime limits, refusal-capacity replay, resources/faults,
all A/A metrics and missing/degenerate intervals. Systematic statistic labels are
frozen in D8 calibration. Do not inspect benefits to choose more coverage/settings.

## Next
Commit/push acquisition closure and HM sizing after full acceptance. Implement and
verify the maintained reporting/diagnostic extensions, then analyze the three valid
D8 blocks with the frozen labels and rules. Include first-task sensitivity, native
allocation-refusal attribution, cross-session reuse, lease activity, resource/fault
observations and every A/A metric. Re-verify CPU identity if A/A intervals demand it.
Close through close-results with per-route verdicts, whole-route difference, harms,
opportunity, limitations and all not-run coverage. Update current docs/FINDINGS,
commit/push, verify GPU still free, send the exact authorized handoff, and give
Philip the plain-language result and next decisions. Do not stop before closure.
