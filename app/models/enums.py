from enum import Enum


class DocumentStatus(str, Enum):
    """
    Lifecycle of a document in Recall.
    """

    uploaded = "uploaded"
    processing = "processing"
    ready = "ready"
    failed = "failed"
