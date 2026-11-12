"""Editor startup: register this plugin's MCP toolset with the Toolset Registry."""

import capture_toolset_mcp
from toolset_registry.registration import Registration

_registration = Registration([capture_toolset_mcp.CaptureTools])
_registration.register()
