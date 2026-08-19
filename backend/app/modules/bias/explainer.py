import shap
import pandas as pd
import numpy as np
from app.modules.bias import gemini_client

# Known proxy features that correlate with protected attributes
PROXY_KEYWORDS = [
    "gap", "zip", "cost", "insurance", "prestige",
    "address", "neighborhood", "redline", "parental"
]


def get_shap_values(model, X_train, X_test):
    explainer = shap.TreeExplainer(model)

    X_sample = X_test.iloc[:min(100, len(X_test))]
    shap_values = explainer.shap_values(X_sample)

    if isinstance(shap_values, list):
        shap_values = shap_values[1]
    elif shap_values.ndim == 3:
        shap_values = shap_values[:, :, 1]

    importance = (
        pd.DataFrame({
            "feature": X_sample.columns,
            "importance": np.abs(shap_values).mean(axis=0)
        })
        .sort_values("importance", ascending=False)
        .reset_index(drop=True)
    )

    top = importance.head(5).to_dict("records")

    # detect proxy variables from ACTUAL features in this dataset
    proxies = [
        f["feature"] for f in top
        if any(kw in f["feature"].lower() for kw in PROXY_KEYWORDS)
    ]

    return {
        "top_features": top,
        "proxy_features": proxies  # real proxies from actual CSV columns
    }



def _fallback_explanation(bias_metrics: dict, group_stats: dict) -> str:
    di = bias_metrics.get("disparate_impact") or 0
    spd = bias_metrics.get("statistical_parity_diff") or 0
    status = bias_metrics.get("status", "unknown")

    group_line = ""
    if group_stats:
        sorted_groups = sorted(
            group_stats.items(), key=lambda x: x[1].get("positive_rate", 0)
        )
        least, most = sorted_groups[0], sorted_groups[-1]
        group_line = (
            f"'{most[0]}' has an approval rate of {most[1].get('positive_rate', 0)*100:.1f}%, "
            f"vs {least[1].get('positive_rate', 0)*100:.1f}% for '{least[0]}'. "
        )

    verdict = (
        f"Disparate Impact is {di:.2f} (legal threshold is 0.80), so this model is "
        f"{'likely violating EEOC fairness guidelines' if di < 0.8 else 'within the legal threshold'}. "
    )
    fix = "Review proxy features correlated with the sensitive attribute and retrain on rebalanced data."
    return f"{group_line}{verdict}{fix}"


def explain_results(bias_metrics: dict, root_causes: dict) -> str:
    """
    Plain-English summary of bias_metrics + root_causes for the Report tab.
    Falls back to a templated explanation if Gemini is unavailable.
    """
    group_stats = root_causes.get("group_stats", {}) if isinstance(root_causes, dict) else {}

    prompt = f"""
You are an AI fairness expert. Be extremely concise.

Bias analysis results:
- Group stats: {group_stats}
- Disparate Impact: {bias_metrics.get('disparate_impact')} (below 0.8 = biased, EEOC threshold)
- Statistical Parity Difference: {bias_metrics.get('statistical_parity_diff')} (above 0.1 = biased)
- Equalized Odds: {bias_metrics.get('equalized_odds')}
- Status: {bias_metrics.get('status')}

Write exactly 3 sentences. No more.
Sentence 1: Which group is disadvantaged and by how much (use actual numbers).
Sentence 2: What this means in practical/legal terms.
Sentence 3: One specific next step.

Rules: no intros, no conclusions, no filler, plain language for a non-technical hiring manager, under 60 words total.
"""

    try:
        return gemini_client.generate_explanation(prompt)
    except Exception as e:
        if gemini_client._is_api_error(e):
            return _fallback_explanation(bias_metrics, group_stats)
        raise