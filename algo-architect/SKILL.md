---
name: algo-architect
description: Approach implementing a complex, well-studied algorithm or system — a chess engine, a pathfinder, a parser/compiler, a constraint solver, a crypto primitive, a physics/simulation engine, a SAT solver, a genetic algorithm or other metaheuristic — with the rigor that kind of code needs, meaning a known reference algorithm instead of an improvised design, a correctness oracle built before or alongside the implementation, and incremental layers each re-verified as complexity is added, using the right verification method for whether the technique is exact, heuristic, or a tunable/stochastic one that needs statistical evaluation across many runs. Use this whenever the task is to build or extend something where "looks right" isn't good enough to trust — the domain has established theory, known test vectors, a brute-force reference behavior, or a benchmark suite to check against. Not for ordinary business logic, CRUD, or UI work, where a ticket's acceptance criteria are already the correctness check.
---

# Algo Architect

Build algorithm-heavy systems the way the domain's own literature would validate them — not by eyeballing output.

This skill ships helper scripts under `scripts/`:
- `compare_runs.py` — bucket 3 (tunable/stochastic) statistical comparison
- `oracle_diff.py` — bucket 1 (exact/behavior-preserving) divergence-finding against a reference implementation
- `benchmark_runner.py` — drives a command across many instances/seeds and produces CSV, including an aggregated form that feeds directly into `compare_runs.py`

See each bucket's section below for when and how to use them.

## Why this is different from ordinary implementation work

Most tickets have a human-checkable definition of done: the button does the thing, the API returns the right shape. Complex algorithms don't work that way. Code can run without errors, produce plausible-looking output, and still be wrong — a move generator that "looks like" it makes legal moves but silently drops en passant; a pathfinder that finds *a* path but not the *shortest* one; a parser that handles the examples you tried but not the grammar's edge cases. The bug is invisible until checked against something authoritative.

The throughline of this skill: **establish ground truth before trusting the implementation, build on known algorithms instead of improvising, and verify after every increment of complexity — not just at the end.**

Running examples throughout: a chess engine, plus other well-studied algorithms — FFT, the Simplex method, the Hungarian algorithm, and Rete. The same shape applies to a pathfinder (oracle = brute-force search on small graphs, known algorithm = Dijkstra/A*), a parser (oracle = a reference grammar/parser, known algorithm = recursive descent or a parser generator), and a crypto primitive (oracle = published test vectors, known algorithm = the actual spec, never an improvised variant).

This applies just as much to **extending an existing, already-working system** as to building one from scratch — adding NNUE to a chess engine that currently uses a classical evaluation, adding a new pruning technique to an existing search or quiescence search, adding a new rule type to an existing Rete network. The oracle in that case includes the existing system's own current behavior: capture it *before* changing anything, so "did this regress something" has an answer.

## Three kinds of technique — each needs a different kind of verification

Not every technique in this space is meant to preserve the exact answer, and some don't have a single "right answer" to check against at all. Sort the technique being added into one of three buckets before deciding how to verify it:

**1. Exact / behavior-preserving** — the technique is purely an efficiency gain; the answer must not change, only the speed.
- Alpha-beta pruning vs. plain minimax, transposition tables, bitboards vs. mailbox representation
- FFT vs. naive DFT
- The Hungarian algorithm vs. brute-force enumeration of assignments
- Rete's incremental match vs. naive full re-evaluation of every rule against working memory every cycle
- Simplex vs. brute-force vertex enumeration (verify via the optimal objective value and feasibility, and check optimality conditions — e.g. zero duality gap — at termination)

Verification: run both the naive/existing version and the new one on the same inputs and require an *exact* match (same result, allowing only floating-point tolerance where relevant). Any difference is a bug, full stop.

Use `scripts/oracle_diff.py` to do this automatically rather than spot-checking a few inputs by hand: point it at the reference and candidate commands (any language — it shells out), and either an existing directory of test-case files or a generator command for fresh random inputs, and it reports the first divergence with the offending input saved to disk for debugging. `--numeric-tolerance` handles floating-point-heavy outputs like FFT or Simplex where exact string equality isn't the right bar.

