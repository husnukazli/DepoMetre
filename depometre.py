import streamlit as st
from supabase import create_client, Client
import pandas as pd
import os
import uuid
from fpdf import FPDF

# ==========================================
# FONKSİYONLAR (Sola tam dayalı - Boşluksuz)
# ==========================================
def create_pdf(sepet_verisi, toplam):
    pdf = FPDF()
    pdf.add_page()
    
    if os.path.exists("arial.ttf"):
        pdf.add_font("ArialTR", "", "arial.ttf", uni=True)
        pdf.set_font("ArialTR", "", 16)
    else:
        pdf.set_font("Arial", "B", 16)
        
    pdf.cell(0, 10, txt="Soguk Hava Deposu Konfigurasyon Ozeti", ln=True, align='C')
    pdf.ln(10)
    
    if os.path.exists("arial.ttf"):
        pdf.set_font("ArialTR", "", 12)
    else:
        pdf.set_font("Arial", "", 12)
        
    pdf.cell(50, 10, txt="Kategori", border=1)
    pdf.cell(100, 10, txt="Marka / Model", border=1)
    pdf.cell(40, 10, txt="Fiyat (TL)", border=1, ln=True)
    
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
    return bytes(pdf.output())

# Sepetten Ürün Silme Geri Çağırımı (Callback)
def sepetten_cikar(uid):
    st.session_state['sepet'] = [item for item in st.session_state['sepet'] if item['sepet_id'] != uid]

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
st.write("Depo ölçülerinizi girerek akıllı kapasite hesaplamalarından yararlanın ve sisteminizi oluşturun.")

# VERİTABANI ÖN YÜKLEME (Tavsiye motoru için verileri en başta çekiyoruz)
try:
    kategoriler_db = supabase.table("kategoriler").select("*").execute().data
    markalar_db = supabase.table("markalar").select("*").execute().data
    parcalar_db = supabase.table("parcalar").select("*").execute().data
    veriler_tamam = bool(kategoriler_db and parcalar_db)
except Exception as e:
    st.error(f"Veritabanı bağlantı hatası: {e}")
    veriler_tamam = False

