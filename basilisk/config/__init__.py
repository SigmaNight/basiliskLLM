"""Configuration module for Basilisk."""

from .account_config import (
	CUSTOM_BASE_URL_PATTERN,
	Account,
	AccountManager,
	AccountOrganization,
)
from .account_config import get_account_config as accounts
from .config_enums import (
	AccountSource,
	AutomaticUpdateModeEnum,
	KeyStorageMethodEnum,
	LogLevelEnum,
	ReleaseChannelEnum,
)
from .conversation_profile import ConversationProfile
from .conversation_profile import (
	get_conversation_profile_config as conversation_profiles,
)
from .main_config import BasiliskConfig
from .main_config import get_basilisk_config as conf

__all__ = [
	"Account",
	"AccountManager",
	"AccountOrganization",
	"AccountSource",
	"accounts",
	"AutomaticUpdateModeEnum",
	"BasiliskConfig",
	"conf",
	"ConversationProfile",
	"conversation_profiles",
	"CUSTOM_BASE_URL_PATTERN",
	"get_account_source_labels",
	"KeyStorageMethodEnum",
	"LogLevelEnum",
	"ReleaseChannelEnum",
]
