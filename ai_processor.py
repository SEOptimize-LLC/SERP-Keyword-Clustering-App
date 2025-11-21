import json
import openai
import io
import asyncio


class AIProcessor:
    def __init__(self, api_key, base_url=None):
        if base_url:
            self.client = openai.AsyncOpenAI(
                api_key=api_key, base_url=base_url
            )
            self.sync_client = openai.OpenAI(
                api_key=api_key, base_url=base_url
            )
        else:
            self.client = openai.AsyncOpenAI(api_key=api_key)
            self.sync_client = openai.OpenAI(api_key=api_key)

    def prepare_batch_file(self, clusters, model="gpt-4o-mini"):
        """
        Prepares a JSONL file for OpenAI Batch API.
        clusters: dict {cluster_id: {'keywords': [kw1, kw2],
                                     'titles': [title1, title2]}}
        """
        jsonl_data = []

        for cluster_id, data in clusters.items():
            # Limit to top 20 keywords to save tokens
            keywords = ", ".join(data['keywords'][:20])
            # Top 10 titles
            titles = "\n".join([f"- {t}" for t in data['titles'][:10]])

            prompt = f"""
            Analyze the following keyword cluster and SERP titles to determine
            the user intent and a descriptive label.

            Keywords:
            {keywords}

            Top Ranking Titles:
            {titles}

            Step 1: Analyze the keywords and titles to understand the core
            topic.
            Step 2: Identify the common user needs (e.g., looking for a
            product, wanting to learn, trying to find a specific website).
            Step 3: Reason whether the intent is Informational, Commercial,
            Transactional, or Navigational.
            Step 4: Create a short, human-readable label (2-4 words) for this
            cluster.

            Output the result in JSON format with keys: "reasoning", "intent",
            "label".
            """

            request_obj = {
                "custom_id": str(cluster_id),
                "method": "POST",
                "url": "/v1/chat/completions",
                "body": {
                    "model": model,
                    "messages": [
                        {
                            "role": "system",
                            "content": "You are an SEO expert specializing in "
                                       "search intent analysis."
                        },
                        {"role": "user", "content": prompt}
                    ],
                    "response_format": {"type": "json_object"}
                }
            }
            jsonl_data.append(json.dumps(request_obj))

        return "\n".join(jsonl_data)

    def upload_batch_file(self, jsonl_content):
        """
        Uploads the JSONL file to OpenAI.
        """
        file_obj = io.BytesIO(jsonl_content.encode('utf-8'))
        file_obj.name = "batch_input.jsonl"

        batch_file = self.sync_client.files.create(
            file=file_obj,
            purpose="batch"
        )
        return batch_file.id

    def create_batch_job(self, file_id):
        """
        Creates a batch job.
        """
        batch_job = self.sync_client.batches.create(
            input_file_id=file_id,
            endpoint="/v1/chat/completions",
            completion_window="24h"
        )
        return batch_job.id

    def check_batch_status(self, batch_id):
        """
        Checks the status of a batch job.
        """
        return self.sync_client.batches.retrieve(batch_id)

    def retrieve_batch_results(self, output_file_id):
        """
        Retrieves the results of a completed batch job.
        """
        file_response = self.sync_client.files.content(output_file_id)
        content = file_response.text

        results = {}
        for line in content.split('\n'):
            if line.strip():
                data = json.loads(line)
                custom_id = data['custom_id']
                response_body = data['response']['body']
                choice = response_body['choices'][0]
                content_json = json.loads(choice['message']['content'])
                results[custom_id] = content_json

        return results

    async def process_single_cluster(self, cluster_id, data, model):
        """
        Process a single cluster using standard chat completions (OpenRouter).
        """
        keywords = ", ".join(data['keywords'][:20])
        titles = "\n".join([f"- {t}" for t in data['titles'][:10]])

        prompt = f"""
        Analyze the following keyword cluster and SERP titles to determine
        the user intent and a descriptive label.

        Keywords:
        {keywords}

        Top Ranking Titles:
        {titles}

        Step 1: Analyze the keywords and titles to understand the core
        topic.
        Step 2: Identify the common user needs (e.g., looking for a
        product, wanting to learn, trying to find a specific website).
        Step 3: Reason whether the intent is Informational, Commercial,
        Transactional, or Navigational.
        Step 4: Create a short, human-readable label (2-4 words) for this
        cluster.

        Output the result in JSON format with keys: "reasoning", "intent",
        "label".
        """

        try:
            response = await self.client.chat.completions.create(
                model=model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are an SEO expert specializing in "
                                   "search intent analysis."
                    },
                    {"role": "user", "content": prompt}
                ],
                response_format={"type": "json_object"}
            )
            content = response.choices[0].message.content
            return cluster_id, json.loads(content)
        except Exception as e:
            print(f"Error processing cluster {cluster_id}: {e}")
            return cluster_id, {
                "label": "Error",
                "intent": "Error",
                "reasoning": str(e)
            }

    async def process_with_openrouter(self, clusters, model):
        """
        Process all clusters concurrently using OpenRouter.
        """
        tasks = []
        for cluster_id, data in clusters.items():
            tasks.append(
                self.process_single_cluster(cluster_id, data, model)
            )

        results = {}
        # Process in chunks to avoid rate limits if necessary,
        # but asyncio.gather is usually fine for moderate loads.
        # For safety with OpenRouter free/paid tiers, we might want a
        # semaphore.
        semaphore = asyncio.Semaphore(5)  # Limit concurrent requests

        async def sem_task(task):
            async with semaphore:
                return await task

        responses = await asyncio.gather(*(sem_task(t) for t in tasks))

        for cid, res in responses:
            results[cid] = res

        return results
