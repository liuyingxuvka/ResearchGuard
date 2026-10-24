"""Purpose: Expose SourceGuard package metadata and public model helpers.
Repository: https://github.com/liuyingxuvka/ResearchGuard
Skill: SourceGuard
Math boundary: Expected utility ranks search value, not factual truth or calibrated probability.
CLI: researchguard source plan <model.yaml>
Boundary: Source candidates and evidence anchors require downstream TraceGuard/LogicGuard review before final claims."""

from __future__ import annotations

from researchguard._exports import lazy_exports

_PUBLIC_API = {
    'researchguard.source.schema': (
        'BeliefState',
        'EvidenceAnchor',
        'Gap',
        'GapClosureBasis',
        'GapQualification',
        'GapTransition',
        'GraphEdge',
        'Lead',
        'Observation',
        'PlanResult',
        'ReplanComparison',
        'ScoredAction',
        'SearchAction',
        'SourceCoverageDimension',
        'SourceCoverageUniverse',
        'SourceDepthPolicy',
        'SourceDepthResult',
        'SourceObjectDepthRow',
        'SourceRecord',
    ),
    'researchguard.source.depth': (
        'apply_observation_and_replan',
        'build_source_coverage_universe',
        'build_source_depth',
        'model_fingerprint',
    ),
    'researchguard.source.task_iteration': (
        'GAP_REDUCTION_LEVELS',
        'SEARCH_ITERATION_RESULT_SCHEMA',
        'SEARCH_OUTCOME_PREDICTION_SCHEMA',
        'NativeDepthRevalidation',
        'ProtectedGapRevalidation',
        'RealizedSearchOutcome',
        'SearchCandidateReview',
        'SearchIterationResult',
        'SearchOutcomePrediction',
        'SearchPredictionError',
        'compare_search_outcome',
        'derive_realized_search_outcome',
        'freeze_search_outcome_prediction',
        'revalidate_native_depth',
        'review_search_candidate',
        'run_search_iteration',
        'validate_search_prediction_binding',
        'affected_source_obligations',
    ),
    'researchguard': (
        '__version__',
    ),
    'researchguard.source.stop_decision': (
        'SearchStopDecision',
        'SearchStopInput',
        'SearchStopStatus',
        'decide_search_stop',
    ),
}


__all__ = [
    '__version__',
    'BeliefState',
    'EvidenceAnchor',
    'Gap',
    'GapClosureBasis',
    'GapQualification',
    'GapTransition',
    'GraphEdge',
    'Lead',
    'Observation',
    'NativeDepthRevalidation',
    'ProtectedGapRevalidation',
    'PlanResult',
    'ReplanComparison',
    'ScoredAction',
    'SearchAction',
    'SearchCandidateReview',
    'SearchIterationResult',
    'SearchOutcomePrediction',
    'SearchPredictionError',
    'RealizedSearchOutcome',
    'SourceCoverageDimension',
    'SourceCoverageUniverse',
    'SourceDepthPolicy',
    'SourceDepthResult',
    'SourceObjectDepthRow',
    'SourceRecord',
    'SearchStopDecision',
    'SearchStopInput',
    'SearchStopStatus',
    'GAP_REDUCTION_LEVELS',
    'SEARCH_ITERATION_RESULT_SCHEMA',
    'SEARCH_OUTCOME_PREDICTION_SCHEMA',
    'apply_observation_and_replan',
    'build_source_coverage_universe',
    'build_source_depth',
    'model_fingerprint',
    'compare_search_outcome',
    'derive_realized_search_outcome',
    'freeze_search_outcome_prediction',
    'revalidate_native_depth',
    'review_search_candidate',
    'run_search_iteration',
    'validate_search_prediction_binding',
    'affected_source_obligations',
    'decide_search_stop',
]


__getattr__, __dir__ = lazy_exports(_PUBLIC_API, globals())
