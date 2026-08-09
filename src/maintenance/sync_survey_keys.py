from ._sync_library_keys import _sync_library_keys


def sync_survey_keys(library_dir=None):
    _sync_library_keys(
        library_dir,
        default_relative_path=("library", "survey"),
        preferred_template_name="survey-bdi.json",
        reset_study_values=True,
        skip_item_prefix=True,
        mark_changed_for_skipped_keys=True,
    )


if __name__ == "__main__":
    sync_survey_keys()
