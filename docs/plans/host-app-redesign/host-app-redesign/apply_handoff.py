"""Apply the delivered source only when every target is unchanged or already applied."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import tempfile


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None


def safe_path(root, value):
    rel = Path(value)
    if rel.is_absolute() or '..' in rel.parts:
        raise ValueError('Unsafe manifest path: ' + value)
    target = root / rel
    if target.is_symlink() or any(parent.is_symlink() for parent in target.parents if parent != root.parent):
        raise ValueError('Symlink target is not supported: ' + value)
    if not target.resolve().is_relative_to(root.resolve()):
        raise ValueError('Path leaves repository: ' + value)
    return target


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--check', action='store_true')
    group.add_argument('--apply', action='store_true')
    parser.add_argument('--repo', type=Path, default=Path.cwd(), help='Repository root (default: current directory)')
    args = parser.parse_args()
    root = args.repo.resolve()
    package = Path(__file__).resolve().parent
    manifest = json.loads((package / 'manifest.json').read_text())
    if not (root / 'App/app').is_dir() or not (root / 'AGENTS.md').is_file():
        parser.error('Run from the UbyHost repository root or provide --repo.')
    changes, errors, applied = [], [], 0
    for entry in manifest['files']:
        try:
            target = safe_path(root, entry['path'])
            payload = safe_path(package / 'payload', entry['path'])
            if sha(payload) != entry['sha256']:
                errors.append('Damaged payload: ' + entry['path'])
                continue
            current = sha(target)
            if current == entry['sha256']:
                applied += 1
            elif current == entry['base_sha256'] and not (target.exists() and not target.is_file()):
                changes.append((target, payload, entry))
            else:
                errors.append('Diverged target: ' + entry['path'])
        except ValueError as exc:
            errors.append(str(exc))
    if errors:
        print('\n'.join(errors))
        print('No source files changed. Merge these paths using implementation.patch; do not force-copy older source.')
        return 2
    if args.check:
        print(f'CHECK OK: {len(changes)} files ready; {applied} already applied. No files changed.')
        return 0
    for target, payload, entry in changes:
        target.parent.mkdir(parents=True, exist_ok=True)
        fd, temporary = tempfile.mkstemp(prefix='.host-redesign-', dir=target.parent)
        try:
            with os.fdopen(fd, 'wb') as stream:
                stream.write(payload.read_bytes())
            os.chmod(temporary, int(entry['mode'], 8))
            os.replace(temporary, target)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)
    print(f'APPLIED: {len(changes)} files; {applied} already applied. Review git diff, reconcile newer work and run all gates.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
