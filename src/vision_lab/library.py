"""Local immutable originals, atomic portable metadata, and editable annotations."""
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import tempfile
import uuid
from vision_lab.sources import FileSource

DEFINITION = "Actual objects or people changing position, excluding illumination/exposure changes alone."


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as handle:
            json.dump(value, handle, indent=2, allow_nan=False)
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def read_json(path):
    return json.loads(Path(path).read_text())


def validate_annotations(value, duration):
    if value.get("motion") not in ("Yes", "No", "Unknown"):
        raise ValueError("Video motion label must be Yes, No, or Unknown")
    if value.get("split") not in ("development", "holdout"):
        raise ValueError("Split must be development or holdout")
    for field in ("description", "definition"):
        if not isinstance(value.get(field), str):
            raise ValueError(f"{field} must be text")
    if not isinstance(value.get("tags"), list) or not all(isinstance(t, str) for t in value['tags']):
        raise ValueError("Tags must be a list of strings")
    intervals = value.get("intervals")
    if not isinstance(intervals, list):
        raise ValueError("Intervals must be a list")
    seen = set()
    for interval in intervals:
        a,b = interval['start'], interval['end']
        if not (math.isfinite(a) and math.isfinite(b) and 0 <= a < b <= duration):
            raise ValueError("Intervals must satisfy 0 <= start < end <= duration")
        if interval.get('target') not in ('Yes','No','Unknown'):
            raise ValueError("Interval target must be Yes, No, or Unknown")
        if not isinstance(interval.get('id'), str) or interval['id'] in seen:
            raise ValueError("Interval IDs must be unique strings")
        seen.add(interval['id'])
        if not all(isinstance(interval.get(k), str) for k in ('category','description')):
            raise ValueError("Category and description must be text")
    for i,a in enumerate(intervals):
        for b in intervals[i+1:]:
            if ({a['target'], b['target']} == {'Yes','No'}
                    and max(a['start'],b['start']) < min(a['end'],b['end'])):
                raise ValueError("Overlapping confirmed positive and negative labels conflict")
    return value


class Library:
    def __init__(self, root="data"):
        self.root = Path(root)
        self.videos = self.root / 'videos'
        self.videos.mkdir(parents=True, exist_ok=True)

    def directory(self, video_id):
        # No imported path is ever interpreted as a filesystem path.
        if str(uuid.UUID(video_id)) != video_id:
            raise ValueError("Invalid video ID")
        return self.videos/video_id

    def list(self):
        return [read_json(p) for p in sorted(self.videos.glob('*/metadata.json'))]

    def path(self, video_id):
        folder = self.directory(video_id)
        meta = read_json(folder/'metadata.json')
        suffix = meta['extension']
        if suffix not in ('.mp4','.mov'):
            raise ValueError("Unsupported stored extension")
        return folder/('original'+suffix)

    def add(self, upload, name, max_bytes=512*1024*1024):
        suffix = Path(name).suffix.lower()
        if suffix not in ('.mp4','.mov'):
            raise ValueError("Upload an MP4 or MOV recording")
        video_id = str(uuid.uuid4())
        folder = self.directory(video_id)
        folder.mkdir()
        digest, size = hashlib.sha256(), 0
        try:
            with (folder/('original'+suffix)).open('xb') as output:
                while block := upload.read(1024*1024):
                    size += len(block)
                    if size > max_bytes:
                        raise ValueError("Upload exceeds the 512 MiB per-file limit")
                    digest.update(block)
                    output.write(block)
            source = FileSource(folder/('original'+suffix), video_id)
            meta = dict(id=video_id, name=Path(name).name, notes='', extension=suffix,
                        sha256=digest.hexdigest(), **source.metadata)
            annotations = dict(motion='Unknown', description='', tags=[], split='development',
                               definition=DEFINITION, intervals=[])
            write_json(folder/'metadata.json', meta)
            write_json(folder/'annotations.json', annotations)
            return meta
        except Exception:
            shutil.rmtree(folder)
            raise

    def annotations(self, video_id):
        return read_json(self.directory(video_id)/'annotations.json')

    def save_annotations(self, video_id, annotations):
        duration = read_json(self.directory(video_id)/'metadata.json')['duration']
        write_json(self.directory(video_id)/'annotations.json', validate_annotations(annotations, duration))

    def rename(self, video_id, name, notes):
        if not name.strip():
            raise ValueError("Name cannot be empty")
        path = self.directory(video_id)/'metadata.json'
        meta = read_json(path)
        meta.update(name=name, notes=notes)
        write_json(path, meta)

    def export(self):
        return dict(schema_version=1, videos=[dict(metadata=m, annotations=self.annotations(m['id'])) for m in self.list()])

    def import_annotations(self, document):
        if document.get('schema_version') != 1:
            raise ValueError("Unsupported annotation schema")
        # Match immutable source hashes, allowing new UUIDs after moving machines.
        local = {}
        for m in self.list():
            local.setdefault(m['sha256'], []).append(m)
        updates = []
        missing = []
        for record in document['videos']:
            matches = local.get(record['metadata']['sha256'], [])
            if not matches:
                missing.append(record['metadata']['name'])
                continue
            for meta in matches:
                annotations = validate_annotations(record['annotations'], meta['duration'])
                name, notes = record['metadata']['name'], record['metadata'].get('notes','')
                if not isinstance(name,str) or not name.strip() or not isinstance(notes,str):
                    raise ValueError("Imported name/notes must be text")
                updates.append((meta['id'], annotations, name, notes))
        for video_id, annotations, name, notes in updates:
            self.save_annotations(video_id, annotations)
            self.rename(video_id, name, notes)
        return len(updates), missing

    def delete(self, video_id):
        shutil.rmtree(self.directory(video_id))
        # Derived artifacts use video UUID directories only, never annotations.
        for category in ('thumbnails','derived','exports'):
            shutil.rmtree(self.root/'cache'/category/video_id, ignore_errors=True)
