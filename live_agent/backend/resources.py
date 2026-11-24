"""Backend resource APIs and media files; browser views belong to frontend/."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re
from urllib.parse import urlencode

from fastapi import Body, FastAPI, HTTPException
from fastapi.responses import FileResponse

from live_agent.backend.config import BOARD_IMAGES
from live_agent.student import ProfileStore

TRACE_NAME = re.compile(r"^sess-[A-Za-z0-9_-]+(\.generated(-part\d+)?)?\.(jsonl|mp4)$")
TRACE_ID = re.compile(r"^sess-[A-Za-z0-9_-]+$")
BOARD_IMAGE = re.compile(r"^([pd][0-9a-f]{15}|[0-9a-f]{16})\.png$")
PRIVATE_HEADERS = {"Cache-Control": "no-store"}


def _trace_events(path: Path, *, metadata_only: bool = False) -> list[dict]:
    """Read only the declared trace file; an unfinished final line is harmless."""
    if not path.is_file() or path.is_symlink():
        return []
    events = []
    with path.open(encoding="utf-8", errors="replace") as trace:
        for line in trace:
            try:
                event = json.loads(line)
            except ValueError:
                continue
            if isinstance(event, dict) and isinstance(event.get("data"), dict):
                events.append(event)
                if metadata_only:
                    break  # new server traces declare scope before any session work
    return events


def _trace_metadata(events: list[dict], session_id: str) -> dict | None:
    records = [event["data"] for event in events
               if event.get("type") == "audit" and event["data"].get("where") == "session_start"]
    if len(records) != 1 or records[0].get("session_id") != session_id:
        return None
    data = records[0]
    student = data.get("student_id")
    if data.get("mode") == "public" and student is None:
        return {"mode": "public", "student_id": None}
    if data.get("mode") == "private" and isinstance(student, str) and re.fullmatch(r"[A-Za-z0-9_-]{1,32}", student):
        return {"mode": "private", "student_id": student}
    return None


def _trace_owner(directory: Path, name: str) -> str | None:
    """An exact declared base owns its media before a parent's part-name convention."""
    if not TRACE_NAME.fullmatch(name):
        return None
    stem = name[:-6] if name.endswith(".jsonl") else name[:-4]
    candidates = [stem]
    if name.endswith(".mp4"):
        parent = re.sub(r"(\.generated(-part\d+)?|-part\d+)$", "", stem)
        if parent != stem:
            candidates.append(parent)
    for owner in candidates:
        path = directory / f"{owner}.jsonl"
        if not TRACE_NAME.fullmatch(path.name):
            continue
        if path.exists() or path.is_symlink():
            return owner if path.is_file() and not path.is_symlink() else None
    return None


