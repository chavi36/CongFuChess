# This file is superseded by application/server/db/db.py.
# Kept as a shim so any legacy imports still resolve.
from application.server.db.db import init_db, add_user, get_user, update_range, UserRecord  # noqa: F401
