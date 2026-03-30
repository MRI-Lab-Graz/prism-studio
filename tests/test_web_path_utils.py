from src.web.path_utils import strip_temp_path, strip_temp_path_from_message


def test_strip_temp_path_hides_internal_rawdata_validate_root() -> None:
    dataset_path = r"C:\temp\preview\rawdata_validate"
    file_path = r"C:\temp\preview\rawdata_validate\code\recipes\survey"

    assert strip_temp_path(file_path, dataset_path) == "code/recipes/survey"


def test_strip_temp_path_keeps_regular_dataset_root_name() -> None:
    dataset_path = r"C:\studies\my_project"
    file_path = r"C:\studies\my_project\code\recipes\survey"

    assert strip_temp_path(file_path, dataset_path) == "my_project/code/recipes/survey"


def test_strip_temp_message_hides_internal_rawdata_validate_root() -> None:
    dataset_path = r"C:\temp\preview\rawdata_validate"
    message = (
        r"Survey data files found but no recipe JSON files in "
        r"C:\temp\preview\rawdata_validate\code\recipes\survey\."
    )

    assert "rawdata_validate" not in strip_temp_path_from_message(message, dataset_path)
    assert "code/recipes/survey" in strip_temp_path_from_message(message, dataset_path)
