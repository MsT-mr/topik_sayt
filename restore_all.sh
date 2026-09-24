#!/usr/bin/env bash
set -Eeuo pipefail

# TOPIK platform recovery script
# Usage:
#   bash restore_all.sh [BACKUP_DB]
#
# Examples:
#   # Local project: repair/import curriculum without replacing current DB
#   bash restore_all.sh
#
#   # Production (/data/db.sqlite3): restore users/progress from a backup, then repair content
#   DATABASE_PATH=/data/db.sqlite3 bash restore_all.sh /path/to/backup.sqlite3

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

if [[ ! -f manage.py || ! -d bot_app || ! -d config ]]; then
  echo "ERROR: restore_all.sh must be placed in the TOPIK project root (next to manage.py)." >&2
  exit 1
fi

PYTHON_BIN="${PYTHON_BIN:-python3}"
if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
  echo "ERROR: $PYTHON_BIN not found." >&2
  exit 1
fi

SOURCE_DB="${1:-}"

# Prefer an explicitly configured production DB. If /data exists, use it.
# Otherwise repair the local db.sqlite3.
if [[ -n "${DATABASE_PATH:-}" ]]; then
  TARGET_DB="$DATABASE_PATH"
elif [[ -d /data && -w /data ]]; then
  TARGET_DB="/data/db.sqlite3"
else
  TARGET_DB="$ROOT_DIR/db.sqlite3"
fi

mkdir -p "$(dirname "$TARGET_DB")" "$ROOT_DIR/backups"

# Choose settings module without forcing production requirements during local repair.
if [[ -n "${DJANGO_SETTINGS_MODULE:-}" ]]; then
  SETTINGS_MODULE="$DJANGO_SETTINGS_MODULE"
