from typing import List

async def fetch_classification_response(openai_client, posts) -> List[str]:
    system_instructions = """
    Your job is to classify social media posts if they are relevant for freelancers or not, based on these criteria: 
    a. The post contains a technical task or problem.
    b. In the post someone is asking for help or looking for a person to resolve a problem or offering an opportunity to complete a job.

    The posts should be categorized as:
    1. Meaning the post meets both criteria a. and b.
    0. Meaning the post neither meets criterium a. nor criterium b.

    The posts are in this format:
        The post ID comes first as 4 hexa characters followed by a colon character,
        then comes the text of the post. At the end of the post there is a line break followed by the next Post ID and so on.

    Go over each post and categorize them this way:
    - '1' (meets both criteria: the post is about a technical issue and someone is seeking a solution or describing a gig)
    - '0' (the post does not contain a technical challenge or there is no job opportunity for a freelancer).
    Respond only with the post ID followed by a colon and then the category number, with line breaks between the individual posts.
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
        max_tokens=5000 
    )

    print(f'OpenAI reponse was:{response}')
    response_text = response.choices[0].message

    result = []
    for line in response_text.splitlines():
        result.append(line.strip())
    
    # array of event id-s truncated to 4 hex chars
    return result






