"""Printing helpers shared by the terminal scripts in this folder."""


def print_table(columns: list[str], rows: list[list]) -> None:
    """Print rows under their column names, each column right-aligned."""
    lines = [columns, *rows]
    widths = [max(len(str(line[index])) for line in lines) for index in range(len(columns))]
    for line in lines:
        print("  ".join(str(value).rjust(width) for value, width in zip(line, widths, strict=True)))
