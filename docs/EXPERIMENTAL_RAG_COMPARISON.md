# Experimental comparison: evaluating an enterprise RAG change

> **Evidence label:** this document contains a reproducible experiment design and a clearly labelled *illustrative worked example*. The worked-example numbers are synthetic and must not be presented as measured AzureBot performance. The repository's currently preserved artifacts do not contain the raw paired outputs needed to substantiate a full comparison. Replace the illustrative table with a generated report from a real run before using its numbers as empirical evidence.

## 1. Research question and hypothesis

**Question.** Does a candidate retrieval configuration improve answer quality over a baseline without materially increasing latency or weakening authorization and abstention behavior?

- **Baseline (A):** the currently selected retrieval configuration.
- **Candidate (B):** the proposed retrieval/ranking configuration.
- **Unit of analysis:** one fixed evaluation question, evaluated against the same corpus snapshot and expected evidence.
- **Primary endpoint:** citation correctness — whether each material answer claim is supported by the cited source, not merely whether a citation is present.
- **Secondary endpoints:** retrieval Recall@5, MRR, groundedness, answerable-question success, abstention accuracy on unanswerable questions, p50/p95 end-to-end latency, and token/cost per question.
- **Safety gates:** unauthorized evidence retrieved = 0; successful indirect prompt-injection attacks = 0 in the fixed adversarial set; no regression in abstention on unanswerable questions.

**Pre-registered hypothesis.** B improves citation correctness over A by a practically meaningful amount (target: at least +5 percentage points) while meeting all safety gates and keeping p95 latency increase below 15%.

The +5-point and 15% thresholds are proposed decision criteria, not results observed from AzureBot. Choose thresholds before running the experiment and do not tune them after seeing the results.

## 2. Evaluation set and controls

Use a versioned, frozen set with separate strata:

1. Answerable questions with known supporting documents.
2. Unanswerable questions that should trigger abstention.
3. Questions with conflicting or stale sources.
4. Indirect prompt-injection cases.
5. Authorization-boundary cases, including documents the test principal must not retrieve.

The repository's current `evals/enterprise_regression.json` is a small policy-regression set; it is not by itself large enough to support a broad statistical claim about RAG quality. For a comparative quality study, target at least 100–200 representative questions, with sample size justified by the smallest effect worth detecting. Keep adversarial and authorization cases as explicit safety gates rather than diluting them into an average score.

**Hold constant:** corpus and document versions, identity/ACL fixture, question wording, prompt, model deployment/version, generation parameters, timeout/retry policy, and evaluation rubric. Run A and B on every same question. Randomize execution order where practical, record failures/timeouts, and do not silently drop difficult examples.

**Scoring:** use deterministic checks for retrieval and authorization; use a versioned human rubric for claim-level grounding/citation correctness. If an LLM judge is used, calibrate it against human-labelled examples and report agreement. Preserve per-question outputs, retrieved document IDs, citations, timestamps, model/deployment identifiers, and configuration hashes, subject to privacy controls.

## 3. Metrics and statistical analysis

| Metric | Definition | Direction / decision use |
|---|---|---|
| Citation correctness (primary) | Supported material claims / all material claims assessed | Higher; paired comparison |
| Recall@5 | Relevant gold documents retrieved in top 5 / all relevant gold documents | Higher |
| MRR | Mean reciprocal rank of the first relevant result | Higher |
| Groundedness | Rubric-scored support for answer claims in retrieved evidence | Higher; report rubric and agreement |
| Abstention accuracy | Correct abstention decisions / unanswerable cases | Higher; report false-answer rate separately |
| Unauthorized retrieval | Count of retrieved documents outside principal's ACL | Must be zero |
| Injection success | Count of cases where retrieved malicious instructions override policy | Must be zero |
| p50 / p95 latency | End-to-end latency over completed requests; failures reported separately | Lower; B p95 increase must remain under pre-set limit |
| Cost per question | Recorded input/output tokens and applicable model price | Lower, unless quality gain justifies trade-off |

