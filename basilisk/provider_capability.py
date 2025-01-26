from enum import Enum


class ProviderCapability(Enum):
	DOCUMENT = "document"
	IMAGE = "image"
	TEXT = "text"
	STT = "stt"
	TTS = "tts"
