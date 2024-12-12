from pathlib import Path
from nostr_dvm.utils.clean_events import clean_text

if __name__ == '__main__':
    # Get the path to the current script's directory
    current_dir = Path(__file__).parent

    test_posts_path = current_dir / 'test_posts'

    test_file_name = 'test_500_posts'
    file_extension = '.txt'

    test_file_full_name = test_file_name + file_extension
    result_file_name = test_file_name + '_cleaned_result' + file_extension

    test_file_path = test_posts_path / test_file_full_name
    

    if test_file_path.is_file():
        # Open the file for reading
        with test_file_path.open('r') as f:
            content = f.read()
            cleaned_text = clean_text(content)
            with open(test_posts_path / result_file_name, 'w') as result_file:
                result_file.write(cleaned_text)

    else:
        raise FileNotFoundError(f'Test file {test_file_path} NOT found')

