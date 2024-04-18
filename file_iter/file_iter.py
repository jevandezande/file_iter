import itertools
from collections import deque
from pathlib import Path
from typing import Any, Callable, Iterable, Iterator, Literal, overload

_marker: Any = object()


class FileIter(Iterator[str]):
    """
    A Swiss Army knife iterator for files (or any iterator of strings)

    - Strips lines
    - Keeps track of the current line: `current_line`
    - Keeps track of the line number: `position`
        - Specify position if entering in the middle of a file: `FileIter(f, position=10)`
    - Peek at the next line: `peek()`
    - Jump ahead `n` lines `jump(n)`
    - Check if empty: `isempty()`
    - Filter out unimportant lines:
        - Always filter: `FileIter(f, filter_func=is_data)`
        - Filter only single next(): `filter_next(filter_func)`

    >>> def is_data(line: str) -> bool:
    ...    return len(line) > 0 and (line[0] != "#")
    >>> my_iter = FileIter(
    ...     ["Hello", "", "# comment", "World", "How", "are", "you?"],
    ...     filter_func=is_data
    ... )
    >>> next(my_iter)
    'Hello'
    >>> my_iter.peek()  # peek does not respect filter_func
    ''
    >>> next(my_iter)  # skips "" and "# comment"
    'World'
    >>> my_iter.position
    3
    >>> my_iter.current_line
    'World'
    >>> my_iter.jump(3)  # jump does not respect filter_func
    'you?'
    >>> my_iter.position
    6
    >>> my_iter.isempty()
    True
    >>> my_iter.peek(default="default")
    'default'
    """

    def __init__(
        self,
        iterable: Iterable[str],
        position: int = -1,
        filter_func: Callable[[str], bool] | None = None,
    ) -> None:
        """
        :param iterable: an iterable object
        :param position: the current position in the iterable
        :param filter_func: a function that checks if the line is useful, otherwise skips
        :return: an iterator object
        """
        self._it = iter(iterable)
        self._cache: deque[str] = deque()
        self._current_line: str = _marker
        self._filter_func = filter_func
        self._position = position

    def __iter__(self) -> Iterator[str]:
        return self

    def __next__(self) -> str:
        """
        Get the next element in the iterator

        Applies the filter function if it exists
        >>> my_iter = FileIter(["", "# comment", "data"], filter_func=is_data)
        >>> next(my_iter)
        'data'
        >>> my_iter.position
        2
        >>> my_iter = FileIter(["", "# no", "", "# data"], filter_func=is_data)
        >>> for line in my_iter:
        ...     print(line)
        """
        if self._filter_func is None:
            return self._next()

        while not (self._filter_func(self._next())):
            pass

        return self._current_line

    def _next(self) -> str:
        """
        Return the next line and update the position

        Updates the line number only if successful
        """
        line = self._cache.popleft() if self._cache else next(self._it)
        self._current_line = line.strip()
        self._position += 1
        return self._current_line

    @overload
    def filtered_next(self, filter_func: Callable[[str], bool]) -> str: ...

    @overload
    def filtered_next(
        self, filter_func: Callable[[str], bool], default: object
    ) -> str | object: ...

    def filtered_next(
        self,
        filter_func: Callable[[str], bool],
        default: str | object = _marker,
    ) -> str | object:
        """
        Get the next element in the iterator that passes the filter function

        :param filter_func: a function that checks if the line is valid

        >>> my_iter = FileIter(["", "# comment", "hello"])
        >>> my_iter.filtered_next(is_data)
        'hello'
        >>> my_iter = FileIter(["", "# no", "", "# data"])
        >>> my_iter.filtered_next(is_data, default="default")
        'default'
        >>> my_iter.filtered_next(is_data)
        Traceback (most recent call last):
        ...
        StopIteration
        """
        try:
            while not filter_func(next(self)):
                pass
            return self._current_line
        except StopIteration:
            if default is _marker:
                raise
            return default

    @property
    def position(self) -> int:
        """
        Get the current position in the iterator

        Note: -1 indicates the iterator has not been read yet

        >>> my_iter = FileIter(["a", "b", "c"])
        >>> my_iter.position
        -1
        >>> next(my_iter), next(my_iter)
        ('a', 'b')
        >>> my_iter.position
        1
        """
        return self._position

    @property
    def current_line(self) -> str:
        """
        Get the current line in the iterator

        >>> my_iter = FileIter(["a", "b", "c"])
        >>> my_iter.current_line
        Traceback (most recent call last):
        ...
        ValueError: Have not read any lines yet
        >>> next(my_iter), next(my_iter)
        ('a', 'b')
        >>> my_iter.current_line
        'b'
        """
        if self._current_line is _marker:
            raise ValueError("Have not read any lines yet")

        return self._current_line

    def jump(self, num: int) -> str:
        """
        Jump forward the specified number of elements in the iterator

        Note: jump does not respect the filter function

        :param num: the number of elements to jump forward
        :return: the line n-steps forward

        >>> my_iter = FileIter(["a", "b", "c"])
        >>> next(my_iter)
        'a'
        >>> my_iter.jump(2)
        'c'
        >>> my_iter.position
        2
        >>> my_iter.jump(-1)
        Traceback (most recent call last):
        ...
        IndexError: Can only jump forward
        """
        if num < 1:
            raise IndexError("Can only jump forward")

        for _ in itertools.islice(self, num - 1):
            pass

        return next(self)

    @overload
    def peek(self) -> str: ...

    @overload
    def peek(self, default: object) -> object | str: ...

    def peek(self, default: object = _marker) -> object | str:
        """
        Get the next element in the iterator without consuming it

        Note: peek does not respect the filter function

        :param default: the value to return if the iterator is empty
        :return: the next element in the iterator

        >>> my_iter = FileIter(["a", "b", "c"], filter_func=lambda x: x != "b")
        >>> my_iter.peek()
        'a'
        >>> my_iter.position
        -1
        >>> next(my_iter), my_iter.position
        ('a', 0)
        >>> my_iter.peek(), my_iter.position
        ('b', 0)
        >>> next(my_iter)
        'c'
        >>> my_iter.peek("default")
        'default'
        >>> my_iter.peek()
        Traceback (most recent call last):
        ...
        StopIteration
        """
        if not self._cache:
            try:
                self._cache.append(next(self._it))
            except StopIteration:
                if default is _marker:
                    raise
                return default
        return self._cache[0]

    def isempty(self) -> bool:
        """
        Check if the iterator is empty

        >>> my_iter = FileIter(["a", "b", "c"])
        >>> my_iter.isempty()
        False
        >>> next(my_iter), next(my_iter), next(my_iter)
        ('a', 'b', 'c')
        >>> my_iter.isempty()
        True
        """
        try:
            self.peek()
            return False
        except StopIteration:
            return True


