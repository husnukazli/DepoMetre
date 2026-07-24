import streamlit as st
from supabase import create_client, Client
import pandas as pd

# --- SUPABASE BAĞLANTISI ---
SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Sayfa Ayarları
st.set_page_config(page_title="Soğuk Hava Deposu Konfigüratörü", page_icon="❄️", layout="wide")

# Özel CSS
st.markdown("""
    <style>
    .stDataFrame {font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;}
    h1, h2, h3 {color: #0284c7; font-weight: 600;}
    </style>
""", unsafe_allow_html=True)

# Sepet için Session State Başlatma
if 'sepet' not in st.session_state:
    st.session_state['sepet'] = []

st.title("❄️ Soğuk Hava Deposu Konfigüratörü")
st.write("Depo ölçülerinizi girerek ihtiyacınız olan soğutma kapasitesini (BTU) hesaplayın ve uygun parçaları seçerek sisteminizi oluşturun.")

# ==========================================
# 1. BÖLÜM: HACİM VE BTU HESAPLAMA
# ==========================================
with st.container():
    st.header("1. Hacim ve Kapasite Hesabı")
    col1, col2, col3 = st.columns(3)
    
    with col1:
        en = st.number_input("En (Metre)", min_value=1.0, value=3.0, step=0.5)
    with col2:
        boy = st.number_input("Boy (Metre)", min_value=1.0, value=4.0, step=0.5)
    with col3:
        yukseklik = st.number_input("Yükseklik (Metre)", min_value=1.0, value=2.5, step=0.5)
        
    hacim = en * boy * yukseklik
    
    # Basit bir BTU formülü (Çarpan projeye göre revize edilebilir)
    hedef_sicaklik = st.selectbox("Hedef Depo Sıcaklığı", ["+4 Derece (Soğuk)", "-18 Derece (Donuk)"])
    btu_carpan = 350 if hedef_sicaklik == "+4 Derece (Soğuk)" else 550
    gerekli_btu = int(hacim * btu_carpan)
    
    st.info(f"**Toplam Hacim:** {hacim:.2f} m³ | **Hesaplanan Yaklaşık İhtiyaç:** {gerekli_btu:,} BTU/h")

st.divider()

# ==========================================
# 2. BÖLÜM: PARÇA SEÇİMİ (KATALOG)
# ==========================================
st.header("2. Sistem Bileşenleri Seçimi")

try:
    # Veritabanından verileri çekme
    kategoriler_db = supabase.table("kategoriler").select("*").execute().data
    markalar_db = supabase.table("markalar").select("*").execute().data
    parcalar_db = supabase.table("parcalar").select("*").execute().data
    
    if not kategoriler_db or not parcalar_db:
        st.warning("Veritabanında henüz parça veya kategori bulunmamaktadır. Lütfen Supabase üzerinden test verileri ekleyin.")
    else:
        # Kategorileri Sekmeler Halinde Gösterme
        kategori_isimleri = [k["kategori_adi"] for k in kategoriler_db]
        sekmeler = st.tabs(kategori_isimleri)
        
        for index, sekme in enumerate(sekmeler):
            with sekme:
                kategori_id = kategoriler_db[index]["id"]
                # Bu kategoriye ait parçaları filtrele
                uygun_parcalar = [p for p in parcalar_db if p["kategori_id"] == kategori_id]
                
                if uygun_parcalar:
                    for parca in uygun_parcalar:
                        marka_adi = next((m["marka_adi"] for m in markalar_db if m["id"] == parca["marka_id"]), "Bilinmiyor")
                        
                        p_col1, p_col2, p_col3, p_col4 = st.columns([3, 2, 2, 2])
                        p_col1.write(f"**{marka_adi} - {parca['model_adi']}**")
                        
                        if parca["btu_kapasite"] > 0:
                            p_col2.write(f"Kapasite: {parca['btu_kapasite']:,} BTU")
                        else:
                            p_col2.write("Kapasite: Bağımsız")
                            
                        p_col3.write(f"Fiyat: {float(parca['fiyat']):,.2f} TL")
                        
                        if p_col4.button("Sepete Ekle", key=f"ekle_{parca['id']}"):
                            st.session_state['sepet'].append({
                                "id": parca["id"],
                                "Kategori": kategoriler_db[index]["kategori_adi"],
                                "Model": f"{marka_adi} - {parca['model_adi']}",
                                "Fiyat": float(parca["fiyat"])
                            })
                            st.rerun()
                else:
                    st.caption("Bu kategoride ürün bulunamadı.")
except Exception as e:
    st.error(f"Veri çekme hatası: {e}")

st.divider()

# ==========================================
# 3. BÖLÜM: SEPET VE TOPLAM FİYAT
# ==========================================
st.header("3. Konfigürasyon Özeti (Sepet)")

if st.session_state['sepet']:
    df_sepet = pd.DataFrame(st.session_state['sepet'])
    # ID sütununu gizleyerek göster
    st.dataframe(df_sepet[["Kategori", "Model", "Fiyat"]], use_container_width=True, hide_index=True)
    
    toplam_tutar = df_sepet["Fiyat"].sum()
    st.success(f"### 💰 Toplam Sistem Maliyeti: {toplam_tutar:,.2f} TL")
    
    if st.button("Sepeti Temizle", type="secondary"):
        st.session_state['sepet'] = []
        st.rerun()
else:
    st.info("Sepetinizde henüz bir parça bulunmuyor. Lütfen yukarıdan sistem bileşenlerini seçin.")
