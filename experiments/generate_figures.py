#!/usr/bin/env python3
"""Generate paper figures and statistical tests from audit results."""

import csv
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from scipy import stats

RESULTS_DIR = Path(__file__).parent / "results"
FIGURES_DIR = Path(__file__).parent / "figures"
FIGURES_DIR.mkdir(exist_ok=True)

# ---------------------------------------------------------------------------
# Load audit data
# ---------------------------------------------------------------------------
def load_audits() -> list[dict]:
    csv_path = RESULTS_DIR / "audit_results.csv"
    with csv_path.open() as f:
        reader = csv.DictReader(f)
        return list(reader)


def load_audits_json() -> list[dict]:
    json_path = RESULTS_DIR / "audit_results.json"
    return json.loads(json_path.read_text())


# ---------------------------------------------------------------------------
# Figure 2: Governance Preservation Heatmap
# ---------------------------------------------------------------------------
def figure_2_heatmap(audits: list[dict]):
    """Two-panel heatmap: agents (x) × layers (y), color = GPR."""

    # Agent order by ID number
    agent_order = ["A1", "A2", "A3", "A4", "A5", "A6", "A7", "A8", "A9", "A10", "A11", "A12"]
    layers = ["GPR-L1", "GPR-L2", "GPR-L3"]
    layer_labels = ["L1 (Prompt)", "L2 (Permission)", "L3 (Platform)"]

    targets = ["claude-code", "copilot"]
    target_labels = ["Claude Code", "GitHub Copilot"]

    fig, axes = plt.subplots(1, 2, figsize=(14, 4), sharey=True)

    for idx, (target, label) in enumerate(zip(targets, target_labels)):
        # Build matrix
        matrix = np.zeros((len(layers), len(agent_order)))
        for a in audits:
            if a["Target"] != target:
                continue
            agent_id = a["Agent"]
            if agent_id not in agent_order:
                continue
            col = agent_order.index(agent_id)
            for row, layer_key in enumerate(layers):
                matrix[row, col] = float(a[layer_key])

        im = axes[idx].imshow(
            matrix, cmap="RdYlGn", vmin=0, vmax=1, aspect="auto"
        )
        axes[idx].set_title(label, fontsize=13, fontweight="bold", pad=10)
        axes[idx].set_xticks(range(len(agent_order)))
        axes[idx].set_xticklabels(agent_order, fontsize=9, rotation=45, ha="right")
        axes[idx].set_yticks(range(len(layer_labels)))
        axes[idx].set_yticklabels(layer_labels, fontsize=10)

        # Annotate cells
        for i in range(len(layers)):
            for j in range(len(agent_order)):
                val = matrix[i, j]
                color = "white" if val < 0.4 else "black"
                axes[idx].text(j, i, f"{val:.2f}", ha="center", va="center",
                               fontsize=8, color=color, fontweight="bold")

    fig.colorbar(im, ax=axes, shrink=0.8, label="GPR Score", pad=0.02)
    fig.suptitle("Figure 2: Governance Preservation Heatmap", fontsize=14, fontweight="bold", y=1.02)
    plt.tight_layout()
    fig.savefig(FIGURES_DIR / "fig2_heatmap.png", dpi=300, bbox_inches="tight")
    fig.savefig(FIGURES_DIR / "fig2_heatmap.pdf", bbox_inches="tight")
    plt.close(fig)
    print(f"  Figure 2 → {FIGURES_DIR / 'fig2_heatmap.png'}")


