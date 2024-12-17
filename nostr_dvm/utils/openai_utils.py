from typing import List

async def fetch_classification_response(openai_client, posts) -> List[str]:
    system_instructions = """
Your job is to classify social media posts if they are relevant for freelancers
or not, based on these criteria:

    Criterium 'a.' : The post contains a technical challenge or task.
    Criterium 'b.' : In the post someone is seeking advice, looking for a person to
    resolve a problem or offering an opportunity to complete a job.
    This indicates that there might be an intent to hire a freelancer.

Criterium 'a.' ensures that problems are of technical nature and criterium 'b.'
helps identifying that there might be a chance for a freelancer to help out in the issue.

Go over each post text and categorize them this way:
Assign category '1' if the post meets both criteria 'a.' and 'b.' so the post is
about a technical challenge and someone is seeking a solution or describing a gig.

Assign category '0' if the post does not meet at least one of criterium 'a.' or criterium 'b.' so it is either not a technical issue or no one is seeking help so there is no job opportunity for a freelancer.

The posts are in this format:
The post ID comes first as 4 hexa characters followed by a colon character,
then comes the text of the post and at the end of each post there are 4 semicolons. After this comes the next post ID and so on.

Respond in this format: For each post, start with the hex-encoded post ID followed by a colon then the category number and a line break at the end. Then comes the next post and so on.
"""

    response = await openai_client.chat.completions.create(
        # 4o-mini is the best price-value for text classification with gpt
        model="gpt-4o-mini",

        messages=
        [
            {"role": "system", "content": system_instructions},
            {"role": "user", "content": posts},
        ],

        # Don't stream response just fetch in whole as soon as ready
        stream=False, 

        temperature=0, # eliminates "creative" answers

        # Max output tokens. These are pricier so you can limit them but
        # this task is inherently limited by the way the inference task is composed
        max_tokens=10_000 
    )

    print(f'OpenAI reponse was:{response}')
    response_text = response.choices[0].message.content

    result = []
    for line in response_text.splitlines():
        result.append(line.strip())
    
    # array of event id-s truncated to 4 hex chars
    return result






