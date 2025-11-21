import streamlit as st
import pandas as pd
import asyncio
import os
from clustering_engine import SERPClusteringEngine
from ai_processor import AIProcessor
from cannibalization_logic import CannibalizationAnalyzer

# --------------------
# Streamlit UI Setup
# --------------------
st.set_page_config(
    page_title="SERP-Based AI Keyword Clustering & Cannibalization Analyzer",
    layout="wide"
)
st.title("🔍 SERP-Based AI Keyword Clustering & Cannibalization Analyzer")

# --------------------
# Sidebar: Configuration
# --------------------
st.sidebar.header("Configuration")

# API Keys
dataforseo_user = st.sidebar.text_input("DataforSEO API User", type="password")
dataforseo_pass = st.sidebar.text_input(
    "DataforSEO API Password", type="password"
)
openai_api_key = st.sidebar.text_input("OpenAI API Key", type="password")
redis_url = st.sidebar.text_input(
    "Redis URL (Optional)",
    value=os.environ.get("REDIS_URL", ""),
    type="password"
)

# Project Settings
domain = st.sidebar.text_input(
    "Your Domain (for Cannibalization Check)", "example.com"
)
sitemap_url = st.sidebar.text_input("Sitemap URL (Optional)", "")
# US
location_code = st.sidebar.number_input(
    "Location Code (DataforSEO)", value=2840
)
language_code = st.sidebar.text_input("Language Code", value="en")
overlap_threshold = st.sidebar.slider(
    "SERP Overlap Threshold (%)", 50, 100, 80
)

# --------------------
# Session State Initialization
# --------------------
if 'serp_results' not in st.session_state:
    st.session_state.serp_results = {}
if 'clusters' not in st.session_state:
    st.session_state.clusters = {}
if 'batch_id' not in st.session_state:
    st.session_state.batch_id = None
if 'ai_results' not in st.session_state:
    st.session_state.ai_results = {}
if 'cannibalization_issues' not in st.session_state:
    st.session_state.cannibalization_issues = []

# --------------------
# Main Interface
# --------------------
tab1, tab2, tab3 = st.tabs([
    "1. Setup & Scrape", "2. Clustering & AI", "3. Analytics & Action"
])

# --- TAB 1: Setup & Scrape ---
with tab1:
    st.header("Upload Keywords & Fetch SERPs")
    uploaded_file = st.file_uploader("Upload Keywords CSV", type="csv")
    
    if uploaded_file:
        df = pd.read_csv(uploaded_file)
        # Try to find keyword column
        cols = [c.lower() for c in df.columns]
        if 'keyword' in cols:
            kw_col = df.columns[cols.index('keyword')]
        elif 'keywords' in cols:
            kw_col = df.columns[cols.index('keywords')]
        else:
            kw_col = st.selectbox("Select Keyword Column", df.columns)
            
        keywords = df[kw_col].dropna().unique().tolist()
        st.write(f"Loaded {len(keywords)} unique keywords.")
        
        if st.button("Fetch SERP Data"):
            if not dataforseo_user or not dataforseo_pass:
                st.error("Please provide DataforSEO credentials.")
            else:
                engine = SERPClusteringEngine(
                    dataforseo_user, dataforseo_pass, redis_url
                )

                with st.spinner(
                    "Fetching SERP data... This may take a while."
                ):
                    # Run async fetch
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    results = loop.run_until_complete(
                        engine.fetch_serps_async(
                            keywords, location_code, language_code
                        )
                    )
                    st.session_state.serp_results = results
                    st.success(
                        f"Fetched SERP data for {len(results)} keywords."
                    )