# ---------------------------------------------------------------------------
# Figure 3: GPR by Agent Complexity
# ---------------------------------------------------------------------------
def figure_3_complexity(audits: list[dict]):
    """Grouped bar chart: Low vs Medium vs High, Claude Code vs Copilot."""

    complexity_order = ["Low", "Medium", "High"]
    targets = ["claude-code", "copilot"]
    target_labels = ["Claude Code", "GitHub Copilot"]
    colors = ["#2196F3", "#FF9800"]

    # Aggregate GPR-Overall by complexity and target
    data: dict[str, dict[str, list[float]]] = {c: {t: [] for t in targets} for c in complexity_order}
    for a in audits:
        comp = a["Complexity"]
        tgt = a["Target"]
        if comp in complexity_order and tgt in targets:
            data[comp][tgt].append(float(a["GPR-Overall"]))

    x = np.arange(len(complexity_order))
    width = 0.35

    fig, ax = plt.subplots(figsize=(8, 5))

    for i, (target, label, color) in enumerate(zip(targets, target_labels, colors)):
        means = [np.mean(data[c][target]) if data[c][target] else 0 for c in complexity_order]
        stds = [np.std(data[c][target]) if len(data[c][target]) > 1 else 0 for c in complexity_order]
        bars = ax.bar(x + i * width, means, width, label=label, color=color,
                      yerr=stds, capsize=4, alpha=0.85, edgecolor="white", linewidth=0.5)
        # Value labels
        for bar, mean in zip(bars, means):
            ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.02,
                    f"{mean:.2f}", ha="center", va="bottom", fontsize=9, fontweight="bold")

    ax.set_xlabel("Agent Complexity", fontsize=12)
    ax.set_ylabel("GPR-Overall", fontsize=12)
    ax.set_title("Figure 3: GPR by Agent Complexity", fontsize=14, fontweight="bold")
    ax.set_xticks(x + width / 2)
    ax.set_xticklabels(complexity_order, fontsize=11)
    ax.set_ylim(0, 1.15)
    ax.legend(fontsize=10)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.axhline(y=1.0, color="gray", linestyle="--", alpha=0.3)

    plt.tight_layout()
    fig.savefig(FIGURES_DIR / "fig3_complexity.png", dpi=300, bbox_inches="tight")
    fig.savefig(FIGURES_DIR / "fig3_complexity.pdf", bbox_inches="tight")
    plt.close(fig)
    print(f"  Figure 3 → {FIGURES_DIR / 'fig3_complexity.png'}")


# ---------------------------------------------------------------------------
# Figure 4 (bonus): Elevation count by target
# ---------------------------------------------------------------------------
def figure_4_elevation(audits_json: list[dict]):
    """Stacked bar showing elevation counts by type per target."""

    targets = ["claude-code", "copilot"]
    target_labels = ["Claude Code", "Copilot"]

    # Count by artifact type per target
    type_counts: dict[str, dict[str, int]] = {}
    for a in audits_json:
        tgt = a["target"]
        if tgt not in targets:
            continue
        for ea in a.get("elevated_artifacts", []):
            art_type = ea["artifact_type"]
            type_counts.setdefault(art_type, {t: 0 for t in targets})
            type_counts[art_type][tgt] += 1

    art_types = sorted(type_counts.keys())
    x = np.arange(len(targets))
    width = 0.5

    fig, ax = plt.subplots(figsize=(8, 5))
    bottom = np.zeros(len(targets))
    cmap = plt.cm.Set3(np.linspace(0, 1, len(art_types)))

    for i, art_type in enumerate(art_types):
        vals = [type_counts[art_type].get(t, 0) for t in targets]
        ax.bar(x, vals, width, bottom=bottom, label=art_type, color=cmap[i], edgecolor="white")
        bottom += vals

    ax.set_xlabel("Target Platform", fontsize=12)
    ax.set_ylabel("Elevated Artifacts (count)", fontsize=12)
    ax.set_title("Figure 4: Governance Elevation by Type", fontsize=14, fontweight="bold")
    ax.set_xticks(x)
    ax.set_xticklabels(target_labels, fontsize=11)
    ax.legend(fontsize=8, loc="upper left", bbox_to_anchor=(1.02, 1))
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    plt.tight_layout()
    fig.savefig(FIGURES_DIR / "fig4_elevation.png", dpi=300, bbox_inches="tight")
    fig.savefig(FIGURES_DIR / "fig4_elevation.pdf", bbox_inches="tight")
    plt.close(fig)
    print(f"  Figure 4 → {FIGURES_DIR / 'fig4_elevation.png'}")


