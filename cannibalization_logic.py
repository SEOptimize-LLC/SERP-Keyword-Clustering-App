import requests
from bs4 import BeautifulSoup


class CannibalizationAnalyzer:
    def __init__(self, domain):
        self.domain = domain
        self.sitemap_urls = []

    def fetch_sitemap_urls(self, sitemap_url):
        """
        Fetches all URLs from a sitemap (and nested sitemaps).
        """
        try:
            response = requests.get(sitemap_url, timeout=30)
            if response.status_code != 200:
                print(f"Failed to fetch sitemap: {response.status_code}")
                return []

            soup = BeautifulSoup(response.content, 'xml')
            urls = []

            # Check for nested sitemaps
            sitemaps = soup.find_all('sitemap')
            if sitemaps:
                for sm in sitemaps:
                    loc = sm.find('loc').text
                    urls.extend(self.fetch_sitemap_urls(loc))
            else:
                # Extract URLs
                for url in soup.find_all('url'):
                    loc = url.find('loc').text
                    urls.append(loc)
            
            self.sitemap_urls = list(set(urls))  # Deduplicate
            return self.sitemap_urls
        except Exception as e:
            print(f"Exception fetching sitemap: {e}")
            return []

    def map_clusters_to_urls(self, clusters, serp_results):
        """
        Maps clusters to the user's URLs that are ranking.
        clusters: dict {cluster_id: [kw1, kw2]}
        serp_results: dict {kw: {'urls': [url1, ...], 'titles': [...]}}
        """
        cluster_mapping = {}  # cluster_id -> {url: [ranking_keywords]}

        for cluster_id, keywords in clusters.items():
            cluster_mapping[cluster_id] = {}

            for kw in keywords:
                if kw in serp_results:
                    urls = serp_results[kw].get('urls', [])

                    # Check if any of the ranking URLs belong to the user's
                    # domain
                    for rank, url in enumerate(urls):
                        if self.domain in url:
                            if url not in cluster_mapping[cluster_id]:
                                cluster_mapping[cluster_id][url] = []
                            cluster_mapping[cluster_id][url].append({
                                'keyword': kw,
                                'rank': rank + 1
                            })

        return cluster_mapping

    def detect_cannibalization(self, cluster_mapping):
        """
        Analyzes the mapping to find cannibalization issues.
        """
        issues = []

        for cluster_id, url_map in cluster_mapping.items():
            ranking_urls = list(url_map.keys())

            if len(ranking_urls) > 1:
                # Multiple URLs ranking for the same cluster

                # Check for Indented Results (usually same path prefix or very
                # similar)
                # For simplicity, we'll flag all multi-URL rankings as
                # potential cannibalization unless explicitly filtered.

                # Logic: If multiple URLs rank for keywords in the SAME
                # cluster, it's cannibalization.
                # We need to determine the "primary" URL (e.g., best average
                # rank or most keywords).

                # Calculate stats for each URL
                url_stats = []
                for url, kws in url_map.items():
                    avg_rank = sum(k['rank'] for k in kws) / len(kws)
                    url_stats.append({
                        'url': url,
                        'keyword_count': len(kws),
                        'avg_rank': avg_rank
                    })

                # Sort by keyword count (desc) then avg_rank (asc)
                url_stats.sort(
                    key=lambda x: (-x['keyword_count'], x['avg_rank'])
                )

                primary_url = url_stats[0]['url']
                cannibals = url_stats[1:]

                for cannibal in cannibals:
                    issues.append({
                        'cluster_id': cluster_id,
                        'primary_url': primary_url,
                        'cannibal_url': cannibal['url'],
                        'severity': 'High' if cannibal['keyword_count'] > 1
                        else 'Medium',
                        'action': 'Consolidate' if cannibal['avg_rank'] > 10
                        else 'Review Intent'
                    })

        return issues
