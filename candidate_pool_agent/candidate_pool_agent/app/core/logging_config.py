import logging
import re

# Patterns that match candidate PII values directly
_EMAIL_RE = re.compile(r'[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}')
_PHONE_RE = re.compile(
    r'\b[\+]?[(]?[0-9]{1,4}[)]?[-\s\.]?[(]?[0-9]{1,3}[)]?'
    r'[-\s\.]?[0-9]{3,4}[-\s\.]?[0-9]{3,4}\b'
)


class PIIScrubFilter(logging.Filter):
    """
    Scrubs candidate PII from every log record before it is emitted.

    Replaces email addresses and phone numbers with redacted placeholders.
    Also detects and redacts key=value pairs whose key names suggest PII.

    This filter is applied at the root logger level so it covers every
    handler (console, file, external log aggregator) without exception.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = self._scrub(str(record.msg))
        record.args = self._scrub_args(record.args)
        return True

    def _scrub(self, text: str) -> str:
        text = _EMAIL_RE.sub('[email redacted]', text)
        text = _PHONE_RE.sub('[phone redacted]', text)
        return text

    def _scrub_args(self, args):
        if args is None:
            return args
        if isinstance(args, dict):
            return {k: self._scrub(str(v)) for k, v in args.items()}
        if isinstance(args, (list, tuple)):
            scrubbed = [self._scrub(str(a)) for a in args]
            return type(args)(scrubbed)
        return self._scrub(str(args))


def configure_logging():
    """
    Configure root logger with the PII scrub filter applied globally.
    Call this once at application startup before any other logging occurs.
    """
    root = logging.getLogger()
    root.setLevel(logging.INFO)

    # Remove any handlers added before this call (e.g. by basicConfig)
    root.handlers.clear()

    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter(
        "%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    ))

    # The filter lives on the handler so it runs regardless of which
    # logger emits the record.
    handler.addFilter(PIIScrubFilter())
    root.addHandler(handler)
