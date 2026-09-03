'''Validate the saved calendar and require both source labels.'''

import argparse
from pathlib import Path

from .calendar_writer import validate_ics
from .models import SourceError


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('file', type=Path, nargs='?', default=Path('docs/zastal.ics'))
    args = parser.parse_args()
    events = validate_ics(args.file.read_bytes()).walk('VEVENT')
    sources = {str(e['X-SOURCE']) for e in events}
    if sources != {'plk', 'fiba'}:
        raise SourceError('Calendar must contain both PLK and FIBA')
    counts = {source: sum(str(e['X-SOURCE']) == source for e in events) for source in sorted(sources)}
    print(f'VALID: {len(events)} events, unique UIDs, chronological order, {counts}')


if __name__ == '__main__':
    main()
