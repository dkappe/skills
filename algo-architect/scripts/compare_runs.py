#!/usr/bin/env python3
"""
compare_runs.py — statistical comparison for tunable/stochastic algorithm changes.

Part of the algo-architect skill, bucket 3 (tunable/stochastic techniques:
SAT solver heuristics, GA/metaheuristic hyperparameters, and similar).

WHY THIS EXISTS
A single run — or even a handful of runs — of a stochastic algorithm tells
you almost nothing about whether a change actually helped. This script
takes many-run results for a "baseline" (pre-change) and a "candidate"
(post-change) configuration and reports whether the observed difference is
large enough, relative to run-to-run noise, to actually trust.

This script evaluates PERFORMANCE ONLY. It does not check mechanism
correctness (e.g. that SAT assignments are valid, or that a GA's operators
only produce legal individuals) — do that separately, first, per the skill.
A statistically significant "improvement" from a broken mechanism is
meaningless.

INPUT FORMATS
Each input file is CSV with a header. Two supported shapes:

  1. Unpaired — one column of numeric results, e.g. fitness scores from N
     independent GA runs with different random seeds, not tied to specific
     benchmark instances:
         value
         0.812
         0.795
         ...

  2. Paired — two columns, an identifier and a numeric result, where BOTH
     files share the same identifiers (e.g. the same benchmark instance or
     seed) so each candidate result can be matched to its baseline
     counterpart:
         instance,value
         sat-001,4.21
         sat-002,11.03
         ...

  Pairing is auto-detected: if both files have an identifier column and
  share the same identifier set, a paired test (Wilcoxon signed-rank) is
  used; otherwise an unpaired test (Mann-Whitney U) is used.

USAGE
    python3 compare_runs.py baseline.csv candidate.csv \\
        --metric "solve time (s)" --lower-is-better

    python3 compare_runs.py baseline.csv candidate.csv \\
        --metric "fitness" --higher-is-better

    # If this is one of several comparisons in the same tuning sweep,
    # correct for multiple comparisons:
    python3 compare_runs.py baseline.csv candidate.csv \\
        --higher-is-better --num-comparisons 5

OUTPUT
A short markdown report: sample sizes, which test was used and why, the
median difference with a bootstrap confidence interval, an effect-size
estimate, the p-value against the (possibly corrected) alpha, and a
plain-language verdict.

Exit codes (usable as a gate in a tuning pipeline):
    0 = significant improvement
    1 = not statistically significant
    2 = significant regression

REQUIREMENTS
    pip install numpy scipy --break-system-packages
"""

import argparse
import csv
import sys
from dataclasses import dataclass

import numpy as np
from scipy import stats


@dataclass
class Sample:
    ids: list  # entries are None if the file had no identifier column
    values: np.ndarray


def load(path: str) -> Sample:
    with open(path, newline="") as f:
        rows = list(csv.reader(f))
    if not rows:
        raise ValueError(f"{path}: empty file")
    header = [h.strip().lower() for h in rows[0]]
    body = [r for r in rows[1:] if r]
    if not body:
        raise ValueError(f"{path}: no data rows")

    if len(header) == 1:
        values = np.array([float(r[0]) for r in body])
        return Sample(ids=[None] * len(values), values=values)
    elif len(header) == 2:
        ids = [r[0] for r in body]
        values = np.array([float(r[1]) for r in body])
        return Sample(ids=ids, values=values)
    else:
        raise ValueError(
            f"{path}: expected 1 column (value) or 2 columns (id,value), got {len(header)}"
        )


def bootstrap_ci(a: np.ndarray, b: np.ndarray, paired: bool, n_boot: int, alpha: float, seed: int = 0):
    """Bootstrap CI for the difference in medians (candidate - baseline)."""
    rng = np.random.default_rng(seed)
    diffs = np.empty(n_boot)
    if paired:
        n = len(a)
        for i in range(n_boot):
            idx = rng.integers(0, n, n)
            diffs[i] = np.median(b[idx]) - np.median(a[idx])
    else:
        n_a, n_b = len(a), len(b)
        for i in range(n_boot):
            idx_a = rng.integers(0, n_a, n_a)
            idx_b = rng.integers(0, n_b, n_b)
            diffs[i] = np.median(b[idx_b]) - np.median(a[idx_a])
    lo, hi = np.percentile(diffs, [100 * alpha / 2, 100 * (1 - alpha / 2)])
    return lo, hi


