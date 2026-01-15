import pandas as pd
import ast
import requests
from PIL import Image
from io import BytesIO
import re
import os

def normalize_product_name(name):
    """
    Normalisasi nama produk untuk menghandle perbedaan penulisan
    """
    if pd.isna(name):
        return ""
    
    name = str(name).strip()
    name = re.sub(r'\s+', ' ', name)
    
    return {
        'original': name,
        'lower': name.lower(),
        'upper': name.upper(),
        'title': name.title(),
        'clean': re.sub(r'[^\w\s]', '', name).strip()
    }

def load_and_merge_data():
    """Load dan merge dataset utama dengan dataset gambar"""
    # Load dataset utama
    df = pd.read_csv("wardah_skincare_clean.csv")
    
    # Konversi string ke list
    df["skin_type"] = df["skin_type"].apply(
        lambda x: ast.literal_eval(x) if isinstance(x, str) else []
    )
    df["category"] = df["category"].apply(
        lambda x: ast.literal_eval(x) if isinstance(x, str) else []
    )
    
    # Normalisasi nama di dataset utama
    df['name_normalized'] = df['name'].apply(normalize_product_name)
    df['name_lower'] = df['name_normalized'].apply(lambda x: x['lower'])
    
    # Load dataset gambar
    try:
        df_img = pd.read_csv("wardah_product_images.csv")
        print(f"✅ Dataset gambar berhasil diload: {len(df_img)} entri")
        
        # Debug info
        print("📋 5 contoh nama di dataset gambar:")
        print(df_img['name'].head())
        
    except Exception as e:
        print(f"⚠️ Error loading image dataset: {e}")
        df_img = pd.DataFrame({'name': [], 'image_url': []})
    
    if not df_img.empty:
        # Normalisasi nama di dataset gambar
        df_img['name_normalized'] = df_img['name'].apply(normalize_product_name)
        df_img['name_lower'] = df_img['name_normalized'].apply(lambda x: x['lower'])
        
        # Merge berdasarkan lowercase (karena case insensitive)
        df_merge = pd.merge(
            df,
            df_img[['name_lower', 'image_url']],
            left_on='name_lower',
            right_on='name_lower',
            how='left',
            suffixes=('', '_img')
        )
        
        # Debug matching
        total_matched = df_merge['image_url'].notna().sum()
        print(f"\n🎯 Hasil merge:")
        print(f"- Total produk: {len(df_merge)}")
        print(f"- Produk dengan gambar: {total_matched}")
        print(f"- Persentase: {round(total_matched/len(df_merge)*100, 1)}%")
        
        # Debug untuk produk yang tidak dapat gambar
        no_image = df_merge[df_merge['image_url'].isna()]
        if len(no_image) > 0:
            print(f"\n⚠️ Produk tanpa gambar ({len(no_image)} produk):")
            for idx, row in no_image.head(3).iterrows():
                print(f"  - {row['name'][:50]}...")
        
    else:
        df_merge = df.copy()
        df_merge['image_url'] = ""
    
    return df_merge.reset_index(drop=True)

def get_product_image(image_url, product_name):
    """Mendapatkan gambar produk dari URL"""
    if pd.isna(image_url) or not image_url or str(image_url).strip() in ["", "nan"]:
        return None
    
    image_url = str(image_url).strip()
    
    # Perbaiki URL jika perlu
    if not image_url.startswith(('http://', 'https://')):
        # Coba cari di folder assets
        if os.path.exists(image_url):
            try:
                return Image.open(image_url)
            except:
                pass
        
        # Coba tambahkan prefix
        if not image_url.startswith('//'):
            image_url = 'https://' + image_url
        else:
            image_url = 'https:' + image_url
    
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0'
        }
        response = requests.get(image_url, timeout=5, headers=headers)
        
        if response.status_code == 200:
            img = Image.open(BytesIO(response.content))
            return img
    except:
        pass
    
    return None

def get_local_fallback_image(category):
    """Mengembalikan gambar fallback lokal berdasarkan kategori"""
    # Mapping kategori ke file gambar lokal
    category_fallbacks = {
        'serum': 'assets/serum.webp',
        'cleanser': 'assets/cleanser.png',
        'face wash': 'assets/facial.png',
        'moisturizer': 'assets/moisturizer.webp',
        'sunscreen': 'assets/sunscreen.webp',
        'mask': 'assets/facemask.webp',
        'toner': 'assets/toner.png',
        'eye cream': 'assets/eyecream.webp',
        'scrub': 'assets/scrub.png',
        'micellar water': 'assets/micellar.webp',
    }
    
    # Cari kategori yang cocok
    category_lower = str(category).lower()
    for cat_key, file_path in category_fallbacks.items():
        if cat_key in category_lower:
            if os.path.exists(file_path):
                try:
                    return Image.open(file_path)
                except:
                    continue
    
    # Coba gunakan default
    if os.path.exists('assets/default_skincare.png'):
        try:
            return Image.open('assets/default_skincare.png')
        except:
            pass
    
    # Buat gambar placeholder sederhana
    return create_placeholder_image(category)

def create_placeholder_image(text):
    """Membuat gambar placeholder sederhana"""
    from PIL import Image, ImageDraw, ImageFont
    import random
    
    # Warna background berdasarkan kategori
    colors = {
        'serum': (230, 240, 255),  # Light blue
        'cleanser': (255, 245, 230),  # Light orange
        'moisturizer': (230, 255, 240),  # Light green
        'sunscreen': (255, 250, 230),  # Light yellow
        'default': (245, 245, 245)  # Light gray
    }
    
    # Pilih warna berdasarkan teks
    bg_color = colors['default']
    for key in colors:
        if key in str(text).lower():
            bg_color = colors[key]
            break
    
    # Buat gambar
    img = Image.new('RGB', (300, 200), color=bg_color)
    draw = ImageDraw.Draw(img)
    
    # Tambahkan teks
    try:
        # Coba gunakan font default
        font = ImageFont.load_default()
    except:
        font = None
    
    # Draw text
    text_lines = str(text).split()
    if len(text_lines) > 3:
        text_display = " ".join(text_lines[:3]) + "..."
    else:
        text_display = str(text)
    
    # Center text
    if font:
        text_bbox = draw.textbbox((0, 0), text_display, font=font)
        text_width = text_bbox[2] - text_bbox[0]
        text_height = text_bbox[3] - text_bbox[1]
        position = ((300 - text_width) // 2, (200 - text_height) // 2)
        draw.text(position, text_display, fill=(100, 100, 100), font=font)
    else:
        draw.text((50, 80), text_display, fill=(100, 100, 100))
    
    return img