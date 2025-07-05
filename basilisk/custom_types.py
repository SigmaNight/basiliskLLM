"""Custom pydantic types for basiliskLLM application."""

from typing import Annotated, Any, Sequence, get_args

from ordered_set import OrderedSet
from pydantic import GetCoreSchemaHandler, PlainValidator
from pydantic_core import CoreSchema, core_schema
from upath import UPath

PydanticUPath = Annotated[
	UPath, PlainValidator(lambda v: UPath(v), json_schema_input_type=str)
]


class PydanticOrderedSet(OrderedSet):
	"""Custom OrderedSet class for Pydantic."""

	@classmethod
	def __get_pydantic_core_schema__(
		cls, source: Any, handler: GetCoreSchemaHandler
	) -> CoreSchema:
		"""Generates a Pydantic core schema for the OrderedSet class.

		Args:
			source: The source type.
			handler: The handler to generate the schema.

		Returns:
			A CoreSchema object representing the schema for the OrderedSet class.
		"""
		instance_schema = core_schema.is_instance_schema(cls)
		args = get_args(source)
		if args:
			sequence_t_schema = handler.generate_schema(Sequence[args[0]])
		else:
			sequence_t_schema = handler.generate_schema(Sequence)
		non_instance_schema = core_schema.no_info_after_validator_function(
			cls, sequence_t_schema
		)
		python_schema = core_schema.union_schema(
			[instance_schema, non_instance_schema]
		)
		return core_schema.json_or_python_schema(
			json_schema=non_instance_schema,
			python_schema=python_schema,
			serialization=core_schema.plain_serializer_function_ser_schema(
				lambda x: list(x), return_schema=core_schema.list_schema()
			),
		)
