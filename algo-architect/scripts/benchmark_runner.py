#!/usr/bin/env python3
"""
benchmark_runner.py — run a command across many instances/seeds and collect results.

Part of the algo-architect skill. Feeds bucket 2 (heuristic) node-count/speed
sanity checks and bucket 3 (tunable/stochastic) performance evaluation — its
CSV output is directly consumable by compare_runs.py.

WHY THIS EXISTS
Evaluating a heuristic or tunable change requires running it across a
benchmark suite of instances and/or many random seeds, not eyeballing one
run. This script drives that: run a command once per (instance, seed) pair,
time it, optionally extract a metric from its output, enforce a timeout,
and write everything to CSV.

USAGE

  Benchmark a SAT solver across a directory of instances, 5 seeds each,
  30s timeout, extracting solve time from its own printed output:
    python3 benchmark_runner.py \\
        --cmd "./solver --seed {seed} {instance}" \\
        --instances-dir benchmarks/sat_instances/ \\
        --seeds 5 \\
        --timeout 30 \\
        --metric-regex "solve_time_ms: ([\\d.]+)" \\
        --output results.csv

  Benchmark a GA with no separate instance files, 50 independent seeds,
  using wall-clock time as the metric (no --metric-regex given):
    python3 benchmark_runner.py \\
        --cmd "./ga_solver --seed {seed}" \\
        --seeds 50 \\
        --output results.csv

  Aggregate to one row per instance (median across seeds) so the output
  can go straight into compare_runs.py's paired mode:
    python3 benchmark_runner.py ... --output results.csv \\
        --aggregate median --aggregated-output results_by_instance.csv

OUTPUT
  --output: one row per (instance, seed) run: instance,seed,elapsed_s,
  exit_code,timed_out,metric

  --aggregated-output (optional, requires --instances-dir): one row per
  instance, id=instance name, value=median/mean of that instance's metric
  across all its seeds. This is the "id,value" shape compare_runs.py
  expects for paired comparisons.

  A summary (solve rate, timeout rate, and PAR-2 score if --par2 is given)
  is printed at the end.
"""

import argparse
import csv
import re
import shlex
import statistics
import subprocess
import sys
import time
from pathlib import Path


def run_once(cmd_template: str, instance: str | None, seed: int, timeout: float):
    cmd_str = cmd_template.format(instance=instance or "", seed=seed)
    cmd = shlex.split(cmd_str)
    start = time.monotonic()
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        elapsed = time.monotonic() - start
        return proc.stdout, proc.returncode, elapsed, False
    except subprocess.TimeoutExpired:
        return "", -1, timeout, True


def extract_metric(stdout: str, elapsed: float, regex: re.Pattern | None) -> float | None:
    if regex is None:
        return elapsed
    m = regex.search(stdout)
    if not m:
        return None
    try:
        return float(m.group(1))
    except (IndexError, ValueError):
        return None


def main():
    parser = argparse.ArgumentParser(
        description="Run a command across many instances/seeds and collect results into CSV (algo-architect).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--cmd", required=True,
                         help='Command template, e.g. "./solver --seed {seed} {instance}". '
                              '{instance} is omitted if --instances-dir isn\'t given.')
    parser.add_argument("--instances-dir", help="Directory of instance files; each file's path fills {instance}")
    parser.add_argument("--seeds", type=int, default=1, help="Number of seeds per instance, 0..N-1 (default 1)")
    parser.add_argument("--seed-start", type=int, default=0, help="First seed value (default 0)")
    parser.add_argument("--timeout", type=float, default=30.0, help="Per-run timeout in seconds (default 30)")
    parser.add_argument("--metric-regex", help="Regex with one capture group to extract a numeric metric from "
                                                "stdout; if omitted, wall-clock elapsed time is used")
    parser.add_argument("--par2", action="store_true",
                         help="Report a PAR-2 score (timeouts scored as 2x the timeout value) in the summary; "
                              "meaningful when the metric is a time")
    parser.add_argument("--output", required=True, help="Path to write the per-run CSV")
    parser.add_argument("--aggregate", choices=["median", "mean"],
                         help="Also aggregate to one row per instance (requires --instances-dir)")
    parser.add_argument("--aggregated-output", help="Path for the aggregated CSV (default: <output>_aggregated.csv)")
    args = parser.parse_args()

    if args.aggregate and not args.instances_dir:
        print("error: --aggregate requires --instances-dir (nothing to group by otherwise)", file=sys.stderr)
        sys.exit(2)

    metric_regex = re.compile(args.metric_regex) if args.metric_regex else None

    if args.instances_dir:
        instances = sorted(str(p) for p in Path(args.instances_dir).iterdir() if p.is_file())
        if not instances:
            print(f"error: no files found in {args.instances_dir}", file=sys.stderr)
            sys.exit(2)
    else:
        instances = [None]

    rows = []
    total_runs = len(instances) * args.seeds
    run_i = 0
    for instance in instances:
        for seed in range(args.seed_start, args.seed_start + args.seeds):
            run_i += 1
            stdout, code, elapsed, timed_out = run_once(args.cmd, instance, seed, args.timeout)
            metric = None if timed_out else extract_metric(stdout, elapsed, metric_regex)
            if metric is None and not timed_out:
                print(f"warning: could not extract metric from run {run_i}/{total_runs} "
                      f"(instance={instance}, seed={seed}); stdout was: {stdout[:200]!r}", file=sys.stderr)
            rows.append({
                "instance": instance or "",
                "seed": seed,
                "elapsed_s": round(elapsed, 6),
                "exit_code": code,
                "timed_out": timed_out,
                "metric": metric if metric is not None else "",
            })
            status = "TIMEOUT" if timed_out else ("ok" if metric is not None else "no-metric")
            print(f"[{run_i}/{total_runs}] instance={instance or '-'} seed={seed} -> {status} ({elapsed:.3f}s)")

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["instance", "seed", "elapsed_s", "exit_code", "timed_out", "metric"])
        writer.writeheader()
        writer.writerows(rows)

    # Summary
    n = len(rows)
    n_timed_out = sum(1 for r in rows if r["timed_out"])
    n_solved = sum(1 for r in rows if not r["timed_out"] and r["metric"] != "")
    print()
    print(f"Ran {n} total (instance, seed) combinations.")
    print(f"Solved: {n_solved}/{n} ({100 * n_solved / n:.1f}%)")
    print(f"Timed out: {n_timed_out}/{n} ({100 * n_timed_out / n:.1f}%)")
    if args.par2:
        par2_values = [
            (2 * args.timeout if r["timed_out"] else r["metric"])
            for r in rows if r["timed_out"] or r["metric"] != ""
        ]
        if par2_values:
            print(f"PAR-2 score (mean, timeouts at 2x timeout): {statistics.mean(par2_values):.4f}")
    print(f"Per-run results written to {out_path}")

    if args.aggregate:
        agg_path = Path(args.aggregated_output) if args.aggregated_output else out_path.with_name(out_path.stem + "_aggregated.csv")
        by_instance: dict[str, list[float]] = {}
        for r in rows:
            if r["metric"] == "":
                continue  # timeouts/failures excluded from the aggregate; handle those separately if needed
            by_instance.setdefault(r["instance"], []).append(r["metric"])
        agg_fn = statistics.median if args.aggregate == "median" else statistics.mean
        with open(agg_path, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["instance", "value"])
            for instance, values in sorted(by_instance.items()):
                writer.writerow([instance, agg_fn(values)])
        print(f"Aggregated ({args.aggregate}) results written to {agg_path}")


if __name__ == "__main__":
    main()
