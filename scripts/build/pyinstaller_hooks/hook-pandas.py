# Custom hook overriding PyInstaller's default pandas hook.
#
# `--collect-submodules=pandas` (needed to avoid an incomplete bundle, see
# build_app.py) walks the filesystem and force-includes every module under
# pandas.tests as a hidden import. Those modules require pytest to actually
# import, which isn't part of the release build environment, so PyInstaller
# logs hundreds of spurious "Hidden import ... not found" errors and wastes
# build time collecting a test suite that's never needed at runtime. Filtering
# them out at collection time (rather than via --exclude-module, which only
# excludes them *after* they've already been forced as hidden imports) avoids
# both problems.
from PyInstaller.utils.hooks import (
    collect_data_files,
    collect_dynamic_libs,
    collect_submodules,
)

hiddenimports = collect_submodules(
    "pandas", filter=lambda name: not name.startswith("pandas.tests")
)
datas = collect_data_files("pandas")
binaries = collect_dynamic_libs("pandas")
