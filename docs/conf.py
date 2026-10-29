
# ADaPT Documentation Configuration

project = "ADaPT"
author = "Concordia Aircraft Systems Lab"
release = "1.0"

extensions = [
    "myst_nb",
    "sphinx_copybutton",
]

# Recognize both Markdown and Jupyter Notebooks
source_suffix = {
    ".rst": "restructuredtext",
    ".md": "markdown",
    ".ipynb": "myst-nb",
}

# Use index.md as the documentation homepage
root_doc = "index"

# Documentation appearance
html_theme = "sphinx_book_theme"
html_title = "ADaPT Documentation"

html_theme_options = {
    "repository_url": (
        "https://github.com/ConcordiaAircraftSystemsLab/"
        "ADaPT-An-Airship-Design-and-Performance-Tool"
    ),
    "use_repository_button": True,
    "use_fullscreen_button": True,
    "show_toc_level": 2,
}

# Do not execute Jupyter notebooks
nb_execution_mode = "off"

exclude_patterns = [
    "_build",
    ".ipynb_checkpoints",
]
