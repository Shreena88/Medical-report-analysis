"""Shared base types for Pydantic models.

Defines PyObjectId — a custom type that accepts a MongoDB ObjectId and
serializes it as a plain string in JSON responses.  This avoids exposing
bson.ObjectId in API output while retaining full ObjectId support inside
the application.

Usage:
    class MyModel(BaseModel):
        id: PyObjectId = Field(alias="_id")

    model_config = ConfigDict(populate_by_name=True)
"""

from typing import Annotated, Any

from bson import ObjectId
from pydantic import GetCoreSchemaHandler
from pydantic_core import core_schema


class _PyObjectId(str):
    """String subclass that additionally validates as a bson.ObjectId."""

    @classmethod
    def __get_pydantic_core_schema__(
        cls,
        source_type: Any,
        handler: GetCoreSchemaHandler,
    ) -> core_schema.CoreSchema:
        return core_schema.no_info_plain_validator_function(
            cls._validate,
            serialization=core_schema.to_string_ser_schema(),
        )

    @classmethod
    def _validate(cls, value: Any) -> "_PyObjectId":
        if isinstance(value, ObjectId):
            return cls(str(value))
        if isinstance(value, cls):
            return value
        if isinstance(value, str) and ObjectId.is_valid(value):
            return cls(value)
        raise ValueError(f"Invalid ObjectId: {value!r}")

    def __repr__(self) -> str:
        return f"PyObjectId({str(self)!r})"


# Public alias — use this in model field annotations
PyObjectId = Annotated[_PyObjectId, ...]
