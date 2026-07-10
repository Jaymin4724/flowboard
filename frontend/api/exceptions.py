class ApiError(Exception):
    """Raised for any non-2xx API response, after auto-refresh has already
    been attempted (if applicable). `message` is the best human-readable
    string we could pull from the response body."""

    def __init__(self, status_code: int, message: str):
        super().__init__(message)
        self.status_code = status_code
        self.message = message
