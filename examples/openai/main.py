import dotenv
from pathlib import Path
import os
import openai

def test(client):
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": "What is OpenAI?"}],
        stream=False,
        # max_tokens=50
    )

    print(f"The response was:{response.choices[0]}")


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
            openai.api_key = api_key
        else:
            print("Could not load api key!")
            raise EnvironmentError("Could not load openai api key!")

        client = openai.OpenAI()

        test(client)
    else:
        raise FileNotFoundError(f'.env file not found at {env_path} ')