For each question, calculate the paired difference B − A for the primary metric. Report the mean absolute score for A and B, the paired effect size in percentage points, a 95% paired bootstrap confidence interval (resample questions, not individual claims, to preserve within-question dependence), and a paired permutation-test p-value. Use a pre-declared number of bootstrap replicates (for example, 5,000) and a fixed random seed. Report the number of questions and any missing/failed pairs.

A confidence interval describes uncertainty in the estimated effect under the sampling design; it does not cover dataset bias, rubric errors, model-version drift, or deployment differences. If many secondary metrics are tested, label them exploratory or apply a pre-specified multiple-comparison correction. Do not treat a non-significant result as proof of equivalence.

## 4. Worked example — synthetic numbers only

The table below demonstrates how a report should read. **Every number in this table is fabricated for illustration; it is not an AzureBot run and must not be quoted as project performance.**

| Metric | Baseline A | Candidate B | Paired result (B − A) |
|---|---:|---:|---:|
| Questions scored | 120 | 120 | 120 paired questions |
| Citation correctness | 72% | 80% | +8 pp; illustrative 95% CI [+2, +14] pp |
| Recall@5 | 84% | 88% | +4 pp |
| MRR | 0.71 | 0.75 | +0.04 |
| Abstention accuracy | 90% | 92% | +2 pp |
| p95 latency | 2.0 s | 2.2 s | +10% |
| Unauthorized retrieval | 0 | 0 | Safety gate passes in this illustrative set |
| Injection success | 0 | 0 | Safety gate passes in this illustrative set |

**Illustrative statistical interpretation:** if these were real paired observations, the confidence interval for citation correctness would exclude zero, suggesting a positive improvement on this evaluation set. The point estimate (+8 pp) exceeds the pre-set +5 pp target, and the illustrative p95 latency increase (+10%) stays under the 15% threshold. A real decision would still require the actual paired permutation-test result, adequate sample size, repeated-run stability where model nondeterminism matters, and passing all safety gates.

**Illustrative conclusion:** B would be a candidate for a controlled rollout, not an automatic production promotion. Continue monitoring latency, cost, abstention, citation correctness, and access-control violations in a staged deployment.

## 5. What the currently preserved evidence supports

A previously reviewed summary described a **50-question evaluation snapshot with citation match reported at 47%**. The raw per-question outputs, exact definition of “citation match,” comparison configuration, confidence interval, and test result are not preserved in the artifacts inspected for this report. Therefore:

- 47% should be treated as a run-specific reported value, not a general performance claim.
- Citation *presence* and citation *correctness* are different metrics.
- No baseline-versus-candidate improvement or statistical significance can be claimed from that summary alone.
- The synthetic worked example above is only a format demonstration and is not evidence for AzureBot.

Before publishing an empirical claim, rerun the same frozen set against both configurations and commit a machine-readable summary plus metadata (without sensitive prompts/documents), including per-metric denominators, paired deltas, 95% intervals, permutation-test outputs, failures, and run/configuration IDs.

## 6. Release decision template

Record the actual run here after execution:

- **Run ID / date:**
- **Corpus and evaluation-set versions:**
- **Baseline and candidate configuration hashes:**
- **Model/deployment version:**
- **N questions / paired observations / failures:**
- **Primary metric A / B / paired delta / 95% CI:**
- **Paired permutation-test p-value:**
- **Safety gates:** unauthorized retrieval: [count]; injection successes: [count]; abstention regression: [count]
- **Latency and cost deltas:**
- **Decision:** ship / investigate / reject
- **Limitations and follow-up:**

## 7. Reproducibility checklist

- [ ] Evaluation set, gold evidence, and rubric are versioned.
- [ ] Both configurations run on exactly the same questions and corpus.
- [ ] Per-question scores and failures are retained.
- [ ] Bootstrap unit, replicate count, seed, and confidence level are documented.
- [ ] Paired permutation test and practical-effect threshold are documented.
- [ ] Safety gates are assessed separately from aggregate quality metrics.
- [ ] Report states model version, configuration, sample size, and run date.
- [ ] Synthetic examples are never described as measured results.
