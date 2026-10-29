
# ==================================================
# ADaPT Documentation - Sphinx Configuration
# ==================================================

project = "ADaPT"
author = "Concordia Aircraft Systems Lab"
release = "1.0"

# Extensions
extensions = [
    "myst_nb",
    "sphinx_copybutton",
]

# Main documentation page
root_doc = "index"

# Theme
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

# Prevent notebook execution during documentation build
nb_execution_mode = "off"

# Exclude generated files
exclude_patterns = [
    "_build",
    ".ipynb_checkpoints",
]
