"""Publish exactly the latest successfully emailed scanner stocks to GitHub.

This script is ONLY used by the scanner GitHub Actions workflow after SMTP
success and after alert-state / price-history caches have been saved.
It does not scan stocks, send email, or require any user-created PAT.

GitHub Actions must have `permissions: contents: write` for GITHUB_TOKEN.
The dashboard keeps using its separate READ-ONLY token.
"""
from __future__ import annotations

import base64
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

SNAPSHOT = Path('state/email_watchlist_snapshot.json')
PUBLISHED_PATH = 'state/alerts.json'


def request_json(method: str, url: str, token: str, payload: dict | None = None) -> tuple[int, dict]:
    headers = {
        'Authorization': f'Bearer {token}',
        'Accept': 'application/vnd.github+json',
        'X-GitHub-Api-Version': '2022-11-28',
        'User-Agent': 'regression-scanner-watchlist-publisher',
    }
    data = None
    if payload is not None:
        headers['Content-Type'] = 'application/json'
        data = json.dumps(payload, separators=(',', ':')).encode('utf-8')
    req = Request(url, data=data, headers=headers, method=method)
    try:
        with urlopen(req, timeout=25) as response:
            body = response.read(2_000_000)
            return response.status, json.loads(body) if body else {}
    except HTTPError as error:
        # Do not print exception bodies or headers (might expose private info).
        return error.code, {}
    except URLError as error:
        raise RuntimeError('GitHub connection failed while publishing emailed alerts') from error


def _timestamp(raw: str) -> datetime:
    stamp = datetime.fromisoformat(str(raw).replace('Z', '+00:00'))
    if stamp.tzinfo is None:
        raise ValueError('Email snapshot timestamp must include a timezone')
    return stamp.astimezone(timezone.utc)


def publish(snapshot_path: Path = SNAPSHOT) -> str:
    if not snapshot_path.is_file():
        return 'No successful scan email snapshot exists; nothing to publish.'
    raw = snapshot_path.read_bytes()
    if len(raw) > 1_000_000:
        raise ValueError('Refusing to publish oversized alert snapshot')
    payload = json.loads(raw.decode('utf-8'))
    last_email = payload.get('last_email')
    if not isinstance(last_email, dict) or not isinstance(last_email.get('stocks'), list):
        raise ValueError('Snapshot has no last_email stock list')
    sent = _timestamp(last_email.get('sent_at'))

    token = os.environ.get('GITHUB_TOKEN', '').strip()
    repo = os.environ.get('GITHUB_REPOSITORY', '').strip()
    branch = os.environ.get('GITHUB_REF_NAME', 'main').strip()
    if not token or not repo or '/' not in repo or not branch:
        raise RuntimeError('GitHub Actions token, repository, or branch is missing')

    api = f'https://api.github.com/repos/{quote(repo, safe="/")}/contents/{PUBLISHED_PATH}'
    for attempt in range(3):
        code, old = request_json('GET', api + '?' + urlencode({'ref': branch}), token)
        if code not in (200, 404):
            raise RuntimeError(f'Unable to read existing alert-history file (GitHub HTTP {code})')
        if code == 200:
            try:
                original = json.loads(base64.b64decode(old['content']).decode('utf-8'))
                previous = original.get('last_email', {})
                previous_time = previous.get('sent_at') if isinstance(previous, dict) else None
                if previous_time and _timestamp(previous_time) >= sent:
                    return 'Existing GitHub snapshot is as new or newer; skipped stale update.'
            except (KeyError, ValueError, TypeError):
                pass  # An older-format snapshot can be replaced.
        data = {
            'message': 'Update successfully emailed regression watchlist',
            'content': base64.b64encode(raw).decode('ascii'),
            'branch': branch,
        }
        if code == 200:
            sha = old.get('sha')
            if not sha:
                raise RuntimeError('Existing GitHub file has no SHA; refusing overwrite')
            data['sha'] = sha
        status, _ = request_json('PUT', api, token, data)
        if status in (200, 201):
            return (f'Published {len(last_email["stocks"])} emailed stocks '
                    f'for {sent.isoformat()} to {PUBLISHED_PATH}')
        if status != 409 or attempt == 2:
            raise RuntimeError(f'GitHub rejected watchlist publication (HTTP {status}); '
                               'check Actions Contents: write permission and branch rules')
    raise RuntimeError('Could not publish watchlist after several retries')


if __name__ == '__main__':
    print(publish(), flush=True)
