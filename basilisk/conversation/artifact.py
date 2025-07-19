"""Artifact management for extracting and handling significant content blocks from messages.

This module provides functionality to detect, extract, and manage artifacts like code blocks,
significant text sections, and other content that users might want to copy, save, or download
from conversation history.
"""

from __future__ import annotations

import enum
import re
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class ArtifactType(enum.StrEnum):
	"""Types of artifacts that can be detected in messages."""
	
	CODE_BLOCK = "code_block"
	TEXT_BLOCK = "text_block"
	MARKDOWN = "markdown"
	DATA = "data"


@dataclass
class ArtifactMatch:
	"""Represents a detected artifact in message content."""
	
	type: ArtifactType
	content: str
	language: Optional[str] = None
	title: Optional[str] = None
	start_pos: int = 0
	end_pos: int = 0


class Artifact(BaseModel):
	"""Model for storing artifact information."""
	
	id: str = Field(description="Unique identifier for the artifact")
	type: ArtifactType = Field(description="Type of artifact")
	content: str = Field(description="The actual content of the artifact")
	title: str = Field(description="Human-readable title for the artifact")
	language: Optional[str] = Field(default=None, description="Programming language for code artifacts")
	created_at: datetime = Field(default_factory=datetime.now)
	source_message_id: Optional[str] = Field(default=None, description="ID of source message")


class ArtifactDetector:
	"""Detects and extracts artifacts from message content."""
	
	# Pattern for fenced code blocks
	CODE_BLOCK_PATTERN = re.compile(
		r'```(\w+)?\n(.*?)```',
		re.DOTALL | re.MULTILINE
	)
	
	# Pattern for inline code
	INLINE_CODE_PATTERN = re.compile(r'`([^`\n]+)`')
	
	# Pattern for significant text blocks (heuristic: 3+ lines, 100+ chars)
	TEXT_BLOCK_PATTERN = re.compile(
		r'(?:^|\n\n)([^\n]*\n[^\n]*\n[^\n]*(?:\n[^\n]*)*)',
		re.MULTILINE
	)
	
	@classmethod
	def detect_artifacts(cls, content: str) -> List[ArtifactMatch]:
		"""Detect artifacts in message content.
		
		Args:
			content: The message content to analyze
			
		Returns:
			List of detected artifacts
		"""
		artifacts = []
		
		# Detect fenced code blocks
		for match in cls.CODE_BLOCK_PATTERN.finditer(content):
			language = match.group(1) if match.group(1) else None
			code_content = match.group(2).strip()
			
			if len(code_content) > 10:  # Only consider substantial code blocks
				artifacts.append(ArtifactMatch(
					type=ArtifactType.CODE_BLOCK,
					content=code_content,
					language=language,
					title=cls._generate_title(code_content, language),
					start_pos=match.start(),
					end_pos=match.end()
				))
		
		# Detect significant text blocks (avoid duplicating code blocks)
		used_ranges = [(a.start_pos, a.end_pos) for a in artifacts]
		
		for match in cls.TEXT_BLOCK_PATTERN.finditer(content):
			text_content = match.group(1).strip()
			start_pos = match.start(1)
			end_pos = match.end(1)
			
			# Skip if overlaps with existing artifacts or too short
			if (len(text_content) < 100 or 
				any(start_pos < end and end_pos > start for start, end in used_ranges)):
				continue
				
			artifacts.append(ArtifactMatch(
				type=ArtifactType.TEXT_BLOCK,
				content=text_content,
				title=cls._generate_title(text_content, None),
				start_pos=start_pos,
				end_pos=end_pos
			))
		
		return artifacts
	
	@classmethod
	def _generate_title(cls, content: str, language: Optional[str] = None) -> str:
		"""Generate a descriptive title for an artifact.
		
		Args:
			content: The artifact content
			language: Programming language if applicable
			
		Returns:
			Generated title
		"""
		lines = content.strip().split('\n')
		first_line = lines[0][:50].strip()
		
		if language:
			return f"{language.title()} Code: {first_line}..."
		elif len(lines) > 3:
			return f"Text Block: {first_line}..."
		else:
			return f"Content: {first_line}..."


class ArtifactManager:
	"""Manages a collection of artifacts from conversations."""
	
	def __init__(self):
		"""Initialize the artifact manager."""
		self.artifacts: List[Artifact] = []
	
	def add_artifacts_from_content(
		self, 
		content: str, 
		source_message_id: Optional[str] = None
	) -> List[Artifact]:
		"""Extract and add artifacts from message content.
		
		Args:
			content: Message content to analyze
			source_message_id: ID of the source message
			
		Returns:
			List of newly added artifacts
		"""
		detected = ArtifactDetector.detect_artifacts(content)
		new_artifacts = []
		
		for match in detected:
			artifact = Artifact(
				id=self._generate_id(),
				type=match.type,
				content=match.content,
				title=match.title,
				language=match.language,
				source_message_id=source_message_id
			)
			self.artifacts.append(artifact)
			new_artifacts.append(artifact)
		
		return new_artifacts
	
	def get_artifacts_by_type(self, artifact_type: ArtifactType) -> List[Artifact]:
		"""Get artifacts filtered by type.
		
		Args:
			artifact_type: Type to filter by
			
		Returns:
			List of artifacts of the specified type
		"""
		return [a for a in self.artifacts if a.type == artifact_type]
	
	def get_artifact_by_id(self, artifact_id: str) -> Optional[Artifact]:
		"""Get an artifact by its ID.
		
		Args:
			artifact_id: The artifact ID
			
		Returns:
			The artifact if found, None otherwise
		"""
		return next((a for a in self.artifacts if a.id == artifact_id), None)
	
	def remove_artifact(self, artifact_id: str) -> bool:
		"""Remove an artifact by ID.
		
		Args:
			artifact_id: The artifact ID to remove
			
		Returns:
			True if removed, False if not found
		"""
		for i, artifact in enumerate(self.artifacts):
			if artifact.id == artifact_id:
				del self.artifacts[i]
				return True
		return False
	
	def clear_all(self) -> None:
		"""Clear all artifacts."""
		self.artifacts.clear()
	
	def _generate_id(self) -> str:
		"""Generate a unique ID for an artifact.
		
		Returns:
			Unique artifact ID
		"""
		import uuid
		return str(uuid.uuid4())[:8]