**2. Heuristic / approximating** — the technique intentionally trades exactness for speed or for a different quality/speed tradeoff; a changed answer is expected, not automatically a bug.
- Search pruning: null-move pruning, late move reductions, futility pruning, qsearch delta/SEE pruning
- NNUE replacing or blending with a classical evaluation function
- Any heuristic that intentionally accepts an approximate or non-optimal result in exchange for speed

Verification here can't be "identical output" — it needs the domain's actual empirical validation method instead:
- **Node-count / speed sanity** at a fixed depth or input size, to confirm the technique is doing what it claims (e.g. pruning reduces nodes searched)
- **Regression suites** of known-correct answers the technique must not break (tactical test suites for chess pruning; known-good matches for a Rete rule change) — some drift is expected, but it shouldn't blunder on positions/cases the un-pruned version got right
- **Head-to-head strength/quality testing** where that's the domain standard — most notably SPRT (Sequential Probability Ratio Test) self-play testing in chess engine development, which is how the community actually validates that a pruning or eval change is a net improvement rather than trusting a few sample games
- Isolate the change: test the new technique against the *immediately preceding* verified version, one technique at a time (see step 6) — don't add NNUE and a new pruning heuristic in the same increment, or a strength regression can't be attributed to either one

**3. Tunable / stochastic** — the *mechanism* has an exact correctness check, but the *performance* is stochastic (random seeds, population dynamics, restart timing) and only meaningful in aggregate across many runs and many problem instances. A single run tells you almost nothing.
- SAT solvers (DPLL/CDCL): the mechanism — unit propagation, clause learning, the resulting assignment — is exactly checkable; the *performance* (how fast it solves, or whether it times out) depends heavily on tunable heuristics (variable selection like VSIDS, restart strategy, clause deletion policy)
- Genetic algorithms and other metaheuristics (simulated annealing, particle swarm): the operators (crossover, mutation, selection) are exactly checkable for producing valid individuals; the *solution quality* is stochastic and depends on tunable hyperparameters (population size, mutation/crossover rate, selection pressure)

For this bucket, split verification into two separate concerns — don't let tuning performance stand in for mechanism correctness, and don't let mechanism correctness stand in for good tuning:
- **Mechanism correctness (exact, do this first, same rigor as bucket 1):** a SAT solver's satisfying assignment is checked by evaluating the formula directly (cheap, always do it — never trust a "SAT" result unverified); a claimed UNSAT result should be backed by a checkable proof certificate (e.g. DRAT/DRUP) rather than trusted blindly, since the search process that decided UNSAT is exactly the part most likely to have a subtle bug. A GA's crossover/mutation operators should be unit-tested to confirm every individual they produce is valid under the problem's encoding/constraints, independent of whether the population converges to anything good.
- **Performance/tuning (statistical, do this second):** evaluate any parameter or heuristic change across a **benchmark suite** of many instances, not one; for stochastic algorithms, run **many repetitions with different random seeds** and report a distribution (mean, median, variance, success rate, or PAR-2-style timeout-penalized score for SAT), not a single number. Tune systematically — a deliberate parameter sweep or an automated tuner (e.g. irace, SMAC-style approaches), isolating one parameter's effect at a time — rather than ad hoc trial and error. Hold out some benchmark instances from the tuning set and check performance on those too, so the tuning doesn't just overfit to the specific instances it was tuned against. Treat an improvement as real only if it holds up beyond what run-to-run noise would explain, not from a single favorable seed.

  Use `scripts/compare_runs.py` to do this comparison rather than eyeballing two medians: point it at a CSV of baseline results and a CSV of candidate results (auto-detects paired-by-instance vs. unpaired, picks Wilcoxon or Mann-Whitney accordingly), and it reports a bootstrap CI, an effect size, and a significance verdict — pass `--num-comparisons` if this is one of several changes tried in the same tuning sweep. See the script's own `--help`/docstring for the exact CSV format.