elif [[ "$TARGET_DB" == /data/* ]]; then
  SETTINGS_MODULE="config.production"
else
  SETTINGS_MODULE="config.settings"
fi
export DJANGO_SETTINGS_MODULE="$SETTINGS_MODULE"

# Keep Django and this script pointed at the same production DB.
if [[ "$SETTINGS_MODULE" == "config.production" ]]; then
  export DATABASE_PATH="$TARGET_DB"
fi

echo "============================================================"
echo "TOPIK recovery"
echo "Project : $ROOT_DIR"
echo "Target  : $TARGET_DB"
echo "Settings: $SETTINGS_MODULE"
[[ -n "$SOURCE_DB" ]] && echo "Source  : $SOURCE_DB"
echo "============================================================"

validate_sqlite() {
  local db="$1"
  "$PYTHON_BIN" - "$db" <<'PY'
import sqlite3, sys
p = sys.argv[1]
try:
    con = sqlite3.connect(f"file:{p}?mode=ro", uri=True)
    result = con.execute("PRAGMA integrity_check").fetchone()[0]
    con.close()
except Exception as e:
    print(f"ERROR: cannot open SQLite database: {e}", file=sys.stderr)
    raise SystemExit(2)
if result != "ok":
    print(f"ERROR: SQLite integrity_check failed: {result}", file=sys.stderr)
    raise SystemExit(3)
print("SQLite integrity_check: ok")
PY
}

sqlite_backup() {
  local src="$1"
  local dst="$2"
  "$PYTHON_BIN" - "$src" "$dst" <<'PY'
import os, sqlite3, sys, tempfile
src, dst = sys.argv[1], sys.argv[2]
os.makedirs(os.path.dirname(os.path.abspath(dst)), exist_ok=True)
fd, tmp = tempfile.mkstemp(prefix=".restore-", suffix=".sqlite3", dir=os.path.dirname(os.path.abspath(dst)))
os.close(fd)
try:
    s = sqlite3.connect(f"file:{src}?mode=ro", uri=True)
    d = sqlite3.connect(tmp)
    s.backup(d)
    d.close(); s.close()
    check = sqlite3.connect(tmp).execute("PRAGMA integrity_check").fetchone()[0]
    if check != "ok":
        raise RuntimeError(f"temporary backup integrity_check failed: {check}")
    os.replace(tmp, dst)
finally:
    if os.path.exists(tmp):
        os.unlink(tmp)
PY
}

STAMP="$(date +%Y%m%d-%H%M%S)"
SAFETY_BACKUP="$ROOT_DIR/backups/recovery-before-$STAMP.sqlite3"

# Always preserve the current target before changing anything.
if [[ -f "$TARGET_DB" ]]; then
  echo "[1/8] Checking current database..."
  validate_sqlite "$TARGET_DB"
  echo "      Safety backup -> $SAFETY_BACKUP"
  sqlite_backup "$TARGET_DB" "$SAFETY_BACKUP"
else
  echo "[1/8] Target database does not exist yet; Django will create it."
fi

# If a backup was supplied, restore it first. This is the part that restores
# students, progress, exam history, messages, etc. Curriculum imports alone
# cannot recreate user data.
if [[ -n "$SOURCE_DB" ]]; then
  SOURCE_DB="$(realpath "$SOURCE_DB")"
  if [[ ! -f "$SOURCE_DB" ]]; then
    echo "ERROR: backup database not found: $SOURCE_DB" >&2
    exit 1
  fi
  echo "[2/8] Validating supplied backup..."
  validate_sqlite "$SOURCE_DB"
  if [[ "$(realpath -m "$TARGET_DB")" != "$SOURCE_DB" ]]; then
    echo "      Restoring backup into $TARGET_DB"
    sqlite_backup "$SOURCE_DB" "$TARGET_DB"
  else
    echo "      Source and target are the same file; replacement skipped."
  fi
else
  echo "[2/8] No backup supplied; preserving existing users/progress and repairing content only."
fi

# Production settings intentionally require secrets/host configuration.
if [[ "$SETTINGS_MODULE" == "config.production" ]]; then
  if [[ -z "${DJANGO_SECRET_KEY:-}" || -z "${DJANGO_ALLOWED_HOSTS:-}" ]]; then
    cat >&2 <<'EOF'
ERROR: production recovery needs DJANGO_SECRET_KEY and DJANGO_ALLOWED_HOSTS.
Set the same values used by your hosting service, then rerun.
EOF
    exit 1
  fi
fi

echo "[3/8] Applying Django migrations..."
"$PYTHON_BIN" manage.py migrate --noinput

echo "[4/8] Restoring 1A-2B curriculum..."
"$PYTHON_BIN" manage.py import_curriculum

echo "[5/8] Restoring grammar exercises..."
"$PYTHON_BIN" manage.py import_exercises

echo "[6/8] Removing only the known empty orphan lesson (1B / lesson 1), if present..."
"$PYTHON_BIN" manage.py shell <<'PY'
from bot_app.models import Lesson
qs = Lesson.objects.filter(book_level='1B', number=1, words__isnull=True, grammar__isnull=True, exams__isnull=True).distinct()
count = qs.count()
if count:
    qs.delete()
print(f"Removed empty orphan lessons: {count}")
PY

echo "[7/8] Running checks and static collection..."
"$PYTHON_BIN" manage.py check
if [[ "$SETTINGS_MODULE" == "config.production" ]]; then
  "$PYTHON_BIN" manage.py collectstatic --noinput
fi

echo "[8/8] Final database summary..."
"$PYTHON_BIN" manage.py shell <<'PY'
from bot_app.models import (
    Student, Lesson, Vocabulary, Grammar, GrammarExercise,
    WordProgress, GrammarProgress, PracticeAttempt, ExamResult, StudentMessage,
)
models = [
    ("Students", Student),
    ("Lessons", Lesson),
    ("Vocabulary", Vocabulary),
    ("Grammar", Grammar),
    ("Grammar exercises", GrammarExercise),
    ("Word progress", WordProgress),
    ("Grammar progress", GrammarProgress),
    ("Practice attempts", PracticeAttempt),
    ("Exam results", ExamResult),
    ("Student messages", StudentMessage),
]
for label, model in models:
    print(f"{label:20} {model.objects.count()}")
print("Lesson map:")
for level in ("1A", "1B", "2A", "2B"):
    nums = list(Lesson.objects.filter(book_level=level).order_by("number").values_list("number", flat=True))
    print(f"  {level}: {nums}")
PY

echo
echo "RECOVERY COMPLETE"
echo "Target DB: $TARGET_DB"
if [[ -f "$SAFETY_BACKUP" ]]; then
  echo "Pre-recovery backup: $SAFETY_BACKUP"
fi
cat <<'EOF'

IMPORTANT:
- This script does NOT create a default admin password.
- If old students/progress were already lost from the live DB, you must supply a real SQLite backup as the first argument to recover them.
- Keep /data mounted as a persistent volume in production; otherwise data can disappear again after redeploy/restart.
EOF
