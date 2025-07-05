"""Test cases for the custom types in the basiliskLLM application."""

import pytest
from pydantic import BaseModel, ValidationError
from upath import UPath

from basilisk.custom_types import PydanticOrderedSet, PydanticUPath


class TestPydanticOrderedSet:
	"""Tests for PydanticOrderedSet custom type."""

	@pytest.fixture
	def basic_set(self):
		"""Return a simple ordered set."""
		return PydanticOrderedSet([1, 2, 3])

	@pytest.fixture
	def duplicate_set(self):
		"""Return an ordered set with duplicates to be removed."""
		return PydanticOrderedSet([3, 1, 4, 1, 5, 9, 2, 6, 5, 3, 5])

	@pytest.fixture
	def test_model_class(self):
		"""Return a Pydantic model class with PydanticOrderedSet fields."""

		class TestModel(BaseModel):
			numbers: PydanticOrderedSet[int]
			strings: PydanticOrderedSet[str]

		return TestModel

	@pytest.fixture
	def simple_model_class(self):
		"""Return a simple Pydantic model with a single PydanticOrderedSet field."""

		class TestModel(BaseModel):
			data: PydanticOrderedSet[int]

		return TestModel

	def test_basic_set_operations(self, basic_set):
		"""Test basic operations of PydanticOrderedSet."""
		assert list(basic_set) == [1, 2, 3]
		assert len(basic_set) == 3
		assert 2 in basic_set
		assert 4 not in basic_set
		assert basic_set[1] == 2

	def test_order_preservation(self, duplicate_set):
		"""Test that order is preserved in PydanticOrderedSet."""
		assert list(duplicate_set) == [3, 1, 4, 5, 9, 2, 6]

	def test_pydantic_model_integration(self, test_model_class):
		"""Test integration of PydanticOrderedSet with Pydantic models."""
		model = test_model_class(
			numbers=[3, 1, 4, 1, 5], strings=['a', 'b', 'a', 'c']
		)
		assert list(model.numbers) == [3, 1, 4, 5]
		assert list(model.strings) == ['a', 'b', 'c']

	def test_json_serialization(self, simple_model_class):
		"""Test JSON serialization and deserialization of PydanticOrderedSet."""
		model = simple_model_class(data=[3, 1, 4, 1, 5])
		json_data = model.model_dump_json()
		assert json_data == "{\"data\":[3,1,4,5]}"

		# Test deserialization
		loaded_model = simple_model_class.model_validate_json(json_data)
		assert list(loaded_model.data) == [3, 1, 4, 5]

	def test_type_validation(self, simple_model_class):
		"""Test type validation in PydanticOrderedSet."""
		with pytest.raises(ValidationError):
			simple_model_class(numbers=["not", "numbers"])

	def test_pydantic_schema(self, simple_model_class):
		"""Test Pydantic schema generation for PydanticOrderedSet."""
		schema = simple_model_class.model_json_schema()
		assert schema['properties']['data']['type'] == 'array'
		assert schema['properties']['data']['items']['type'] == 'integer'


class TestPydanticUPath:
	"""Tests for PydanticUPath custom type."""

	def test_valid_path(self, tmp_path):
		"""Test PydanticUPath with valid path."""
		path = PydanticUPath(tmp_path)
		assert path == UPath(tmp_path)

	def test_invalid_path(self):
		"""Test PydanticUPath with invalid input."""
		with pytest.raises(TypeError):
			PydanticUPath(12345)
