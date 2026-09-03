'''Bounded HTTP, transient retries and optional audit snapshots.'''

import hashlib
import logging
from pathlib import Path
from urllib.parse import urlparse

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from .models import SourceError

LOG = logging.getLogger(__name__)
ALLOWED_HOSTS = {'plk.pl', 'www.plk.pl', 'www.fiba.basketball', 'fiba.basketball',
                 'digital-api.fiba.basketball'}


class HttpClient:
    def __init__(self, snapshot_dir: Path | None = None) -> None:
        self.snapshot_dir = snapshot_dir

    def get(self, url: str, *, headers: dict[str, str] | None = None) -> str:
        if urlparse(url).scheme != 'https' or urlparse(url).hostname not in ALLOWED_HOSTS:
            raise SourceError(f'Unexpected official source URL: {url}')
        # Each request owns a session, so concurrent match-detail reads do not share state.
        with requests.Session() as session:
            retries = Retry(total=3, backoff_factor=0.8,
                            status_forcelist=[429, 500, 502, 503, 504],
                            allowed_methods={'GET'}, respect_retry_after_header=False)
            session.mount('https://', HTTPAdapter(max_retries=retries))
            try:
                response = session.get(url, timeout=(10, 40), headers={
                    'User-Agent': 'Mozilla/5.0 (compatible; ZastalCalendar/1.0)',
                    'Accept': 'text/html,application/json;q=0.9',
                    'Accept-Language': 'en,pl;q=0.8',
                    **(headers or {}),
                })
                response.raise_for_status()
            except requests.RequestException as exc:
                raise SourceError(f'HTTP retrieval failed for {url}: {exc}') from exc
            if urlparse(response.url).hostname not in ALLOWED_HOSTS:
                raise SourceError('Unexpected redirect away from the official source')
            if not response.content or len(response.content) > 20_000_000:
                raise SourceError('Empty or unexpectedly large response')
            response.encoding = 'utf-8'
            if self.snapshot_dir:
                self.snapshot_dir.mkdir(parents=True, exist_ok=True)
                key = hashlib.sha256(url.encode()).hexdigest()[:16]
                (self.snapshot_dir / f'{key}.html').write_text(response.text, encoding='utf-8')
                (self.snapshot_dir / f'{key}.url').write_text(url, encoding='utf-8')
            LOG.info('HTTP 200: %s (%d bytes)', url, len(response.content))
            return response.text
