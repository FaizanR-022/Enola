"""SQLAlchemy models, one module per entity group.

Importing this package registers every table on `Base.metadata`; Alembic and the
test fixtures rely on that, so keep the import list complete.
"""

from enola.core.models.academics import Assessment, Course, FypMilestone
from enola.core.models.base import Base, IdMixin, TimestampMixin
from enola.core.models.documents import EMBEDDING_DIM, Document, DocumentChunk, scope_key
from enola.core.models.finance import (
    Account,
    Category,
    Settlement,
    SettlementAllocation,
    Transaction,
    TransactionSplit,
)
from enola.core.models.infra import (
    ActivityLog,
    ApprovalRequest,
    MemoryFact,
    Notification,
    UserSession,
)
from enola.core.models.jobs import Application, ApplicationEvent, Company, JobPosting
from enola.core.models.journal import LogEntry
from enola.core.models.learning import LearningGoal, LearningResource
from enola.core.models.people import Interaction, Person, PersonTag
from enola.core.models.projects import Project, ProjectSnapshot
from enola.core.models.tasks import Task, TaskLink

__all__ = [
    "EMBEDDING_DIM",
    "Account",
    "ActivityLog",
    "Application",
    "ApplicationEvent",
    "ApprovalRequest",
    "Assessment",
    "Base",
    "Category",
    "Company",
    "Course",
    "Document",
    "DocumentChunk",
    "FypMilestone",
    "IdMixin",
    "Interaction",
    "JobPosting",
    "LearningGoal",
    "LearningResource",
    "LogEntry",
    "MemoryFact",
    "Notification",
    "Person",
    "PersonTag",
    "Project",
    "ProjectSnapshot",
    "Settlement",
    "SettlementAllocation",
    "Task",
    "TaskLink",
    "TimestampMixin",
    "Transaction",
    "TransactionSplit",
    "UserSession",
    "scope_key",
]
