# 2080 Ti evidence details

Both ARC routes are INCONCLUSIVE on D8/W1. Neither observed a speedup. Missing
required bootstrap intervals prevent efficacy STOP; harm bounds also remain
unestablished. This is a closed budget-bounded screen, not a request to continue
acquisition. The recommendation is to hold 5080 promotion pending a separate decision.

## Comparisons and interpretation

Three complete decision seeds (12101–12103), seven arms, 21 valid cells and 1,603
planned requests, all complete. The better native baseline A2 was frozen from
calibration. Positive benefit means faster; positive recomputation change means
more work. Intervals below are 95%; the delta method is a required sensitivity,
not a replacement for missing paired-seed BCa.

| Route | Hinted TTFT benefit | BCa | Delta sensitivity | Recompute change |
| --- | ---: | --- | --- | ---: |
| A4t | -1.385% | unavailable | [-3.31, 0.51]% | +1.286 pp |
| A4p | -0.919% | unavailable | [-4.04, 2.11]% | +1.286 pp |

A2 hinted-return TTFT is 4.7185 seconds. Its post-stratified recomputation share is
20.383%, so the frozen opportunity label is **present**. This label does not prove
that all this recomputation could have been avoided by preserving a ready CPU prefix.
Whole-route post-response minus TTL benefit is +0.466 percentage points
(delta [-0.737, +1.669] pp; BCa unavailable). It bundles information, delivery timing,
final-turn holds and the delivery patch; it cannot isolate a hook advantage.

Some bootstrap samples omit a required prompt-length stratum: seed 12101 has no
medium hinted-return session and 12103 has no short one. Pooling all three seeds
covers all strata, but draws consisting only of one such seed do not. The frozen
rule invalidates the interval when any replicate is undefined. No replicate was
dropped and no percentile fallback used. The calculator's method-disagreement
wording means BCa INCONCLUSIVE versus delta STOP here; it is not two valid conflicting
intervals. The delta result alone cannot become the final efficacy STOP.

First-task-occurrence sensitivity retains 46 distinct source tasks, removing two
repeated sessions from seed 12103 and retaining every one-shot and failed first
occurrence. TTL/post benefits are -2.151%/-1.679%, with BCa still unavailable;
baseline recomputation becomes 19.454%. This separately labelled sensitivity does
not replace the primary opportunity label, denominators or verdict. A5 (LRU plus
TTL) is descriptive: +13.450% benefit versus A1 and +10.276% versus A2, both with
unavailable BCa; hinted recomputation changes -1.543 pp versus A1 and 0 versus A2.
It establishes no alternate route promotion.

## Harms

Positive means worse. TTFT and token interval entries are relative percent;
recomputation entries are percentage points. Margin is max(A/A 95% interval
half-width, 5% latency or 2 pp recomputation). Passing requires point <= margin
and upper bound <= twice margin. This table shows BCa; both interval methods and
all pass/fail criteria are retained in [guardrails.json](guardrails.json).

| Route | Harm | Point | 95% BCa | Margin | Point / upper pass |
| --- | --- | ---: | --- | ---: | --- |
| A4t | unhinted_recompute | -5.48 | [-23.82, 7.93] | 2.00 | True / False |
| A4t | unhinted_ttft | -12.67 | [-20.48, 15.28] | 5.00 | True / False |
| A4t | unhinted_itl | +10.36 | [1.62, 36.57] | 5.00 | False / False |
| A4t | one_shot_ttft | -12.26 | [-25.62, 4.52] | 10.75 | True / True |
| A4t | one_shot_itl | -1.41 | [-2.64, -0.63] | 5.00 | True / True |
| A4p | unhinted_recompute | -5.48 | [-23.82, 7.93] | 15.88 | True / True |
| A4p | unhinted_ttft | -13.69 | [-20.51, 10.06] | 16.91 | True / True |
| A4p | unhinted_itl | +10.91 | [0.63, 37.38] | 17.07 | True / False |
| A4p | one_shot_ttft | -11.10 | [-25.88, 6.97] | 15.32 | True / True |
| A4p | one_shot_itl | -1.31 | [-2.07, 0.01] | 5.00 | True / True |

