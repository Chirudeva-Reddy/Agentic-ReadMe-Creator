# Evaluation & Benchmark Protocol

To rigorously evaluate **Agentic ReadMe Creator** as an academic or portfolio benchmark, we use the following experimental setup.

---

## 1. Test Dataset (~20 Repositories)

- **Gold Standard References (5)**:
  - `duet`: CLI / multi-agent evaluation tool.
  - `body2health`: Fullstack ML and health metrics platform.
  - `odoo-salon-erp`: Dockerized ERP suite.
  - `ClaimLens`: Computer vision total-loss insurance triage pipeline.
  - `NLP-Proj`: Hallucination detection and NLP evaluation suite.
- **External Open Source Projects (15)**:
  - Diverse repositories across Python, TypeScript, Rust, and Go covering CLI tools, web APIs, data pipelines, and ML models.

---

## 2. Core Evaluation Metrics

1. **Claim Accuracy (% Grounded)**:
   - Percentage of numeric claims, badge statistics, and versions in the generated README that resolve to an exact key in `facts.json`.
   - **Target**: 100%. Seeded fact drifts (e.g. 52 vs 44 tests) must be caught deterministically.
2. **Render Validity (Broken Asset Rate)**:
   - Must achieve **0 broken assets** under GitHub Markdown rendering rules.
   - 0 repo-relative `<video>` tags.
   - 0 oversized hero GIFs (> 5MB).
   - 100% alt-text coverage.
3. **The 5-Second Test**:
   - Human peer review: Can an evaluator explain what the project does within 5 seconds of viewing the above-the-fold README section?
4. **Rubric LLM-Judge Score (1–5 Scale)**:
   - Independent judge scoring clarity, pain framing, groundedness, and lack of AI marketing fluff.
5. **Human Edit Distance on PR**:
   - Levenshtein character edit distance and token diff between generated PR README and human-accepted version.

---

## 3. Ablation Studies

| Ablation Configuration | Hypothesis Tested |
| :--- | :--- |
| **Full Pipeline vs. Single-Agent Single-Pass** | Measures whether multi-agent separation of grounding, production, and verification yields higher accuracy than monolithic prompting. |
| **Pipeline With vs. Without Claim Auditor** | Isolates the impact of the Claim Auditor in preventing fact drift and catching leaked development jargon. |
| **With vs. Without Locked Story Spec** | Tests Cognition's finding on conflicting decisions: proves that parallel producers drift in pitch and numbers unless constrained by an immutable contract. |
