"""Unreal MCP toolset that exposes ue_capture_toolset to AI agents.

Discovered by the Toolset Registry at editor startup (this file lives in the plugin's
Content/Python). Every tool forwards to ``ue_capture_toolset.mcp`` with the real ``unreal`` module
and returns a JSON string whose first key is ``summary``. Captures only write new files under the
project's Saved/Captures folder; nothing is deleted.
"""

import toolset_registry
import unreal

from ue_capture_toolset import mcp


@unreal.uclass()
class CaptureTools(unreal.ToolsetDefinition):
    """Take reproducible editor screenshots with a JSON sidecar and build visual evidence.

    Use it for dev logs, bug reports, before/after comparisons and camera tours. Each capture is
    saved as Saved/Captures/<date>/<time>-<label>.png with a .json sidecar recording map, camera
    transform, sg.* quality preset, git commit and time. HighResShot is asynchronous: capture tools
    return at once with a capture_id; call capture_status until it is ready before the next capture.
    """

    @staticmethod
    @toolset_registry.tool_call
    def capture_viewport(
        label: str = "viewport", resolution: str = "1920x1080", camera: str = ""
    ) -> str:
        """Request a screenshot of the level viewport, or from a camera actor, with a sidecar.

        Args:
            label: Short description used in the file name (for example "hero shot").
            resolution: Image size as WIDTHxHEIGHT, up to 16384 per side.
            camera: Optional actor label of a camera to pilot first; empty uses the viewport.

        Returns:
            JSON with summary, capture_id, status ("pending"), camera, resolution, image_path and
            sidecar_path. Poll capture_status with the capture_id.
        """
        return mcp.capture_viewport(unreal, label, resolution, camera)

    @staticmethod
    @toolset_registry.tool_call
    def capture_status(capture: str, timeout_s: float = 30.0) -> str:
        """Check once, without waiting, whether captures have been written to disk.

        Args:
            capture: A capture_id or path under Saved/Captures, or a JSON list of them.
            timeout_s: Seconds after the request at which a missing image counts as timed out.

        Returns:
            JSON with summary, done, ready, pending, timeout and captures (capture_id, status
            "ready", "pending" or "timeout", image_path).
        """
        return mcp.capture_status(unreal, capture, timeout_s)

    @staticmethod
    @toolset_registry.tool_call
    def capture_pair(before: str, label: str = "after", resolution: str = "") -> str:
        """Request an "after" capture from the exact camera transform of an earlier capture.

        Args:
            before: capture_id or path of the "before" capture under Saved/Captures.
            label: Short description used in the file name of the new capture.
            resolution: WIDTHxHEIGHT; empty reuses the resolution of the before capture.

        Returns:
            JSON with summary, capture_id, status, camera, resolution, image_path, sidecar_path
            and before_id.
        """
        return mcp.capture_pair(unreal, before, label, resolution)

    @staticmethod
    @toolset_registry.tool_call
    def capture_series(
        label: str,
        cameras_json: str = "",
        tag: str = "",
        resolution: str = "1920x1080",
        cursor: int = 0,
    ) -> str:
        """Capture one camera of a series per call, from named cameras or cameras with a tag.

        Args:
            label: Series name; each image is named <label>-<camera>.
            cameras_json: JSON list of camera actor labels (give this or tag).
            tag: Actor tag shared by the cameras, for example "Portfolio" (give this or
                cameras_json).
            resolution: Image size as WIDTHxHEIGHT.
            cursor: Index of the camera to capture; pass the returned cursor after the previous
                capture is ready.

        Returns:
            JSON with summary, cameras, captures (one pending capture) and cursor (null when the
            series is complete).
        """
        return mcp.capture_series(unreal, label, cameras_json, tag, resolution, cursor)

    @staticmethod
    @toolset_registry.tool_call
    def capture_bug(
        title: str,
        severity: str = "medium",
        notes: str = "",
        label: str = "bug",
        resolution: str = "1920x1080",
    ) -> str:
        """Capture the viewport and write a Markdown bug report next to the image.

        Args:
            title: One-line bug title.
            severity: "low", "medium", "high" or "critical".
            notes: Free text such as steps to reproduce (up to 20000 characters).
            label: Short description used in the file name.
            resolution: Image size as WIDTHxHEIGHT.

        Returns:
            JSON with summary, capture_id, status, report_path, error_count (recent "Error:" lines
            of the newest editor log) and markdown (ready to paste into bugs.md).
        """
        return mcp.capture_bug(unreal, title, severity, notes, label, resolution)

    @staticmethod
    @toolset_registry.tool_call
    def list_captures(limit: int = 100, since: str = "", label: str = "") -> str:
        """List the newest captures under Saved/Captures, oldest first (read-only).

        Args:
            limit: Maximum captures returned (1 to 500).
            since: Optional ISO date or date-time; only captures taken at or after it.
            label: Optional text that the capture label must contain (case-insensitive).

        Returns:
            JSON with summary, captures (capture_id, label, map, camera, captured_at, resolution,
            git_commit) and skipped (unreadable sidecars).
        """
        return mcp.list_captures(unreal, limit, since, label)

    @staticmethod
    @toolset_registry.tool_call
    def build_contact_sheet_md(captures_json: str, title: str = "Contact sheet") -> str:
        """Render a Markdown contact sheet that links capture images with their metadata.

        Args:
            captures_json: JSON list of capture_ids or paths (1 to 200).
            title: Heading of the sheet.

        Returns:
            JSON with summary, content (Markdown; image links are relative to the Saved folder)
            and count. Images are never opened or modified.
        """
        return mcp.build_contact_sheet_md(unreal, captures_json, title)
