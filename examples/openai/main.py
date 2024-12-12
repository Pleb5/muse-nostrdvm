import dotenv
from pathlib import Path
import os
from nostr_sdk.nostr_sdk import asyncio
import openai

async def test(client):
    response = await client.chat.completions.create(
        model="gpt-4o-mini",
        messages=
        [
            {"role": "system", "content": create_system_instructions()},
            {"role": "user", "content": load_test_content()},
        ],
        stream=False,
        # max_tokens=50
    )

    print(f"The response was:{response.choices[0]}")


def load_test_content():
    test_file = Path(r'/home/johnd/Projects/muse-nostrdvm/tests/test_posts/test_500_posts_cleaned_result.txt'
    )

    if test_file.is_file():
        # Open the file for reading
        with test_file.open('r') as f:
            content = f.read()
            return content
    else:
        raise FileNotFoundError(f'Test file {test_file} NOT found')

def create_system_instructions():
    instructions = """
    You are a classifier that identifies freelancing-related social media posts. 
    A post is relevant if:
    1. The user is seeking a solution to a task or problem.
    2. The user is searching for someone to complete a task.

    The posts are in this format:\
        '<Post ID as Decimal number>.<new line><Post text>'
    Respond only with the post IDs if the post is relevant.
    """
    return instructions

if __name__ == '__main__':
    env_path = Path('.env')
    if not env_path.is_file():
        with open('.env', 'w') as f:
            print("Writing new .env file")
            f.write('')
    if env_path.is_file():
        print(f"env path: {env_path}")
        print(f'loading environment from {env_path.resolve()}')

        dotenv.load_dotenv(env_path, verbose=True, override=True)

        api_key = os.getenv("OPENAI_API_KEY")

        if api_key:
            print(f"api key: {api_key[:5]}")
        else:
            print("Could not load api key!")
            raise EnvironmentError("Could not load openai api key!")

        client = openai.AsyncOpenAI(api_key = api_key)

        asyncio.run(test(client))
    else:
        raise FileNotFoundError(f'.env file not found at {env_path} ')
