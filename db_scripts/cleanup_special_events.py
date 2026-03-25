#!/usr/bin/env python3
"""
Remove bookings that were imported from special Google Calendar event types
(birthdays, focus time, out of office, working location).

These were accidentally imported before the event type filter was added.

Usage:
    python db_scripts/cleanup_special_events.py              # dry run (preview)
    python db_scripts/cleanup_special_events.py --apply      # actually delete
"""
import sys
import os
import argparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dotenv import load_dotenv
load_dotenv()

SPECIAL_TYPES = ('birthday', 'focusTime', 'outOfOffice', 'workingLocation')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--apply', action='store_true', help='Actually delete (default is dry run)')
    parser.add_argument('--company-id', type=int, help='Only clean one company')
    args = parser.parse_args()

    from src.services.database import get_database
    from src.services.google_calendar_oauth import get_company_google_calendar
    from psycopg2.extras import RealDictCursor

    db = get_database()
    conn = db.get_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)

    # Find companies with Google Calendar connected
    if args.company_id:
        cursor.execute("SELECT id, company_name FROM companies WHERE id = %s", (args.company_id,))
    else:
        cursor.execute(
            "SELECT id, company_name FROM companies "
            "WHERE google_credentials_json IS NOT NULL"
        )
    companies = cursor.fetchall()
    db.return_connection(conn)

    if not companies:
        print("No companies with Google Calendar connected.")
        return

    total_found = 0
    total_deleted = 0

    for company in companies:
        cid = company['id']
        cname = company['company_name']
        print(f"\nCompany {cid} ({cname}):")

        gcal = get_company_google_calendar(cid, db)
        if not gcal:
            print("  [SKIP] Could not connect to Google Calendar")
            continue

        # Get all bookings with a real calendar_event_id
        conn = db.get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute("""
            SELECT b.id, b.calendar_event_id, b.service_type, b.appointment_time,
                   c.name as client_name
            FROM bookings b
            LEFT JOIN clients c ON b.client_id = c.id
            WHERE b.company_id = %s
              AND b.calendar_event_id IS NOT NULL
              AND b.calendar_event_id NOT LIKE 'db_%%'
        """, (cid,))
        bookings = cursor.fetchall()
        db.return_connection(conn)

        print(f"  Checking {len(bookings)} bookings with gcal event IDs...")

        to_delete = []
        for booking in bookings:
            event_id = booking['calendar_event_id']
            try:
                event = gcal.service.events().get(
                    calendarId=gcal.calendar_id, eventId=event_id
                ).execute()
                event_type = event.get('eventType', 'default')
                if event_type in SPECIAL_TYPES:
                    to_delete.append({
                        'id': booking['id'],
                        'event_id': event_id,
                        'event_type': event_type,
                        'client_name': booking['client_name'],
                        'service_type': booking['service_type'],
                        'appointment_time': booking['appointment_time'],
                    })
            except Exception as e:
                # Event might not exist anymore — check by service type as fallback
                if '404' in str(e) or 'notFound' in str(e):
                    # If it was imported as "Imported Event" with birthday-like name, flag it
                    svc = booking['service_type'] or ''
                    name = booking['client_name'] or ''
                    if svc == 'Imported Event' and ('birthday' in name.lower() or 'happy birthday' in name.lower()):
                        to_delete.append({
                            'id': booking['id'],
                            'event_id': event_id,
                            'event_type': 'birthday (inferred - event gone)',
                            'client_name': booking['client_name'],
                            'service_type': booking['service_type'],
                            'appointment_time': booking['appointment_time'],
                        })
                    continue
                print(f"    [WARN] Could not check event {event_id}: {e}")

        # Also find bookings that look like birthdays by name (covers cases where gcal event is gone)
        already_found_ids = {item['id'] for item in to_delete}
        conn2 = db.get_connection()
        cursor2 = conn2.cursor(cursor_factory=RealDictCursor)
        cursor2.execute("""
            SELECT b.id, b.calendar_event_id, b.service_type, b.appointment_time,
                   c.name as client_name, c.email as client_email
            FROM bookings b
            LEFT JOIN clients c ON b.client_id = c.id
            WHERE b.company_id = %s
              AND b.service_type = 'Imported Event'
              AND (
                LOWER(c.name) LIKE '%%birthday%%'
                OR LOWER(c.name) LIKE '%%bday%%'
                OR LOWER(c.name) LIKE '%%b day%%'
              )
        """, (cid,))
        name_matches = cursor2.fetchall()
        db.return_connection(conn2)
        for bk in name_matches:
            if bk['id'] not in already_found_ids:
                to_delete.append({
                    'id': bk['id'],
                    'event_id': bk['calendar_event_id'] or 'N/A',
                    'event_type': 'birthday (matched by name)',
                    'client_name': bk['client_name'],
                    'service_type': bk['service_type'],
                    'appointment_time': bk['appointment_time'],
                })

        if not to_delete:
            print("  ✅ No special event bookings found")
            continue

        total_found += len(to_delete)
        print(f"  Found {len(to_delete)} special event booking(s):")
        for item in to_delete:
            print(f"    - Booking {item['id']}: {item['event_type']} | {item['client_name']} | {item['service_type']} | {item['appointment_time']}")

        if args.apply:
            conn = db.get_connection()
            cursor = conn.cursor()
            for item in to_delete:
                bid = item['id']
                # Delete worker assignments first (FK constraint)
                cursor.execute("DELETE FROM worker_assignments WHERE booking_id = %s", (bid,))
                cursor.execute("DELETE FROM appointment_notes WHERE booking_id = %s", (bid,))
                cursor.execute("DELETE FROM bookings WHERE id = %s", (bid,))
            conn.commit()
            db.return_connection(conn)
            total_deleted += len(to_delete)
            print(f"  🗑️  Deleted {len(to_delete)} booking(s)")
        else:
            print(f"  ⏭️  Dry run — run with --apply to delete")

    print(f"\nDone. Found {total_found} special event bookings.")
    if args.apply:
        print(f"Deleted {total_deleted} bookings.")
    else:
        print("Dry run — no changes made. Run with --apply to delete.")


if __name__ == "__main__":
    main()
