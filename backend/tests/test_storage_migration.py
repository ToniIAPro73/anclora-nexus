import json

from types import SimpleNamespace

from backend.scripts import migrate_supabase_storage_to_vercel_blob as migration


class BucketStub:
    def __init__(self, files):
        self.files = files
        self.download_calls = []

    def list(self, prefix, options):
        limit = options["limit"]
        offset = options["offset"]
        entries = []
        immediate_folders = set()
        for path, body in self.files.items():
            parent, _, leaf = path.rpartition("/")
            if parent == prefix:
                entries.append({
                    "id": "file-id",
                    "name": leaf,
                    "updated_at": "2026-10-26T00:00:00Z",
                    "metadata": {"size": len(body), "mimetype": "application/pdf"},
                })
            elif parent.startswith(f"{prefix}/") or (not prefix and parent):
                folder = parent[len(prefix):].strip("/").split("/", 1)[0]
                immediate_folders.add(folder)
        entries.extend({"id": None, "name": name, "metadata": None} for name in immediate_folders)
        return entries[offset:offset + limit]

    def download(self, path):
        self.download_calls.append(path)
        return self.files[path]


class StorageStub:
    def __init__(self, buckets):
        self.buckets = buckets

    def list_buckets(self):
        return [{"id": name} for name in self.buckets]

    def from_(self, name):
        return self.buckets[name]


def install_source(monkeypatch, buckets):
    storage = StorageStub(buckets)
    monkeypatch.setattr(migration, "create_client", lambda *_args: SimpleNamespace(storage=storage))
    monkeypatch.setenv("SUPABASE_URL", "https://example.invalid")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "test-only")
    monkeypatch.delenv("BLOB_READ_WRITE_TOKEN", raising=False)
    return storage


def test_list_bucket_objects_recurses_and_returns_metadata():
    bucket = BucketStub({"org/documents/contract.pdf": b"pdf-bytes"})

    assert list(migration.list_bucket_objects(bucket)) == [
        ("org/documents/contract.pdf", {"size": 9, "mimetype": "application/pdf"})
    ]


def test_dry_run_inventories_only_selected_application_bucket(monkeypatch, capsys):
    buckets = {
        "dms": BucketStub({"org/contract.pdf": b"contract"}),
        "avatars": BucketStub({"user/avatar.png": b"avatar"}),
        "logos": BucketStub({"logo.svg": b"unrelated"}),
    }
    storage = install_source(monkeypatch, buckets)
    monkeypatch.setattr("sys.argv", ["migration", "--dry-run", "--buckets", "dms"])

    assert migration.main() == 0

    result = json.loads(capsys.readouterr().out)
    assert result == {
        "status": "inventory_only",
        "objects": 1,
        "bytes": 8,
        "buckets": [{"bucket": "dms", "objects": 1, "bytes": 8}],
        "source_deleted": False,
    }
    assert buckets["dms"].download_calls == []
    assert buckets["avatars"].download_calls == []
    assert buckets["logos"].download_calls == []
