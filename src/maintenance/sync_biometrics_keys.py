from ._sync_library_keys import _sync_library_keys


def sync_biometrics_keys(library_dir=None):
    _sync_library_keys(
        library_dir,
        default_relative_path=("library", "biometrics"),
        preferred_template_name="biometrics-cmj.json",
        reset_study_values=False,
        skip_item_prefix=False,
        mark_changed_for_skipped_keys=False,
    )


if __name__ == "__main__":
    sync_biometrics_keys()
