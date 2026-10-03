class RetryableGenerationError(Exception):
    """Generation failed due to a transient/retryable cause (e.g., empty LLM response).

    These failures should NOT count toward the consecutive failure limit
    in the pipeline orchestrator — they are retried freely up to max_iterations.
    """
