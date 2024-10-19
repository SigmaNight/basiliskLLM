from enum import Enum


class ProviderCapability(Enum):
	IMAGE = "image"
	TEXT = "text"
	STT = "stt"
	TTS = "tts"
	VOICE = "voice"
