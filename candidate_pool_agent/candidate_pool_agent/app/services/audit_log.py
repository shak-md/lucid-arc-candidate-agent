import logging
from datetime import datetime
from sqlalchemy import create_engine, Column, String, Integer, DateTime
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from app.core.config import settings
from app.models.schemas import AuditLogEntry

logger = logging.getLogger(__name__)

engine = create_engine(settings.AUDIT_LOG_DB_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine)


class Base(DeclarativeBase):
    pass


class AuditLog(Base):
    __tablename__ = "audit_log"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String, nullable=False, index=True)
    recruiter_id = Column(String, nullable=False, index=True)
    pool_id = Column(String, nullable=False)
    pool_name = Column(String, nullable=False)
    records_submitted = Column(Integer, nullable=False)
    records_succeeded = Column(Integer, nullable=False)
    records_failed = Column(Integer, nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow)


Base.metadata.create_all(engine)


def write_audit_log(entry: AuditLogEntry):
    db = SessionLocal()
    try:
        record = AuditLog(
            session_id=entry.session_id,
            recruiter_id=entry.recruiter_id,
            pool_id=entry.pool_id,
            pool_name=entry.pool_name,
            records_submitted=entry.records_submitted,
            records_succeeded=entry.records_succeeded,
            records_failed=entry.records_failed,
            timestamp=entry.timestamp,
        )
        db.add(record)
        db.commit()
        logger.info(f"Audit log written: session={entry.session_id} pool={entry.pool_name} submitted={entry.records_submitted}")
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to write audit log: {e}")
    finally:
        db.close()


def get_audit_log(recruiter_id: str | None = None, limit: int = 100) -> list[dict]:
    db = SessionLocal()
    try:
        query = db.query(AuditLog)
        if recruiter_id:
            query = query.filter(AuditLog.recruiter_id == recruiter_id)
        records = query.order_by(AuditLog.timestamp.desc()).limit(limit).all()
        return [
            {
                "session_id": r.session_id,
                "recruiter_id": r.recruiter_id,
                "pool_id": r.pool_id,
                "pool_name": r.pool_name,
                "records_submitted": r.records_submitted,
                "records_succeeded": r.records_succeeded,
                "records_failed": r.records_failed,
                "timestamp": r.timestamp.isoformat(),
            }
            for r in records
        ]
    finally:
        db.close()
