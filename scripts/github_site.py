"""Create/update a clean GitHub Pages shell using the user's existing Git login."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from urllib.request import Request, build_opener
from urllib.error import HTTPError, URLError
import vocab


def git(*args, cwd=None, input=None):
    result = subprocess.run(['git', *args], cwd=cwd, input=input, text=True, encoding='utf-8',
                            capture_output=True, timeout=60,
                            env=dict(os.environ, GIT_TERMINAL_PROMPT='0', GCM_INTERACTIVE='never'))
    if result.returncode:
        raise ValueError('Git operation failed. Existing files retained; no automatic retry. Check your GitHub login/network.')
    return result.stdout.strip()


def client():
    result = subprocess.run(['git', 'credential', 'fill'], input='protocol=https\nhost=github.com\n\n',
                            text=True, encoding='utf-8', capture_output=True, timeout=25,
                            env=dict(os.environ, GIT_TERMINAL_PROMPT='0', GCM_INTERACTIVE='never'))
    values = dict(line.split('=', 1) for line in result.stdout.splitlines() if '=' in line)
    token = values.get('password')
    if result.returncode or not token:
        raise ValueError('No existing GitHub login found. Sign in to GitHub through Git Credential Manager/browser, then retry explicitly. Do not paste a token into chat.')
    def api(method, route, body=None, missing=False):
        request = Request('https://api.github.com' + route, method=method,
                          data=None if body is None else json.dumps(body).encode(), headers={
                              'Authorization': 'Bearer ' + token, 'Accept': 'application/vnd.github+json',
                              'X-GitHub-Api-Version': '2022-11-28', 'User-Agent': 'Vocab-Workflow-Kit',
                              'Content-Type': 'application/json'})
        try:
            with build_opener(vocab.NoRedirect).open(request, timeout=35) as response:
                data = response.read()
                return json.loads(data) if data else {}
        except HTTPError as error:
            code = error.code; error.close()
            if missing and code == 404: return None
            raise ValueError(f'GitHub HTTP {code}. No automatic retry.') from None
        except (URLError, TimeoutError):
            raise ValueError('GitHub network failure. No automatic retry.') from None
    return api


def publish(name, apply=False):
    import re
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{1,79}', name):
        raise ValueError('Choose a simple new repository name, for example my-private-vocab.')
    vocab.config()
    shell = vocab.local('site')
    found = {p.relative_to(shell).as_posix() for p in shell.rglob('*') if p.is_file()}
    if found != vocab.SITE_FILES:
        raise ValueError('Build the site first; public file whitelist failed.')
    api = client(); user = api('GET', '/user'); owner = user['login']
    route = '/repos/' + owner + '/' + name
    remote = api('GET', route, missing=True)
    marker = vocab.local('github_site.json')
    owned = vocab.read_json(marker) if marker.exists() else None
    if remote and (not owned or owned.get('repo') != owner + '/' + name):
        raise ValueError('Repository already exists and was not created by this kit. Choose a NEW name; do not reuse a production repository.')
    print('GitHub account:', owner)
    print('Public page shell repository:', owner + '/' + name)
    print('Only the nine whitelisted website files will be pushed. Vocabulary remains in the private database.')
    if not apply:
        print('Preview only. Run again with --apply to create/publish this new shell.'); return
    if remote is None:
        remote = api('POST', '/user/repos', {'name': name, 'private': False, 'auto_init': False,
                                           'description': 'Personal vocabulary app. Public login shell; vocabulary and progress require owner authentication.'})
        vocab.atomic(marker, {'repo': owner + '/' + name, 'url': remote['html_url']})
    repo = vocab.local('site-repo')
    if not repo.exists():
        repo.mkdir(); git('init', '-b', 'main', cwd=repo)
        git('remote', 'add', 'origin', remote['clone_url'], cwd=repo)
        git('config', 'user.name', owner, cwd=repo)
        git('config', 'user.email', str(user['id']) + '+' + owner + '@users.noreply.github.com', cwd=repo)
    if git('remote', 'get-url', 'origin', cwd=repo) != remote['clone_url']:
        raise ValueError('Unexpected Git destination; stopped.')
    files = {p.relative_to(repo).as_posix() for p in repo.rglob('*') if p.is_file() and '.git' not in p.relative_to(repo).parts}
    if files - vocab.SITE_FILES:
        raise ValueError('Unexpected files in publishing checkout.')
    tracked = set(git('ls-files', cwd=repo).splitlines())
    if tracked - vocab.SITE_FILES:
        raise ValueError('Unexpected tracked files in publishing checkout.')
    for path in vocab.SITE_FILES:
        dest = repo / path; dest.parent.mkdir(parents=True, exist_ok=True); shutil.copyfile(shell / path, dest)
    git('add', '--', *sorted(vocab.SITE_FILES), cwd=repo)
    if git('status', '--porcelain', cwd=repo):
        git('commit', '-m', 'Publish private vocabulary page shell', cwd=repo)
    git('push', '-u', 'origin', 'main', cwd=repo)
    pages = api('GET', route + '/pages', missing=True)
    if pages is None:
        pages = api('POST', route + '/pages', {'source': {'branch': 'main', 'path': '/'}, 'build_type': 'legacy'})
    elif pages.get('source') != {'branch': 'main', 'path': '/'}:
        raise ValueError('Existing Pages configuration differs; do not overwrite it automatically.')
    print('Pages requested:', pages.get('html_url', f'https://{owner}.github.io/{name}/'))
    print('Deployment may still be building. Verify the URL, anonymous API denial and owner login before reporting readiness.')


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    p = argparse.ArgumentParser(description=__doc__); p.add_argument('--name', required=True); p.add_argument('--apply', action='store_true')
    args = p.parse_args()
    try:
        with vocab.lock(): publish(args.name, args.apply)
    except (ValueError, OSError, KeyError) as error:
        print('Stopped:', str(error)); sys.exit(1)
