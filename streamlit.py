import streamlit as st
import mysql.connector
from mysql.connector import Error
import pandas as pd
import os

from utils import load_and_merge_data, get_product_image, get_local_fallback_image
from recommender import SkincareRecommender

def load_css(file_name):
    with open(file_name) as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

load_css("style.css")

# ===============================
# CONFIG
# ===============================
st.set_page_config(
    page_title="Wardah Skincare Recommendation",
    page_icon="🧴",
    layout="wide"
)
# ===============================
# DATABASE CONNECTION (DENGAN SECRETS)
# ===============================
def get_db_connection():
    """Membuat koneksi ke MySQL Aiven menggunakan secrets"""
    try:
        # Ambil konfigurasi dari secrets
        mysql_secrets = st.secrets.get("mysql", {})
        
        if not mysql_secrets:
            st.error("❌ Konfigurasi database tidak ditemukan di secrets.toml")
            return None
        
        connection_config = {
            "host": mysql_secrets.get("host"),
            "port": mysql_secrets.get("port", 3306),
            "database": mysql_secrets.get("database", "defaultdb"),
            "user": mysql_secrets.get("user", "avnadmin"),
            "password": mysql_secrets.get("password"),
            "use_pure": True,
            "connection_timeout": 10
        }
    # Penanganan ssl
        ssl_ca_content = mysql_secrets.get("ssl_ca")
        
        if ssl_ca_content:
            with tempfile.NamedTemporaryFile(delete=False) as ca_file:
                ca_file.write(ssl_ca_content.encode("utf-8"))
                ca_path = ca_file.name
        
            connection_config["ssl_ca"] = ca_path
            connection_config["ssl_verify_cert"] = True
        else:
            st.error("❌ SSL CA tidak ditemukan di secrets")
            return None
        
        # Koneksi
        connection = mysql.connector.connect(**connection_config)
        
        if connection.is_connected():
            return connection
        else:
            return None
            
    except Error as e:
        st.error(f"❌ Error connecting to MySQL Aiven: {e}")
        return None
    except Exception as e:
        st.error(f"❌ Unexpected error: {e}")
        return None
  

# ===============================
# LOAD DATA
# ===============================
@st.cache_data
def load_data():
    return load_and_merge_data()

df = load_data()

# ===============================
# INITIALIZE RECOMMENDER
# ===============================
@st.cache_resource
def get_recommender():
    return SkincareRecommender(df)

recommender = get_recommender()

# ===============================
# HEADER SECTION
# ===============================
st.markdown("""
<div class="hero-box">
    <h1 class="main-title">Wardah Recommendation Product</h1>
    <p class="subtitle">Rekomendasi Personal Berdasarkan Jenis Kulit & Kategori Produk</p>
</div>
""", unsafe_allow_html=True)
# ===============================
# CATEGORY SHOWCASE
# ===============================
st.markdown("### 📌 Kategori Skincare")
CATEGORY_MAP = {
    "Serum": "assets/serum.webp",
    "Cleanser": "assets/cleanser.png",
    "Face Wash": "assets/facial.png",
    "Moisturizer": "assets/moisturizer.webp",
    "Sunscreen": "assets/sunscreen.webp",
    "Mask": "assets/facemask.webp",
    "Toner": "assets/toner.png",
    "Eye Cream": "assets/eyecream.webp",
    "Scrub": "assets/scrub.png",
    "Micellar Water": "assets/micellar.webp",
}

# Display categories in a grid
st.markdown('<div class="category-grid">', unsafe_allow_html=True)

cols = st.columns(5)
for idx, (category, image_path) in enumerate(CATEGORY_MAP.items()):
    with cols[idx % 5]:
        try:
            st.image(image_path, use_container_width=True)
        except:
            st.markdown(f'''
            <div class="image-wrapper">
                <div class="placeholder-text">
                    📷<br>
                    <small>{category}</small>
                </div>
            </div>
            ''', unsafe_allow_html=True)
        st.markdown(f'<p class="category-name">{category}</p>', unsafe_allow_html=True)

st.markdown('</div>', unsafe_allow_html=True)

# ===============================
# SIDEBAR - USER INPUT
# ===============================
with st.sidebar:
    st.markdown('<div class="sidebar-title"> <span>🌸</span> Beauty Skin</div>', unsafe_allow_html=True)
    
    user_name = st.text_input("**Nama**", value="Guest")
    user_age = st.number_input("**Usia**", min_value=10, max_value=80, value=25, step=1)
    gender = st.selectbox(
        "Jenis kelamin:",
        ["Perempuan", "Laki-laki"],
        key="gender_input")

    # Extract options from data
    skin_type_options = sorted({s for sub in df["skin_type"] for s in sub})
    category_options = sorted({c for sub in df["category"] for c in sub})
    
    selected_skin_type = st.multiselect(
        "**Jenis Kulit**",
        skin_type_options,
        default=["all skin types"] if "all skin types" in skin_type_options else skin_type_options[:1]
    )
    
    selected_category = st.multiselect(
        "**Kategori Produk**",
        category_options,
        default=["serum"] if "serum" in category_options else category_options[:1]
    )
    
    top_n = st.slider(
        "**Jumlah Rekomendasi**",
        min_value=3,
        max_value=12,
        value=6,
        step=1
    )
    
    # Option untuk fallback
    use_local_fallback = st.checkbox("Gunakan gambar default jika tidak ada", value=True, 
                                     help="Gunakan gambar dari folder assets jika gambar produk tidak ditemukan")
    
    search_clicked = st.button(
        "🔍 **Cari Rekomendasi**", 
        type="primary", 
        use_container_width=True
    )