# ---------------------------------------------------------------------------
# Statistical tests
# ---------------------------------------------------------------------------
def run_statistical_tests(audits: list[dict]):
    """Run Wilcoxon, Spearman, and Chi-squared tests."""

    print("\n" + "=" * 60)
    print("STATISTICAL TESTS")
    print("=" * 60)

    # Organize by agent
    agents_cc: dict[str, float] = {}
    agents_cp: dict[str, float] = {}
    agent_complexity: dict[str, str] = {}

    for a in audits:
        agent_id = a["Agent"]
        if a["Target"] == "claude-code":
            agents_cc[agent_id] = float(a["GPR-Overall"])
            agent_complexity[agent_id] = a["Complexity"]
        elif a["Target"] == "copilot":
            agents_cp[agent_id] = float(a["GPR-Overall"])

    agent_order = sorted(set(agents_cc.keys()) & set(agents_cp.keys()))
    cc_scores = [agents_cc[a] for a in agent_order]
    cp_scores = [agents_cp[a] for a in agent_order]

    # 1. Wilcoxon signed-rank: GPR(Claude Code) vs GPR(Copilot)
    print("\n1. Wilcoxon signed-rank test: GPR(CC) vs GPR(CP)")
    print("-" * 50)
    stat, p_value = stats.wilcoxon(cc_scores, cp_scores)
    print(f"   Statistic: {stat:.4f}")
    print(f"   p-value:   {p_value:.6f}")
    print(f"   Significant (p<0.05): {'YES' if p_value < 0.05 else 'NO'}")
    print(f"   Mean CC: {np.mean(cc_scores):.4f}, Mean CP: {np.mean(cp_scores):.4f}")
    print(f"   Median CC: {np.median(cc_scores):.4f}, Median CP: {np.median(cp_scores):.4f}")

    # 2. Spearman correlation: complexity vs GPR-Overall
    print("\n2. Spearman correlation: Complexity vs GPR-Overall")
    print("-" * 50)
    complexity_map = {"Low": 1, "Medium": 2, "High": 3}

    # For Claude Code
    cc_complexities = [complexity_map[agent_complexity[a]] for a in agent_order]
    rho_cc, p_cc = stats.spearmanr(cc_complexities, cc_scores)
    print(f"   Claude Code: rho={rho_cc:.4f}, p={p_cc:.6f}")

    # For Copilot
    rho_cp, p_cp = stats.spearmanr(cc_complexities, cp_scores)
    print(f"   Copilot:     rho={rho_cp:.4f}, p={p_cp:.6f}")

    # Combined
    all_complex = cc_complexities + cc_complexities
    all_gpr = cc_scores + cp_scores
    rho_all, p_all = stats.spearmanr(all_complex, all_gpr)
    print(f"   Combined:    rho={rho_all:.4f}, p={p_all:.6f}")

    # 3. Chi-squared: governance loss distribution across L1/L2/L3
    print("\n3. Chi-squared test: Loss distribution across layers")
    print("-" * 50)
    # Count losses per layer across all conversions
    l1_lost = 0
    l2_lost = 0
    l3_lost = 0
    l1_total = 0
    l2_total = 0
    l3_total = 0

    for a in audits:
        l1_t = int(a["L1 Total"])
        l1_p = int(a["L1 Preserved"])
        l2_t = int(a["L2 Total"])
        l2_p = int(a["L2 Preserved"])
        l3_t = int(a["L3 Total"])
        l3_p = int(a["L3 Preserved"])

        l1_total += l1_t
        l2_total += l2_t
        l3_total += l3_t
        l1_lost += (l1_t - l1_p)
        l2_lost += (l2_t - l2_p)
        l3_lost += (l3_t - l3_p)

    # Contingency table: [preserved, lost] × [L1, L2, L3]
    observed = np.array([
        [l1_total - l1_lost, l2_total - l2_lost, l3_total - l3_lost],  # preserved
        [l1_lost, l2_lost, l3_lost],  # lost
    ])

    print(f"   Layer totals: L1={l1_total}, L2={l2_total}, L3={l3_total}")
    print(f"   Preserved:    L1={l1_total-l1_lost}, L2={l2_total-l2_lost}, L3={l3_total-l3_lost}")
    print(f"   Lost:         L1={l1_lost}, L2={l2_lost}, L3={l3_lost}")

    chi2, p_chi, dof, expected = stats.chi2_contingency(observed)
    print(f"   Chi2={chi2:.4f}, dof={dof}, p={p_chi:.6f}")
    print(f"   Significant (p<0.05): {'YES' if p_chi < 0.05 else 'NO'}")

    # Save results
    stats_results = {
        "wilcoxon": {
            "statistic": float(stat),
            "p_value": float(p_value),
            "significant": bool(p_value < 0.05),
            "mean_cc": float(np.mean(cc_scores)),
            "mean_cp": float(np.mean(cp_scores)),
        },
        "spearman_cc": {"rho": float(rho_cc), "p_value": float(p_cc)},
        "spearman_cp": {"rho": float(rho_cp), "p_value": float(p_cp)},
        "spearman_combined": {"rho": float(rho_all), "p_value": float(p_all)},
        "chi_squared": {
            "chi2": float(chi2),
            "dof": int(dof),
            "p_value": float(p_chi),
            "significant": bool(p_chi < 0.05),
            "observed": observed.tolist(),
        },
    }

    stats_path = RESULTS_DIR / "statistical_tests.json"
    stats_path.write_text(json.dumps(stats_results, indent=2))
    print(f"\n  Results saved → {stats_path}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    print("Loading audit data...")
    audits = load_audits()
    audits_json = load_audits_json()
    print(f"  {len(audits)} audit records loaded\n")

    print("Generating figures...")
    figure_2_heatmap(audits)
    figure_3_complexity(audits)
    figure_4_elevation(audits_json)

    run_statistical_tests(audits)

    print("\nDone.")
