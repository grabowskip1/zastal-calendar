'''CLI: fetch both competitions before publishing a single validated file.'''

import argparse
from dataclasses import asdict
from datetime import UTC, datetime
import json
import logging
from pathlib import Path

from . import fiba, plk
from .calendar_writer import write_calendar
from .http_client import HttpClient
from .models import Game

LOG = logging.getLogger(__name__)


def generate(output: Path, client: HttpClient | None = None,
             *, repair_integrity: bool = False) -> tuple[bool, list[Game]]:
    client = client or HttpClient()
    # Any failed source, including any required match detail, aborts before writing.
    games = plk.fetch(client) + fiba.fetch(client)
    changed = write_calendar(output, games, repair_integrity=repair_integrity)
    return changed, games


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=Path('docs/zastal.ics'))
    parser.add_argument('--snapshot-dir', type=Path, help='Optional raw HTTP audit directory')
    parser.add_argument('--report', type=Path, help='Optional JSON audit report; not part of ICS')
    parser.add_argument('--repair-integrity', action='store_true',
                        help='Rebuild hash-mismatched existing events from official data, preserving UID/SEQUENCE')
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
    try:
        changed, games = generate(args.output, HttpClient(args.snapshot_dir),
                                 repair_integrity=args.repair_integrity)
        LOG.info('SUCCESS: %d games, changed=%s, timed=%d, TBD=%d', len(games), changed,
                 sum(g.start is not None for g in games), sum(g.start is None for g in games))
        if args.report:
            args.report.parent.mkdir(parents=True, exist_ok=True)
            args.report.write_text(json.dumps({
                'checked_at': datetime.now(UTC).isoformat(), 'changed': changed,
                'counts': {s: sum(g.source == s for g in games) for s in ('plk', 'fiba')},
                'games': [asdict(g) for g in sorted(games, key=lambda g: (g.day, g.uid))],
            }, ensure_ascii=False, indent=2, default=str) + '\n', encoding='utf-8')
        return 0
    except Exception:
        LOG.exception('Generation failed; publication aborted')
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
