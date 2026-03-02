"""Report rendering for context-eval results: terminal tables, JSON output."""

from __future__ import annotations

import math
import statistics as _statistics

from rich.console import Console
from rich.table import Table

from coderace.context_eval import ContextEvalResult, TrialResult
from coderace.statistics import _confidence_interval_95, _mean, _stddev, _t_critical_95


def _pass_rate(results: list[TrialResult]) -> float:
    if not results:
        return 0.0
    return sum(1 for r in results if r.passed) / len(results)


def _mean_score(results: list[TrialResult]) -> float:
    if not results:
        return 0.0
    return _mean([r.score for r in results])


def _mean_time(results: list[TrialResult]) -> float:
    if not results:
        return 0.0
    return _mean([r.wall_time for r in results])


def _score_ci_95(results: list[TrialResult]) -> tuple[float, float]:
    if not results:
        return (0.0, 0.0)
    return _confidence_interval_95([r.score for r in results])


def _cohens_d(baseline: list[float], treatment: list[float]) -> float:
    """Compute Cohen's d effect size between two groups."""
    if not baseline or not treatment:
        return 0.0
    mean_b = _mean(baseline)
    mean_t = _mean(treatment)
    if len(baseline) < 2 and len(treatment) < 2:
        return 0.0
    # Pooled standard deviation
    var_b = _statistics.variance(baseline) if len(baseline) >= 2 else 0.0
    var_t = _statistics.variance(treatment) if len(treatment) >= 2 else 0.0
    n_b = len(baseline)
    n_t = len(treatment)
    pooled_var = ((n_b - 1) * var_b + (n_t - 1) * var_t) / (n_b + n_t - 2) if (n_b + n_t - 2) > 0 else 0.0
    pooled_sd = math.sqrt(pooled_var)
    if pooled_sd == 0:
        return 0.0
    return (mean_t - mean_b) / pooled_sd


def _delta_ci_95(baseline: list[float], treatment: list[float]) -> tuple[float, float, float]:
    """Compute delta (treatment - baseline) with 95% CI.

    Returns (delta, ci_low, ci_high).
    """
    if not baseline or not treatment:
        return (0.0, 0.0, 0.0)
    mean_b = _mean(baseline)
    mean_t = _mean(treatment)
    delta = mean_t - mean_b

    n_b = len(baseline)
    n_t = len(treatment)
    var_b = _statistics.variance(baseline) if n_b >= 2 else 0.0
    var_t = _statistics.variance(treatment) if n_t >= 2 else 0.0

    se = math.sqrt(var_b / n_b + var_t / n_t) if (n_b > 0 and n_t > 0) else 0.0

    # Use Welch-Satterthwaite for degrees of freedom
    if se == 0:
        return (delta, delta, delta)

    num = (var_b / n_b + var_t / n_t) ** 2
    denom_parts = []
    if n_b > 1:
        denom_parts.append((var_b / n_b) ** 2 / (n_b - 1))
    if n_t > 1:
        denom_parts.append((var_t / n_t) ** 2 / (n_t - 1))
    denom = sum(denom_parts)
    df = int(num / denom) if denom > 0 else 1
    df = max(1, min(df, 30))

    t_val = _t_critical_95(df + 1)  # _t_critical_95 expects sample_size, not df
    margin = t_val * se
    return (delta, delta - margin, delta + margin)


def _verdict(delta: float, ci_low: float, ci_high: float) -> str:
    """Generate a summary verdict string."""
    if ci_low > 0:
        return f"Context file improved performance by {delta:+.1f} points (CI: [{ci_low:.1f}, {ci_high:.1f}])"
    elif ci_high < 0:
        return f"Context file degraded performance by {delta:+.1f} points (CI: [{ci_low:.1f}, {ci_high:.1f}])"
    else:
        return f"No significant improvement detected (delta: {delta:+.1f}, CI: [{ci_low:.1f}, {ci_high:.1f}])"


