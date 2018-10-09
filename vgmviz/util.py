from typing import Optional, TypeVar


T = TypeVar('T')


def coalesce(*args: Optional[T]) -> T:
    if len(args) == 0:
        raise TypeError('coalesce expected 1 argument, got 0')
    for arg in args:
        if arg is not None:
            return arg
    # return args[-1]
    raise TypeError('coalesce() called with all None')
