class EvaluationProviderError(RuntimeError):
    """The AI provider could not complete a request."""


class EvaluationValidationError(RuntimeError):
    """The provider returned data that did not satisfy the evaluation schema."""