def render_context_eval_terminal(result: ContextEvalResult, console: Console) -> None:
    """Render context-eval results as Rich terminal tables."""

    # Per-agent summary table
    table = Table(
        title=f"Context Eval: {result.context_file}",
        show_lines=True,
        expand=False,
    )
    table.add_column("Agent", style="cyan")
    table.add_column("Baseline Pass Rate", justify="right")
    table.add_column("Treatment Pass Rate", justify="right")
    table.add_column("Baseline Score", justify="right")
    table.add_column("Treatment Score", justify="right")
    table.add_column("Delta", justify="right")
    table.add_column("CI (95%)", justify="center")
    table.add_column("Effect Size", justify="right")

    all_baseline_scores: list[float] = []
    all_treatment_scores: list[float] = []

    for agent in result.agents:
        baseline = result.get_results(agent=agent, condition="baseline")
        treatment = result.get_results(agent=agent, condition="treatment")

        b_pass = _pass_rate(baseline)
        t_pass = _pass_rate(treatment)
        b_score = _mean_score(baseline)
        t_score = _mean_score(treatment)

        b_scores = [r.score for r in baseline]
        t_scores = [r.score for r in treatment]
        all_baseline_scores.extend(b_scores)
        all_treatment_scores.extend(t_scores)

        delta, ci_lo, ci_hi = _delta_ci_95(b_scores, t_scores)
        d = _cohens_d(b_scores, t_scores)

        delta_style = "[green]" if delta > 0 else "[red]" if delta < 0 else ""
        delta_end = "[/green]" if delta > 0 else "[/red]" if delta < 0 else ""

        table.add_row(
            agent,
            f"{b_pass:.0%}",
            f"{t_pass:.0%}",
            f"{b_score:.1f}",
            f"{t_score:.1f}",
            f"{delta_style}{delta:+.1f}{delta_end}",
            f"[{ci_lo:.1f}, {ci_hi:.1f}]",
            f"{d:.2f}",
        )

    console.print(table)

    # Per-task breakdown
    task_table = Table(
        title="Per-Task Breakdown",
        show_lines=True,
        expand=False,
    )
    task_table.add_column("Task", style="bold")
    task_table.add_column("Agent", style="cyan")
    task_table.add_column("Baseline", justify="right")
    task_table.add_column("Treatment", justify="right")
    task_table.add_column("Delta", justify="right")

    for task_name in result.tasks:
        for agent in result.agents:
            baseline = result.get_results(agent=agent, task_name=task_name, condition="baseline")
            treatment = result.get_results(agent=agent, task_name=task_name, condition="treatment")

            b_score = _mean_score(baseline)
            t_score = _mean_score(treatment)
            delta = t_score - b_score

            delta_style = "[green]" if delta > 0 else "[red]" if delta < 0 else ""
            delta_end = "[/green]" if delta > 0 else "[/red]" if delta < 0 else ""

            task_table.add_row(
                task_name,
                agent,
                f"{b_score:.1f}",
                f"{t_score:.1f}",
                f"{delta_style}{delta:+.1f}{delta_end}",
            )

    console.print()
    console.print(task_table)

    # Overall verdict
    delta, ci_lo, ci_hi = _delta_ci_95(all_baseline_scores, all_treatment_scores)
    v = _verdict(delta, ci_lo, ci_hi)
    console.print(f"\n[bold]{v}[/bold]")


def render_context_eval_json(result: ContextEvalResult) -> dict:
    """Render context-eval results as a JSON-serializable dict."""
    agents_data = []
    all_baseline_scores: list[float] = []
    all_treatment_scores: list[float] = []

    for agent in result.agents:
        baseline = result.get_results(agent=agent, condition="baseline")
        treatment = result.get_results(agent=agent, condition="treatment")

        b_scores = [r.score for r in baseline]
        t_scores = [r.score for r in treatment]
        all_baseline_scores.extend(b_scores)
        all_treatment_scores.extend(t_scores)

        delta, ci_lo, ci_hi = _delta_ci_95(b_scores, t_scores)
        d = _cohens_d(b_scores, t_scores)

        agents_data.append({
            "agent": agent,
            "baseline_pass_rate": _pass_rate(baseline),
            "treatment_pass_rate": _pass_rate(treatment),
            "baseline_mean_score": _mean_score(baseline),
            "treatment_mean_score": _mean_score(treatment),
            "delta": delta,
            "ci_95": [ci_lo, ci_hi],
            "effect_size": d,
        })

    tasks_data = []
    for task_name in result.tasks:
        for agent in result.agents:
            baseline = result.get_results(agent=agent, task_name=task_name, condition="baseline")
            treatment = result.get_results(agent=agent, task_name=task_name, condition="treatment")

            b_score = _mean_score(baseline)
            t_score = _mean_score(treatment)

            tasks_data.append({
                "task": task_name,
                "agent": agent,
                "baseline_mean_score": b_score,
                "treatment_mean_score": t_score,
                "delta": t_score - b_score,
                "baseline_passed": [r.passed for r in baseline],
                "treatment_passed": [r.passed for r in treatment],
            })

    delta, ci_lo, ci_hi = _delta_ci_95(all_baseline_scores, all_treatment_scores)

    return {
        "type": "context-eval",
        "context_file": result.context_file,
        "trials_per_condition": result.trials_per_condition,
        "agents": agents_data,
        "tasks": tasks_data,
        "summary": {
            "overall_delta": delta,
            "overall_ci_95": [ci_lo, ci_hi],
            "verdict": _verdict(delta, ci_lo, ci_hi),
        },
        "trials": [
            {
                "agent": r.agent,
                "task": r.task_name,
                "condition": r.condition,
                "trial": r.trial_number,
                "passed": r.passed,
                "wall_time": r.wall_time,
                "score": r.score,
                "error": r.error,
            }
            for r in result.results
        ],
    }
