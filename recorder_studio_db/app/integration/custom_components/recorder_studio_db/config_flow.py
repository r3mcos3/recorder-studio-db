from __future__ import annotations

from homeassistant.config_entries import ConfigFlow

from .const import DOMAIN


class RecorderStudioDbConfigFlow(ConfigFlow, domain=DOMAIN):
    """Created by the add-on (no questions asked); a second entry is refused."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")
        return self.async_create_entry(title="Recorder Studio DB", data={})
