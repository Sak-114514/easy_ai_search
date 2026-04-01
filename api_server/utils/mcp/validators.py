"""
MCP参数验证工具
"""

import json
import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class SchemaValidationError(Exception):
    """Schema验证错误"""

    pass


class ParameterValidator:
    """参数验证器"""

    @staticmethod
    def validate(schema: Dict[str, Any], data: Dict[str, Any]) -> Dict[str, Any]:
        """
        验证参数是否符合JSON Schema

        Args:
            schema: JSON Schema
            data: 参数数据

        Returns:
            验证后的数据

        Raises:
            SchemaValidationError: 验证失败
        """
        if not isinstance(schema, dict):
            raise SchemaValidationError("Schema must be a dictionary")

        schema_type = schema.get("type")
        if schema_type == "object":
            return ParameterValidator._validate_object(schema, data)
        elif schema_type == "array":
            return ParameterValidator._validate_array(schema, data)
        elif schema_type == "string":
            return ParameterValidator._validate_string(schema, data)
        elif schema_type == "number":
            return ParameterValidator._validate_number(schema, data)
        elif schema_type == "integer":
            return ParameterValidator._validate_integer(schema, data)
        elif schema_type == "boolean":
            return ParameterValidator._validate_boolean(schema, data)
        else:
            return data

    @staticmethod
    def _validate_object(
        schema: Dict[str, Any], data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        验证对象类型

        Args:
            schema: JSON Schema
            data: 参数数据

        Returns:
            验证后的数据

        Raises:
            SchemaValidationError: 验证失败
        """
        if not isinstance(data, dict):
            raise SchemaValidationError(f"Expected object, got {type(data).__name__}")

        properties = schema.get("properties", {})
        required = schema.get("required", [])
        additional_properties = schema.get("additionalProperties", True)

        result = {}

        for prop_name, prop_schema in properties.items():
            if prop_name in data:
                try:
                    result[prop_name] = ParameterValidator.validate(
                        prop_schema, data[prop_name]
                    )
                except SchemaValidationError as e:
                    raise SchemaValidationError(f"Property '{prop_name}': {str(e)}")
            elif prop_name in required:
                raise SchemaValidationError(f"Missing required property: {prop_name}")

        for key, value in data.items():
            if key not in properties:
                if additional_properties:
                    result[key] = value
                else:
                    logger.warning(f"Ignoring additional property: {key}")

        return result

    @staticmethod
    def _validate_array(schema: Dict[str, Any], data: Any) -> list:
        """
        验证数组类型

        Args:
            schema: JSON Schema
            data: 参数数据

        Returns:
            验证后的数据

        Raises:
            SchemaValidationError: 验证失败
        """
        if not isinstance(data, list):
            raise SchemaValidationError(f"Expected array, got {type(data).__name__}")

        items_schema = schema.get("items", {})
        min_items = schema.get("minItems")
        max_items = schema.get("maxItems")

        if min_items is not None and len(data) < min_items:
            raise SchemaValidationError(
                f"Array length {len(data)} < minItems {min_items}"
            )

        if max_items is not None and len(data) > max_items:
            raise SchemaValidationError(
                f"Array length {len(data)} > maxItems {max_items}"
            )

        if items_schema:
            return [ParameterValidator.validate(items_schema, item) for item in data]

        return data

    @staticmethod
    def _validate_string(schema: Dict[str, Any], data: Any) -> str:
        """
        验证字符串类型

        Args:
            schema: JSON Schema
            data: 参数数据

        Returns:
            验证后的数据

        Raises:
            SchemaValidationError: 验证失败
        """
        if not isinstance(data, str):
            raise SchemaValidationError(f"Expected string, got {type(data).__name__}")

        min_length = schema.get("minLength")
        max_length = schema.get("maxLength")
        pattern = schema.get("pattern")
        enum = schema.get("enum")

        if min_length is not None and len(data) < min_length:
            raise SchemaValidationError(
                f"String length {len(data)} < minLength {min_length}"
            )

        if max_length is not None and len(data) > max_length:
            raise SchemaValidationError(
                f"String length {len(data)} > maxLength {max_length}"
            )

        if pattern is not None:
            import re

            if not re.match(pattern, data):
                raise SchemaValidationError(f"String does not match pattern: {pattern}")

        if enum is not None and data not in enum:
            raise SchemaValidationError(f"Value must be one of: {enum}")

        return data

    @staticmethod
    def _validate_number(schema: Dict[str, Any], data: Any) -> float:
        """
        验证数字类型

        Args:
            schema: JSON Schema
            data: 参数数据

        Returns:
            验证后的数据

        Raises:
            SchemaValidationError: 验证失败
        """
        if not isinstance(data, (int, float)):
            raise SchemaValidationError(f"Expected number, got {type(data).__name__}")

        minimum = schema.get("minimum")
        maximum = schema.get("maximum")
        exclusive_minimum = schema.get("exclusiveMinimum")
        exclusive_maximum = schema.get("exclusiveMaximum")

        value = float(data)

        if minimum is not None and value < minimum:
            raise SchemaValidationError(f"Value {value} < minimum {minimum}")

        if maximum is not None and value > maximum:
            raise SchemaValidationError(f"Value {value} > maximum {maximum}")

        if exclusive_minimum is not None and value <= exclusive_minimum:
            raise SchemaValidationError(
                f"Value {value} <= exclusiveMinimum {exclusive_minimum}"
            )

        if exclusive_maximum is not None and value >= exclusive_maximum:
            raise SchemaValidationError(
                f"Value {value} >= exclusiveMaximum {exclusive_maximum}"
            )

        return value

    @staticmethod
    def _validate_integer(schema: Dict[str, Any], data: Any) -> int:
        """
        验证整数类型

        Args:
            schema: JSON Schema
            data: 参数数据

        Returns:
            验证后的数据

        Raises:
            SchemaValidationError: 验证失败
        """
        if not isinstance(data, int) or isinstance(data, bool):
            raise SchemaValidationError(f"Expected integer, got {type(data).__name__}")

        value = ParameterValidator._validate_number(schema, data)

        return int(value)

    @staticmethod
    def _validate_boolean(schema: Dict[str, Any], data: Any) -> bool:
        """
        验证布尔类型

        Args:
            schema: JSON Schema
            data: 参数数据

        Returns:
            验证后的数据

        Raises:
            SchemaValidationError: 验证失败
        """
        if not isinstance(data, bool):
            raise SchemaValidationError(f"Expected boolean, got {type(data).__name__}")

        return data
