"""工具之间的通用接口（DESIGN §2）：frozen dataclass ⇄ JSON。

to_json 输出纯 JSON；from_json 按 dataclass 的类型注解还原。
"""

import dataclasses
import json
import types
import typing
from datetime import UTC, date, datetime
from enum import Enum
from typing import Any

from tradesys.calendar_utils import to_utc


def to_plain(obj: Any) -> Any:
    if dataclasses.is_dataclass(obj):
        return {f.name: to_plain(getattr(obj, f.name)) for f in dataclasses.fields(obj)}
    if isinstance(obj, Enum):
        return obj.value
    if isinstance(obj, datetime):
        return to_utc(obj).isoformat()
    if isinstance(obj, date):
        return obj.isoformat()
    if isinstance(obj, tuple | list):
        return [to_plain(x) for x in obj]
    if isinstance(obj, dict | types.MappingProxyType):
        return {k: to_plain(v) for k, v in obj.items()}
    return obj


def to_json(obj: Any) -> str:
    return json.dumps(to_plain(obj), ensure_ascii=False, indent=2)


def from_plain(tp: Any, data: Any) -> Any:
    if data is None:
        return None
    origin, args = typing.get_origin(tp), typing.get_args(tp)
    if origin in (typing.Union, types.UnionType):
        return from_plain(next(a for a in args if a is not type(None)), data)
    if origin is tuple:
        if len(args) == 2 and args[1] is Ellipsis:
            return tuple(from_plain(args[0], x) for x in data)
        return tuple(from_plain(a, x) for a, x in zip(args, data, strict=True))
    if dataclasses.is_dataclass(tp):
        hints = typing.get_type_hints(tp)
        fields = {f.name for f in dataclasses.fields(tp)}
        return tp(**{k: from_plain(hints[k], v) for k, v in data.items() if k in fields})
    if tp is datetime:
        dt = datetime.fromisoformat(data)
        return dt.astimezone(UTC) if dt.tzinfo else dt.replace(tzinfo=UTC)
    if tp is date:
        return date.fromisoformat(data)
    if isinstance(tp, type) and issubclass(tp, Enum):
        return tp(data)
    return data


def from_json(tp: type, text: str) -> Any:
    return from_plain(tp, json.loads(text))
