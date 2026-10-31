"""Windows vocabulary kit. All personal state lives in .local/, never in templates/."""
import argparse
import base64
import contextlib
import ctypes
from ctypes import wintypes
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import subprocess
import sys
from urllib.error import HTTPError, URLError
from urllib.request import Request, build_opener, HTTPRedirectHandler
import uuid
import zipfile

ROOT = Path(__file__).resolve().parent.parent
SITE_FILES = {'.nojekyll', 'index.html', 'app.js', 'auth.js', 'config.js', 'sync.js', 'sw.js', 'vendor/supabase.js', 'vendor/LICENSE.supabase'}
FIELDS = ('word phonetic pos defEn meanings usage example exampleCn prefix root suffix synonyms derivatives phrase stars archived order').split()
WORD = re.compile(r"[A-Za-z][A-Za-z '’\-]*\Z")


def local(name):
    return ROOT / '.local' / name


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def atomic(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + '.tmp')
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    temp.replace(path)


@contextlib.contextmanager
def lock():
    local('').mkdir(parents=True, exist_ok=True)
    target = local('operation.lock')
    try:
        fd = os.open(target, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        raise ValueError('Another operation is running. If it crashed, inspect .local/operation.lock before removing it.') from None
    try:
        with os.fdopen(fd, 'w') as file:
            file.write(str(os.getpid()))
        yield
    finally:
        target.unlink()


def state():
    if not local('state.json').exists():
        raise ValueError('Run init first.')
    return read_json(local('state.json'))


def save_state(value):
    old = local('state.json')
    if old.exists():
        shutil.copyfile(old, local('state.previous.json'))
    atomic(old, value)


def config():
    if not local('config.json').exists():
        raise ValueError('Configure the kit first; see docs/SETUP.md.')
    return read_json(local('config.json'))


def conversation_id(value):
    value = value.strip()
    if '/share/' in value:
        raise ValueError('Use the original conversation URL, not a shared snapshot link.')
    match = re.fullmatch(r'(?:https://chatgpt\.com/c/|chatgpt-conversation://)?([0-9a-fA-F-]{36})/?', value)
    if not match:
        raise ValueError('Expected an original chatgpt.com/c/UUID URL or conversation UUID.')
    return str(uuid.UUID(match.group(1)))


def checkpoint(timestamp, message_id):
    dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
    if dt.tzinfo is None or not message_id or not str(message_id).strip():
        raise ValueError('A reliable source-message timestamp with timezone and message ID are required.')
    return {'timestamp': dt.astimezone(timezone.utc).isoformat().replace('+00:00', 'Z'), 'id': str(message_id)}


def public_key(value):
    if value.startswith('sb_publishable_'):
        return value
    try:
        claim = value.split('.')[1]
        role = json.loads(base64.urlsafe_b64decode(claim + '=' * (-len(claim) % 4)))['role']
        if role == 'anon':
            return value
    except (ValueError, KeyError, IndexError):
        pass
    raise ValueError('Only a Supabase publishable key or legacy anon key is accepted. Never use a secret/service_role key.')


def configure(args):
    url = args.supabase_url.rstrip('/')
    if not re.fullmatch(r'https://[a-z0-9]{20}\.supabase\.co', url):
        raise ValueError('This version requires a hosted Supabase project URL.')
    c = {'version': 1, 'pdf_directory': str(Path(args.pdf_directory).resolve()),
         'conversation_id': conversation_id(args.conversation), 'supabase_url': url,
         'public_key': public_key(args.public_key), 'owner_id': str(uuid.UUID(args.owner_id))}
    if local('config.json').exists():
        if config() != c:
            raise ValueError('Configuration already exists. Do not silently switch data sources or databases; use a new kit copy for this trial.')
        print('Configuration already current.')
        return
    if state()['chat_checkpoint'] is not None:
        raise ValueError('Unexpected existing conversation checkpoint.')
    folder = Path(c['pdf_directory'])
    folder.mkdir(parents=True, exist_ok=True)
    atomic(local('config.json'), c)
    print('Configured. No account password or management key was saved. Mark this OneDrive folder as always available on this device.')


def protect(data, decrypt=False):
    if os.name != 'nt':
        raise ValueError('This release supports Windows only.')
    class Blob(ctypes.Structure):
        _fields_ = [('size', wintypes.DWORD), ('data', ctypes.POINTER(ctypes.c_ubyte))]
    buf = ctypes.create_string_buffer(data)
    src = Blob(len(data), ctypes.cast(buf, ctypes.POINTER(ctypes.c_ubyte)))
    dest = Blob()
    function = ctypes.WinDLL('crypt32', use_last_error=True).CryptUnprotectData if decrypt else ctypes.WinDLL('crypt32', use_last_error=True).CryptProtectData
    function.argtypes = [ctypes.POINTER(Blob), ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(Blob)]
    function.restype = wintypes.BOOL
    if not function(ctypes.byref(src), None, None, None, None, 1, ctypes.byref(dest)):
        raise ValueError('Credential encryption failed. Use the Windows account that configured this kit; do not reset the key automatically.')
    try:
        return ctypes.string_at(dest.data, dest.size)
    finally:
        free = ctypes.WinDLL('kernel32').LocalFree
        free.argtypes = [ctypes.c_void_p]
        free(ctypes.cast(dest.data, ctypes.c_void_p))


def credential(create=False):
    c = config()
    path = local('publisher.dpapi')
    if not path.exists():
        if not create:
            raise ValueError('Run prepare first and execute the generated setup.sql once.')
        content = json.dumps({'url': c['supabase_url'], 'owner': c['owner_id'], 'token': secrets.token_hex(32)}).encode()
        with path.open('xb') as file:
            file.write(protect(content))
    secret = json.loads(protect(path.read_bytes(), True))
    if secret['url'] != c['supabase_url'] or secret['owner'] != c['owner_id']:
        raise ValueError('Publishing credential belongs to a different destination; transmission refused.')
    return secret['token']


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def api(path, body=None):
    c = config()
    headers = {'apikey': c['public_key'], 'Content-Type': 'application/json', 'Cache-Control': 'no-store'}
    if not c['public_key'].startswith('sb_publishable_'):
        headers['Authorization'] = 'Bearer ' + c['public_key']
    request = Request(c['supabase_url'] + '/rest/v1/' + path,
                      data=None if body is None else json.dumps(body, ensure_ascii=False).encode(), headers=headers)
    try:
        with build_opener(NoRedirect).open(request, timeout=35) as response:
            return json.load(response)
    except HTTPError as error:
        code = error.code
        error.close()
        raise ValueError(f'API HTTP {code}; local data and progress retained. No automatic retry.') from None
    except (URLError, TimeoutError):
        raise ValueError('Network failure; local data and progress retained. No automatic retry.') from None


def publish(status_only=False):
    token = credential()
    before = api('rpc/vocab_kit_publish_status', {'p_token': token})
    if status_only:
        print(f"Publisher authorized: {before['words']} words, {before['sentences']} sentences.")
        return
    payload = state()['library']
    validate_library(payload)
    after = api('rpc/vocab_kit_publish', {'p_token': token, 'p_payload': payload, 'p_expected_hash': before['hash']})
    if (after['words'], after['sentences']) != (len(payload['vocab']), len(payload['sentences'])):
        raise ValueError('Unexpected upload acknowledgement; do not claim synchronization.')
    verified = api('rpc/vocab_kit_publish_status', {'p_token': token})
    if verified != after:
        raise ValueError('Post-upload verification differs; do not claim synchronization.')
    atomic(local('last_upload.json'), verified)
    label = 'Already current' if before['hash'] == after['hash'] else 'Uploaded and verified'
    print(f"{label}: {after['words']} words, {after['sentences']} sentences. Refresh the private website.")


def validate_library(library):
    if set(library) != {'vocab', 'sentences'} or not all(isinstance(library[k], list) for k in library):
        raise ValueError('Expected vocab and sentences arrays.')
    seen, orders = set(), set()
    for v in library['vocab']:
        if not isinstance(v, dict) or any(k not in v for k in FIELDS):
            raise ValueError('Incomplete vocabulary entry; see docs/ENTRY_SCHEMA.md.')
        if not WORD.fullmatch(v['word']) or v['word'].lower() in seen:
            raise ValueError('Invalid or duplicate word.')
        for key in ('meanings', 'synonyms', 'derivatives'):
            if not isinstance(v[key], list) or any(not isinstance(x, str) for x in v[key]):
                raise ValueError('Vocabulary lists must contain strings.')
        for key in ('word', 'phonetic', 'pos', 'defEn', 'usage', 'example', 'exampleCn', 'prefix', 'root', 'suffix', 'phrase'):
            if not isinstance(v[key], str):
                raise ValueError('Vocabulary text fields must be strings.')
        if not v['defEn'].strip() or not v['meanings'] or not v['example'].strip():
            raise ValueError('Definition, meanings and example are required.')
        if type(v['order']) is not int or v['order'] < 1 or v['order'] in orders:
            raise ValueError('Word order must be a unique positive integer.')
        if type(v['stars']) is not int or not 0 <= v['stars'] <= 5 or type(v['archived']) is not bool:
            raise ValueError('Invalid learning defaults.')
        seen.add(v['word'].lower()); orders.add(v['order'])
    ids = set()
    for s in library['sentences']:
        if any(k not in s for k in ('id', 'original', 'translation', 'main', 'clauses')):
            raise ValueError('Incomplete sentence entry.')
        if not re.fullmatch(r'[0-9]+', str(s['id'])) or str(s['id']) in ids:
            raise ValueError('Sentence IDs must be unique numeric identifiers.')
        if not all(isinstance(s[k], str) and s[k].strip() for k in ('original', 'translation', 'main')) or not isinstance(s['clauses'], list) or any(not isinstance(x, str) for x in s['clauses']):
            raise ValueError('Invalid sentence analysis.')
        ids.add(str(s['id']))


def fingerprint(path):
    path = Path(path)
    before = path.stat()
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    after = path.stat()
    if (before.st_mtime_ns, before.st_size) != (after.st_mtime_ns, after.st_size):
        raise ValueError('PDF changed during reading; wait for OneDrive to finish syncing.')
    return {'name': path.name, 'mtime_ns': after.st_mtime_ns, 'size': after.st_size, 'sha256': digest}


def scan():
    c, st = config(), state()
    folder = Path(c['pdf_directory'])
    selected = []
    for path in sorted(folder.glob('*'), key=lambda x: x.stat().st_mtime_ns):
        if path.is_file() and path.suffix.lower() == '.pdf':
            item = fingerprint(path)
            if st['pdf_processed'].get(path.name) != item:
                selected.append(item)
    name = str(uuid.uuid4())
    manifest = {'version': 1, 'id': name, 'directory': str(folder.resolve()), 'files': selected}
    atomic(local('batches') / (name + '.json'), manifest)
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    print('Manifest:', local('batches') / (name + '.json'))


def apply_batch(path):
    batch = read_json(path)
    st, c = state(), config()
    source = batch['source']
    if source.get('complete') is not True:
        raise ValueError('Source batch is incomplete; progress will not advance.')
    if source['kind'] == 'chat':
        if source['conversation_id'] != c['conversation_id'] or st['chat_checkpoint'] is None:
            raise ValueError('Initialize the correct conversation start first.')
        if source['previous'] != st['chat_checkpoint']:
            raise ValueError('Chat checkpoint changed; read from the saved boundary again.')
        upper = checkpoint(source['upper']['timestamp'], source['upper']['id'])
        if datetime.fromisoformat(upper['timestamp'].replace('Z', '+00:00')) < datetime.fromisoformat(st['chat_checkpoint']['timestamp'].replace('Z', '+00:00')):
            raise ValueError('Chat checkpoint cannot move backwards.')
    elif source['kind'] == 'pdf':
        name = str(uuid.UUID(source['manifest_id']))
        manifest = read_json(local('batches') / (name + '.json'))
        if manifest['directory'] != c['pdf_directory']:
            raise ValueError('PDF source changed.')
        for item in manifest['files']:
            if fingerprint(Path(c['pdf_directory']) / item['name']) != item:
                raise ValueError('A PDF changed after scan; rescan and recheck it. Progress retained.')
    else:
        raise ValueError('Unknown source kind.')
    current = st['library']
    words = {v['word'].lower() for v in current['vocab']}
    originals = {s['original'].strip() for s in current['sentences']}
    order = max((v['order'] for v in current['vocab']), default=0)
    sid = max((int(s['id']) for s in current['sentences']), default=0)
    added = 0
    for entry in batch['vocab']:
        if entry['word'].lower() in words:
            continue
        order += 1
        entry = dict(entry, order=order, stars=0, archived=False)
        current['vocab'].append(entry); words.add(entry['word'].lower()); added += 1
    for entry in batch['sentences']:
        if entry['original'].strip() in originals:
            continue
        sid += 1
        current['sentences'].append(dict(entry, id=sid)); originals.add(entry['original'].strip())
    validate_library(current)
    if source['kind'] == 'chat':
        st['chat_checkpoint'] = upper
    else:
        for item in manifest['files']:
            st['pdf_processed'][item['name']] = item
    save_state(st)
    print(f'Local batch committed atomically: {added} new words. Now run publish, even if no words were added.')


def prepare():
    c = config()
    token = credential(create=True)
    schema = (ROOT / 'templates/sql/schema.sql').read_text(encoding='utf-8').replace('__OWNER_ID__', c['owner_id'])
    publisher = (ROOT / 'templates/sql/publisher.sql').read_text(encoding='utf-8').replace('__TOKEN_HASH__', hashlib.sha256(token.encode()).hexdigest())
    local('setup.sql').write_text(schema + '\n' + publisher, encoding='utf-8')
    shutil.copyfile(ROOT / 'templates/sql/verify.sql', local('verify.sql'))
    build_site()
    print('Prepared .local/setup.sql and verify.sql. Execute them in your NEW Supabase project. Re-running does not reset the library or learning state.')


def build_site():
    c = config()
    target = local('site')
    if target.exists():
        extras = {str(p.relative_to(target)).replace('\\', '/') for p in target.rglob('*') if p.is_file()} - SITE_FILES
        if extras:
            raise ValueError('Unexpected files in public site output; refusing to include them.')
    target.mkdir(exist_ok=True)
    for name in SITE_FILES - {'config.js'}:
        dest = target / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        if name == 'index.html':
            dest.write_text((ROOT / 'templates/site' / name).read_text(encoding='utf-8').replace('__SUPABASE_URL__', c['supabase_url']), encoding='utf-8')
        else:
            shutil.copyfile(ROOT / 'templates/site' / name, dest)
    cfg = {'supabaseUrl': c['supabase_url'], 'supabaseAnonKey': c['public_key']}
    (target / 'config.js').write_text('window.APP_CONFIG = ' + json.dumps(cfg) + ';\n', encoding='utf-8')
    print('Public page shell generated in .local/site (no vocabulary, SQL, owner ID or publishing credential).')


def site_zip():
    target = local('site')
    found = {p.relative_to(target).as_posix() for p in target.rglob('*') if p.is_file()}
    if found != SITE_FILES:
        raise ValueError('Public shell file whitelist failed.')
    with zipfile.ZipFile(local('site-shell.zip'), 'w', zipfile.ZIP_DEFLATED) as archive:
        for name in sorted(SITE_FILES):
            archive.write(target / name, name)
    print('Created .local/site-shell.zip. Publish only this shell, never the whole personal working directory.')


def probe():
    for table in ('vocab_kit_library', 'vocab_kit_state'):
        try:
            api(table + '?select=*')
        except ValueError as error:
            if 'HTTP 401;' in str(error) or 'HTTP 403;' in str(error):
                print('PASS anonymous access denied:', table)
                continue
            raise
        raise ValueError('Privacy check failed: anonymous read was allowed.')
    try:
        api('rpc/vocab_kit_publish_status', {'p_token': '0' * 64})
    except ValueError as error:
        if 'HTTP 401;' in str(error) or 'HTTP 403;' in str(error):
            print('PASS invalid publisher credential denied.')
            return
        raise
    raise ValueError('Invalid publishing credential was accepted.')


def doctor():
    report = {'platform': sys.platform, 'python': sys.version.split()[0],
              'pymupdf': importlib.util.find_spec('pymupdf') is not None,
              'git': bool(shutil.which('git')), 'gh_optional': bool(shutil.which('gh')),
              'tesseract': bool(shutil.which('tesseract') or Path('C:/Program Files/Tesseract-OCR/tesseract.exe').is_file()),
              'onedrive_candidates': [os.environ[k] for k in ('OneDrive', 'OneDriveConsumer', 'OneDriveCommercial') if os.environ.get(k)],
              'configured': local('config.json').exists(), 'initialized': local('state.json').exists()}
    if report['configured']:
        c = config()
        report['pdf_directory_exists'] = Path(c['pdf_directory']).is_dir()
        report['chat_baseline_recorded'] = state()['chat_checkpoint'] is not None
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if os.name != 'nt' or sys.version_info < (3, 10):
        raise ValueError('Use Windows and Python 3.10 or newer.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    for command in ('doctor', 'init', 'prepare', 'build-site', 'site-zip', 'publish', 'status', 'probe', 'scan', 'show-state'):
        sub.add_parser(command)
    p = sub.add_parser('configure')
    for key in ('pdf-directory', 'conversation', 'supabase-url', 'public-key', 'owner-id'):
        p.add_argument('--' + key, required=True)
    p = sub.add_parser('record-start'); p.add_argument('--timestamp', required=True); p.add_argument('--message-id', required=True)
    p = sub.add_parser('apply'); p.add_argument('--batch', required=True)
    args = parser.parse_args()
    if args.command == 'doctor':
        doctor(); return
    if args.command == 'show-state':
        print(json.dumps(state(), ensure_ascii=False, indent=2)); return
    with lock():
        if args.command == 'init':
            if local('state.json').exists():
                print('Already initialized; no state reset.'); return
            save_state({'version': 1, 'library': {'vocab': [], 'sentences': []}, 'chat_checkpoint': None, 'pdf_processed': {}})
            print('Empty personal library initialized. No sample words inserted.')
        elif args.command == 'configure': configure(args)
        elif args.command == 'record-start':
            config(); st = state()
            if st['chat_checkpoint'] is not None:
                raise ValueError('A start point already exists; refusing to skip intervening messages.')
            st['chat_checkpoint'] = checkpoint(args.timestamp, args.message_id)
            save_state(st); print('Start recorded. No historical words collected.')
        elif args.command == 'apply': apply_batch(args.batch)
        elif args.command == 'prepare': prepare()
        elif args.command == 'build-site': build_site()
        elif args.command == 'site-zip': site_zip()
        elif args.command == 'scan': scan()
        elif args.command == 'publish': publish()
        elif args.command == 'status': publish(status_only=True)
        elif args.command == 'probe': probe()


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    try:
        main()
    except (ValueError, OSError, KeyError, TypeError) as error:
        # Do not dump request objects, credential bytes or API response bodies.
        print('Stopped:', str(error))
        sys.exit(1)