## Process

### 1. Find the domain's own definition of correct
Before designing anything, find how this domain actually validates implementations:
- Published test vectors or reference values (e.g. chess: perft node counts at fixed depths for standard starting positions; crypto: NIST/RFC test vectors)
- A brute-force or naive reference implementation that's obviously correct even if too slow to ship (e.g. a pathfinder that just tries every path; a naive O(n²) sort as ground truth for a fancier one; naive DFT for FFT; brute-force assignment for the Hungarian algorithm)
- A formal spec or protocol the output must conform to (e.g. UCI for chess engines, a grammar spec for a parser)
- Known test suites built by the domain's community (e.g. chess: Bratko-Kopec, WAC test positions; SAT: SATLIB/SAT Competition benchmark sets)
- For tunable/stochastic techniques (bucket 3): a **benchmark suite** of problem instances, not one instance, plus a plan for how many random seeds/repetitions per instance is enough to distinguish real improvement from run-to-run noise

If this is a change to an existing system rather than a new build, the ground truth also includes **the existing system's own current behavior**: run it now, before making any change, and record what you get (node counts at reference positions, current benchmark results, current test-suite pass rate, current solve-rate/timing distribution across the benchmark suite for tunable techniques). That snapshot is what step 6 compares against.

If none of these exist yet for this specific project, build the simplest one yourself before writing the real implementation — a brute-force reference function is often only a few lines and is worth far more than it costs.

### 2. Identify the known algorithm — don't improvise a design
These problem spaces are usually solved. Name the actual established technique before writing code:
- Chess engine: minimax with alpha-beta pruning, iterative deepening, bitboard representation, Zobrist hashing for transposition tables; adding NNUE means the accumulator-based incremental update scheme from its actual spec/reference implementation, not an improvised network integration
- Pathfinding: Dijkstra, A*, or BFS depending on whether edges are weighted and whether a heuristic exists
- Parsing: recursive descent, Pratt parsing, or a parser generator, depending on the grammar's shape
- Crypto: the exact named primitive and mode from its spec — never a homegrown variant
- Signal processing: the Cooley-Tukey FFT algorithm, not an improvised divide-and-conquer over DFT
- Linear programming: Simplex (or interior-point, depending on problem size/structure) — not an ad hoc iterative improvement scheme
- Assignment problems: the Hungarian algorithm, not a greedy heuristic assignment
- Rule/pattern matching engines: Rete (or a documented variant like TREAT/RETE-OA), not a naive re-scan unless the working-memory size makes that genuinely fine
- SAT solving: CDCL (conflict-driven clause learning) with an established variable-selection heuristic (e.g. VSIDS) as the starting point, not an improvised DPLL variant
- Combinatorial/black-box optimization: a standard genetic algorithm structure (selection, crossover, mutation — e.g. tournament selection, established crossover operators for the encoding in use) or another established metaheuristic (simulated annealing, particle swarm), not an ad hoc evolutionary scheme invented from scratch

Search for how the domain's literature or well-known open-source implementations solve this before designing from scratch. Reinventing an approach to a solved problem is where subtle, hard-to-find bugs come from.

### 3. Decompose into a tree, not just a line
Real decomposition usually isn't one straight pipeline — it branches. There are two different axes, and it's worth keeping them separate:

- **Vertical** — incremental sophistication within one component (naive minimax → alpha-beta → transposition tables). This is what steps 5–6 already cover.
- **Horizontal** — splitting one component into independent siblings that don't depend on each other to exist. This is the tree, and it's usually where the bigger decomposition win is.

**Where the tree comes from.** Sometimes the algorithm hands you the tree for free — FFT's divide-and-conquer halving into two N/2 subproblems, alpha-beta's own game-tree recursion, mergesort's split-merge structure. There, the decomposition isn't a design choice, it's the algorithm's literal structure, and the correctness check at each level is "does this subtree's result compose correctly into the level above." Other systems don't come with a built-in tree — a chess engine as a whole, a SAT solver's subsystems, a GA's pipeline — and the tree has to be imposed by you, cutting along whatever actually separates concerns.

