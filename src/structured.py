'''Extract JSON data supplied by official Next.js sites, independent of CSS.'''

from collections.abc import Iterator
import json
import re
from typing import Any

from bs4 import BeautifulSoup

from .models import SourceError


def walk(value: Any) -> Iterator[dict[str, Any]]:
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from walk(child)
    elif isinstance(value, list):
        for child in value:
            yield from walk(child)


def flight_text(html: str) -> str:
    chunks: list[str] = []
    decoder = json.JSONDecoder()
    for tag in BeautifulSoup(html, 'html.parser').find_all('script'):
        script = tag.string or tag.get_text()
        for match in re.finditer(r'self\.__next_f\.push\(\s*', script):
            try:
                packet, _ = decoder.raw_decode(script[match.end():])
            except ValueError as exc:
                raise SourceError('Malformed Next.js JSON packet') from exc
            if isinstance(packet, list) and len(packet) > 1 and packet[0] == 1:
                if isinstance(packet[1], str):
                    chunks.append(packet[1])
    return ''.join(chunks)


def documents(html: str) -> list[Any]:
    '''Decode JSON, never execute JavaScript. Join Flight chunks before decoding.'''
    soup = BeautifulSoup(html, 'html.parser')
    result: list[Any] = []
    for tag in soup.find_all('script'):
        script = tag.string or tag.get_text()
        if tag.get('type') in {'application/json', 'application/ld+json'}:
            try:
                result.append(json.loads(script))
            except ValueError:
                continue
    for line in flight_text(html).splitlines():
        # Flight includes module, text and dependency records; only JSON data rows matter.
        match = re.match(r'^[0-9a-f]+:([\[{].*)$', line)
        if match:
            try:
                result.append(json.loads(match[1]))
            except ValueError:
                continue
    if not result:
        raise SourceError('No structured source data; possible error page or schema change')
    return result


def records(html: str) -> list[dict[str, Any]]:
    return [record for doc in documents(html) for record in walk(doc)]


def unique_collection(items: list[dict[str, Any]], key: str) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for item in items:
        identity = str(item[key])
        if identity in result:
            raise SourceError(f'Duplicate source record: {identity}')
        result[identity] = item
    return result
