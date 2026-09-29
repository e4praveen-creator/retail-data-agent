"""Strict provider contracts and matching local checks for the approved tools.

The provider schema is a generation aid, not the execution boundary. Every
returned call is checked locally before dispatch. Optional values are nullable
on the wire and omitted for handlers so existing Python defaults still apply.
Only the JSON Schema subset used by this application's tool registry is supported.
"""
from copy import deepcopy
import json
import math

MAX_ARGUMENT_BYTES = 256_000


def _strict_schema(schema, *, optional=False):
    result = deepcopy(schema)
    if result.get('type') == 'object':
        properties = result.get('properties', {})
        required = set(result.get('required', properties))
        result['properties'] = {
            name: _strict_schema(value, optional=name not in required)
            for name, value in properties.items()
        }
        result['required'] = list(properties)
        result['additionalProperties'] = False
    elif result.get('type') == 'array':
        result['items'] = _strict_schema(result['items'])
    if optional:
        kinds = result['type'] if isinstance(result['type'], list) else [result['type']]
        result['type'] = list(dict.fromkeys([*kinds, 'null']))
        if 'enum' in result and None not in result['enum']:
            result['enum'].append(None)
    return result


def function(name, description, properties, required=None):
    """Build a Responses function schema without changing handler defaults."""
    schema = {
        'type': 'object', 'properties': properties,
        'required': list(properties) if required is None else required,
        'additionalProperties': False,
    }
    return {
        'type': 'function', 'name': name, 'description': description,
        'strict': True, 'parameters': _strict_schema(schema),
    }


def _nullable(schema):
    return 'null' in (schema['type'] if isinstance(schema['type'], list) else [schema['type']])


def _validate(value, schema, path):
    kinds = schema['type'] if isinstance(schema['type'], list) else [schema['type']]
    matches = {
        'null': value is None,
        'string': isinstance(value, str),
        'boolean': isinstance(value, bool),
        'integer': isinstance(value, int) and not isinstance(value, bool),
        'number': not isinstance(value, bool) and (isinstance(value, int) or isinstance(value, float) and math.isfinite(value)),
        'array': isinstance(value, list),
        'object': isinstance(value, dict),
    }
    if not any(matches.get(kind, False) for kind in kinds):
        raise ValueError(f'{path} must have type {" or ".join(kinds)}.')
    if 'enum' in schema and value not in schema['enum']:
        raise ValueError(f'{path} must use one of its declared values.')
    if value is None:
        return None
    if isinstance(value, dict):
        properties = schema.get('properties', {})
        unknown = set(value) - set(properties)
        if unknown:
            raise ValueError(f'{path} contains undeclared fields: {", ".join(sorted(unknown))}.')
        # Older recorded calls can omit optional fields. Strict model requests
        # supply null; both forms deliberately select the same handler default.
        missing = [name for name in schema.get('required', [])
                   if name not in value and not _nullable(properties[name])]
        if missing:
            raise ValueError(f'{path} is missing required fields: {", ".join(missing)}.')
        return {name: _validate(item, properties[name], f'{path}.{name}')
                for name, item in value.items()
                if item is not None or not _nullable(properties[name])}
    if isinstance(value, list):
        return [_validate(item, schema['items'], f'{path}[{index}]')
                for index, item in enumerate(value)]
    if 'minimum' in schema and value < schema['minimum']:
        raise ValueError(f'{path} must be at least {schema["minimum"]}.')
    return value


def _unique_object(pairs):
    result = {}
    for name, value in pairs:
        if name in result:
            raise ValueError('Tool arguments contain a duplicate JSON field.')
        result[name] = value
    return result


def _reject_constant(_):
    raise ValueError('Tool arguments must use finite JSON values.')


def parse_arguments(name, raw_arguments, approved_tools):
    """Reject undeclared tools and malformed arguments before any side effects."""
    definition = approved_tools.get(name)
    if definition is None:
        raise ValueError('Tool is not in the approved tool registry for this run.')
    if not isinstance(raw_arguments, str):
        raise ValueError('Tool arguments must be a JSON object encoded as text.')
    if len(raw_arguments.encode('utf-8')) > MAX_ARGUMENT_BYTES:
        raise ValueError('Tool arguments exceed the 256,000-byte limit.')
    try:
        arguments = json.loads(raw_arguments, object_pairs_hook=_unique_object, parse_constant=_reject_constant)
    except json.JSONDecodeError as exc:
        raise ValueError('Tool arguments must contain valid JSON.') from exc
    return _validate(arguments, definition['parameters'], 'arguments')