Every decision request completed. No failed store or transfer occurred. Native
allocation refusals are separate outcomes: A2 counts 9/4/16 across seeds, TTL
10/4/15 (paired deltas +1/0/-1), post 8/4/15 (-1/0/-1). Every refusal was also
infeasible at that instant without holds under native capacity replay. This rules
out direct hold obstruction in those states, not indirect cache/scheduling effects.
No observed correctness or resource failure is attributed to treatment; neither
route establishes the complete harm requirements.

## Disabled controls and diagnosis

The following are treatment-control relative changes (%) except recomputation
(percentage points). Positive is more latency/work. All cohorts and both interval
methods remain in the statistical JSON, including hinted outcomes whose BCa is
unavailable. The full control-route difference A3p/A3 is retained, not called an
isolated delivery-method cost.

| Control pair | Cohort | Metric | Point | 95% BCa | 95% delta |
| --- | --- | --- | ---: | --- | --- |
| A3/A2 | first_turn | ttft_ns | +8.95 | [1.76, 14.95] | [0.81, 17.74] |
| A3/A2 | first_turn | client_itl_ns | +6.55 | [0.39, 16.85] | [-4.40, 18.75] |
| A3/A2 | hinted_return | ttft_ns | -1.71 | unavailable | [-3.56, 0.18] |
| A3/A2 | hinted_return | client_itl_ns | +2.42 | unavailable | [-0.29, 5.20] |
| A3/A2 | unhinted_return | ttft_ns | -10.08 | [-11.21, -3.59] | [-13.26, -6.77] |
| A3/A2 | unhinted_return | client_itl_ns | +7.73 | [3.01, 11.93] | [0.91, 15.01] |
| A3/A2 | one_shot | ttft_ns | +10.45 | [-0.92, 20.58] | [-4.19, 27.32] |
| A3/A2 | one_shot | client_itl_ns | -0.21 | [-0.85, 0.37] | [-1.11, 0.69] |
| A3/A2 | hinted_return | recompute | +2.09 | unavailable | [-1.15, 5.33] |
| A3/A2 | unhinted_return | recompute | -1.13 | [-3.23, 0.00] | [-3.31, 1.05] |
| A3p/A2 | first_turn | ttft_ns | +3.39 | [-10.81, 10.82] | [-8.67, 17.03] |
| A3p/A2 | first_turn | client_itl_ns | +2.98 | [-0.93, 22.70] | [-5.19, 11.85] |
| A3p/A2 | hinted_return | ttft_ns | +1.85 | unavailable | [-0.10, 3.83] |
| A3p/A2 | hinted_return | client_itl_ns | -2.43 | unavailable | [-7.00, 2.38] |
| A3p/A2 | unhinted_return | ttft_ns | -13.30 | [-20.69, 13.12] | [-28.31, 4.84] |
| A3p/A2 | unhinted_return | client_itl_ns | +10.36 | [1.49, 35.64] | [-3.80, 26.60] |
| A3p/A2 | one_shot | ttft_ns | -12.84 | [-26.64, 4.00] | [-31.73, 11.27] |
| A3p/A2 | one_shot | client_itl_ns | -0.39 | [-2.27, 1.14] | [-2.72, 2.00] |
| A3p/A2 | hinted_return | recompute | +1.70 | unavailable | [-3.73, 7.14] |
| A3p/A2 | unhinted_return | recompute | -5.48 | [-23.82, 7.93] | [-26.49, 15.54] |
| A3p/A3 | first_turn | ttft_ns | -5.11 | [-18.62, -3.34] | [-9.56, -0.43] |
| A3p/A3 | first_turn | client_itl_ns | -3.35 | [-15.50, 8.16] | [-17.36, 13.04] |
| A3p/A3 | hinted_return | ttft_ns | +3.62 | unavailable | [1.83, 5.43] |
| A3p/A3 | hinted_return | client_itl_ns | -4.73 | unavailable | [-11.60, 2.67] |
| A3p/A3 | unhinted_return | ttft_ns | -3.59 | [-12.52, 17.34] | [-18.79, 14.46] |
| A3p/A3 | unhinted_return | client_itl_ns | +2.44 | [-2.46, 28.24] | [-8.67, 14.90] |
| A3p/A3 | one_shot | ttft_ns | -21.08 | [-39.16, 4.96] | [-46.33, 16.03] |
| A3p/A3 | one_shot | client_itl_ns | -0.18 | [-2.61, 2.01] | [-3.28, 3.03] |
| A3p/A3 | hinted_return | recompute | -0.39 | unavailable | [-2.63, 1.86] |
| A3p/A3 | unhinted_return | recompute | -4.34 | [-20.60, 7.93] | [-23.24, 14.55] |

