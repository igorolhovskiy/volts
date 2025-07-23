"""
Core functionality for custom JSON dump with preserved newlines and tabs.
"""

import json
import sys
from typing import Any, TextIO, Optional, Union


def custom_json_dump(obj: Any, fp: TextIO = sys.stdout, indent: Optional[Union[int, str]] = None, **kwargs) -> None:
    """
    Serialize obj to a JSON formatted string and write it to fp,
    with special handling for \n and \t characters in strings.

    Args:
        obj: The object to serialize
        fp: File-like object to write to
        indent: Number of spaces for indentation (int) or string to use for indentation
        **kwargs: Additional arguments passed to json.dumps (except indent)
    """
    # Remove indent from kwargs if present to avoid conflicts
    kwargs.pop('indent', None)

    # First, serialize to string with regular json
    json_str = json.dumps(obj, indent=indent, **kwargs)

    if indent is None:
        # No indentation requested, just handle newlines in strings
        result = _process_string_without_indent(json_str)
    else:
        # Process with indentation
        result = _process_string_with_indent(json_str, indent)

    # Add final line break
    result += "\n"

    fp.write(result)


def _process_string_without_indent(json_str: str) -> str:
    """Process JSON string without indentation, handling newlines and tabs in strings."""
    # First process tabs
    processed = _process_tabs_in_line(json_str)

    # Then process newlines in strings
    result = []
    in_string = False
    escape_next = False

    i = 0
    while i < len(processed):
        char = processed[i]

        if escape_next:
            if char == 'n' and in_string:
                # This is \n in a string - convert to actual newline
                result.append('\n')
            else:
                result.append('\\')
                result.append(char)
            escape_next = False
        elif char == '\\':
            escape_next = True
        elif char == '"':
            in_string = not in_string
            result.append(char)
        else:
            result.append(char)

        i += 1

    return ''.join(result)


def _process_string_with_indent(json_str: str, indent: Union[int, str]) -> str:
    """Process JSON string with indentation, handling \n and \t in strings."""
    # Determine indent string and size
    if isinstance(indent, int):
        indent_str = ' ' * indent
        indent_size = indent
    else:
        indent_str = str(indent)
        indent_size = len(indent_str)

    lines = json_str.split('\n')
    result_lines = []

    for line in lines:
        # Process tabs in string values first
        processed_line = _process_tabs_in_line(line)

        # Check if this line contains a string with newlines that need special handling
        if _contains_string_with_newlines(processed_line):
            # Extract the current indentation level
            current_indent = _get_line_indent(processed_line)

            # Process string literals with newlines
            processed_line = _process_newlines_in_strings(processed_line, current_indent, indent_size)

            # This might result in multiple lines
            if '\n' in processed_line:
                result_lines.extend(processed_line.split('\n'))
            else:
                result_lines.append(processed_line)
        else:
            result_lines.append(processed_line)

    return '\n'.join(result_lines)


def _process_tabs_in_line(line: str) -> str:
    """Replace \t characters in JSON string values with 4 spaces."""
    result = []
    in_string = False
    escape_next = False

    i = 0
    while i < len(line):
        char = line[i]

        if escape_next:
            if char == 't' and in_string:
                # This is a \t in a string, replace with 4 spaces
                result.append('    ')
            else:
                # Keep other escaped characters as-is
                result.append('\\')
                result.append(char)
            escape_next = False
        elif char == '\\':
            escape_next = True
        elif char == '"' and not escape_next:
            in_string = not in_string
            result.append(char)
        else:
            result.append(char)

        i += 1

    return ''.join(result)


def _contains_string_with_newlines(line: str) -> bool:
    """Check if line contains a JSON string with \n characters."""
    in_string = False
    escape_next = False

    for char in line:
        if escape_next:
            if char == 'n' and in_string:
                return True
            escape_next = False
        elif char == '\\':
            escape_next = True
        elif char == '"':
            in_string = not in_string

    return False


def _get_line_indent(line: str) -> str:
    """Get the indentation string from the beginning of a line."""
    indent = ""
    for char in line:
        if char in ' \t':
            indent += char
        else:
            break
    return indent


def _process_newlines_in_strings(line: str, base_indent: str, global_indent_size: int) -> str:
    """Process \n characters in JSON string values."""
    result = []
    in_string = False
    escape_next = False

    i = 0
    while i < len(line):
        char = line[i]

        if escape_next:
            if char == 'n' and in_string:
                # This is \n in a string - convert to actual newline with proper indent
                current_line = ''.join(result)

                # Look for the pattern where we have a key-value pair like: "key": "value
                # vs array element like: "value
                colon_pos = current_line.rfind('": "')

                if colon_pos != -1 and global_indent_size <= 2:
                    # For small global indentation (1-2 spaces), align continuation with string value start
                    string_indent = ' ' * (colon_pos + 4)  # position after ": "
                    result.append('\n' + string_indent)
                else:
                    # For other cases (arrays, larger indents, etc.), use base indentation
                    result.append('\n' + base_indent)
            elif char == 't' and in_string:
                # This is \t in a string - should already be handled, but keep as-is
                result.append('\\t')
            else:
                result.append('\\')
                result.append(char)
            escape_next = False
        elif char == '\\':
            escape_next = True
        elif char == '"':
            in_string = not in_string
            result.append(char)
        else:
            result.append(char)

        i += 1

    return ''.join(result)
