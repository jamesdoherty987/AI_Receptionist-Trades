"""
Fix HTML-encoded strings in the database.

The old sanitize_string() was HTML-entity-encoding characters before storage,
causing values like "Smith&#x27;s Plumbing" instead of "Smith's Plumbing".
This script decodes those entities back to their original characters.

Usage:
    python db_scripts/fix_html_encoded_strings.py          # dry-run (default)
    python db_scripts/fix_html_encoded_strings.py --apply   # actually update rows
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

from src.services.database import get_database

# HTML entities that the old sanitize_string produced
REPLACEMENTS = [
    ('&amp;',  '&'),   # must be last when encoding, first when decoding
    ('&lt;',   '<'),
    ('&gt;',   '>'),
    ('&quot;', '"'),
    ('&#x27;', "'"),
]

# (table, column) pairs that went through sanitize_string
COLUMNS_TO_FIX = [
    ('companies', 'company_name'),
    ('companies', 'owner_name'),
    ('companies', 'phone'),
    ('companies', 'trade_type'),
]


def decode_entities(value: str) -> str:
    for encoded, decoded in REPLACEMENTS:
        value = value.replace(encoded, decoded)
    return value


def fix_encoded_strings(apply: bool = False):
    db = get_database()
    conn = db.get_connection()

    from psycopg2.extras import RealDictCursor
    cursor = conn.cursor(cursor_factory=RealDictCursor)

    total_fixed = 0

    try:
        for table, column in COLUMNS_TO_FIX:
            # Find rows containing any HTML entity
            cursor.execute(
                f"SELECT id, {column} FROM {table} "
                f"WHERE {column} LIKE %s OR {column} LIKE %s OR {column} LIKE %s "
                f"OR {column} LIKE %s OR {column} LIKE %s",
                tuple(f'%{ent}%' for ent, _ in REPLACEMENTS)
            )
            rows = cursor.fetchall()

            if not rows:
                print(f"  ✅ {table}.{column} — no encoded values found")
                continue

            print(f"  🔧 {table}.{column} — {len(rows)} row(s) to fix:")
            for row in rows:
                old_val = row[column]
                new_val = decode_entities(old_val)
                print(f"     [{row['id']}] {old_val!r}  →  {new_val!r}")

                if apply:
                    cursor.execute(
                        f"UPDATE {table} SET {column} = %s WHERE id = %s",
                        (new_val, row['id'])
                    )

            total_fixed += len(rows)

        if apply:
            conn.commit()
            print(f"\n✅ Done — updated {total_fixed} value(s).")
        else:
            print(f"\n🔍 Dry run — {total_fixed} value(s) would be updated. "
                  f"Run with --apply to commit changes.")

    except Exception as e:
        conn.rollback()
        print(f"\n❌ Error: {e}")
        raise
    finally:
        cursor.close()
        db.return_connection(conn)


if __name__ == "__main__":
    apply = '--apply' in sys.argv
    print(f"\n{'🚀 APPLYING FIXES' if apply else '🔍 DRY RUN (pass --apply to commit)'}:\n")
    fix_encoded_strings(apply=apply)
