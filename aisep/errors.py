"""Tool-execution error of the AISEP library (docs/mcp-interface.md §7.1). The CLI prints `message` to stderr and exits 1;
the MCP server turns it into an isError result with structuredContent.error."""


class AisepError(Exception):
    def __init__(self, code, message, hint=None, details=None, retryable=False):
        super().__init__(message)
        self.code, self.message, self.hint, self.details, self.retryable = code, message, hint, details or {}, retryable
