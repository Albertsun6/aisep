"""Tool-execution error of the AISEP library (docs/mcp-interface.md §7.1, codes §7.2). The CLI prints `message` to
stderr and exits 1; the MCP server turns it into an isError result with structuredContent.error."""

CODES = frozenset("""
INVALID_ARGUMENT UNKNOWN_TYPE ABSTRACT_TYPE INVALID_DATETIME ACTIVITY_TIME_ORDER GATE_UNKNOWN
MODULES_NOT_IN_REF PATH_OUTSIDE_ROOT NOT_A_GIT_REPO NOT_A_WORKTREE MODEL_NOT_FOUND ELEMENT_NOT_FOUND REF_NOT_FOUND
BRANCH_NOT_CHECKED_OUT WORKTREE_NOT_FOUND
PLAN_STALE STALE_BASE WRITE_REJECTED REFERENCED CASCADE_REQUIRED PROTECTED_RESOURCE IRI_EXISTS MODEL_INVALID GATE_FAILED
APPROVER_NOT_ALLOWED AGENT_NOT_ALLOWED STALE_HEAD
NO_MERGE_BASE AMBIGUOUS_MERGE_BASE DETACHED_HEAD DIRTY_WORKTREE COMMIT_FAILED
LOCKED CONFLICT WORKTREE_CHANGED
PARSE_FAILED EDIT_UNSAFE DIFF_PARSE_FAILED DIFF_BNODE_UNSUPPORTED QUERY_FAILED QUERY_NOT_READONLY QUERY_TIMEOUT
INTERNAL
""".split())
# §7.1 rule 4: retrying unchanged makes sense only for these (callers override for the exceptions §7.1 names)
RETRYABLE = frozenset({"LOCKED", "CONFLICT", "WORKTREE_CHANGED", "QUERY_TIMEOUT"})


class AisepError(Exception):
    def __init__(self, code, message, hint=None, details=None, retryable=None):
        assert code in CODES, code
        super().__init__(message)
        self.code, self.message, self.hint, self.details = code, message, hint, details or {}
        self.retryable = code in RETRYABLE if retryable is None else retryable

    def to_dict(self):
        d = {"code": self.code, "message": self.message, "retryable": self.retryable, "details": self.details}
        if self.hint:
            d["hint"] = self.hint
        return d