Intervals excluding zero triggered fresh CPU rechecks: pr-policy-feasibility-12
and pr-post-feasibility-04 both pass, including stock/disabled ARC and LRU eviction
identity and real MessagePack utility A3/A3p identity. The recheck's disabled CPU
dispatch p50/p99 are 64.495/123.857 microseconds (transport and serving excluded).
Measured control differences remain evidence. Fixed initial arrivals and tool gaps
do not imply identical later arrival times: each return follows the preceding
response. Disabled observation/delivery work and scheduler timing can therefore
change cache histories without changing eviction policy for the same events.
Their individual contributions remain unresolved; no post-hoc cell invalidation,
point-shift correction or threshold change was made.

## Mechanism exposure and resources

| Arm | Observed leases | Final-turn leases | Refusals | Hinted CPU tokens reused | Hinted GPU tokens reused | Hinted recomputed tokens |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| A1 | 0 | 0 | 32 | 64 | 147584 | 43648 |
| A2 | 0 | 0 | 29 | 128 | 150592 | 40576 |
| A3 | 0 | 0 | 21 | 1088 | 145472 | 44736 |
| A3p | 0 | 0 | 26 | 576 | 146752 | 43968 |
| A4t | 91 | 16 | 29 | 576 | 147584 | 43136 |
| A4p | 39 | 5 | 27 | 576 | 147584 | 43136 |
| A5 | 87 | 18 | 23 | 0 | 150720 | 40576 |

All arms have 191,296 raw eligible hinted-return tokens. These raw counts are
not the population-weighted primary estimator. Holds were active, but CPU restore
was rare: both ARC treatments reused only 576 hinted tokens from CPU, versus 128
for A2. Neither route had any successful CPU load in the first two decision seeds.
Most reuse was already on GPU. The screen exercises holds more than useful restores.
TTL produced 91 observed leases versus 39 post-response leases, including 16 versus
5 holds on the final recorded turn. All such final-turn holds in these cells are
at truncated endings, not proof of real-world abandonment. Observed lifetime
segments and deadlines are retained per lease; snapshots do not identify exact
release/expiry times. `return_release` counts release attempts, not actual leases.

Definite first-turn cross-session reuse is identical in every arm: 25,088 GPU tokens
out of 55,808 eligible tokens, zero CPU tokens. Later-turn cross-session reuse is
not exhaustively attributed. Primary first-turn within-session eligibility is zero.

Full per-cell files in diagnostics/ retain first-turn/hinted/unhinted/one-shot TTFT,
client per-token/per-chunk and engine token intervals, output and requested tokens,
submission lateness, session completion durations, transfers/evictions, working-set
and overlap, hint responses/outcomes, metadata, faults and startup/full-job memory.
Complete-response descriptions keep their failure denominators. No metric was
selected away after inspecting benefits.

Valid cells' mean outside CPU usage ranges from 3.715% to 7.122% of one core, below the frozen 10% mean gate. Minimum available RAM across cells is 9.639 GiB. Owned swap and host swap-out growth are zero.

