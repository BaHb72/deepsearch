from typing import Any


class Layout:
    def __init__(self, *args: Any, **kwargs: Any) -> None: ...

    def split(self, *layouts: "Layout") -> None: ...
