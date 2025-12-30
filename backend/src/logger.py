import logging
import sys
from datetime import datetime, timezone

import structlog
from sqlmodel import Session, create_engine
from src.models.db import Logs


class DatabaseHandler(logging.Handler):
    """Custom logging handler that writes logs to the database."""
    
    def __init__(self, engine, tenant_id: str, service_name: str):
        super().__init__()
        self.engine = engine
        self.tenant_id = tenant_id
        self.service_name = service_name
    
    def emit(self, record):
        try:
            log_entry = Logs(
                tenant_id=self.tenant_id,
                service_name=self.service_name,
                log=self.format(record),
                timestamp=datetime.now(timezone.utc),
            )
            with Session(self.engine) as session:
                session.add(log_entry)
                session.commit()
        except Exception:
            self.handleError(record)


def configure_logger(engine, tenant_id: str, service_name: str):
    """Configure structlog once at application startup."""
    structlog.configure(
        processors=[
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
    db_handler = DatabaseHandler(engine, tenant_id, service_name)
    logging.root.addHandler(db_handler)


def get_logger(name: str = __name__):
    """Get a logger instance with the given name."""
    return structlog.get_logger(name)