"""Module for managing conversation between users and the bot."""

from .attached_file import (
	URL_PATTERN,
	AttachmentFile,
	AttachmentFileTypes,
	ImageFile,
	NotImageError,
	build_from_url,
	get_mime_type,
	parse_supported_attachment_formats,
)
from .conversation_helper import PROMPT_TITLE
from .conversation_model import (
	Conversation,
	Message,
	MessageBlock,
	MessageRoleEnum,
	SystemMessage,
)

__all__ = [
	"PROMPT_TITLE",
	"URL_PATTERN",
	"AttachmentFile",
	"AttachmentFileTypes",
	"Conversation",
	"ImageFile",
	"Message",
	"MessageBlock",
	"MessageRoleEnum",
	"NotImageError",
	"SystemMessage",
	"build_from_url",
	"get_mime_type",
	"parse_supported_attachment_formats",
]