# --- TAB 2: Clustering & AI ---
with tab2:
    st.header("Clustering & AI Analysis")
    
    if not st.session_state.serp_results:
        st.warning("Please fetch SERP data in Tab 1 first.")
    else:
        if st.button("Run SERP Overlap Clustering"):
            engine = SERPClusteringEngine(
                dataforseo_user, dataforseo_pass, redis_url
            )
            keywords = list(st.session_state.serp_results.keys())
            clusters, kw_map = engine.cluster_keywords(
                keywords, st.session_state.serp_results, overlap_threshold
            )

            # Enrich clusters with titles for AI
            enriched_clusters = {}
            for cid, kws in clusters.items():
                # Get titles from the first keyword (leader)
                leader_kw = kws[0]
                titles = st.session_state.serp_results[leader_kw].get(
                    'titles', []
                )
                enriched_clusters[cid] = {
                    'keywords': kws,
                    'titles': titles
                }

            st.session_state.clusters = enriched_clusters
            st.success(
                f"Created {len(clusters)} clusters from "
                f"{len(keywords)} keywords."
            )
            
        if st.session_state.clusters:
            st.subheader("AI Intent Analysis (OpenAI Batch API)")
            
            if st.button("Submit Batch Job to OpenAI"):
                if not openai_api_key:
                    st.error("Please provide OpenAI API Key.")
                else:
                    ai_processor = AIProcessor(openai_api_key)
                    jsonl_content = ai_processor.prepare_batch_file(
                        st.session_state.clusters
                    )

                    try:
                        file_id = ai_processor.upload_batch_file(jsonl_content)
                        batch_id = ai_processor.create_batch_job(file_id)
                        st.session_state.batch_id = batch_id
                        st.success(f"Batch Job Submitted! ID: {batch_id}")
                        st.info(
                            "Check back in ~24 hours (or sooner) for results."
                        )
                    except Exception as e:
                        st.error(f"Error submitting batch: {e}")

            if st.session_state.batch_id:
                st.write(f"Current Batch ID: `{st.session_state.batch_id}`")
                if st.button("Check Batch Status"):
                    ai_processor = AIProcessor(openai_api_key)
                    try:
                        status = ai_processor.check_batch_status(
                            st.session_state.batch_id
                        )
                        st.write(f"Status: **{status.status}**")

                        if (status.status == "completed" and
                                status.output_file_id):
                            st.success(
                                "Batch Completed! Retrieving results..."
                            )
                            results = ai_processor.retrieve_batch_results(
                                status.output_file_id
                            )
                            st.session_state.ai_results = results
                            st.success("Results retrieved and stored.")
                    except Exception as e:
                        st.error(f"Error checking status: {e}")

# --- TAB 3: Analytics & Action ---
with tab3:
    st.header("Analytics & Action Plan")
    
    if not st.session_state.clusters:
        st.warning("No clusters generated yet.")
    else:
        # Prepare Data for Display
        cluster_data = []
        for cid, data in st.session_state.clusters.items():
            ai_info = st.session_state.ai_results.get(str(cid), {})
            cluster_data.append({
                "Cluster ID": cid,
                "Label": ai_info.get("label", "Pending..."),
                "Intent": ai_info.get("intent", "Pending..."),
                "Keywords": ", ".join(data['keywords']),
                "Size": len(data['keywords'])
            })
        
        df_clusters = pd.DataFrame(cluster_data)
        
        # Metrics
        col1, col2, col3 = st.columns(3)
        col1.metric("Total Clusters", len(df_clusters))
        col2.metric("Avg Cluster Size", round(df_clusters['Size'].mean(), 1))
        
        st.subheader("Cluster Overview")
        st.dataframe(df_clusters, use_container_width=True)
        
        # Cannibalization Check
        st.subheader("Cannibalization Diagnosis")
        if st.button("Check for Cannibalization"):
            if not domain:
                st.error("Please enter your domain in the sidebar.")
            else:
                analyzer = CannibalizationAnalyzer(domain)
                
                # If sitemap provided, fetch URLs (optional, mainly for
                # coverage check)
                # But for cannibalization, we rely on SERP results we already
                # have.

                # Map clusters to ranking URLs
                # We need a simplified cluster dict: {cid: [kws]}
                simple_clusters = {
                    cid: data['keywords']
                    for cid, data in st.session_state.clusters.items()
                }

                mapping = analyzer.map_clusters_to_urls(
                    simple_clusters, st.session_state.serp_results
                )
                issues = analyzer.detect_cannibalization(mapping)

                st.session_state.cannibalization_issues = issues

                if issues:
                    st.error(
                        f"Found {len(issues)} potential cannibalization "
                        "issues."
                    )
                    df_issues = pd.DataFrame(issues)
                    st.dataframe(df_issues, use_container_width=True)
                else:
                    st.success(
                        "No obvious cannibalization issues found in the top "
                        "10 results."
                    )

        # Download
        csv = df_clusters.to_csv(index=False).encode('utf-8')
        st.download_button(
            "Download Cluster Report",
            csv,
            "cluster_report.csv",
            "text/csv",
            key='download-csv'
        )