# ===============================
# SAVE RECOMMENDATION TO DATABASE
# ===============================
def save_recommendation_to_db(user_name, user_age, gender, skin_types, categories, recommendations):
    """Simpan rekomendasi ke database"""
    conn = get_db_connection()
    if not conn:
        return None
    
    try:
        cursor = conn.cursor()
        
        # 1. Simpan user history
        skin_types_str = ",".join(skin_types) if skin_types else ""
        categories_str = ",".join(categories) if categories else ""
        
        cursor.execute("""
        INSERT INTO user_history 
        (username, age, gender, skin_type, category) 
        VALUES (%s, %s, %s, %s, %s)
        """, (user_name, user_age, gender, skin_types_str, categories_str))
        
        user_id = cursor.lastrowid
        
        # 2. Simpan rekomendasi produk
        max_recommendations = 3
        for i in range(min(max_recommendations, len(recommendations))):
            product = recommendations.iloc[i]
            cursor.execute("""
            INSERT INTO item_recommend 
            (user_id, product_name, rank_position, product_urls) 
            VALUES (%s, %s, %s, %s)
            """, (
                user_id,
                product['name'],
                i + 1,
                product.get('url')
            ))
        conn.commit()
        cursor.close()
        conn.close()
        
        return user_id
        
    except Error as e:
        st.error(f"❌ Error saving to database: {e}")
        return None
    
# ===============================
# MAIN CONTENT - RECOMMENDATIONS
# ===============================
if search_clicked:
    if not selected_skin_type or not selected_category:
        st.warning("⚠️ Silakan pilih minimal 1 jenis kulit dan 1 kategori.")
    else:
        # Results header
        st.markdown(f'''
        <div class="result-header">
            <h2 class="result-title">✨ Rekomendasi Personal untuk Anda</h2>
            <p class="result-subtitle">
                👤 {user_name} • 📅 {user_age} tahun<br>
                🧬 {', '.join(selected_skin_type)} • 📦 {', '.join(selected_category)}
            </p>
        </div>
        ''', unsafe_allow_html=True)
        
        # Get recommendations
        recs = recommender.recommend(selected_skin_type, selected_category, top_n)
        if recs.empty:
            st.error("Tidak ditemukan produk yang sesuai.")
        else:
            # Simpan ke database
            user_id = save_recommendation_to_db(
                user_name, user_age, gender,
                selected_skin_type, selected_category,
                recs
            )
            
            if user_id:
                st.success(f"✅ Rekomendasi tersimpan (ID: {user_id})")
        
        if recs.empty:
            st.error("❌ Tidak ditemukan produk yang sesuai dengan kriteria Anda.")
        else:
            st.markdown(f'<div class="success-badge">✅ Ditemukan {len(recs)} rekomendasi terbaik!</div>', unsafe_allow_html=True)
            
            # Display in grid (3 columns)
            cols_per_row = 3
            rows = [recs[i:i+cols_per_row] for i in range(0, len(recs), cols_per_row)]
            
            for row_products in rows:
                cols = st.columns(cols_per_row)
                for col_idx, (_, product) in zip(range(cols_per_row), row_products.iterrows()):
                    with cols[col_idx]:
                        # Product Card
                        st.markdown('<div class="product-card">', unsafe_allow_html=True)
                        
                        # Header dengan nama produk
                        st.markdown(f'<div class="product-name">{product["name"]}</div>', unsafe_allow_html=True)
                        
                        # Product Image
                        display_img = None
                        image_source = "original"
                        
                        # Coba ambil gambar asli
                        if pd.notna(product.get('image_url')) and product['image_url'] not in ["", "nan"]:
                            display_img = get_product_image(product['image_url'], product['name'])
                        
                        # Jika tidak ada, gunakan fallback lokal
                        if not display_img and use_local_fallback:
                            # Ambil kategori pertama untuk fallback
                            if product['category']:
                                category = product['category'][0]
                                display_img = get_local_fallback_image(category)
                                image_source = "fallback"
                        
                        # Tampilkan gambar
                        if display_img:
                            st.image(display_img, use_container_width=True)
                            badge_class = "badge-success" if image_source == "original" else "badge-info"
                            badge_text = "Gambar produk" if image_source == "original" else "Gambar ilustrasi"
                            st.markdown(f'<span class="image-badge {badge_class}">{badge_text}</span>', unsafe_allow_html=True)
                        else:
                            st.markdown(f'''
                            <div class="image-wrapper">
                                <div class="placeholder-text">
                                    📸<br>
                                    <small>Gambar tidak tersedia</small>
                                </div>
                            </div>
                            ''', unsafe_allow_html=True)
                            st.markdown(f'<span class="image-badge badge-warning">❌ Tanpa gambar</span>', unsafe_allow_html=True)
                        
                        # Metadata dalam satu baris
                        st.markdown('<div class="meta-row">', unsafe_allow_html=True)
                        
                        tags_html = '<div class="tag-container">'

                        # Categories
                        if product['category']:
                            for cat in product['category'][:2]:
                                tags_html += f'<span class="category-tag">{cat.title()}</span>'

                        # Skin types
                        if product['skin_type']:
                            for skin in product['skin_type'][:2]:
                                tags_html += f'<span class="skin-tag">{skin.title()}</span>'

                        tags_html += '</div>'
                        st.markdown(tags_html, unsafe_allow_html=True)

                        # About Product (collapsible)
                        with st.expander("📝 **Deskripsi Produk**", expanded=False):
                            about_text = product["about"][:300] + "..." if len(product["about"]) > 300 else product["about"]
                            st.markdown(f'<div class="expand-content">{about_text}</div>', unsafe_allow_html=True)
                        
                        # Ingredients (collapsible)
                        with st.expander("🧪 **Komposisi**", expanded=False):
                            ingredients_text = product["ingredients"][:250] + "..." if len(product["ingredients"]) > 250 else product["ingredients"]
                            st.markdown(f'<div class="expand-content">{ingredients_text}</div>', unsafe_allow_html=True)
                        
                        # Product Link Button
                        st.markdown(f'''
                        <a href="{product['url']}" target="_blank" class="btn-product-link">
                            🔗 Lihat Produk Lengkap
                        </a>
                        ''', unsafe_allow_html=True)
                        
                        st.markdown('</div>', unsafe_allow_html=True)

