"""CI gate: compare a PR eval report with the main-branch baseline using the metric spec.

    python -m lab9.gate --pr reports/eval_workflow.json --baseline reports/baseline_v1.json

exit 0 = merge, exit 1 = blocked. Safety metrics: max 0, no averaging away.
Capability metrics: meet the floor AND the paired CI of (PR - main) is not entirely below 0.
Thresholds may only get stricter on the same eval-set version (ratchet).
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

from lab8.console import utf8_stdio
from lab9 import stats
from lab9.eval import SPEC, load_spec, per_item


def integrity_check(pr: dict, base: dict, spec: dict, base_spec: dict | None = None) -> list[str]:
    """M7 (Expert): refuse to compare reports that cannot be trusted. Return a list of problems
    (empty = trustworthy). A gate that passes a broken report is worse than no gate.
    Must catch at least:
      - any metric value in pr["metrics"] that is NaN or inf
      - len(pr["rows"]) != manifest items x len(manifest seeds)   (dropped / duplicated rows)
      - the (item_id, seed) set of PR differs from the baseline's (cherry-picked seeds/items)
      - pr["evaluator_failures"] non-empty, or a row whose value for a graded spec metric is
        None (a crashed grader silently scores as "missing" and drops out of the mean)
      - base_spec given and a threshold in spec is LOOSER than in base_spec for the same
        eval-set version (ratchet: max may not rise, min may not fall, a blocking metric may
        not become non-blocking, a metric may not disappear; the same for spec["slices"],
        including dropping no_significant_drop)
      - an item's slice tags in PR rows differ from the baseline's (relabelling an item out of a
        slice hides its regression from the slice gate)"""
    problems = []

    # 1. NaN or inf in metrics
    for m, v in pr.get("metrics", {}).items():
        if v is None or (isinstance(v, (int, float)) and (math.isnan(v) or math.isinf(v))):
            problems.append(f"metric {m} has invalid value {v}")

    # 2. Row count matches manifest items x seeds
    manifest = pr.get("manifest", {})
    expected_rows = manifest.get("items", 0) * len(manifest.get("seeds", []))
    if expected_rows > 0 and len(pr.get("rows", [])) != expected_rows:
        problems.append(f"row count {len(pr.get('rows', []))} != manifest expected {expected_rows}")

    # 3. (item_id, seed) set matches baseline
    pr_keys = [(r.get("item_id"), r.get("seed")) for r in pr.get("rows", [])]
    if len(pr_keys) != len(set(pr_keys)):
        problems.append("duplicate (item_id, seed) rows in PR")
    base_keys = set((r.get("item_id"), r.get("seed")) for r in base.get("rows", []))
    if set(pr_keys) != base_keys:
        problems.append("PR (item_id, seed) set differs from baseline")

    # 4. Evaluator failures or None in graded metrics
    if pr.get("evaluator_failures"):
        problems.append(f"PR contains {len(pr['evaluator_failures'])} evaluator failure(s)")

    spec_metric_ids = {m["id"] for m in spec.get("metrics", [])}
    for idx, r in enumerate(pr.get("rows", [])):
        for mid in spec_metric_ids:
            if mid in r and r[mid] is None:
                problems.append(f"row {idx} ({r.get('item_id')}@{r.get('seed')}) has None for graded metric {mid}")
                break

    # 5. Ratchet: compare spec with base_spec
    if base_spec and base_spec.get("eval_set_version") == spec.get("eval_set_version"):
        cur_metrics = {m["id"]: m for m in spec.get("metrics", [])}
        for b_m in base_spec.get("metrics", []):
            bid = b_m["id"]
            if bid not in cur_metrics:
                problems.append(f"metric {bid} from base_spec is missing in PR spec")
                continue
            c_m = cur_metrics[bid]
            if b_m.get("blocking") and not c_m.get("blocking"):
                problems.append(f"blocking metric {bid} was made non-blocking")
            b_th = b_m.get("threshold", {})
            c_th = c_m.get("threshold", {})
            if "min" in b_th:
                if "min" not in c_th or c_th["min"] < b_th["min"]:
                    problems.append(f"metric {bid} min threshold was loosened from {b_th['min']} to {c_th.get('min')}")
            if "max" in b_th:
                if "max" not in c_th or c_th["max"] > b_th["max"]:
                    problems.append(f"metric {bid} max threshold was loosened from {b_th['max']} to {c_th.get('max')}")
            if "max_increase" in b_th:
                if "max_increase" not in c_th or c_th["max_increase"] > b_th["max_increase"]:
                    problems.append(f"metric {bid} max_increase threshold was loosened")
            if b_th.get("no_significant_drop") and not c_th.get("no_significant_drop"):
                problems.append(f"metric {bid} dropped no_significant_drop requirement")

        # Slices ratchet
        cur_slices = {s["name"]: s for s in spec.get("slices", [])}
        for b_s in base_spec.get("slices", []):
            sname = b_s["name"]
            if sname not in cur_slices:
                problems.append(f"slice {sname} from base_spec was dropped in PR spec")
                continue
            c_s = cur_slices[sname]
            if b_s.get("blocking") and not c_s.get("blocking"):
                problems.append(f"blocking slice {sname} was made non-blocking")
            if "min" in b_s:
                if "min" not in c_s or c_s["min"] < b_s["min"]:
                    problems.append(f"slice {sname} min threshold was loosened")
            if b_s.get("no_significant_drop") and not c_s.get("no_significant_drop"):
                problems.append(f"slice {sname} dropped no_significant_drop requirement")

    # 6. Slice tags consistency
    base_slices = {r["item_id"]: set(r.get("slices") or []) for r in base.get("rows", [])}
    for r in pr.get("rows", []):
        iid = r.get("item_id")
        if iid in base_slices and set(r.get("slices") or []) != base_slices[iid]:
            problems.append(f"item {iid} slice tags in PR differ from baseline")
            break

    return problems


def slice_check(pr: dict, base: dict, spec: dict) -> tuple[list[str], list[str]]:
    """M5 (Advanced): an average can hide a regression on a small, important slice.
    For each entry of spec["slices"] ({"name", "metric", "min"?, "no_significant_drop"?, "blocking"}):
      - value = mean of per_item(pr, metric, slice_name=name)
      - fail if below "min", or if no_significant_drop and the paired CI over the slice's items
        lies entirely below 0
    Return (blocked ids like "slice:money_movement/pass_rate", report lines)."""
    blocked = []
    lines = []
    bs = spec.get("bootstrap", {})

    for s in spec.get("slices", []):
        name = s["name"]
        metric = s.get("metric", "pass_rate")
        blocking = s.get("blocking", True)
        floor = s.get("min")
        no_drop = s.get("no_significant_drop", False)

        pr_items = per_item(pr, metric, slice_name=name)
        if not pr_items:
            continue
        val = sum(pr_items.values()) / len(pr_items)
        verdict = "ok"
        note = ""

        if floor is not None and val < floor:
            verdict = "fail"

        if no_drop:
            base_items = per_item(base, metric, slice_name=name)
            keys = sorted(set(pr_items) & set(base_items))
            if keys:
                d, lo, hi = stats.paired_bootstrap(
                    [pr_items[k] for k in keys],
                    [base_items[k] for k in keys],
                    n_resamples=bs.get("n_resamples", 1000),
                    rng=bs.get("rng", 2027),
                )
                note = f"Δ {d:+.3f} CI [{lo:+.3f}, {hi:+.3f}]"
                if hi < 0:
                    verdict = "fail"

        if verdict != "ok" and blocking:
            blocked.append(f"slice:{name}/{metric}")

        label = {"ok": "ok"}.get(verdict, "BLOCK" if blocking else "warn")
        lines.append(f"  slice:{name}/{metric:<15} {val:<8.4f} {json.dumps(s):<40} {note:<28} {label}")

    return blocked, lines


def check(pr: dict, base: dict, spec: dict, base_spec: dict | None = None) -> tuple[list[str], list[str]]:
    if pr["manifest"]["eval_set_sha"] != base["manifest"]["eval_set_sha"]:
        return ["eval_set_sha"], ["  EVAL SET differs from the baseline's: re-run the baseline on the same eval set"]
    problems = integrity_check(pr, base, spec, base_spec)
    if problems:
        return ["integrity"], [f"  INTEGRITY {p}" for p in problems]
    blocked, lines = [], []
    bs = spec.get("bootstrap", {})
    for m in spec["metrics"]:
        mid, th, val = m["id"], m.get("threshold", {}), pr["metrics"].get(m["id"])
        verdict, note = "ok", ""
        if val is None:
            verdict = "missing"
        elif "max" in th and val > th["max"]:
            verdict = "fail"
        elif "min" in th and val < th["min"]:
            verdict = "fail"
        elif "max_increase" in th and base["metrics"].get(mid):
            if val > base["metrics"][mid] * (1 + th["max_increase"]):
                verdict = "fail"
        if th.get("no_significant_drop") and val is not None:
            a, b = per_item(pr, mid), per_item(base, mid)
            keys = sorted(set(a) & set(b))
            d, lo, hi = stats.paired_bootstrap([a[k] for k in keys], [b[k] for k in keys],
                                               n_resamples=bs.get("n_resamples", 1000), rng=bs.get("rng", 2027))
            note = f"Δ {d:+.3f} CI [{lo:+.3f}, {hi:+.3f}]"
            if hi < 0:
                verdict = "fail"
        if verdict != "ok" and m.get("blocking"):
            blocked.append(mid)
        label = {"ok": "ok", "missing": "MISSING"}.get(verdict, "BLOCK" if m.get("blocking") else "warn")
        lines.append(f"  {mid:<22} {val!s:<8} {json.dumps(th):<40} {note:<28} {label}")
    if spec.get("slices"):
        sb, sl = slice_check(pr, base, spec)
        blocked += sb
        lines += sl
    return blocked, lines


def main(argv: list[str] | None = None) -> int:
    utf8_stdio()
    ap = argparse.ArgumentParser(prog="lab9.gate")
    ap.add_argument("--pr", required=True)
    ap.add_argument("--baseline", required=True)
    ap.add_argument("--spec", default=str(SPEC))
    ap.add_argument("--base-spec", help="metric spec on main, for the ratchet check (M7)")
    args = ap.parse_args(argv)
    pr = json.loads(Path(args.pr).read_text(encoding="utf-8"))
    base = json.loads(Path(args.baseline).read_text(encoding="utf-8"))
    base_spec = load_spec(Path(args.base_spec)) if args.base_spec else None
    spec = load_spec(Path(args.spec))
    blocked, lines = check(pr, base, spec, base_spec)
    print(f"gate: PR {pr.get('run_id')} vs main {base.get('run_id')} · eval set {pr.get('manifest', {}).get('eval_set_sha')}")
    for line in lines:
        print(line)
    if blocked:
        print(f"exit 1 — blocked: {', '.join(blocked)}")
        return 1
    print("exit 0 — merge")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
