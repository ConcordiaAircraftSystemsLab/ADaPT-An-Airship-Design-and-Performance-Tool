"""Sphinx configuration for the ADaPT documentation website."""

project = "ADaPT"
author = "Concordia Aircraft Systems Lab"
release = "1.0"

extensions = [
    "myst_parser",
    "sphinx_copybutton",
]

root_doc = "index"

html_theme = "sphinx_book_theme"
html_title = "ADaPT Documentation"
html_theme_options = {
    "repository_url": (
        "https://github.com/ConcordiaAircraftSystemsLab/"
        "ADaPT-An-Airship-Design-and-Performance-Tool"
    ),
    "use_repository_button": True,
    "use_issues_button": True,
    "use_fullscreen_button": True,
    "show_toc_level": 2,
}

# Support MyST directives and LaTeX math in Markdown source files.
myst_enable_extensions = ["dollarmath", "amsmath", "colon_fence"]
myst_dmath_double_inline = False

exclude_patterns = ["_build", ".ipynb_checkpoints"]
