# Configuration file for the Sphinx documentation builder.
# https://www.sphinx-doc.org/en/master/usage/configuration.html

import os
import sys

# The block reference is generated from the plugin source (see _ext/).
sys.path.insert(0, os.path.abspath("_ext"))

# -- Project information -----------------------------------------------------

project = "Protein Set Selection"
copyright = "2026, BSC | Barcelona Supercomputing Center"
author = "Barcelona Supercomputing Center"
release = "0.1"

# -- General configuration ---------------------------------------------------

extensions = [
    "sphinx.ext.autosectionlabel",
    "sphinx_copybutton",
    "sphinx_design",
    "protselect_reference",
]

# Section labels are prefixed with the document, so the same heading
# ("Inputs", "Parameters", ...) on every block page does not clash.
autosectionlabel_prefix_document = True

templates_path = ["_templates"]
html_static_path = ["_static"]
html_css_files = ["custom.css"]
source_suffix = ".rst"
master_doc = "index"
language = "en"
exclude_patterns = ["_build", "build", "Thumbs.db", ".DS_Store"]
pygments_style = "sphinx"

# Keep "--gres", "--threads" and the like as typed rather than as dashes.
smartquotes = False

# -- Options for HTML output -------------------------------------------------

html_theme = "pydata_sphinx_theme"
html_title = "Protein Set Selection"
html_show_sourcelink = False
html_show_sphinx = False
# Top-level pages have no sub-pages, so the section sidebar would be empty
# there; keep it for the block reference.
html_sidebars = {"*": [], "reference/**": ["sidebar-nav-bs"]}
html_theme_options = {
    "show_nav_level": 1,
    "navigation_depth": 2,
    "logo": {"text": "Protein Set Selection"},
    "icon_links": [
        {
            "name": "GitHub",
            "url": "https://github.com/BSC-CNS-EAPM/protein-set-selection-horus",
            "icon": "fa-brands fa-github",
        },
        {
            "name": "Barcelona Supercomputing Center",
            "url": "https://www.bsc.es/",
            "icon": "fa fa-globe",
        },
    ],
}
