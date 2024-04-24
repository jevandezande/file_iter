"""A Swiss Army knife iterator for files (or any iterator of strings)."""

import gzip
import itertools
from collections import deque
from contextlib import contextmanager
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import IO, Any, Callable, Iterable, Iterator, Literal, overload

_marker: Any = object()


class FileIter(Iterator[str]):
    """
    A Swiss Army knife iterator for files (or any iterator of strings).

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
    - Supports gzip

    >>> def is_data(line:  str) -> bool:
    ...    return len(line) > 0 and (line[0] != "#")
    >>> file_iter = FileIter(
    ...     ["Hello", "", "# comment", "World", "How", "are", "you?"],
    ...     filter_func=is_data
    ... )
    >>> next(file_iter)
    'Hello'
    >>> file_iter.peek()  # peek does not respect filter_func
    ''
    >>> next(file_iter)  # skips "" and "# comment"
    'World'
    >>> file_iter.position
    3
    >>> file_iter.current_line
    'World'
    >>> file_iter.jump(3)  # jump does not respect filter_func
    'you?'
    >>> file_iter.position
    6
    >>> file_iter.isempty()
    True
    >>> file_iter.peek(default="default")
    'default'
    """

    def __init__(
        self,
        iterable: Iterable[str],
        position: int = -1,
        filter_func: Callable[[str], bool] | None = None,
    ) -> None:
        """
        Initialize the FileIter object.

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
        """Iterate over self."""
        return self

    def __next__(self) -> str:
        """
        Get the next element in the iterator.

        Applies the filter function if it exists
        >>> file_iter = FileIter(["", "# comment", "data"], filter_func=is_data)
        >>> next(file_iter)
        'data'
        >>> file_iter.position
        2
        >>> file_iter = FileIter(["", "# no", "", "# data"], filter_func=is_data)
        >>> for line in file_iter:
        ...     print(line)
        """
        if self._filter_func is None:
            return self._next()

        while not (self._filter_func(self._next())):
            pass

        return self._current_line

    def _next(self) -> str:
        """
        Return the next line and update the position.

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
        Get the next element in the iterator that passes the filter function.

        :param filter_func: a function that checks if the line is valid

        >>> file_iter = FileIter(["", "# comment", "hello"])
        >>> file_iter.filtered_next(is_data)
        'hello'
        >>> file_iter = FileIter(["", "# no", "", "# data"])
        >>> file_iter.filtered_next(is_data, default="default")
        'default'
        >>> file_iter.filtered_next(is_data)
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
        Get the current position in the iterator.

        Note: -1 indicates the iterator has not been read yet

        >>> file_iter = FileIter(["a", "b", "c"])
        >>> file_iter.position
        -1
        >>> next(file_iter), next(file_iter)
        ('a', 'b')
        >>> file_iter.position
        1
        """
        return self._position

    @property
    def current_line(self) -> str:
        """
        Get the current line in the iterator.

        >>> file_iter = FileIter(["a", "b", "c"])
        >>> file_iter.current_line
        Traceback (most recent call last):
        ...
        ValueError: Have not read any lines yet
        >>> next(file_iter), next(file_iter)
        ('a', 'b')
        >>> file_iter.current_line
        'b'
        """
        if self._current_line is _marker:
            raise ValueError("Have not read any lines yet")

        return self._current_line

    def jump(self, num: int) -> str:
        """
        Jump forward the specified number of elements in the iterator.

        Note: jump does not respect the filter function

        :param num: the number of elements to jump forward
        :return: the line n-steps forward

        >>> file_iter = FileIter(["a", "b", "c"])
        >>> next(file_iter)
        'a'
        >>> file_iter.jump(2)
        'c'
        >>> file_iter.position
        2
        >>> file_iter.jump(-1)
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
        Get the next element in the iterator without consuming it.

        Note: peek does not respect the filter function

        :param default: the value to return if the iterator is empty
        :return: the next element in the iterator

        >>> file_iter = FileIter(["a", "b", "c"], filter_func=lambda x: x != "b")
        >>> file_iter.peek()
        'a'
        >>> file_iter.position
        -1
        >>> next(file_iter), file_iter.position
        ('a', 0)
        >>> file_iter.peek(), file_iter.position
        ('b', 0)
        >>> next(file_iter)
        'c'
        >>> file_iter.peek("default")
        'default'
        >>> file_iter.peek()
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
        Check if the iterator is empty.

        >>> file_iter = FileIter(["a", "b", "c"])
        >>> file_iter.isempty()
        False
        >>> next(file_iter), next(file_iter), next(file_iter)
        ('a', 'b', 'c')
        >>> file_iter.isempty()
        True
        """
        try:
            self.peek()
            return False
        except StopIteration:
            return True


class FileIterContextManager:
    r"""
    Manage opening and closing a file for iteration.

    See FileIter for more information
    Note: contextlib.contextmanager is not used to avoid mypy issues

    Test regular files
    >>> with tmp_file("Hello\n# comment\n\nWorld") as f:
    ...     with FileIterContextManager(f.name, filter_func=is_data) as file_iter:
    ...         for line in file_iter:
    ...             print(line, file_iter.position)
    Hello 0
    World 3

    Test gzipped files (tmp_file automatically recognizes gzipped files)
    >>> with tmp_file("Hello\n# comment\n\nWorld", gzipped=True) as f:
    ...     with FileIterContextManager(f.name, filter_func=is_data) as file_iter:
    ...         for line in file_iter:
    ...             print(line, file_iter.position)
    Hello 0
    World 3

    Test jumping
    >>> with tmp_file("Hello\n# comment\n\nWorld") as f:  # doctest: +ELLIPSIS
    ...     with FileIterContextManager(f.name, filter_func=is_data) as file_iter:
    ...         _ = file_iter.jump(2)
    ...         file_iter.jump(-1)
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
        gzipped: bool | Literal["auto"] = "auto",
    ) -> None:
        """
        Initialize the FileIterContextManager object.

        :param filename: the name of the file to open
        :param position: the current position in the file
        :param filter_func: a function that checks if the line is useful
        :param gzipped: whether the file is gzipped
        """
        self.filename = Path(filename)
        self.start_position = position
        self.filter_func = filter_func
        self.gzipped = gzipped

    def __enter__(self) -> FileIter:
        """Open the file and return a FileIter object."""
        filename, gzipped = self.filename, self.gzipped
        if gzipped == "auto":
            gzipped = filename.suffix == ".gz"

        self.file = gzip.open(filename, "rt") if gzipped else open(filename)
        self.file_iter = FileIter(self.file, self.start_position, self.filter_func)
        return self.file_iter

    def __exit__(
        self, exc_type: type | None, exc_value: Exception | None, traceback: Any | None
    ) -> Literal[False]:
        """Close the file and indicate the position if there is an exception."""
        if exc_value is not None:
            exc_value.add_note(f"Error reading {self.filename} at line={self.file_iter.position}")
        self.file.close()
        return False


def is_data(line: str) -> bool:
    """
    Check if the line contains data (presumes it has been stripped).

    >>> is_data("hello")
    True
    >>> is_data("# comment")
    False
    >>> is_data("")
    False
    """
    return len(line) > 0 and (line[0] != "#")


@contextmanager  # type: ignore
def tmp_file(data_str: str, gzipped=False, **kwargs: Any) -> Iterable[IO[str]]:
    r"""
    Create a NamedTemporaryFile file with contents `data_str`.

    :param data_str: the string to write to the file
    :param gzipped: whether to write a gzipped file
    :param kwargs: additional keyword arguments to pass to NamedTemporaryFile
    :return: a readable/writable file object

    >>> with tmp_file("Hello\nWorld") as f:
    ...     for line in f:
    ...         print(line.strip())
    Hello
    World
    """
    if gzipped:
        with NamedTemporaryFile("w+", delete=True, suffix=".gz", **kwargs) as f:
            with gzip.open(f.name, "wt") as fgz:
                _ = fgz.write(data_str)
            yield f

    else:
        with NamedTemporaryFile("w+", delete=True, **kwargs) as f:
            _ = f.write(data_str)
            _ = f.seek(0)
            yield f
