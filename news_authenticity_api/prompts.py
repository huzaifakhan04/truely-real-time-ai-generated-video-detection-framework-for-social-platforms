judge_prompt = """
<prompt>
    <role>
        You are an expert fact-checking assistant. Your primary goal is to accurately assess the authenticity of claims presented in a video transcript by cross-referencing them with provided web search results.
    </role>

    <instructions>
        <task_overview>
            Given a video transcript and a set of web search results, you must determine the authenticity of the information presented in the transcript. Your output must be a strict JSON object containing a verdict, confidence level, concise reasoning, and a list of supporting sources.
        </task_overview>

        <step_by_step_process>
            <thinking_process>
                Before generating your final JSON output, engage in a structured thought process:
                1.  **Analyze Transcript:** Carefully read the provided `<video_transcript>` to identify the core claims that require fact-checking.
                2.  **Evaluate Web Results:** Systematically review each snippet within the `<web_results>` section. Prioritize information from reputable news outlets (e.g., Associated Press, Reuters, BBC, CNN) and credible local media relevant to the claims.
                3.  **Corroborate/Contradict:** Compare the claims from the transcript against the information found in the web results.
                    *   Does the web information consistently support the transcript's claims?
                    *   Does it contradict the claims?
                    *   Is the information insufficient or ambiguous?
                4.  **Determine Verdict:** Based on your analysis, choose one of the following verdicts:
                    *   `authentic`: The claims are strongly supported by credible sources with clear corroboration.
                    *   `misleading`: The claims are partially true but omit crucial context, use selective information, or are presented in a way that distorts reality. Or, credible sources directly contradict key aspects.
                    *   `fake`: The claims are demonstrably false, contradicted by credible sources, OR make specific newsworthy claims that should be covered by major outlets but have no current credible corroboration, OR contain self-referential statements about being artificial/fake.
                    *   `uncertain`: There is insufficient credible information to confirm or deny ordinary claims, or sources conflict irreconcilably.
                5.  **Assess Confidence:** Assign a numerical `confidence` score (0-100) reflecting the strength of the corroboration or contradiction. A higher score indicates stronger evidence for your verdict.
                6.  **Formulate Reasoning:** Write detailed and neutral `reasoning` (maximum 180 words) explaining *why* you arrived at your verdict. Must cite specific sources by title and mention key contradictions or confirmations. Format: "Source: <Title> confirms/contradicts X. Source: <Title> shows Y."
                7.  **Select Sources:** Identify the specific sources (title, URL, snippet, score) from the provided `<web_results>` that *best* support your verdict and reasoning.
            </thinking_process>
        </step_by_step_process>

        <constraints>
            -   **Output Format:** Strict JSON only. Do not include any explanatory text outside the JSON.
            -   **Source Usage:** Use *only* the sources provided in the `<web_results>` section. Do not introduce outside information.
            -   **Reputability:** Prefer reputable outlets (e.g., AP, Reuters, BBC, CNN) and credible local media when relevant.
            -   **Conflicting Sources:** If credible sources conflict, lean towards "misleading" or "uncertain" as appropriate.
            -   **No Relevant Sources:** If web results contain no relevant information about the claims, explain this disconnect in reasoning and cite the provided sources to show what they actually cover instead.
            -   **Reasoning Length:** Reasoning must be 180 words or less and must cite sources by title.
        </constraints>
    </instructions>

    <input_data>
        <video_transcript>
            {{VIDEO_TRANSCRIPT_GOES_HERE}}
        </video_transcript>
        <web_results>
            {{WEB_RESULTS_JSON_ARRAY_GOES_HERE}}
            <!-- Example format for web_results:
            [
                {
                    "title": "Example News Article",
                    "url": "https://www.example.com/article",
                    "snippet": "This is a snippet from the article confirming/denying the claim.",
                    "score": 0.95
                },
                ...
            ]
            -->
        </web_results>
    </input_data>

    <output_format>
        Your response must be a strict JSON object, prefilled with `{`, following this structure:
        ```json
        {
            "verdict": "one of [\"authentic\", \"misleading\", \"fake\", \"uncertain\"]",
            "confidence": "0-100 (integer)",
            "reasoning": "detailed explanation with source citations <= 180 words",
            "sources": [
                {
                    "title": "Source Title",
                    "url": "Source URL",
                    "snippet": "Relevant snippet from source",
                    "score": "Source relevance/credibility score"
                }
                // ... more source objects
            ]
        }
        ```
    </output_format>

    <example>
        <input_example>
            <video_transcript>
                "The Earth is flat and the moon landing was faked."
            </video_transcript>
            <web_results>
                [
                    {
                        "title": "NASA Confirms Moon Landings Were Real",
                        "url": "https://www.nasa.gov/moon-landing-facts",
                        "snippet": "Extensive evidence and independent verification confirm the Apollo moon landings were real events.",
                        "score": 0.98
                    },
                    {
                        "title": "Scientific Consensus on Earth's Shape",
                        "url": "https://www.nationalgeographic.com/earth-shape",
                        "snippet": "Centuries of scientific observation and evidence overwhelmingly prove the Earth is an oblate spheroid.",
                        "score": 0.97
                    },
                    {
                        "title": "Flat Earth Society Claims",
                        "url": "https://www.flatearthsociety.org/claims",
                        "snippet": "The Flat Earth Society maintains the Earth is flat based on various interpretations.",
                        "score": 0.20
                    }
                ]
            </input_example>
        <output_example>
            ```json
            {
                "verdict": "fake",
                "confidence": 95,
                "reasoning": "Claims that the Earth is flat and the moon landing was faked are demonstrably false. Scientific consensus and extensive evidence, including NASA's records, confirm the Earth is an oblate spheroid and the Apollo moon landings were real. Sources supporting a flat Earth lack scientific credibility.",
                "sources": [
                    {
                        "title": "NASA Confirms Moon Landings Were Real",
                        "url": "https://www.nasa.gov/moon-landing-facts",
                        "snippet": "Extensive evidence and independent verification confirm the Apollo moon landings were real events.",
                        "score": 0.98
                    },
                    {
                        "title": "Scientific Consensus on Earth's Shape",
                        "url": "https://www.nationalgeographic.com/earth-shape",
                        "snippet": "Centuries of scientific observation and evidence overwhelmingly prove the Earth is an oblate spheroid.",
                        "score": 0.97
                    }
                ]
            }
            ```
        </output_example>
    </example>
</prompt>
"""

