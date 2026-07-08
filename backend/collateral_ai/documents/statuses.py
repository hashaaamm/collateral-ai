class DocumentStatus:
    PENDING = "pending"
    PROCESSING = "processing"
    PROCESSED = "processed"
    FAILED = "failed"

    CHOICES = [
        (PENDING, "Pending"),
        (PROCESSING, "Processing"),
        (PROCESSED, "Processed"),
        (FAILED, "Failed"),
    ]
