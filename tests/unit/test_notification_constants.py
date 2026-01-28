"""Unit tests for notification constants."""

import importlib.util
from pathlib import Path


# Load const.py directly to avoid importing all dependencies
const_path = (
    Path(__file__).parent.parent.parent
    / "multizone_climate"
    / "custom_components"
    / "multizone_climate"
    / "const.py"
)
spec = importlib.util.spec_from_file_location("const", const_path)
const = importlib.util.module_from_spec(spec)
spec.loader.exec_module(const)


class TestNotificationConstants:
    """Test notification constants are properly defined."""

    def test_notification_id_exists(self):
        """Test that notification ID constant exists."""
        assert const.NOTIFICATION_ID_RESTART is not None
        assert isinstance(const.NOTIFICATION_ID_RESTART, str)
        assert len(const.NOTIFICATION_ID_RESTART) > 0

    def test_notification_title_exists(self):
        """Test that notification title constant exists."""
        assert const.NOTIFICATION_TITLE_RESTART is not None
        assert isinstance(const.NOTIFICATION_TITLE_RESTART, str)
        assert len(const.NOTIFICATION_TITLE_RESTART) > 0

    def test_notification_message_exists(self):
        """Test that notification message constant exists."""
        assert const.NOTIFICATION_MESSAGE_RESTART is not None
        assert isinstance(const.NOTIFICATION_MESSAGE_RESTART, str)
        assert len(const.NOTIFICATION_MESSAGE_RESTART) > 0

    def test_notification_message_mentions_restart(self):
        """Test that notification message mentions restart."""
        assert "restart" in const.NOTIFICATION_MESSAGE_RESTART.lower()
