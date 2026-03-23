#!/usr/bin/env python3
"""
Bidirectional sync between the database and Google Calendar.

Phase 1 (push): DB bookings → Google Calendar events
Phase 2 (pull): Google Calendar events → DB bookings

Usage:
    python db_scripts/sync_gcal.py                  # sync all companies
    python db_scripts/sync_gcal.py --company-id 5   # sync one company
    python db_scripts/sync_gcal.py --dry-run         # preview without writing
    python db_scripts/sync_gcal.py --push-only       # only DB → Google
    python db_scripts/sync_gcal.py --pull-only       # only Google → DB
"""
import sys
import os
import re
import argparse
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()


def sync_company(company_id: int, db, dry_run: bool = False,
                 push: bool = True, pull: bool = True):
    from src.services.google_calendar_oauth import get_company_google_calendar

    gcal = get_company_google_calendar(company_id, db)
    if not gcal:
        print(f"  [SKIP] Company {company_id}: Google Calendar not connected")
        return {}

    stats = {
        'push_created': 0, 'push_updated': 0, 'push_skipped': 0, 'push_errors': 0,
        'pull_imported': 0, 'pull_skipped': 0, 'pull_errors': 0,
    }

    bookings = db.get_all_bookings(company_id=company_id)
    now = datetime.now()

    # Track known gcal event IDs so pull phase can skip them
    known_gcal_ids = set()
    for b in bookings:
        eid = b.get('calendar_event_id', '')
        if eid and not str(eid).startswith('db_'):
            known_gcal_ids.add(eid)

    # ── Phase 1: Push (DB → Google) ───────────────────────────────
    if push:
        print(f"    [PUSH] DB → Google Calendar")
        for booking in bookings:
            if booking.get('status') == 'cancelled':
                stats['push_skipped'] += 1
                continue

            is_completed = booking.get('status') == 'completed'

            appt_time = booking.get('appointment_time')
            if not appt_time:
                stats['push_skipped'] += 1
                continue
            if isinstance(appt_time, str):
                try:
                    appt_time = datetime.fromisoformat(appt_time.replace('Z', '+00:00')).replace(tzinfo=None)
                except Exception:
                    stats['push_skipped'] += 1
                    continue
            elif hasattr(appt_time, 'replace'):
                appt_time = appt_time.replace(tzinfo=None)

            # Skip past bookings unless they're completed (fix their gcal display)
            if appt_time <= now and not is_completed:
                stats['push_skipped'] += 1
                continue

            customer_name = booking.get('client_name') or booking.get('customer_name') or 'Customer'
            service = booking.get('service_type') or 'Job'
            duration = booking.get('duration_minutes', 60)
            phone = booking.get('phone_number') or ''
            address = booking.get('address') or ''
            summary = f"{'✅ ' if is_completed else ''}{service} - {customer_name}"
            desc = (
                f"Synced from BookedForYou\n"
                f"{'Status: COMPLETED\n' if is_completed else ''}"
                f"Customer: {customer_name}\n"
                f"Phone: {phone}\n"
                f"Address: {address}\n"
                f"Duration: {duration} mins"
            )

            existing_event_id = booking.get('calendar_event_id', '')
            has_real_gcal = existing_event_id and not str(existing_event_id).startswith('db_')
            bid = booking.get('id', '?')

            if has_real_gcal:
                print(f"      [{bid}] UPDATE  {summary}  {appt_time.strftime('%Y-%m-%d %H:%M')}  {duration}min")
                if not dry_run:
                    try:
                        gcal.reschedule_appointment(
                            existing_event_id, appt_time, duration_minutes=duration,
                            description=desc, summary=summary
                        )
                        stats['push_updated'] += 1
                    except Exception as e:
                        print(f"      [{bid}] ERROR: {e}")
                        stats['push_errors'] += 1
                else:
                    stats['push_updated'] += 1
            elif not is_completed:
                # Only create new gcal events for active bookings, not completed ones
                print(f"      [{bid}] CREATE  {summary}  {appt_time.strftime('%Y-%m-%d %H:%M')}  {duration}min")
                if not dry_run:
                    try:
                        gcal_event = gcal.book_appointment(
                            summary=summary, start_time=appt_time,
                            duration_minutes=duration, description=desc, phone_number=phone
                        )
                        if gcal_event and booking.get('id'):
                            new_id = gcal_event.get('id')
                            db.update_booking(bid, calendar_event_id=new_id, company_id=company_id)
                            if new_id:
                                known_gcal_ids.add(new_id)
                        stats['push_created'] += 1
                    except Exception as e:
                        print(f"      [{bid}] ERROR: {e}")
                        stats['push_errors'] += 1
                else:
                    stats['push_created'] += 1

    # ── Phase 2: Pull (Google → DB) ───────────────────────────────
    if pull:
        print(f"    [PULL] Google Calendar → DB")
        try:
            gcal_events = gcal.get_future_events(days_ahead=90)
        except Exception as e:
            print(f"      ERROR fetching events: {e}")
            gcal_events = []

        for event in gcal_events:
            gcal_id = event['id']
            if gcal_id in known_gcal_ids:
                stats['pull_skipped'] += 1
                continue

            summary = event.get('summary', '').strip()
            if not summary:
                stats['pull_skipped'] += 1
                continue

            # Skip events originally created by this app (avoids re-importing
            # orphaned bookings whose DB record was deleted).
            desc = event.get('description', '')
            ext_private = event.get('extendedProperties', {}).get('private', {})
            if ext_private.get('bookedForYou') == 'true' or 'Synced from BookedForYou' in desc:
                stats['pull_skipped'] += 1
                continue

            start_dt = event['start']
            duration = event.get('duration_minutes', 60)

            # Parse customer name and service from summary
            customer_name = summary
            service_type = 'Imported Event'
            if ' - ' in summary:
                parts = summary.split(' - ', 1)
                service_part = parts[0].strip()
                name_part = parts[1].strip()
                for prefix in ['URGENT:', 'SCHEDULED:', 'EMERGENCY:']:
                    if service_part.upper().startswith(prefix):
                        service_part = service_part[len(prefix):].strip()
                        break
                if name_part:
                    customer_name = name_part
                    service_type = service_part or 'Imported Event'

            # Extract phone from description
            phone = ''
            desc = event.get('description', '')
            if desc:
                phone_match = re.search(r'(?:Phone|Customer Phone)[:\s]*([+\d\s\-()]{7,})', desc, re.IGNORECASE)
                if phone_match:
                    phone = phone_match.group(1).strip()

            # Try to extract email from description
            import_email = None
            if desc:
                email_match = re.search(r'[\w.+-]+@[\w-]+\.[\w.-]+', desc)
                if email_match:
                    import_email = email_match.group(0).strip()

            # External events may have no contact info — use placeholder
            if not phone and not import_email:
                import_email = f"imported-{gcal_id[:12]}@external.calendar"

            print(f"      IMPORT  {summary}  {start_dt.strftime('%Y-%m-%d %H:%M')}  {duration}min")

            if not dry_run:
                try:
                    client_id = db.find_or_create_client(
                        name=customer_name, phone=phone or None,
                        email=import_email, company_id=company_id
                    )
                    booking_id = db.add_booking(
                        client_id=client_id, calendar_event_id=gcal_id,
                        appointment_time=start_dt.strftime('%Y-%m-%d %H:%M:%S'),
                        service_type=service_type, phone_number=phone or None,
                        email=import_email if not phone else None,
                        company_id=company_id, duration_minutes=duration
                    )
                    if booking_id:
                        known_gcal_ids.add(gcal_id)
                        stats['pull_imported'] += 1
                    else:
                        # add_booking returned None — likely a duplicate
                        stats['pull_skipped'] += 1
                except Exception as e:
                    if 'UniqueViolation' in type(e).__name__ or 'unique constraint' in str(e).lower():
                        stats['pull_skipped'] += 1
                    else:
                        print(f"      ERROR: {e}")
                        stats['pull_errors'] += 1
            else:
                stats['pull_imported'] += 1

    return stats


