"""Exceptions raised by the sales package."""


class SalesDataError(Exception):
    """Raised for problems loading the sales CSV file itself (missing file, unreadable file,
    etc.) as opposed to problems with an individual data row, which are collected instead of
    raised (see :class:`sales.models.MalformedRow`).

    Carries a clear, user-facing message so callers can present a clean error instead of a raw
    traceback.
    """
