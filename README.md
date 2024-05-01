# File Iter

[![License](https://img.shields.io/github/license/jevandezande/file_iter)](https://github.com/jevandezande/file_iter/blob/master/LICENSE)
[![Code style: ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://github.com/astral-sh/ruff)
[![GitHub Workflow Status](https://img.shields.io/github/actions/workflow/status/jevandezande/file_iter/test.yml?branch=master&logo=github-actions)](https://github.com/jevandezande/file_iter/actions/)
[![Codecov](https://img.shields.io/codecov/c/github/jevandezande/file_iter)](https://codecov.io/gh/jevandezande/file_iter)
[![PyPI version](https://img.shields.io/pypi/v/file_iter)](https://pypi.python.org/pypi/file_iter/)

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

```python
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
```

Opening and closing the file can be performed with a context manager, this even works on gzipped files!

`document.txt`
```txt
Hello

# comment
World
```
```python
>>> with FileIterContextManager("document.txt", filter_func=is_data) as file_iter:
...     for line in file_iter:
...         print(line, file_iter.position)
Hello 0
World 3
```

## Credits
This package was created with [Cookiecutter](https://github.com/audreyr/cookiecutter) and the [jevandezande/poetry-cookiecutter](https://github.com/jevandezande/poetry-cookiecutter) project template.
