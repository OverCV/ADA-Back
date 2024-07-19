from typing import TypedDict


class StructProps:
    TITLE: str = 'title'
    ISTATE: str = 'istate'
    EFFECT: str = 'effect'
    ACTUAL: str = 'actual'
    SUBSYS: str = 'bgcond'
    FORMAT: str = 'format'
    TENSOR: str = 'tensor'
    SIZE: str = 'size'

    DIST_IDX: int = 0
    DIST_ARR: int = 1


class ConceptType(TypedDict):
    bool: list[int]
    # bool: list[int]
