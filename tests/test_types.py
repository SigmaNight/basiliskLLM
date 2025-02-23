"""Test cases for the custom types in the basiliskLLM application."""

import pytest
from pydantic import BaseModel, ValidationError
from upath import UPath

from basilisk.types import PydanticOrderedSet, PydanticUPath


def test_basic_set_operations():
	"""Test basic operations of PydanticOrderedSet."""
	test_set = PydanticOrderedSet([1, 2, 3])
	assert list(test_set) == [1, 2, 3]
	assert len(test_set) == 3
	assert 2 in test_set
	assert 4 not in test_set
	assert test_set[1] == 2


def test_order_preservation():
	"""Test that order is preserved in PydanticOrderedSet."""
	test_set = PydanticOrderedSet([3, 1, 4, 1, 5, 9, 2, 6, 5, 3, 5])
	assert list(test_set) == [3, 1, 4, 5, 9, 2, 6]


def test_pydantic_model_integration():
	"""Test integration of PydanticOrderedSet with Pydantic models."""

	class TestModel(BaseModel):
		numbers: PydanticOrderedSet[int]
		strings: PydanticOrderedSet[str]

	model = TestModel(numbers=[3, 1, 4, 1, 5], strings=['a', 'b', 'a', 'c'])
	assert list(model.numbers) == [3, 1, 4, 5]
	assert list(model.strings) == ['a', 'b', 'c']


def test_json_serialization():
	"""Test JSON serialization and deserialization of PydanticOrderedSet."""

	class TestModel(BaseModel):
		data: PydanticOrderedSet[int]

	model = TestModel(data=[3, 1, 4, 1, 5])
	json_data = model.model_dump_json()
	assert json_data == "{\"data\":[3,1,4,5]}"

	# Test deserialization
	loaded_model = TestModel.model_validate_json(json_data)
	assert list(loaded_model.data) == [3, 1, 4, 5]


def test_type_validation():
	"""Test type validation in PydanticOrderedSet."""

	class TestModel(BaseModel):
		numbers: PydanticOrderedSet[int]

	with pytest.raises(ValidationError):
		TestModel(numbers=["not", "numbers"])


def test_pydantic_schema():
	"""Test Pydantic schema generation for PydanticOrderedSet."""

	class TestModel(BaseModel):
		data: PydanticOrderedSet[int]

	schema = TestModel.model_json_schema()
	assert schema['properties']['data']['type'] == 'array'
	assert schema['properties']['data']['items']['type'] == 'integer'


def test_pydantic_upath(tmp_path: str):
	"""Test PydanticUPath."""
	path = PydanticUPath(tmp_path)
	assert path == UPath(tmp_path)


def test_invalid_pydantic_upath():
	"""Test invalid PydanticUPath."""
	with pytest.raises(TypeError):
		PydanticUPath(12345)
