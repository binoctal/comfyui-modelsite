# The repository root is itself a ComfyUI custom-node package (it has __init__.py with relative imports);
# keep pytest from trying to import it as a test package.
collect_ignore = ["__init__.py"]
