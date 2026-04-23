def merge_labels(existing, add, clear):
    """Return the final label list after merge, or None if no API change needed.

    - clear=True  → wipe existing first, then add
    - clear=False → union of existing + add, preserving existing order
    - If result equals existing, return None to signal no-op.
    """
    if clear:
        result = []
        for label in add:
            if label not in result:
                result.append(label)
        return result if result != existing else None

    result = list(existing)
    for label in add:
        if label not in result:
            result.append(label)
    return result if result != existing else None
