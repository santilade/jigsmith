# Rubric — Loop (loop engineering)

The inner agentic loop, turn by turn. Where **Sessions** is the macro lens (runs
*across* sessions — parallel, chains, babysitting wall-time), Loop is the micro
lens: what happens *inside* one human prompt before the agent yields control. The
fourth engineering discipline alongside prompt, context, and harness — it shapes
*how far and how well the agent iterates on its own*. Signals exclude sidechain
events, so a sub-agent swarm shows as one delegation step, not inflated depth.

## Read for
- **Leash length (`leash`, `overall.tool_calls_per_turn`).** How many tool-calls
  the agent runs per human prompt. A leash that's too short (`tool_depth_buckets`
  piled at `1`/`2-4`, high `resteer.pct_turns_resteered`) = the human steering every
  step → the loop isn't trusted to run; candidates: a verify/test hook so the agent
  self-checks, a clearer up-front brief (cross-ref Context preambles), a plan-first
  skill. A leash that's too long with many `interrupts` = it runs off the rails →
  candidates: tighter guardrails, a checkpoint/plan gate. A long leash with *no*
  interrupts isn't automatically healthy: if changes ship unreviewed it accrues
  **comprehension debt** (you stop understanding what the loop shipped) and drift
  from the brief is **intent debt** — name these when the cheap is large but the
  re-steering is low. The fix for both is a feedback signal, not a shorter leash.
- **Tool grammar (`cycle`).** `verify_after_change` (edit/write→bash) is the
  self-correction loop — the **maker/checker** split run inside one agent, the
  checker being the loop's own QA. *Low* relative to edits = changes shipped
  unverified → candidate: a post-edit test/typecheck hook (fires automatically, the
  loop's feedback signal). `explore_then_act` (read/search→edit) shows whether it
  looks before it leaps. `top_transitions` is the loop's actual cadence in the dev's
  own work — name it in those terms.
- **Delegation (`cycle.delegation_turns`, `max_fanout_in_turn`).** Sub-agent use
  *within* a turn = the loop fanning out, the maker/checker split across *separate*
  agents (a checker sub-agent verifying the maker's work). Near-zero fan-out on big
  multi-file turns = serial work that could parallelize → candidate: a sub-agent/
  workflow harness (cross-ref Sessions' manual-swarm finding; if both fire it's one
  candidate, dedup).
- **Re-steer cadence (`resteer`).** `quick_short_resteers` + `interrupts` = the
  human repeatedly cutting in to correct mid-loop. High rate = the loop is doing the
  wrong thing by default → fix the default (memory/skill/output-style), don't forge
  over the correcting. `loop_control_commands` (`/clear`, `/compact`) = manual
  context hygiene mid-loop → cross-ref Context.

## Current best practice (tend this)
- Give the loop a feedback signal: a fast post-edit check (typecheck/scoped test)
  beats the human eyeballing every diff. Verify-after-change should track edits.
- Brief once, well, over re-steering N times. A short correction every turn is a
  missing memory/skill, not a personality.
- Let a trusted loop run; gate an untrusted one with a plan step — don't shorten the
  leash by hand-holding every tool-call.
- Fan out independent work to sub-agents; keep dependent reasoning in one loop.

## Autonomy ladder (a property of the fix, not the dev)
When a loop fix proposes handing more to the loop, tag *how far* — it sets the
guardrails the fix needs, and lets the dev graduate deliberately:
- **L1 — report-only.** The loop surfaces, the human decides/acts. No write risk.
- **L2 — assisted.** The loop proposes a change; a human gate (plan step, review,
  approval) stands before it lands.
- **L3 — unattended.** The loop executes on its own, behind a denylist/checkpoint.
This is a property of the *recommendation*, never a label on the developer — N=1,
no buckets. Most fixes start at L1 and earn their way up only after the feedback
signal (verify-after-change, a checker) is proven. Higher rungs demand more
guardrail, or they just convert speed into comprehension debt.

## Flag (craft, leave alone)
- Exploratory, interrupt-heavy loops on genuinely unknown problems are *thinking*,
  not a broken default — the re-steering is the work. Don't automate the judgment of
  when to cut in.
- A deep, long autonomous run on a well-specified task is the loop working, not a
  runaway. Length alone isn't a smell; length + interrupts is.
