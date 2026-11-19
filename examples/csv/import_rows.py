def import_rows(rows, save):
    rows = list(rows)
    if any(not row.get("id") for row in rows):
        return 0
    return save(rows)
