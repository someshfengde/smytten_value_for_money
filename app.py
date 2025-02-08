import streamlit as st
import pandas as pd
import requests
import re
from stqdm import stqdm

st.set_page_config(layout="wide")
# Smytten API Endpoint
SMYTTEN_URL = "https://route.smytten.com/discover_item/app/products/list"
HEADERS = {
    "accept": "application/json",
    "content-type": "application/json"
}
PAYLOAD_TEMPLATE = {
    "page": {"pageId": 0},
    "timestamp": 0,
    "id": "1234"
}

# Function to fetch data from API
@st.cache_data(ttl=86400)  # Cache for 24 hours
def fetch_smytten_data():
    all_collections = []

    for page in stqdm(range(64)):
        payload = PAYLOAD_TEMPLATE.copy()
        payload["page"]["pageId"] = page

        response = requests.post(SMYTTEN_URL, json=payload, headers=HEADERS)
        if response.status_code != 200:
            print(f"Error on page {page}: HTTP {response.status_code}")
            continue

        data = response.json()
        content = data.get("content", [])

        if isinstance(content, list):
            for category in content:
                if not isinstance(category, dict):
                    continue
                category_name = category.get("category_name", "Unknown Category")

                for subcategory in category.get("subcategories", []):
                    subcategory_name = subcategory.get("subcategory_name", "Unknown Subcategory")

                    for collection in subcategory.get("collections", []):
                        collection["category_name"] = category_name
                        collection["subcategory_name"] = subcategory_name
                        all_collections.append(collection)
        elif isinstance(content, dict) and "products" in content:
            all_collections.extend(content.get("products", []))

    print(f"Total collections scraped: {len(all_collections)}")

    # Function to process and filter the product data
    def process_product_data(products):
        def parse_size(size_str):
            """Extracts numeric value from size string (e.g., '25 ml' -> 25.0)."""
            match = re.search(r'([\d\.]+)', str(size_str))
            return float(match.group(1)) if match else 0.0

        # Sort products based on multiple criteria
        sorted_products = sorted(
            products,
            key=lambda prod: (
                -(prod.get("rate_count") or 0),  # Highest ratings first
                prod.get("product_point") or float('inf'),  # Lowest product points first
                -parse_size(prod.get("size") or "0")  # Largest size first
            )
        )

        df = pd.DataFrame(sorted_products)

        # Filtered relevant columns
        columns_needed = ['categorySlug', 'subcatSlug', 'name', 'average_rating', 'product_point', 'size']
        if df.empty:
            return df

        df_filtered = df[columns_needed].copy()
        df_filtered['average_rating'] = pd.to_numeric(df_filtered['average_rating'], errors='coerce')
        df_filtered['product_point'] = pd.to_numeric(df_filtered['product_point'], errors='coerce')
        df_filtered['size'] = df_filtered['size'].astype(str)
        df_filtered['size_numeric'] = df_filtered['size'].str.extract(r'(\d+\.?\d*)').astype(float)

        # Filtering top-rated, lowest product points, and larger sizes
        high_rating_threshold = df_filtered['average_rating'].quantile(0.75)
        low_product_points_threshold = df_filtered['product_point'].quantile(0.25)
        high_size_threshold = df_filtered['size_numeric'].quantile(0.75)

        filtered_products = df_filtered[
            (df_filtered['average_rating'] >= high_rating_threshold) &
            (df_filtered['product_point'] <= low_product_points_threshold) &
            (df_filtered['size_numeric'] >= high_size_threshold)
        ]

        additional_columns = ['brand', 'web_url', 'product_family', 'sku']
        filtered_products_extended = filtered_products.merge(df[additional_columns + columns_needed], on=columns_needed, how='left')

        # Constructing product URLs
        base_url = "https://smytten.com/trial/product/face-wash-and-cleansers/"
        filtered_products_extended['new_url'] = base_url + \
            filtered_products_extended['name'].str.replace(" ", "-").str.lower() + "/" + \
            filtered_products_extended['sku']

        # Adding price columns
        price_columns = ['price', 'selling_price']
        filtered_products_extended = filtered_products_extended.merge(df[price_columns + columns_needed], on=columns_needed, how='left')

        return filtered_products_extended

    data = process_product_data(all_collections)
    return data

# Load data
df = fetch_smytten_data()

# Streamlit App

st.title("🛍️ Smytten Product Explorer")


# Sidebar Filters
st.sidebar.header("🔍 Filter Products")

# Category Filter
category_options = ["All"] + sorted(df["categorySlug"].dropna().unique().tolist())
selected_category = st.sidebar.selectbox("Select Category", category_options)

# Subcategory Filter
subcat_options = (
    ["All"] + sorted(df[df["categorySlug"] == selected_category]["subcatSlug"].dropna().unique().tolist())
    if selected_category != "All" else ["All"] + sorted(df["subcatSlug"].dropna().unique().tolist())
)
selected_subcategory = st.sidebar.selectbox("Select Subcategory", subcat_options)

# Brand Filter
brand_options = ["All"] + sorted(df["brand"].dropna().unique().tolist())
selected_brand = st.sidebar.selectbox("Select Brand", brand_options)

# Price Filter
min_price, max_price = int(df["price"].min()), int(df["price"].max())
price_range = st.sidebar.slider("Select Price Range", min_value=min_price, max_value=max_price, value=(min_price, max_price))

# Product Point Filter (new slider)
min_points, max_points = int(df["product_point"].min()), int(df["product_point"].max())
points_range = st.sidebar.slider("Select Product Points Range", min_value=min_points, max_value=max_points, value=(min_points, max_points))

# Search Bar
search_query = st.sidebar.text_input("Search for a product", "")

# Apply Filters
filtered_df = df.copy()
if selected_category != "All":
    filtered_df = filtered_df[filtered_df["categorySlug"] == selected_category]
if selected_subcategory != "All":
    filtered_df = filtered_df[filtered_df["subcatSlug"] == selected_subcategory]
if selected_brand != "All":
    filtered_df = filtered_df[filtered_df["brand"] == selected_brand]

# Apply price and product_point filtering
filtered_df = filtered_df[(filtered_df["price"] >= price_range[0]) & (filtered_df["price"] <= price_range[1])]
filtered_df = filtered_df[(filtered_df["product_point"] >= points_range[0]) & (filtered_df["product_point"] <= points_range[1])]

if search_query:
    filtered_df = filtered_df[filtered_df["name"].str.contains(search_query, case=False, na=False)]

# Display Products in a dataframe
st.subheader(f"Showing top {len(filtered_df)} Products across {len(filtered_df['categorySlug'].unique())} categories")
st.dataframe(filtered_df[["categorySlug", "subcatSlug", "name", "brand", "price", "selling_price", "average_rating", "product_point", "new_url"]])

# Clickable Product Links (highlighting product points)
st.markdown("### Clickable Product Links")
for _, row in filtered_df.iterrows():
    st.markdown(
        f"- **{row['brand']}** | [{row['name']}]({row['new_url']}) - **Points: {row['product_point']}**, Rating: {row['average_rating']}, Size: {row['size']} Selling price: {row['selling_price']}"
    )


