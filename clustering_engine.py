import requests
import json
import redis
import base64


class DataForSEOClient:
    def __init__(self, api_user, api_password):
        self.api_user = api_user
        self.api_password = api_password
        self.base_url = (
            "https://api.dataforseo.com/v3/serp/google/organic/live/advanced"
        )

    def fetch_serp(self, keyword, location_code=2840, language_code="en"):
        """
        Fetches live SERP data for a single keyword.
        """
        post_data = dict()
        post_data[len(post_data)] = dict(
            keyword=base64.b64encode(keyword.encode('utf-8')).decode('utf-8'),
            location_code=location_code,
            language_code=language_code,
            depth=10
        )

        try:
            response = requests.post(
                self.base_url,
                auth=(self.api_user, self.api_password),
                json=list(post_data.values()),
                timeout=60
            )
            if response.status_code == 200:
                return response.json()
            else:
                print(f"Error fetching SERP for {keyword}: "
                      f"{response.status_code} - {response.text}")
                return None
        except Exception as e:
            print(f"Exception fetching SERP for {keyword}: {e}")
            return None


class SERPClusteringEngine:
    def __init__(self, dataforseo_user, dataforseo_password, redis_url=None):
        self.client = DataForSEOClient(dataforseo_user, dataforseo_password)
        self.redis_client = None
        if redis_url:
            try:
                self.redis_client = redis.from_url(redis_url)
                self.redis_client.ping()  # Test connection
            except Exception as e:
                print(f"Redis connection failed: {e}")
                self.redis_client = None

    def get_cached_serp(self, keyword):
        if self.redis_client:
            cached_data = self.redis_client.get(f"serp:{keyword}")
            if cached_data:
                return json.loads(cached_data)
        return None

    def cache_serp(self, keyword, data):
        if self.redis_client and data:
            # 30 days TTL
            self.redis_client.setex(
                f"serp:{keyword}", 2592000, json.dumps(data)
            )

    async def fetch_serps_async(
        self, keywords, location_code=2840, language_code="en"
    ):
        """
        Fetches SERPs for a list of keywords, checking cache first.
        This is a wrapper around the synchronous DataForSEO call to make it
        compatible with async flows if needed, though DataForSEO live endpoint
        is synchronous.
        """
        results = {}
        keywords_to_fetch = []

        # Check cache first
        for kw in keywords:
            cached = self.get_cached_serp(kw)
            if cached:
                results[kw] = cached
            else:
                keywords_to_fetch.append(kw)

        # Fetch missing keywords
        # Note: DataForSEO supports batching up to 100 keywords in a single POST
        # We will implement batching here for efficiency.
        batch_size = 50  # Safe batch size
        for i in range(0, len(keywords_to_fetch), batch_size):
            batch = keywords_to_fetch[i:i+batch_size]
            # Prepare batch request
            post_data = []
            for kw in batch:
                post_data.append(dict(
                    keyword=base64.b64encode(
                        kw.encode('utf-8')
                    ).decode('utf-8'),
                    location_code=location_code,
                    language_code=language_code,
                    depth=10
                ))

            try:
                response = requests.post(
                    "https://api.dataforseo.com/v3/serp/google/organic/"
                    "live/advanced",
                    auth=(self.client.api_user, self.client.api_password),
                    json=post_data,
                    timeout=120
                )

                if response.status_code == 200:
                    resp_json = response.json()
                    if 'tasks' in resp_json:
                        for task in resp_json['tasks']:
                            if task['status_code'] == 20000:
                                # Decode keyword from result if possible,
                                # or map by index if order is preserved
                                # DataForSEO returns results in order.
                                # However, let's rely on the 'data' object
                                # inside result if available,
                                # but 'keyword' is in the 'data' block.
                                result_data = task['result'][0]
                                # This might be the query
                                kw_original = result_data['keyword']

                                # Extract URLs
                                urls = []
                                titles = []
                                for item in result_data.get('items', []):
                                    if item['type'] == 'organic':
                                        urls.append(item['url'])
                                        titles.append(item['title'])

                                serp_data = {
                                    'urls': urls[:10],
                                    'titles': titles[:10]
                                }
                                results[kw_original] = serp_data
                                self.cache_serp(kw_original, serp_data)
                            else:
                                print(f"Task error: {task['status_message']}")
                else:
                    print(f"Batch request failed: {response.status_code}")

            except Exception as e:
                print(f"Exception in batch fetch: {e}")

            # Simple progress update if running in Streamlit
            # if 'progress_bar' in st.session_state:
            #     st.session_state.progress_bar.progress(...)

        return results

    def calculate_overlap(self, urls1, urls2):
        """
        Calculates the percentage of overlapping URLs between two lists.
        """
        set1 = set(urls1)
        set2 = set(urls2)
        if not set1 or not set2:
            return 0.0
        
        intersection = len(set1.intersection(set2))
        # Using the smaller set size as denominator is a common strategy for
        # "hard" clustering to group specific long-tails with broader terms
        # if they share the same top results.
        # However, the requirement says "share >= 80% of the same URLs".
        # Usually this implies Intersection / Union or
        # Intersection / min(len(set1), len(set2)).
        # Let's use Intersection / 10 (since we take top 10) or
        # Intersection / min(len).
        # We'll use Intersection / 10 as a standard SERP similarity metric.

        return (intersection / 10.0) * 100

    def cluster_keywords(self, keywords, serp_results, threshold=80):
        """
        Clusters keywords based on SERP URL overlap.
        """
        clusters = {}  # cluster_id -> list of keywords
        keyword_to_cluster = {}
        cluster_counter = 0

        # Sort keywords by volume if available (not passed here yet),
        # otherwise alphabetical
        # Processing high volume keywords first is usually better for
        # "leader" based clustering.
        # For now, we'll just iterate.

        sorted_keywords = sorted(keywords)

        for kw in sorted_keywords:
            if kw not in serp_results:
                continue
            
            urls = serp_results[kw].get('urls', [])
            if not urls:
                continue

            assigned = False
            
            # Try to match with existing clusters
            # We compare with the "leader" (first keyword) of the cluster
            for cid, cluster_kws in clusters.items():
                leader_kw = cluster_kws[0]
                leader_urls = serp_results[leader_kw].get('urls', [])
                
                overlap = self.calculate_overlap(urls, leader_urls)
                
                if overlap >= threshold:
                    clusters[cid].append(kw)
                    keyword_to_cluster[kw] = cid
                    assigned = True
                    break
            
            if not assigned:
                # Create new cluster
                cluster_counter += 1
                clusters[cluster_counter] = [kw]
                keyword_to_cluster[kw] = cluster_counter

        return clusters, keyword_to_cluster