**The test for where to cut: sibling independence.** At each split, the question isn't "is this a distinct concept" (almost everything is) — it's "can I implement and verify this child without any of its siblings existing yet." Move generation isn't one monolithic thing; it branches into pawn moves, knight moves, sliding-piece moves, castling, en passant, and promotion — each of those can be built and perft-tested alone, in any order, none waiting on the others. That's a real tree split. By contrast, "is this move legal" (does it expose the king to check) is *not* a sibling of the piece-type rules — it's a cross-cutting concern that applies on top of all of them. Treating a cross-cutting concern as if it were just another leaf is where integration bugs come from; it needs its own place in the tree, layered above the leaves it applies to, not beside them.

Chess move generation as a tree (illustrating the split, not the whole engine):
```
Move generation
├── Pawn moves (incl. promotion, en passant)     ← independent leaf, own perft check
├── Knight moves                                  ← independent leaf, own perft check
├── Sliding pieces (bishop/rook/queen)            ← independent leaf, own perft check
├── King moves + castling                         ← independent leaf, own perft check
└── Check/pin legality filter                     ← cross-cutting, applies ABOVE all the leaves
```

Other examples:
- **GA pipeline:** selection, crossover, mutation, and the termination criterion are near-independent leaves — each unit-testable for producing valid output before any of them are wired into the generational loop.
- **SAT/CDCL:** unit propagation, the decision heuristic, conflict analysis/clause learning, and the restart policy are largely separable modules, each with its own small correctness check, composed into the solve loop.

**Leaves bottom out where the oracle gets cheap.** Same atomicity instinct as decomposing a ticket into small steps, applied to subproblems instead of file edits: stop splitting once a node has a small, clear correctness check and fits in one sitting. A "pawn moves" leaf with its own tiny perft-style check is the right granularity; splitting further into "single pawn push" and "double pawn push" as separate tree nodes is usually more ceremony than the oracle needs.

**Composition is its own node, not a freebie.** Verified leaves combining correctly isn't automatic — build a check for the *parent* too, after its children are each independently verified, specifically aimed at interaction bugs the leaf checks can't see. This is exactly what running perft on the *whole* move generator does: it verifies pawn rules + knight rules + sliding-piece rules + castling + en passant + the check/pin filter all compose correctly together, over and above each piece type already being independently right.

**Build order follows risk and dependency, not left-to-right.** Once the tree is laid out, decide build order by which leaf is riskiest (most likely to have a subtle bug, so verify it early) or which unblocks the most siblings (a shared board-representation leaf needed by every move-generation leaf goes first) — not simply the order the tree happened to get written down in. Across the whole system this still traces the familiar vertical spine — board representation, then move generation (itself the horizontal tree above), then search, then evaluation, then protocol — and within that spine, never start verifying a parent against a child that isn't verified yet. A search algorithm built on top of a move generator with an undiscovered bug will produce results that look reasonable and are wrong in ways that take far longer to trace back once search and evaluation are layered on top of it.

### 4. Build the correctness oracle alongside — or before — the real implementation
Turn step 1's ground truth into an actual runnable check, at both the leaf and composition level from step 3:
- Chess: implement `perft(depth)` per piece-type leaf where practical (e.g. a position with only pawns present), and again for the fully composed move generator against published node counts for standard test positions at multiple depths — before writing any search code
- Pathfinder: assert your algorithm's path length matches brute-force on small random graphs across many trials
- Parser: assert against a reference parser or a hand-built table of (input, expected AST) pairs, including deliberately malformed input
- Crypto: assert exact byte-for-byte match against the spec's official test vectors

