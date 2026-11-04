"""Build a clean source ZIP; never package .local, credentials or Git history."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import sys
import zipfile

ROOT = Path(__file__).resolve().parent.parent
ROOT_FILES = {'README.md', 'START_HERE.md', 'AGENTS.md', 'THIRD_PARTY_NOTICES.md', 'requirements.txt', '.gitignore', '.gitattributes'}
SOURCE_DIRS = {'.agents', 'scripts', 'templates', 'docs', 'tests'}
EXTENSIONS = {'.md', '.yaml', '.py', '.cjs', '.mjs', '.js', '.html', '.sql', '.ps1', '.json', '.txt', '.supabase'}


def source_files(root=ROOT):
    selected = []
    for path in root.rglob('*'):
        rel = path.relative_to(root)
        if rel.parts[0] not in SOURCE_DIRS and rel.as_posix() not in ROOT_FILES:
            continue
        if any(p in {'.git', '.local', '.venv', 'node_modules', '__pycache__'} for p in rel.parts):
            continue
        if path.is_symlink():
            raise ValueError('Source symlinks are not allowed in a release.')
        if not path.is_file():
            continue
        if path.suffix not in EXTENSIONS and path.name not in ROOT_FILES | {'.nojekyll'}:
            raise ValueError('Unexpected release source file: ' + rel.as_posix())
        content = path.read_bytes()
        text = content.decode('utf-8-sig')
        if re.search(r'eyJ[A-Za-z0-9_-]{15,}\.[A-Za-z0-9_-]{15,}\.[A-Za-z0-9_-]{10,}', text) or re.search(r'sb_secret_[A-Za-z0-9_-]{12,}', text):
            raise ValueError('Possible embedded credential in ' + rel.as_posix())
        selected.append(path)
    return sorted(selected)


def package(output):
    output = Path(output).resolve()
    if output.is_relative_to(ROOT):
        raise ValueError('Write the release ZIP outside the working project.')
    files = source_files()
    output.parent.mkdir(parents=True, exist_ok=True)
    prefix = 'vocab-workflow-windows-v0.2.1'
    manifest = {p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
    with zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED) as archive:
        for path in files:
            archive.write(path, prefix + '/' + path.relative_to(ROOT).as_posix())
        archive.writestr(prefix + '/RELEASE_MANIFEST.json', json.dumps(manifest, indent=2))
    print(f'Clean release: {len(files)} source files; no runtime data or Git history.')
    print(output)
    print('SHA256:', hashlib.sha256(output.read_bytes()).hexdigest())


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument('--output', required=True)
    try:
        package(parser.parse_args().output)
    except (ValueError, OSError) as error:
        print('Packaging stopped:', str(error)); sys.exit(1)
