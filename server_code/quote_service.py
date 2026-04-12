from anvil.tables import app_tables


def get_bucket_messages(bucket):
    rows = [r for r in app_tables.completion_messages.search(bucket=bucket, active=True)]
    rows.sort(key=lambda r: (r["sort_order"] or 9999, r.get_id()))
    return rows


def get_rotated_message(bucket, completed_session_count):
    rows = get_bucket_messages(bucket)
    if not rows:
        return {
            "skipped": "Any progress is great progress. It all adds up.",
            "standard": "Great work. Another workout in the bank.",
            "exceeded": "You pushed beyond the plan today. That extra effort matters.",
        }.get(bucket, "Great work.")
    return rows[completed_session_count % len(rows)]["message"]


import anvil.server


@anvil.server.callable
def get_rotated_message_client(bucket, completed_session_count):
    return get_rotated_message(bucket, int(completed_session_count or 0))
