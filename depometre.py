import streamlit as st
from supabase import create_client, Client
import pandas as pd
import os
from fpdf import FPDF

# --- SUPABASE BAĞLANTISI ---
SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Sayfa Ayarları
st.set_page_config(page_title="Soğuk Hava Deposu Konfigüratörü", page_icon="❄️", layout="wide")

st.markdown("""
    <style>
    .stDataFrame {font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;}
    h1, h2, h3 {color: #0284c7; font-weight: 600;}
    </style>
""", unsafe_allow_html=True)

if 'sepet' not in st.session_state:
    st.session_state['sepet'] = []

st.title("❄️ Soğuk Hava Deposu Konfigüratörü")
st.write("Depo ölçülerinizi girerek ihtiyacınız olan soğutma kapasitesini hesaplayın ve sisteminizi oluşturun.")

# ==========================================
# 1. BÖLÜM: HACİM VE BTU HESAPLAMA
# ==========================================
with st.container():
    st.header("1. Hacim ve Kapasite Hesabı")
    col1, col2, col3 = st.columns(3)
    with col1: en = st.number_input("En (Metre)", min_value=1.0, value=3.0, step=0.5)
    with col2: boy = st.number_input("Boy (Metre)", min_value=1.0, value=4.0, step=0.5)
    with col3: yukseklik = st.number_input("Yükseklik (Metre)", min_value=1.0, value=2.5, step=0.5)
        
    hacim = en * boy * yukseklik
    hedef_sicaklik = st.selectbox("Hedef Depo Sıcaklığı", ["+4 Derece (Soğuk)", "-18 Derece (Donuk)"])
    btu_carpan = 350 if hedef_sicaklik == "+4 Derece (Soğuk)" else 550
    gerekli_btu = int(hacim * btu_carpan)
    st.info(f"**Toplam Hacim:** {hacim:.2f} m³ | **Hesaplanan İhtiyaç:** {gerekli_btu:,} BTU/h")

st.divider()

# ==========================================
# 2. BÖLÜM: PARÇA SEÇİMİ
# ==========================================
st.header("2. Sistem Bileşenleri Seçimi")

try:
    kategoriler_db = supabase.table("kategoriler").select("*").execute().data
    markalar_db = supabase.table("markalar").select("*").execute().data
    parcalar_db = supabase.table("parcalar").select("*").order("btu_kapasite").execute().data
    
    if kategoriler_db and parcalar_db:
        kategori_isimleri = [k["kategori_adi"] for k in kategoriler_db]
        sekmeler = st.tabs(kategori_isimleri)
        
        for index, sekme in enumerate(sekmeler):
            with sekme:
                kategori_id = kategoriler_db[index]["id"]
                uygun_parcalar = [p for p in parcalar_db if p["kategori_id"] == kategori_id]
                
                if uygun_parcalar:
                    for parca in uygun_parcalar:
                        marka_adi = next((m["marka_adi"] for m in markalar_db if m["id"] == parca["marka_id"]), "Bilinmiyor")
                        p_col1, p_col2, p_col3, p_col4 = st.columns([3, 2, 2, 2])
                        p_col1.write(f"**{marka_adi} - {parca['model_adi']}**")
                        p_col2.write(f"Kapasite: {parca['btu_kapasite']:,} BTU" if parca["btu_kapasite"] > 0 else "Kapasite: Bağımsız")
                        p_col3.write(f"Fiyat: {float(parca['fiyat']):,.2f} TL")
                        
                        if p_col4.button("Sepete Ekle", key=f"ekle_{parca['id']}"):
                            st.session_state['sepet'].append({
                                "Kategori": kategoriler_db[index]["kategori_adi"],
                                "Marka/Model": f"{marka_adi} - {parca['model_adi']}",
                                "Fiyat": float(parca["fiyat"])
                            })
                            st.rerun()
                else:
                    st.caption("Bu kategoride ürün bulunamadı.")
except Exception as e:
    st.error(f"Veri çekme hatası: {e}")

st.divider()

# ==========================================
# 3. BÖLÜM: SEPET VE PDF ÇIKTISI
# ==========================================
st.header("3. Konfigürasyon Özeti")

if st.session_state['sepet']:
    df_sepet = pd.DataFrame(st.session_state['sepet'])
    st.dataframe(df_sepet, use_container_width=True, hide_index=True)
    
    toplam_tutar = df_sepet["Fiyat"].sum()
    st.success(f"### 💰 Toplam Sistem Maliyeti: {toplam_tutar:,.2f} TL")
    
    col_pdf, col_temizle = st.columns([1, 1])
    
    # PDF OLUŞTURMA FONKSİYONU
    def create_pdf(sepet_verisi, toplam):
        pdf = FPDF()
        pdf.add_page()
        
        # Font Yükleme (GitHub'a eklenen arial.ttf üzerinden)
        if os.path.exists("arial.ttf"):
            pdf.add_font("ArialTR", "", "arial.ttf", uni=True)
            pdf.set_font("ArialTR", "", 16)
        else:
            pdf.set_font("Arial", "B", 16) # Fallback
            
        pdf.cell(0, 10, txt="Soguk Hava Deposu Konfigurasyon Ozeti", ln=True, align='C')
        pdf.ln(10)
        
        if os.path.exists("arial.ttf"):
            pdf.set_font("ArialTR", "", 12)
        else:
            pdf.set_font("Arial", "", 12)
            
        # Başlıklar
        pdf.cell(50, 10, txt="Kategori", border=1)
        pdf.cell(100, 10, txt="Marka / Model", border=1)
        pdf.cell(40, 10, txt="Fiyat (TL)", border=1, ln=True)
        
        # Ürünler
        for index, row in sepet_verisi.iterrows():
            pdf.cell(50, 10, txt=str(row['Kategori']), border=1)
            pdf.cell(100, 10, txt=str(row['Marka/Model']), border=1)
            pdf.cell(40, 10, txt=f"{row['Fiyat']:,.2f}", border=1, ln=True)
            
        pdf.ln(10)
        if os.path.exists("arial.ttf"):
            pdf.set_font("ArialTR", "", 14)
        else:
            pdf.set_font("Arial", "B", 14)
            
        pdf.cell(0, 10, txt=f"Genel Toplam: {toplam:,.2f} TL", ln=True, align='R')
        return pdf.output(dest="S").encode("latin-1")

    # Butonlar
    with col_pdf:
        try:
            pdf_bytes = create_pdf(df_sepet, toplam_tutar)
            st.download_button(
                label="📄 PDF Olarak İndir (Teklif Al)",
                data=pdf_bytes,
                file_name="Soguk_Hava_Deposu_Teklifi.pdf",
                mime="application/pdf",
                type="primary",
                use_container_width=True
            )
        except Exception as e:
            st.error(f"PDF oluşturulurken bir hata oluştu. requirements.txt dosyanızda 'fpdf2' olduğundan emin olun. Hata: {e}")

    with col_temizle:
        if st.button("Sepeti Temizle", type="secondary", use_container_width=True):
            st.session_state['sepet'] = []
            st.rerun()
else:
    st.info("Sepetinizde henüz bir parça bulunmuyor.")