def main():
    parser = argparse.ArgumentParser(description="Bidirectional sync: DB ↔ Google Calendar")
    parser.add_argument("--company-id", type=int, help="Sync a single company")
    parser.add_argument("--dry-run", action="store_true", help="Preview without writing")
    parser.add_argument("--push-only", action="store_true", help="Only push DB → Google")
    parser.add_argument("--pull-only", action="store_true", help="Only pull Google → DB")
    args = parser.parse_args()

    do_push = not args.pull_only
    do_pull = not args.push_only

    from src.services.database import get_database
    db = get_database()

    if args.dry_run:
        print("=== DRY RUN — no changes will be made ===\n")

    direction = "push+pull"
    if args.push_only:
        direction = "push only (DB → Google)"
    elif args.pull_only:
        direction = "pull only (Google → DB)"
    print(f"Sync direction: {direction}\n")

    if args.company_id:
        company_ids = [args.company_id]
    else:
        conn = db.get_connection()
        from psycopg2.extras import RealDictCursor
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute(
            "SELECT id, company_name FROM companies "
            "WHERE google_calendar_connected = true OR google_calendar_refresh_token IS NOT NULL"
        )
        rows = cur.fetchall()
        db.return_connection(conn)
        company_ids = [r['id'] for r in rows]
        print(f"Found {len(company_ids)} companies with Google Calendar connected.\n")

    totals = {
        'push_created': 0, 'push_updated': 0, 'push_skipped': 0, 'push_errors': 0,
        'pull_imported': 0, 'pull_skipped': 0, 'pull_errors': 0,
    }

    for cid in company_ids:
        print(f"  Company {cid}:")
        s = sync_company(cid, db, dry_run=args.dry_run, push=do_push, pull=do_pull)
        for k in totals:
            totals[k] += s.get(k, 0)
        if s:
            print(f"    → push: created={s.get('push_created',0)}, updated={s.get('push_updated',0)}, errors={s.get('push_errors',0)}")
            print(f"    → pull: imported={s.get('pull_imported',0)}, skipped={s.get('pull_skipped',0)}, errors={s.get('pull_errors',0)}")
        print()

    print(f"Done. Totals:")
    print(f"  Push: created={totals['push_created']}, updated={totals['push_updated']}, errors={totals['push_errors']}")
    print(f"  Pull: imported={totals['pull_imported']}, skipped={totals['pull_skipped']}, errors={totals['pull_errors']}")
    if args.dry_run:
        print("(Dry run — no changes written. Run without --dry-run to apply.)")


if __name__ == "__main__":
    main()