This oracle isn't a nice-to-have written after the fact — build it as part of step 3's tree, one check per leaf and one per composition point, not as an afterthought once everything's already assembled. For any of these where the reference and candidate can each be run as a command over many inputs (pathfinder-vs-brute-force, an FFT-vs-naive-DFT check, comparing against a hand-built AST table), `scripts/oracle_diff.py` runs this automatically instead of a hand-rolled loop.


### 5. Implement the simplest correct version first
Before any optimization: naive minimax before alpha-beta, O(n²) before the clever version, unindexed lookup before the fancy data structure. Verify the simple version against the oracle from step 4. This gives you a known-correct baseline to compare every later optimization against — if a "faster" version ever disagrees with the naive one, you know immediately which change introduced the bug.

### 6. Add complexity one technique at a time, re-verifying after each
Each optimization or feature is a single, isolated increment on top of something already verified. Verify it according to which bucket it falls into (see above):

Exact/behavior-preserving increments — require an identical result, just faster:
- Add alpha-beta pruning → verify it still returns the same best move and score as unpruned minimax on test positions (fewer nodes searched, same answer)
- Add transposition tables → verify the search still returns identical scores with and without the table on the same positions
- Add iterative deepening, move ordering (as a pure ordering change, not a pruning change), etc. → same pattern each time

Heuristic/approximating increments — compare against the pre-change baseline using the domain's real validation method, not an exact-match assertion:
- Add a new pruning technique (null-move, LMR, futility, qsearch delta/SEE) → run the tactical regression suite against the pre-change baseline from step 1, confirm no new blunders on positions the un-pruned version got right, and validate the net effect via the domain's actual method (e.g. SPRT self-play against the previous version for chess) rather than a single example game
- Add NNUE → first verify the accumulator's incremental update exactly matches a full recompute from scratch on the same position (this part *is* exact and any mismatch is a critical bug) — then validate the resulting evaluation/playing strength against the pre-change baseline using the domain's standard method, same as a pruning change

Tunable/stochastic increments — verify the mechanism exactly, then evaluate performance statistically against the benchmark suite:
- Add/change a SAT heuristic (VSIDS variant, restart schedule, clause deletion policy) → the assignment or proof-checking mechanism doesn't change and must still pass exactly (checkable satisfying assignment, checkable UNSAT proof); then compare solve-rate/timing across the full benchmark suite with multiple seeds against the pre-change baseline, not a single instance
- Tune a GA's hyperparameters (population size, mutation/crossover rate) or change an operator → verify the operator still only produces valid individuals (exact check), then compare solution-quality distributions (many seeds, many problem instances) against the pre-change baseline, holding out some instances from whatever set was used to pick the new parameters

`scripts/benchmark_runner.py` runs the baseline and candidate configurations across an instance directory and/or many seeds, with a timeout, and writes CSV — including an aggregated `id,value` form (one row per instance) that feeds directly into `scripts/compare_runs.py`. This is the concrete way to do "compare the full benchmark suite with multiple seeds" rather than a manual loop.

If an increment in the *exact* bucket changes the answer, not just the speed, something's wrong — stop and find the bug before moving on. If an increment in the *heuristic* bucket changes the answer, that's expected; the question is whether the change is a net improvement by the domain's own measure, and whether it introduces new blunders on cases the baseline handled correctly. If an increment in the *tunable/stochastic* bucket changes single-run results, that's expected and not informative on its own — the question is whether the aggregate, statistically-evaluated performance improved on both the tuning set and the held-out instances. Never let two changes land unverified between checks; when something breaks, you want it traceable to exactly one increment.

### 7. Profile before optimizing performance
Don't guess at the bottleneck. Measure it — profiler output, timing instrumentation, node-per-second counts — before deciding what to optimize. Complex algorithms invite premature optimization that adds risk (see step 6) without addressing the actual cost.