else:
    # Welcome message
    st.markdown("---")
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown('''
        <div style="text-align: center; padding: 40px; background: white; border-radius: 15px; box-shadow: 0 6px 20px rgba(0,0,0,0.08);">
            <h3 style="color: #1e40af; margin-bottom: 20px;">🎯 Mulai Perjalanan Skincare Anda</h3>
            <p style="color: #4b5563; margin-bottom: 25px; line-height: 1.6;">
                Isi profil kulit Anda di sidebar, pilih kategori produk yang diinginkan, 
                dan temukan rekomendasi produk Wardah yang paling sesuai!
            </p>
            <div style="background: linear-gradient(135deg, #dbeafe, #eff6ff); padding: 20px; border-radius: 10px; border: 2px solid #3b82f6;">
                <p style="color: #1e40af; font-weight: 600; margin: 0;">
                    💡 <strong>Tips:</strong> Pilih semua jenis kulit yang relevan untuk hasil yang lebih akurat
                </p>
            </div>
        </div>
        ''', unsafe_allow_html=True)

# ===============================
# AUTO-SCROLL JAVASCRIPT
# ===============================
# Add JavaScript for auto-scrolling when results are shown
if 'show_results' in st.session_state and st.session_state.get('show_results', False):
    # Clear the flag to prevent re-scrolling on refresh
    st.session_state['show_results'] = False
    
    st.markdown("""
    <script>
    // Function to scroll to results section
    function scrollToResults() {
        const element = document.getElementById('results-anchor');
        if (element) {
            // Add a small delay to ensure content is rendered
            setTimeout(() => {
                element.scrollIntoView({ 
                    behavior: 'smooth', 
                    block: 'start',
                    inline: 'nearest'
                });
                
                // Add visual feedback
                element.style.transition = 'all 0.3s ease';
                element.style.boxShadow = '0 0 0 3px rgba(255, 107, 53, 0.3)';
                
                setTimeout(() => {
                    element.style.boxShadow = 'none';
                }, 1000);
            }, 300);
        }
    }
    
    // Execute scroll function
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', scrollToResults);
    } else {
        scrollToResults();
    }
    
    // Also try after a longer delay to ensure Streamlit has rendered everything
    setTimeout(scrollToResults, 800);
    </script>
    """, unsafe_allow_html=True)

# ===============================
# FOOTER
# ===============================
st.markdown("---")
st.markdown("""
<div style="text-align: center; color: #4b5563; padding: 20px; font-size: 14px;">
    <p>🧴 <strong>Sistem Rekomendasi Skincare Wardah</strong> • Content-Based Filtering</p>
    <p style="font-size: 12px; opacity: 0.7;">TF-IDF + Cosine Similarity • Data dari Wardah Beauty</p>
</div>

""", unsafe_allow_html=True)