class FileIterContextManager:
    """
    Manage opening and closing a file for iteration

    See FileIter for more information
    Note: contextlib.contextmanager is not used to avoid mypy issues

    >>> from tempfile import NamedTemporaryFile
    >>> with NamedTemporaryFile("w") as f:
    ...     _ = f.write("Hello\\n# comment\\n\\nWorld")
    ...     _ = f.seek(0)
    ...
    ...     with FileIterContextManager(f.name, filter_func=is_data) as my_iter:
    ...         for line in my_iter:
    ...             print(line, my_iter.position)
    Hello 0
    World 3
    >>> with NamedTemporaryFile("w") as f:  # doctest: +ELLIPSIS
    ...     name = f.name
    ...     _ = f.write("Hello\\n# comment\\n\\nWorld")
    ...     _ = f.seek(0)
    ...
    ...     with FileIterContextManager(f.name, filter_func=is_data) as my_iter:
    ...         _ = next(my_iter), next(my_iter)
    ...         my_iter.jump(-1)
    Traceback (most recent call last):
    ...
    IndexError: Can only jump forward
    Error reading ... at line=3
    """

    def __init__(
        self,
        filename: str | Path,
        position: int = -1,
        filter_func: Callable[[str], bool] | None = None,
    ) -> None:
        self.filename = Path(filename)
        self.start_position = position
        self.filter_func = filter_func

    def __enter__(self) -> FileIter:
        self.file = open(self.filename)
        self.file_iter = FileIter(self.file, self.start_position, self.filter_func)
        return self.file_iter

    def __exit__(
        self, exc_type: type | None, exc_value: Exception | None, traceback: Any | None
    ) -> Literal[False]:
        if exc_value is not None:
            exc_value.add_note(f"Error reading {self.filename} at line={self.file_iter.position}")
        self.file.close()
        return False


def is_data(line: str) -> bool:
    """
    Check if the line contains data (presumes it has been stripped)

    >>> is_data("hello")
    True
    >>> is_data("# comment")
    False
    >>> is_data("")
    False
    """
    return len(line) > 0 and (line[0] != "#")