# ==========================================
# 1. BÖLÜM: HACİM, ALAN VE BTU HESAPLAMA
# ==========================================
if veriler_tamam:
    with st.container():
        st.header("1. Hacim ve Kapasite Hesabı")
        col1, col2, col3 = st.columns(3)
        with col1: en = st.number_input("En (Metre)", min_value=1.0, value=3.0, step=0.5)
        with col2: boy = st.number_input("Boy (Metre)", min_value=1.0, value=4.0, step=0.5)
        with col3: yukseklik = st.number_input("Yükseklik (Metre)", min_value=1.0, value=2.5, step=0.5)
            
        # Geometrik Hesaplamalar
        hacim = en * boy * yukseklik
        zemin_alani = en * boy
        toplam_yuzey_alani = (2 * zemin_alani) + (2 * en * yukseklik) + (2 * boy * yukseklik) # Zemin, Tavan ve 4 Duvar
        
        hedef_sicaklik = st.selectbox("Hedef Depo Sıcaklığı", ["+4 Derece (Soğuk)", "-18 Derece (Donuk)"])
        btu_carpan = 350 if hedef_sicaklik == "+4 Derece (Soğuk)" else 550
        gerekli_btu = int(hacim * btu_carpan)
        
        st.info(f"**Toplam Hacim:** {hacim:.2f} m³ | **Zemin:** {zemin_alani:.2f} m² | **Toplam İzolasyon Yüzeyi:** {toplam_yuzey_alani:.2f} m² \n\n **Hesaplanan İhtiyaç:** {gerekli_btu:,} BTU/h")

        # --- AKILLI KOMPRESÖR KOMBİNASYON ÖNERİSİ ---
        komp_kategori_id = next((k["id"] for k in kategoriler_db if "Kompresör" in k["kategori_adi"]), None)
        if komp_kategori_id:
            # Kompresörleri al ve BTU'ya göre büyükten küçüğe sırala
            kompresorler = sorted([p for p in parcalar_db if p["kategori_id"] == komp_kategori_id], key=lambda x: x["btu_kapasite"], reverse=True)
            
            kalan_btu = gerekli_btu
            kombinasyon_sonucu = {}
            
            for komp in kompresorler:
                if komp["btu_kapasite"] > 0:
                    adet = kalan_btu // komp["btu_kapasite"]
                    if adet > 0:
                        marka_ad = next((m["marka_adi"] for m in markalar_db if m["id"] == komp["marka_id"]), "")
                        isim = f"{marka_ad} - {komp['model_adi']} ({komp['btu_kapasite']:,} BTU)"
                        kombinasyon_sonucu[isim] = adet
                        kalan_btu = kalan_btu % komp["btu_kapasite"]
                        
            # Hala ufak bir BTU açığı kaldıysa en küçük cihazdan 1 tane ekleyerek sistemi güvenceye al
            if kalan_btu > 0 and kompresorler:
                en_kucuk = kompresorler[-1]
                marka_ad = next((m["marka_adi"] for m in markalar_db if m["id"] == en_kucuk["marka_id"]), "")
                isim = f"{marka_ad} - {en_kucuk['model_adi']} ({en_kucuk['btu_kapasite']:,} BTU)"
                kombinasyon_sonucu[isim] = kombinasyon_sonucu.get(isim, 0) + 1
                
            onerilen_metin = " + ".join([f"{adet} Adet {isim}" for isim, adet in kombinasyon_sonucu.items()])
            st.success(f"💡 **İhtiyacınıza Yönelik Otomatik Kombinasyon Önerisi:** {onerilen_metin}")

    st.divider()

    # ==========================================
    # 2. BÖLÜM: PARÇA SEÇİMİ
    # ==========================================
    st.header("2. Sistem Bileşenleri Seçimi")

    kategori_isimleri = [k["kategori_adi"] for k in kategoriler_db]
    sekmeler = st.tabs(kategori_isimleri)
    
    for index, sekme in enumerate(sekmeler):
        with sekme:
            kategori_id = kategoriler_db[index]["id"]
            kategori_adi = kategoriler_db[index]["kategori_adi"]
            uygun_parcalar = [p for p in parcalar_db if p["kategori_id"] == kategori_id]
            
            if uygun_parcalar:
                for parca in uygun_parcalar:
                    marka_adi = next((m["marka_adi"] for m in markalar_db if m["id"] == parca["marka_id"]), "Bilinmiyor")
                    
                    # Dinamik Fiyat ve Tavsiye Mantığı
                    gosterilecek_fiyat = float(parca['fiyat'])
                    tavsiye_etiketi = ""
                    
                    # Kural 1: Panel ise metrekare ile çarp
                    if "Panel" in kategori_adi:
                        gosterilecek_fiyat = float(parca['fiyat']) * toplam_yuzey_alani
                        tavsiye_etiketi = f"*(Toplam {toplam_yuzey_alani:.2f} m² için hesaplanmıştır)*"
                        
                    # Kural 2: Zemin alanına göre kapı önerisi
                    if "Kapı" in kategori_adi:
                        if (zemin_alani > 20 and "Sürgülü" in parca['model_adi']) or (zemin_alani <= 20 and "Menteşeli" in parca['model_adi']):
                            tavsiye_etiketi = "💡 **(Alanınıza Göre Tavsiye Edilir)**"

                    p_col1, p_col2, p_col3, p_col4 = st.columns([4, 2, 2, 2])
                    p_col1.write(f"**{marka_adi} - {parca['model_adi']}** {tavsiye_etiketi}")
                    p_col2.write(f"Kapasite: {parca['btu_kapasite']:,} BTU" if parca["btu_kapasite"] > 0 else "")
                    p_col3.write(f"Fiyat: {gosterilecek_fiyat:,.2f} TL")
                    
                    if p_col4.button("Sepete Ekle", key=f"ekle_{parca['id']}"):
                        st.session_state['sepet'].append({
                            "sepet_id": str(uuid.uuid4()), # Silme işlemi için benzersiz ID
                            "Kategori": kategori_adi,
                            "Marka/Model": f"{marka_adi} - {parca['model_adi']}",
                            "Fiyat": gosterilecek_fiyat
                        })
                        st.rerun()
            else:
                st.caption("Bu kategoride ürün bulunamadı.")

    st.divider()

    # ==========================================
    # 3. BÖLÜM: SEPET VE PDF ÇIKTISI
    # ==========================================
    st.header("3. Konfigürasyon Özeti")

    if st.session_state['sepet']:
        # Görsel Sepet Tablosu (Silme Butonlu)
        for item in st.session_state['sepet']:
            s_col1, s_col2, s_col3, s_col4 = st.columns([3, 4, 3, 2])
            s_col1.write(item['Kategori'])
            s_col2.write(item['Marka/Model'])
            s_col3.write(f"{item['Fiyat']:,.2f} TL")
            s_col4.button("❌ Çıkar", key=f"sil_{item['sepet_id']}", on_click=sepetten_cikar, args=(item['sepet_id'],))
            
        st.write("---")
        
        # DataFrame Çevirimi (PDF için gerekli)
        df_sepet = pd.DataFrame(st.session_state['sepet'])
        toplam_tutar = df_sepet["Fiyat"].sum()
        st.success(f"### 💰 Toplam Sistem Maliyeti: {toplam_tutar:,.2f} TL")
        
        col_pdf, col_temizle = st.columns([1, 1])
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
                st.error(f"PDF oluşturulurken bir hata oluştu: {e}")

        with col_temizle:
            if st.button("Tüm Sepeti Temizle", type="secondary", use_container_width=True):
                st.session_state['sepet'] = []
                st.rerun()
    else:
        st.info("Sepetinizde henüz bir parça bulunmuyor.")
