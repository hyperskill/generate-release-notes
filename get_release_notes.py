from __future__ import annotations  # noqa: INP001

import json
import os
import re
import sys
from collections import defaultdict
from functools import cached_property
from typing import Final
from urllib.parse import urljoin

import httpx
from httpx import Response

YOUTRACK_API_URL: Final = os.getenv('YOUTRACK_API_URL', '')
YOUTRACK_API_TOKEN: Final = os.getenv('YOUTRACK_API_TOKEN', '')

if not YOUTRACK_API_TOKEN:
    print('YOUTRACK_API_TOKEN is not set', file=sys.stderr)  # noqa: T201
    sys.exit(1)


def get(url: str, params: dict[str, object] | None = None) -> Response:
    response = httpx.get(
        urljoin(YOUTRACK_API_URL, url),
        params=params,
        headers={
            'Authorization': f'Bearer {YOUTRACK_API_TOKEN}',
            'Accept': 'application/json',
        },
        timeout=60,
    )

    if not response.is_success:
        print(response.content, file=sys.stderr)  # noqa: T201
        response.raise_for_status()

    return response


class Issue:
    FIELDS = (
        'id',
        'idReadable',
        'customFields(id,value(text,name,minutes,isResolved),name)',
    )

    def __init__(self, issue: dict[str, object]) -> None:
        self._issue = issue

    def get_field_value(self, field_name: str) -> object | None:
        """Return raw field by name."""
        fields = self._issue['customFields']

        for field in fields:
            if field['name'] == field_name:
                return field['value']

        return None

    @property
    def id_readable(self) -> str | None:
        """Return issue id."""
        return self._issue['idReadable']

    @property
    def release_note(self) -> str | None:
        """Return issue's release note."""
        value = self.get_field_value('Release note')
        if not value:
            return None
        release_note = value['text'].strip()
        if release_note == 'No release note':
            return None
        return release_note

    @property
    def product_team(self) -> str:
        """Return issue product team."""
        value = self.get_field_value('Product team')
        if not value:
            return 'Other'
        return value['name'] or 'Other'

    @cached_property
    def feature_name(self) -> str | None:
        """Return issue's Feature name."""
        value = self.get_field_value('Feature name')
        if not value or value == 'No feature name':
            return None
        return value

    @property
    def feature_admin_link(self) -> str:
        """Return issue's Feature admin link."""
        if not self.feature_name:
            return ''
        return f'<https://hyperskill.org/admin/feature_switcher/feature/?q={self.feature_name}|{self.feature_name}>'

    @property
    def link(self) -> str:
        """Return issue link."""
        issue_id = self.id_readable
        return f'<https://vyahhi.myjetbrains.com/youtrack/issue/{issue_id}|{issue_id}>'


def get_issues(query: str) -> tuple[Issue, ...]:
    """Return issues by query."""
    issues = get('issues', params={'fields': ','.join(Issue.FIELDS), 'query': query}).json()

    if not issues:
        return ()

    return tuple(map(Issue, issues))


def extract_issues(commit: str) -> tuple[str, ...]:
    """Return issues from commit."""
    issues = set()
    pattern = re.compile(r'[#^]([A-Z]+-\d+)|^\[([A-Z]+-\d+)]')
    issues.update(match[0] or match[1] for match in pattern.findall(commit))
    return tuple(issues)


def release_note(commit_message: str, sha: str) -> dict[str, dict[tuple[str, str], set[str]]]:
    """Return release note for commit."""
    issues = extract_issues(commit_message)
    yt_issues = get_issues(f'issue id: {",".join(issues)}') if issues else ()
    commit_short_message = commit_message.split('\n')[0]
    release_notes = defaultdict(lambda: defaultdict(set))
    github_url = f'<https://github.com/hyperskill/alt/commit/{sha}|GitHub>'

    for yt_issue in yt_issues:
        product_team = yt_issue.product_team
        release_note = yt_issue.release_note or commit_short_message
        yt_issue_id = yt_issue.id_readable

        links = [yt_issue.link, github_url]
        if feature_admin_link := yt_issue.feature_admin_link:
            links.append(feature_admin_link)
        release_notes[product_team][
            (
                yt_issue_id,
                release_note,
            )
        ].update(links)

    if not release_notes:
        release_notes['Other'][
            (
                None,
                commit_short_message,
            )
        ].add(github_url)

    return release_notes


def generate_release_notes(commits: tuple[str, str]) -> str:
    """Return release notes for Branch or Tag."""
    release_notes = defaultdict(lambda: defaultdict(set))
    for sha, commit in commits:
        for product_team, issues in release_note(commit, sha).items():
            for (issue_id, note), links in issues.items():
                release_notes[product_team][
                    (
                        issue_id,
                        note,
                    )
                ].update(links)

    release_notes_str = ''
    for product_team, issues in release_notes.items():
        release_notes_str += f'\n\n{product_team}:\n'
        for index, ((issue_id, note), links) in enumerate(issues.items(), start=1):
            if issue_id is None:
                issue_link = ''
            else:
                issue_link = (
                    f'<https://vyahhi.myjetbrains.com/youtrack/issue/{issue_id}|{issue_id}>: '
                )
            release_notes_str += f'{index}. {issue_link}{note}'
            if links:
                release_notes_str += f" [{", ".join(links)}]\n"
            else:
                release_notes_str += '\n'

    return release_notes_str.strip()


if __name__ == '__main__':
    title = sys.argv[1]
    text = sys.stdin.read()
    separator, text = text.split('\n', 1)
    commits = tuple(commit.strip().split('\n', 1) for commit in text.strip().split(separator))
    release_notes = title + '\n' + generate_release_notes(commits)
    json.dump({'text': release_notes}, sys.stdout)
    sys.stdout.write('\n')