def effect_size(a: np.ndarray, b: np.ndarray, paired: bool) -> tuple[str, float]:
    """
    Returns (label, value):
      - paired: fraction of pairs where candidate beat baseline (ties excluded)
      - unpaired: common-language effect size, P(random candidate > random baseline)
    Both are direction-agnostic (report is "b > a"); the caller applies
    higher/lower-is-better when writing the verdict.
    """
    if paired:
        wins = np.sum(b > a)
        losses = np.sum(b < a)
        decided = wins + losses
        frac = wins / decided if decided > 0 else float("nan")
        return "fraction of pairs where candidate > baseline", frac
    else:
        # Common-language effect size via Mann-Whitney U: P(random b > random a)
        u_stat, _ = stats.mannwhitneyu(b, a, alternative="two-sided")
        cles = u_stat / (len(a) * len(b))
        return "P(random candidate value > random baseline value)", cles


def main():
    parser = argparse.ArgumentParser(
        description="Compare baseline vs candidate results for a tunable/stochastic technique (algo-architect, bucket 3).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("baseline", help="CSV of baseline (pre-change) results")
    parser.add_argument("candidate", help="CSV of candidate (post-change) results")
    parser.add_argument("--metric", default="value", help="Name of the metric being compared, for the report")
    dir_group = parser.add_mutually_exclusive_group(required=True)
    dir_group.add_argument("--higher-is-better", action="store_true")
    dir_group.add_argument("--lower-is-better", action="store_true")
    parser.add_argument("--alpha", type=float, default=0.05, help="Significance threshold before correction (default 0.05)")
    parser.add_argument(
        "--num-comparisons", type=int, default=1,
        help="If this is one of several comparisons in a tuning sweep, apply Bonferroni "
             "correction across this many comparisons (default 1, no correction)",
    )
    parser.add_argument("--n-boot", type=int, default=10000, help="Bootstrap resamples for the CI (default 10000)")
    args = parser.parse_args()

    try:
        base = load(args.baseline)
        cand = load(args.candidate)
    except (ValueError, FileNotFoundError) as e:
        print(f"error: {e}", file=sys.stderr)
        sys.exit(1)

    paired = (
        all(i is not None for i in base.ids)
        and all(i is not None for i in cand.ids)
        and set(base.ids) == set(cand.ids)
    )

    if paired:
        base_by_id = dict(zip(base.ids, base.values))
        cand_by_id = dict(zip(cand.ids, cand.values))
        ids = sorted(base_by_id)
        a = np.array([base_by_id[i] for i in ids])
        b = np.array([cand_by_id[i] for i in ids])
        test_name = "Wilcoxon signed-rank test (paired)"
        if np.all(a == b):
            stat, p = float("nan"), 1.0
        else:
            stat, p = stats.wilcoxon(b, a)
    else:
        a, b = base.values, cand.values
        test_name = "Mann-Whitney U test (unpaired)"
        stat, p = stats.mannwhitneyu(b, a, alternative="two-sided")

    adjusted_alpha = args.alpha / max(args.num_comparisons, 1)
    median_a, median_b = float(np.median(a)), float(np.median(b))
    diff = median_b - median_a
    lo, hi = bootstrap_ci(a, b, paired=paired, n_boot=args.n_boot, alpha=args.alpha)
    es_label, es_value = effect_size(a, b, paired=paired)

    direction = "higher is better" if args.higher_is_better else "lower is better"
    improved = (diff > 0) if args.higher_is_better else (diff < 0)
    significant = p < adjusted_alpha

    print(f"# Comparison: {args.metric} ({direction})\n")
    print(f"- Baseline: n={len(a)}, median={median_a:.4g}")
    print(f"- Candidate: n={len(b)}, median={median_b:.4g}")
    print(f"- Test used: {test_name} — pairing was auto-detected from the input files")
    print(f"- Median difference (candidate − baseline): {diff:+.4g}")
    print(f"- {int((1 - args.alpha) * 100)}% bootstrap CI for the difference: [{lo:+.4g}, {hi:+.4g}]")
    print(f"- Effect size ({es_label}): {es_value:.3f}")
    threshold_note = f", Bonferroni-corrected for {args.num_comparisons} comparisons" if args.num_comparisons > 1 else ""
    print(f"- p-value: {p:.4g} (threshold: {adjusted_alpha:.4g}{threshold_note})")
    print()

    if not significant:
        print(
            "**Verdict: NOT statistically significant.** The observed difference is plausibly "
            "run-to-run noise. Don't treat this as a real improvement or regression yet — more "
            "runs, more instances, or a genuinely different change are needed."
        )
        exit_code = 1
    elif improved:
        print(
            f"**Verdict: Significant improvement.** The candidate beats the baseline on "
            f"{args.metric}, beyond what noise would explain."
        )
        exit_code = 0
    else:
        print(
            f"**Verdict: Significant regression.** The candidate is WORSE than the baseline on "
            f"{args.metric} — don't keep this change as-is."
        )
        exit_code = 2

    print(
        "\n_Reminder: this checks performance only. Confirm mechanism correctness "
        "(valid SAT assignments/proofs, valid GA individuals, etc.) separately before "
        "trusting these results — see algo-architect's bucket 3 guidance._"
    )
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
