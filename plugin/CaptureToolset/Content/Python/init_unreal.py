"""Editor startup: register this plugin's MCP toolset with the Toolset Registry (same pattern as Epic's toolsets)."""

from toolset_registry.registration import Registration

import capture_toolset_mcp

_registration = Registration([capture_toolset_mcp.CaptureTools])
_registration.register()
