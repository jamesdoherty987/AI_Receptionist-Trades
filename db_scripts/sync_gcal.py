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

import json as _json

# Maximum events to send in a single LLM batch call
_LLM_BATCH_SIZE = 40


def _build_fallback(summary: str) -> dict:
    """Return a safe fallback when LLM parsing isn't available."""
    return {
        'customer_name': '',
        'job_description': summary,
        'address': '',
        'phone': '',
    }


def parse_gcal_events_batch(events: list[dict]) -> list[dict]:
    """Parse multiple gcal events in a single LLM call.

    Each item in *events* should have keys 'summary' and 'description'.
    Returns a list of dicts (same order) with keys:
        customer_name, job_description, address, phone
    Falls back per-event on any error.
    """
    if not events:
        return []

    from src.services.llm_stream import get_openai_client

    # Build numbered event list for the prompt
    event_lines = []
    for i, ev in enumerate(events):
        line = f"{i + 1}. Title: {ev['summary']}"
        if ev.get('description'):
            # Truncate long descriptions to keep prompt reasonable
            desc_short = ev['description'][:300]
            line += f" | Description: {desc_short}"
        event_lines.append(line)

    prompt = (
        "Extract structured info from each Google Calendar event below.\n"
        "Return ONLY valid JSON: an object with a single key \"events\" containing "
        "an array of objects in the SAME ORDER as the input.\n"
        "Each object must have exactly these keys:\n"
        '  "customer_name": the person\'s name (empty string if not identifiable),\n'
        '  "job_description": what work/service is being done (empty string if unclear),\n'
        '  "address": any address or location mentioned (empty string if none),\n'
        '  "phone": any phone number mentioned (empty string if none)\n\n'
        "Rules:\n"
        "- Do NOT invent information that isn't present in the event.\n"
        "- If the title is only a person's name with no job info, job_description should be empty.\n"
        "- If the title is only a job/task description with no person's name, customer_name should be empty.\n"
        "- Generic titles like 'Meeting', 'Busy', 'Lunch' etc. have no customer — leave customer_name empty.\n"
        "- Look in both the title AND description for names, addresses, and phone numbers.\n\n"
        "Events:\n" + "\n".join(event_lines)
    )

    fallbacks = [_build_fallback(ev['summary']) for ev in events]

    try:
        client = get_openai_client()
        resp = client.chat.completions.create(
            model='gpt-4o-mini',
            messages=[{'role': 'user', 'content': prompt}],
            temperature=0,
            max_tokens=max(300, 150 * len(events)),
            response_format={'type': 'json_object'},
        )
        raw = resp.choices[0].message.content.strip()
        data = _json.loads(raw)

        # Handle both {"events": [...]} and direct [...] responses
        parsed_list = data.get('events', data) if isinstance(data, dict) else data
        if not isinstance(parsed_list, list):
            print(f"      [LLM batch] unexpected response shape, using fallbacks")
            return fallbacks

        # If LLM returned fewer/more items than expected, pad or truncate
        results = []
        for i, ev in enumerate(events):
            if i < len(parsed_list) and isinstance(parsed_list[i], dict):
                item = parsed_list[i]
                # Ensure all keys exist and are strings
                result = {}
                for key in ('customer_name', 'job_description', 'address', 'phone'):
                    val = item.get(key, '')
                    result[key] = val.strip() if isinstance(val, str) else ''
                results.append(result)
            else:
                results.append(fallbacks[i])

        return results

    except Exception as e:
        print(f"      [LLM batch fallback] {e}")
        return fallbacks


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
    from datetime import timedelta
    sync_cutoff = now - timedelta(days=30)

    # Check if worker invites are enabled for this company
    company = db.get_company(company_id)
    invite_workers = company.get('gcal_invite_workers', False) if company else False

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

            # Include future bookings + last 30 days of past bookings
            if appt_time < sync_cutoff:
                stats['push_skipped'] += 1
                continue

            existing_event_id = booking.get('calendar_event_id', '')
            has_real_gcal = existing_event_id and not str(existing_event_id).startswith('db_')

            # Skip bookings already synced and not modified since last sync
            if has_real_gcal:
                gcal_synced_at = booking.get('gcal_synced_at')
                updated_at = booking.get('updated_at')
                if gcal_synced_at and updated_at:
                    if hasattr(gcal_synced_at, 'replace'):
                        gcal_synced_at = gcal_synced_at.replace(tzinfo=None)
                    if hasattr(updated_at, 'replace'):
                        updated_at = updated_at.replace(tzinfo=None)
                    if updated_at <= gcal_synced_at:
                        stats['push_skipped'] += 1
                        continue

            customer_name = booking.get('client_name') or booking.get('customer_name') or 'Customer'
            service = booking.get('service_type') or 'Job'
            duration = booking.get('duration_minutes', 60)
            phone = booking.get('phone_number') or ''
            address = booking.get('address') or ''
            summary = f"{'✅ ' if is_completed else ''}{service} - {customer_name}"

            # Build worker info
            bid = booking.get('id', '?')
            job_workers = db.get_job_workers(bid, company_id=company_id) if bid != '?' else []
            worker_lines = ''
            if job_workers:
                worker_names = [f"{w['name']}{' (' + w['trade_specialty'] + ')' if w.get('trade_specialty') else ''}" for w in job_workers]
                worker_lines = f"\nWorkers: {', '.join(worker_names)}"

            desc = (
                f"Synced from BookedForYou\n"
                f"{'Status: COMPLETED\n' if is_completed else ''}"
                f"Customer: {customer_name}\n"
                f"Phone: {phone}\n"
                f"Address: {address}\n"
                f"Duration: {duration} mins"
                f"{worker_lines}"
            )

            # Build attendee list if enabled
            attendee_emails = None
            if invite_workers and job_workers:
                attendee_emails = [w['email'] for w in job_workers if w.get('email')]
                if not attendee_emails:
                    attendee_emails = None

            if has_real_gcal:
                print(f"      [{bid}] UPDATE  {summary}  {appt_time.strftime('%Y-%m-%d %H:%M')}  {duration}min")
                if not dry_run:
                    try:
                        result = gcal.reschedule_appointment(
                            existing_event_id, appt_time, duration_minutes=duration,
                            description=desc, summary=summary,
                            attendee_emails=attendee_emails
                        )
                        if result is not None:
                            stats['push_updated'] += 1
                            db.stamp_gcal_synced(bid, company_id=company_id)
                        else:
                            stats['push_skipped'] += 1
                    except Exception as e:
                        err_str = str(e)
                        if 'eventTypeRestriction' in err_str or 'birthday' in err_str.lower():
                            print(f"      [{bid}] SKIP (special event type)")
                            stats['push_skipped'] += 1
                        else:
                            print(f"      [{bid}] ERROR: {e}")
                            stats['push_errors'] += 1
                else:
                    stats['push_updated'] += 1
            else:
                # Create new gcal event for any booking in the sync window
                print(f"      [{bid}] CREATE  {summary}  {appt_time.strftime('%Y-%m-%d %H:%M')}  {duration}min")
                if not dry_run:
                    try:
                        gcal_event = gcal.book_appointment(
                            summary=summary, start_time=appt_time,
                            duration_minutes=duration, description=desc, phone_number=phone,
                            attendee_emails=attendee_emails
                        )
                        if gcal_event and booking.get('id'):
                            new_id = gcal_event.get('id')
                            db.update_booking(bid, calendar_event_id=new_id, company_id=company_id)
                            db.stamp_gcal_synced(bid, company_id=company_id)
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

        # First pass: filter to importable events
        importable = []
        for event in gcal_events:
            gcal_id = event['id']
            if gcal_id in known_gcal_ids:
                stats['pull_skipped'] += 1
                continue

            summary = event.get('summary', '').strip()
            if not summary:
                stats['pull_skipped'] += 1
                continue

            desc = event.get('description', '')
            ext_private = event.get('extendedProperties', {}).get('private', {})
            if ext_private.get('bookedForYou') == 'true' or 'Synced from BookedForYou' in desc:
                stats['pull_skipped'] += 1
                continue

            importable.append(event)

        # Batch LLM parse all importable events at once (in chunks)
        parsed_results = []
        for chunk_start in range(0, len(importable), _LLM_BATCH_SIZE):
            chunk = importable[chunk_start:chunk_start + _LLM_BATCH_SIZE]
            llm_input = [
                {'summary': ev.get('summary', ''), 'description': ev.get('description', '')}
                for ev in chunk
            ]
            parsed_results.extend(parse_gcal_events_batch(llm_input))

        # Counter for unnamed customers (per company sync run)
        unnamed_counter = 0

        # Second pass: import with parsed data
        for idx, event in enumerate(importable):
            gcal_id = event['id']
            summary = event.get('summary', '').strip()
            desc = event.get('description', '')
            start_dt = event['start']
            duration = event.get('duration_minutes', 60)

            parsed = parsed_results[idx] if idx < len(parsed_results) else _build_fallback(summary)

            customer_name = parsed.get('customer_name', '').strip()
            service_type = parsed.get('job_description', '').strip() or 'Imported Event'
            address_from_llm = parsed.get('address', '').strip()
            phone_from_llm = parsed.get('phone', '').strip()

            # If no customer name was found, generate a descriptive placeholder
            if not customer_name:
                unnamed_counter += 1
                customer_name = f"GCal Import #{unnamed_counter}"

            # Extract phone: prefer LLM-extracted, fall back to regex from description
            phone = phone_from_llm
            if not phone and desc:
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

            print(f"      IMPORT  \"{summary}\" → customer=\"{customer_name}\", job=\"{service_type}\"  {start_dt.strftime('%Y-%m-%d %H:%M')}  {duration}min")

            if not dry_run:
                try:
                    existing = db.get_booking_by_calendar_event_id(gcal_id)
                    if existing:
                        known_gcal_ids.add(gcal_id)
                        stats['pull_skipped'] += 1
                        continue

                    client_id = db.find_or_create_client(
                        name=customer_name, phone=phone or None,
                        email=import_email, company_id=company_id
                    )
                    booking_id = db.add_booking(
                        client_id=client_id, calendar_event_id=gcal_id,
                        appointment_time=start_dt.strftime('%Y-%m-%d %H:%M:%S'),
                        service_type=service_type, phone_number=phone or None,
                        email=import_email if not phone else None,
                        company_id=company_id, duration_minutes=duration,
                        address=address_from_llm or None
                    )
                    if booking_id:
                        known_gcal_ids.add(gcal_id)
                        stats['pull_imported'] += 1
                    else:
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