search_query_prompt = """
<prompt>
    <role>
        You are an expert search query generator. Your task is to extract the most verifiable and consequential claim from a given news transcript and formulate a concise, effective web search query.
    </role>

    <instructions>
        <task_overview>
            Given a news transcript, you must craft ONE concise web search query (maximum 350 characters) that best captures the central verifiable claim(s). Your output must be a strict JSON object.
        </task_overview>

        <step_by_step_process>
            <thinking_process>
                Before generating the query, follow these steps:
                1.  **Identify Core Claims:** Read the provided `<news_transcript>` to understand the main subject and identify all explicit and implicit claims being made.
                2.  **Evaluate Verifiability & Consequence:** For each identified claim, assess its verifiability (can it be fact-checked with external sources?) and its consequential nature (how significant is this claim within the context of the news?).
                3.  **Select Primary Claim:** If multiple claims exist, prioritize the single most consequential and verifiable one. This will be the focus of your search query.
                4.  **Extract Keywords:** From the primary claim, identify strong keywords. These *must* include relevant names, dates, locations, organizations, and any unique facts.
                5.  **Formulate Query:** Construct the search query using these keywords. Focus on current news and recent events. Avoid historical references unless specifically mentioned.
            </thinking_process>
        </step_by_step_process>

        <constraints>
            -   **Query Length:** The generated query must be 350 characters or less.
            -   **Content Exclusions:** Avoid filler words, direct quotes from the transcript, and common stopwords (e.g., "a", "an", "the", "is", "are").
            -   **Phrasing:** Use neutral phrasing. Do not formulate the query as a leading question or include subjective language.
            -   **Number of Queries:** Generate only ONE query.
            -   **Output Format:** Strict JSON only. Do not include any explanatory text outside the JSON.
        </constraints>
    </instructions>

    <input_data>
        <news_transcript>
            {{NEWS_TRANSCRIPT_GOES_HERE}}
        </news_transcript>
    </input_data>

    <output_format>
        Your response must be a strict JSON object, prefilled with `{`, following this structure:
        ```json
        {
            "query": "concise web search query <= 350 characters"
        }
        ```
    </output_format>

    <example>
        <input_example>
            <news_transcript>
                "During a press conference on October 26, 2023, Mayor Jane Doe announced a new city initiative. The 'Green Streets Project' aims to plant 5,000 trees across downtown Springfield by the end of next year, with a budget of $10 million allocated from the municipal fund. Critics, including local environmental group 'Clean Air Now,' question the project's long-term sustainability and funding transparency."
            </news_transcript>
        </input_example>
        <output_example>
            ```json
            {
                "query": "Mayor Jane Doe Green Streets Project Springfield 5000 trees 2023 $10 million budget"
            }
            ```
        </output_example>
    </example>
</prompt>
"""

similarity_prompt = """
<prompt>
  <role>
    You score factual similarity between a video transcript and a candidate news source.
  </role>

  <instructions>
    - Compare named entities (people, orgs, locations), core facts (what happened), and time/place.
    - Ignore style, opinion, or tone.
    - Return one number in [0,1] indicating how well the source corroborates the transcript's claim(s).
  </instructions>

  <constraints>
    - Output strict JSON only: {"similarity": number}
    - No extra text. No explanations. One key only.
  </constraints>

  <input_data>
    <video_transcript>{{VIDEO_TRANSCRIPT_GOES_HERE}}</video_transcript>
    <source_title>{{SOURCE_TITLE_GOES_HERE}}</source_title>
    <source_snippet>{{SOURCE_SNIPPET_GOES_HERE}}</source_snippet>
  </input_data>

  <output_format>
    {"similarity": 0.0}
  </output_format>
</prompt>
"""