### 8. Document and assert the invariants
Complex algorithms accumulate implicit invariants that are easy to silently violate later (a bitboard's bit-ordering convention, a hash table's collision policy, a parser's operator precedence table). Write them down near the code that depends on them, and add runtime assertions for the ones cheap enough to check — an invariant that's only in someone's head breaks the first time someone else touches the code.

## Anti-patterns to avoid

- **Big-bang implementation** — writing the whole search + evaluation + protocol stack before running anything against an oracle. When it's wrong, there's no way to localize which layer broke it.
- **Treating a cross-cutting concern as a sibling leaf** — e.g. check/pin legality isn't another piece-type rule sitting next to pawn/knight/sliding moves; it applies on top of all of them. Misplacing it in the tree hides exactly the interaction bugs the tree was supposed to expose.
- **Skipping the composition check** — verifying each leaf alone and assuming they combine correctly for free. The parent node needs its own oracle (e.g. perft on the whole move generator, not just each piece type) aimed at interaction bugs.
- **"Looks right" as the correctness check** — a chess engine that plays plausible-looking moves in a few games you watched is not the same as one verified against perft.
- **Reinventing a solved algorithm** — an improvised variant of alpha-beta or a homegrown crypto mode is exactly where the domain's decades of known pitfalls resurface.
- **Treating a heuristic technique's changed answer as automatically a bug** — a pruning change or NNUE swap is *supposed* to change results; the bug signal is a regression against the domain's real validation method, not a diff from the old answer.
- **Skipping the domain's real validation method for heuristic changes** — judging a new pruning technique or NNUE integration by a handful of sample games instead of the tactical regression suite and strength testing (e.g. SPRT) the domain actually relies on.
- **Trusting a SAT solver's result unverified** — always check a claimed satisfying assignment directly, and require a checkable proof certificate for a claimed UNSAT rather than trusting the search that produced it.
- **Judging a tunable/stochastic technique from a single run or a single instance** — one lucky (or unlucky) seed tells you nothing about whether a GA/SAT-heuristic change actually helped; compare distributions across a benchmark suite and multiple seeds.
- **Overfitting tuning to the benchmark set used to tune it** — a parameter change that only helps on the exact instances it was tuned against, with nothing held out to check, isn't validated.
- **Optimizing before profiling** — guessing at the bottleneck instead of measuring it.
- **Stacking multiple unverified changes** — makes regressions untraceable; verify after each increment, not after a batch. Especially important for heuristic and tunable changes, where two techniques added together make it impossible to attribute a strength/performance change to either one.
- **Skipping the oracle because "it's just a small project"** — the oracle is often a few lines (brute force, a couple of test vectors) and is cheap insurance against a bug that's invisible until much later.

## Output when using this skill on a task

1. **Which known algorithm/technique is being used, and why** — one or two sentences, not a full literature review, but the reference point should be named explicitly rather than left implicit.
2. **Which bucket it falls in** — exact/behavior-preserving, heuristic/approximating, or tunable/stochastic — since that determines what "verified" means for this change.
3. **The decomposition tree** for this specific task — leaves and their sibling-independence rationale, cross-cutting concerns called out separately, build order and why — for new builds; or the pre-change baseline captured (for extensions to an existing system).
4. **The oracle or validation method** — what it checks against and how it's run: exact match against a naive reference for behavior-preserving techniques, the domain's empirical method (regression suite, SPRT, etc.) for heuristic ones, or mechanism-exactness plus benchmark-suite statistics (seeds, instances, held-out check) for tunable/stochastic ones.
5. **A verification note per increment** — what was added, what it was checked against, and the result. E.g. "added alpha-beta pruning; verified against perft-derived node counts and unpruned minimax on 5 test positions; same best move and score in all 5, node count reduced ~90%" for an exact change; "added NNUE eval; accumulator incremental update matches full recompute exactly on 1,000 random positions; tactical suite pass rate unchanged; SPRT vs. previous version pending" for a heuristic one; or "tuned VSIDS decay parameter; satisfying assignments still verified on all solved instances; solve-rate on the 200-instance benchmark suite (20 seeds each) up from 78% to 84%, held-out set up from 75% to 81%" for a tunable one.