The calibrated configured pool/mean working-set ratio is 1.31554 (usable 1.30654),
with calibrated actual mean overlap 2.14–2.94 and peaks 2.98–3.79 GiB. It is not steady
half-working-set pressure or eight continually overlapping sessions. GPU memory,
utilization, temperature and power were sampled; clocks and Windows processes were
not captured. Process faults use PID plus start-time identity and may miss startup
before the first sample. RSS sums can double-count shared pages. Capture was
CPU-qualified; there is no uninstrumented GPU performance control.

## Coverage, failures and decisions

D8 and HM passed all seven admission arms with poisoned destination bytes,
store/load provenance and same-boundary deterministic continuation. HM exercised
active holds in all four groups. D8's admission prefix exceeds the 50% hold cap;
its byte check qualifies restore, not active holding. Active D8 screen holds do not
retroactively fill that qualification gap. HS is not admitted: 8.44 GiB weights leave
0.20 GiB native GPU KV against 0.74 GiB required at the frozen context/memory settings.

HM completed only three A2 sizing cells (48 sessions, 173 requests, all complete);
working-set calibration, all-arm calibration and every decision seed are not run.
Its next 968-second job would exceed 877.708 seconds remaining screen budget. D8 seeds
12104–12108 cannot fit another complete 4,389-second reserved block. Both historical
60 s and 12 s W2 variants are entirely not run; a seven-arm block requires at least
4,200 seconds before overhead. Stage 2b, Stage 3 including the 2080 Ti pilot, 5080/rental and the
competitor/simulator lanes are not run. No unused admission allocation was moved
to the screen.

Admission used 0.529174 h, screen 7.756192 h, total 8.285366 GPU h. This includes startup,
cleanup and every failed/invalid attempt. Two invalid D8 decision attempts used
1.324007 h: the first exposed a 32 ms resource-end coverage race; the repaired runner
preserves the strict check. The second had measured external CPU interference,
correlated with another thread's filesystem search; the exited process's exact
command is unknown. Neither contributes to primary results. The second stopped
after 3 arms and its other 4 are explicitly not run. The subsequent complete rerun
and both remaining valid blocks are retained without seed or metric selection.

Five initial admission starts tripped host swap growth despite zero experiment
swap. A captured-client path failure and an illegal CUDA host-pointer copy also
required repairs before performance acquisition. Both environments carry the same
hashed Gemma/Turing and mapped-device-pointer compatibility fixes; only A3p/A4p
carry the hashed post-response delivery patch. Exact upstream wheel installation
is not a local CUDA source build. Post-response observation timing was fixed and
readmitted before comparison. All 36 CPU attempt directories, including 5 failed or
incomplete attempts, and all GPU attempts remain retained.

The earlier public-callback-only feasibility stop was mistaken and corrected.
Pinned read-only scheduler state makes both routes feasible; this is not a stable
public upstream API promise. Adversarial bookkeeping at 1M chunks/1k holds costs
p99 14.9 ms ARC/81.5 ms LRU versus 7.6 us/27.0 us without holds, with 18.2 MB owned metadata.
The Qwen diverged-hit component boundary persists; full-scheduler GPU reproduction
is unqualified. LMCache 0.5.6 conflicts with pinned OpenTelemetry dependencies.
W1 replays recorded prompts with synthetic gaps; generated text is not fed into
later prompts. Request completion does not measure live agent task success.

vm.swappiness is restored from 0 to 60; WSL memory, 2 GiB headroom, no-swap guard and all
rules stayed fixed. The periodic healthcheck is deleted. No raw evidence or shared
dependency was deleted. Exact source/hash indexes and [regeneration.json](regeneration.json)
retain the CPU-only reproduction recipe; four representative CLI replays match.

Recommendation: do not promote automatically. Larger hardware could admit HS and
permit fuller HM/pressure coverage, but that would buy missing evidence without a
positive ARC signal from this screen. Any follow-up needs prospective scope,
coverage, budget and authorization; it must not rewrite this result. Philip still
needs to decide the proposed fixed 5% later-stage harm limit and whether to authorize
Stage 2b public maintainer outreach. Neither was assumed approved.
