import dataclasses
import re
from typing import List, Tuple

from .helpers import (
    add_indent,
    consume_empty_lines,
    consume_match,
    join_nonempty_lines,
    read_until_closing_bracket,
    snake_to_camel_case,
)
from .models import Documented

_PATTERN_VARIANT = re.compile(r"^ *(?P<ident>\w+) = (?P<value>.+?),\n")


@dataclasses.dataclass()
class Variant(Documented):
    ident: str
    value: str

    @classmethod
    def consume(cls, s: str) -> Tuple["Variant", str]:
        doc, s = Documented.consume(s)
        match, s = consume_match(_PATTERN_VARIANT, s)
        s = consume_empty_lines(s)

        variant = cls(documentation=doc, ident=match["ident"], value=match["value"])
        return variant, s

    def get_value_type(self) -> type:
        if self.value.startswith('"'):
            return str
        elif self.value.isnumeric():
            return int

        raise TypeError(f"can't infer value type for variant: {self}")

    def to_rust(self) -> str:
        ident = snake_to_camel_case(self.ident)
        return join_nonempty_lines(
            (self.rust_documentation(), f"{ident} = {self.value},",)
        )


_PATTERN_ENUM_OPEN = re.compile(r"^ *export enum (?P<ident>\w+) \{\n")
_TYPE2MACRO = {int: "int_enum!", str: "str_enum!"}


@dataclasses.dataclass()
class JsEnum(Documented):
    ident: str
    variants: List[Variant]

    @classmethod
    def consume(cls, s: str) -> Tuple["JsEnum", str]:
        doc, s = Documented.consume(s)
        match, s = consume_match(_PATTERN_ENUM_OPEN, s)
        s = consume_empty_lines(s)

        variants = []
        enum = cls(documentation=doc, ident=match["ident"], variants=variants)

        body, s = read_until_closing_bracket(s)
        s = consume_empty_lines(s)
        while body:
            variant, body = Variant.consume(body)
            variants.append(variant)

        return enum, s

    def get_value_type(self) -> type:
        it = (variant.get_value_type() for variant in self.variants)
        try:
            first_ty = next(it)
        except StopIteration:
            raise ValueError(f"can't infer value type for empty enum: {self}") from None

        if not all(ty == first_ty for ty in it):
            raise TypeError(f"enum has multiple conflicting value types: {self}")

        return first_ty

    def macro(self) -> str:
        ty = self.get_value_type()
        return _TYPE2MACRO[ty]

    def to_rust(self) -> str:
        enum_body = "\n".join(variant.to_rust() for variant in self.variants)
        macro_body = f"pub enum {self.ident} {{\n{add_indent(enum_body)}\n}}"
        return f"{self.macro()} {{\n{add_indent(macro_body)}\n}}"
