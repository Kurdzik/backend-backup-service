import logging
import sys
from contextlib import contextmanager
from datetime import datetime, timezone
from contextvars import ContextVar
from typing import Optional

import structlog
from sqlmodel import Session, create_engine
from src.models.db import Logs


# Context variable to store tenant_id and service_name per request
_tenant_context: ContextVar[Optional[dict]] = ContextVar("tenant_context", default=None)


class DatabaseHandler(logging.Handler):
    """Custom logging handler that writes logs to the database."""

    def __init__(self, engine):
        super().__init__()
        self.engine = engine

    def emit(self, record):
        try:
            # Get tenant info from context
            context = _tenant_context.get()
            if not context:
                return  # Skip logging if no tenant context

            tenant_id = context.get("tenant_id")
            service_name = context.get("service_name", "unknown")

            log_entry = Logs(
                tenant_id=tenant_id,
                service_name=service_name,
                log=self.format(record),
                timestamp=datetime.now(timezone.utc),
            )
            with Session(self.engine) as session:
                session.add(log_entry)
                session.commit()
        except Exception:
            self.handleError(record)


def configure_logger(engine, service_name: str = "default"):
    """Configure structlog once at application startup."""

    def add_context(logger, method_name, event_dict):
        """Add tenant_id from context to log dict."""
        context = _tenant_context.get()
        if context:
            event_dict["tenant_id"] = context.get("tenant_id")
            event_dict["service_name"] = context.get("service_name", service_name)
        return event_dict

    structlog.configure(
        processors=[
            add_context,  # Add tenant context first
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=logging.INFO,
    )

    # Add database handler
    db_handler = DatabaseHandler(engine)
    logging.root.addHandler(db_handler)


def get_logger(name: str = __name__):
    """Get a logger instance with the given name."""
    return structlog.get_logger(name)


@contextmanager
def tenant_context(tenant_id: str, service_name: str = "default"):
    """Context manager for setting tenant context.

    Usage:
        with tenant_context(tenant_id="user-123"):
            logger.info("user_action")  # tenant_id will be included
    """
    token = _tenant_context.set({"tenant_id": tenant_id, "service_name": service_name})
    try:
        yield
    finally:
        _tenant_context.reset(token)