def register_resources(app: FastAPI, args: argparse.Namespace, profiles: ProfileStore, *, teaching: bool = True) -> None:
    def scope_query(student: str | None, mode: str | None) -> tuple[str | None, str | None]:
        if mode not in (None, "private", "public") or mode == "public" and student is not None:
            raise HTTPException(400, "choose a learner or public recordings")
        if student is not None:
            if student not in profiles.allowed:
                raise HTTPException(404, "unknown student")
            return "private", student
        if mode == "private":
            raise HTTPException(400, "private recordings require a student")
        return mode, None

    def matches_scope(metadata: dict | None, mode: str | None, student: str | None) -> bool:
        if mode is None:
            return True  # compatibility: the operator's unfiltered index
        return metadata is not None and metadata["mode"] == mode and metadata["student_id"] == student

    def scope_suffix(mode: str | None, student: str | None) -> str:
        values = {"student": student} if student is not None else {"mode": mode} if mode else {}
        return "?" + urlencode(values) if values else ""

    @app.get("/api/health")
    async def health() -> dict:
        # Uvicorn does not serve until model startup has completed.
        return {"status": "ok", "generator": args.generator, "protocol_version": 1}

    @app.get("/api/traces")
    def traces(student: str | None = None, mode: str | None = None) -> dict:
        """Structured trace metadata for the frontend's recorded-session view."""
        mode, student = scope_query(student, mode)
        suffix = scope_suffix(mode, student)
        directory = Path(args.log_dir)
        sessions = []
        files = [f for f in directory.glob("sess-*.jsonl") if TRACE_NAME.fullmatch(f.name) and f.is_file() and not f.is_symlink()]
        for f in sorted(files, key=lambda x: x.stat().st_mtime, reverse=True):
            initial_events = _trace_events(f, metadata_only=True)
            metadata = _trace_metadata(initial_events, f.stem)
            mesh_recording = any(event.get("data", {}).get("renderer") == "mesh" for event in initial_events)
            if not matches_scope(metadata, mode, student):
                continue
            stat = f.stat()
            video_name = re.compile(re.escape(f.stem) + r"(\.generated(-part\d+)?|-part\d+)?\.mp4$")
            videos = []
            for video in sorted(directory.glob(f"{f.stem}*.mp4")):
                if not video.is_file() or video.is_symlink() or not video_name.fullmatch(video.name) \
                        or _trace_owner(directory, video.name) != f.stem:
                    continue
                rest = video.name[len(f.stem):-4].lstrip(".-")
                label = rest if rest.startswith("generated") else "presented" + (" " + rest if rest else "")
                videos.append({"name": video.name, "label": label, "url": f"/traces/file/{video.name}{suffix}",
                               **({"visual_source": "server_video_fallback"} if mesh_recording else {})})
            sessions.append({"id": f.stem, "updated_at": datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat(),
                             "size_bytes": stat.st_size, "trace_url": f"/traces/file/{f.name}{suffix}", "videos": videos,
                             "mode": metadata["mode"] if metadata else "unknown",
                             "student_id": metadata["student_id"] if metadata else None,
                             "transcript_url": f"/api/traces/{f.stem}/transcript{suffix}"})
            if len(sessions) >= 200:
                break
        return {"sessions": sessions}

    @app.get("/api/traces/{session_id}/transcript")
    def transcript(session_id: str, student: str | None = None, mode: str | None = None) -> dict:
        mode, student = scope_query(student, mode)
        path = Path(args.log_dir) / f"{session_id}.jsonl"
        if not TRACE_ID.fullmatch(session_id) or not path.is_file() or path.is_symlink():
            raise HTTPException(404)
        events = _trace_events(path)
        metadata = _trace_metadata(events, session_id)
        if not matches_scope(metadata, mode, student):
            raise HTTPException(404)
        presentations = {}
        for event in events:
            request, chunk = event.get("request_index"), event.get("chunk_index")
            if event.get("type") != "chunk_presented" or type(request) is not int or type(chunk) is not int or chunk < 0:
                continue
            evidence = presentations.setdefault(request, {"chunks": set(), "expected": set()})
            evidence["chunks"].add(chunk)
            expected = event["data"].get("chunks_per_request")
            if type(expected) is int and expected > 0:
                evidence["expected"].add(expected)
        entries, omitted = [], []
        for event in events:
            data = event["data"]
            if event.get("type") == "utterance_end" and isinstance(data.get("text"), str) and data["text"].strip():
                entries.append({"role": "user", "text": data["text"], "source": "utterance_end"})
            elif event.get("type") == "lock" and isinstance(data.get("transcript"), str) and data["transcript"].strip():
                request = event.get("request_index")
                if type(request) is int and request in presentations:
                    evidence = presentations[request]
                    expected = next(iter(evidence["expected"])) if len(evidence["expected"]) == 1 else None
                    chunks = evidence["chunks"]
                    complete = expected is not None and len(chunks) == expected and all(i in chunks for i in range(expected))
                    if expected is not None and not complete:
                        omitted.append(request)
                        continue
                    entries.append({"role": "teacher", "text": data["transcript"], "source": "lock",
                                    "request_index": request, "presented": True, "kind": "planned_script",
                                    "may_include_unplayed_words": True,
                                    "presentation": {"status": "complete" if complete else "unknown",
                                                     "chunks_acknowledged": sorted(chunks), "chunks_expected": expected}})
        return {"id": session_id, "mode": metadata["mode"] if metadata else "unknown",
                "student_id": metadata["student_id"] if metadata else None,
                "kind": "script_aid", "verified_audio": False, "entries": entries,
                "omitted_partial_requests": omitted}

    @app.get("/traces/file/{name}")
    async def trace_file(name: str, student: str | None = None, mode: str | None = None) -> FileResponse:
        mode, student = scope_query(student, mode)
        if not TRACE_NAME.fullmatch(name):
            raise HTTPException(404)
        path = Path(args.log_dir) / name
        if not path.is_file() or path.is_symlink():
            raise HTTPException(404)
        if mode is not None:
            session_id = _trace_owner(Path(args.log_dir), name)
            if session_id is None:
                raise HTTPException(404)
            metadata = _trace_metadata(_trace_events(Path(args.log_dir) / f"{session_id}.jsonl", metadata_only=True), session_id)
            if not matches_scope(metadata, mode, student):
                raise HTTPException(404)
        return FileResponse(path, media_type="video/mp4" if name.endswith(".mp4") else "application/x-ndjson",
                            filename=name, headers=PRIVATE_HEADERS)

    @app.get("/board/img/{name}")
    async def board_img(name: str) -> FileResponse:
        path = BOARD_IMAGES / name
        if not BOARD_IMAGE.fullmatch(name) or not path.is_file():
            raise HTTPException(404)
        return FileResponse(path, media_type="image/png", headers=PRIVATE_HEADERS)

    def profile_or_404(student_id: str):
        if not teaching:  # a live persona (no board) exposes no learner profiles (D-068)
            raise HTTPException(404, "learner profiles are not available for this persona")
        profile = profiles.get(student_id)
        if profile is None:
            raise HTTPException(404, "unknown student")
        return profile

    def full(profile) -> dict:
        return {**profile.view(), "saved": profiles.exists(profile.student_id)}

    @app.get("/api/students")
    async def list_students() -> dict:
        if not teaching:  # clients keep working: the picker shows no learners instead of erroring
            return {"students": []}
        return {"students": [{"id": sid, "name": profiles.get(sid).name, "grade": profiles.get(sid).grade,
                              "saved": profiles.exists(sid)} for sid in profiles.allowed]}

    @app.get("/api/students/{student_id}")
    async def get_student(student_id: str) -> dict:
        return full(profile_or_404(student_id))

    @app.put("/api/students/{student_id}")
    async def put_student(student_id: str, body: dict = Body(...)) -> dict:
        profile = profile_or_404(student_id)
        if body.get("version") != profile.version:
            raise HTTPException(409, "the profile changed since it was loaded (reload to see the latest)")
        try:
            profile.page_edit(body)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from None
        profiles.changed(student_id)
        return full(profile)

    @app.post("/api/students/{student_id}/reset")
    async def reset_student(student_id: str, body: dict = Body(default={})) -> dict:
        profile = profile_or_404(student_id)
        if body.get("version") != profile.version:
            raise HTTPException(409, "the profile changed since it was loaded (reload to see the latest)")
        return full(profiles.reset(student_id))
