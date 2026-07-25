import streamlit as st
import pandas as pd
import requests
import xml.etree.ElementTree as ET
from datetime import datetime

# --- SAYFA AYARLARI ---
st.set_page_config(page_title="Soğutma Sistemleri Konfigüratörü V2", page_icon="❄️", layout="wide")

# --- 1. TCMB DÖVİZ KURU ENTEGRASYONU ---
@st.cache_data(ttl=3600)
def get_tcmb_euro_kur():
    try:
        response = requests.get("https://www.tcmb.gov.tr/kurlar/today.xml")
        response.raise_for_status()
        tree = ET.fromstring(response.content)
        for currency in tree.findall('Currency'):
            if currency.get('CurrencyCode') == 'EUR':
                return float(currency.find('ForexSelling').text)
    except Exception:
        return 38.50  # Hata durumunda varsayılan yedek kur

guncel_euro_kuru = get_tcmb_euro_kur()

# --- 2. YARDIMCI FONKSİYONLAR ---
def eur_to_tl(eur_fiyat):
    return eur_fiyat * guncel_euro_kuru

def format_fiyat(fiyat_eur):
    fiyat_tl = eur_to_tl(fiyat_eur)
    return f"{fiyat_eur:,.2f} EUR ({fiyat_tl:,.2f} TL)"

# --- 3. ANA ARAYÜZ (SEKME YÖNETİMİ) ---
st.title("❄️ Soğutma Sistemleri Konfigüratörü v2")
st.info(f"💶 **TCMB Güncel Euro Kuru:** 1 EUR = {guncel_euro_kuru:.4f} TL")

# Arayüzü 3 ana sekmeye ayırıyoruz
tab1, tab2, tab3 = st.tabs(["⚙️ Konfigüratör", "📦 Katalog Yönetimi", "👥 Bayi ve CRM Paneli"])

# ==========================================
# SEKME 1: KONFİGÜRATÖR VE HESAPLAMA
# ==========================================
with tab1:
    st.header("Proje ve Hesaplama Parametreleri")
    
    # -- İl ve Tasarım Sıcaklığı Seçimi --
    col_il, col_sicaklik = st.columns(2)
    il_sicakliklari = {
        "İzmir": 35.0, "Antalya": 38.0, "Adana": 37.0, 
        "İstanbul": 33.0, "Ankara": 32.0, "Zonguldak": 31.0, "Diğer": 35.0
    }
    
    with col_il:
        secilen_il = st.selectbox("Projenin Uygulanacağı İl", list(il_sicakliklari.keys()))
    with col_sicaklik:
        t_dis = st.number_input(
            "Dış Hava Sıcaklığı (°C) (İl bazlı öneridir, değiştirebilirsiniz):", 
            min_value=-10.0, max_value=55.0, value=il_sicakliklari[secilen_il], step=1.0
        )

    # -- Depo Ölçüleri ve Ara Duvar Mantığı --
    st.subheader("Depo Ölçüleri")
    col1, col2, col3 = st.columns(3)
    en = col1.number_input("En (m)", min_value=1.0, value=3.0, step=0.1)
    boy = col2.number_input("Boy (m)", min_value=1.0, value=4.0, step=0.1)
    yukseklik = col3.number_input("Yükseklik (m)", min_value=1.0, value=2.5, step=0.1)
    
    # Ara Duvar Checkbox
    bolme_istiyor_mu = st.checkbox("🔲 Bu depoyu ortadan ikiye bölmek (ara duvar eklemek) istiyorum")
    
    ekstra_duvar_alani = 0.0
    kapi_sayisi = 1
    evaporator_carpani = 1

    if bolme_istiyor_mu:
        bolme_yonu = st.radio("Bölme duvarı hangi yönde olacak?", ["Enine Böl (Kısa kenarı keser)", "Boyuna Böl (Uzun kenarı keser)"])
        if "Enine" in bolme_yonu:
            ekstra_duvar_alani = en * yukseklik
        else:
            ekstra_duvar_alani = boy * yukseklik
            
        kapi_sayisi = 2 # Depo bölündüğü için 2 kapı gerekiyor
        evaporator_carpani = 2 # Hava akışı kesildiği için 2 evaporatör gerekiyor
        st.success(f"✔️ Sistem İkiye Bölündü: Tasarıma {ekstra_duvar_alani:.2f} m² ara duvar, toplam {kapi_sayisi} adet kapı ve {evaporator_carpani} adet evaporatör uygulanacaktır.")

    # -- Temel Yüzey Hesaplamaları --
    zemin_tavan_alani = 2 * (en * boy)
    duvar_alani = 2 * (en * yukseklik) + 2 * (boy * yukseklik)
    toplam_yuzey_alani = zemin_tavan_alani + duvar_alani + ekstra_duvar_alani

    if st.button("Hesapla ve Teklif Oluştur", type="primary"):
        st.markdown("---")
        st.subheader("🧾 Teklif Özeti ve Seçilen Ürünler")
        
        # NOT: Gerçek projede bu kısımdaki fiyatlar Supabase'den gelen verilerle değişecek.
        panel_birim_fiyat_eur = 25.0 
        kapi_birim_fiyat_eur = 450.0
        kompresor_fiyat_eur = 1200.0
        evaporator_fiyat_eur = 650.0
        
        # Kalem Maliyetleri Hesaplaması
        panel_toplam_eur = toplam_yuzey_alani * panel_birim_fiyat_eur
        kapi_toplam_eur = kapi_sayisi * kapi_birim_fiyat_eur
        sogutma_grubu_eur = kompresor_fiyat_eur + (evaporator_fiyat_eur * evaporator_carpani)
        
        genel_toplam_eur = panel_toplam_eur + kapi_toplam_eur + sogutma_grubu_eur
        
        # Sonuç Tablosu Çıktısı
        teklif_verisi = {
            "Kalem": [
                f"PUR/PIR Sandviç Panel ({toplam_yuzey_alani:.2f} m²)", 
                f"Soğuk Oda Kapısı ({kapi_sayisi} Adet)", 
                "Kompresör Grubu (Örn: 15 kW - 20 HP)", 
                f"Evaporatör ({evaporator_carpani} Adet)"
            ],
            "Birim Fiyat": [
                format_fiyat(panel_birim_fiyat_eur),
                format_fiyat(kapi_birim_fiyat_eur),
                format_fiyat(kompresor_fiyat_eur),
                format_fiyat(evaporator_fiyat_eur)
            ],
            "Toplam Tutar": [
                format_fiyat(panel_toplam_eur),
                format_fiyat(kapi_toplam_eur),
                format_fiyat(kompresor_fiyat_eur),
                format_fiyat(evaporator_fiyat_eur * evaporator_carpani)
            ]
        }
        
        st.table(pd.DataFrame(teklif_verisi))
        
        # En alt toplam ekranı
        col_t1, col_t2 = st.columns(2)
        with col_t1:
            st.metric("Toplam Maliyet (EUR)", f"{genel_toplam_eur:,.2f} EUR")
        with col_t2:
            st.metric("Toplam Maliyet (TL)", f"{eur_to_tl(genel_toplam_eur):,.2f} TL")
            
        st.caption(f"📌 Bu teklif {datetime.now().strftime('%d.%m.%Y')} tarihli TCMB kuru (1 EUR = {guncel_euro_kuru:.4f} TL) baz alınarak hazırlanmıştır.")

# ==========================================
# SEKME 2: KATALOG YÖNETİMİ (Ürün Güncelleme)
# ==========================================
with tab2:
    st.header("Katalog ve Veritabanı Yönetimi")
    st.write("Mevcut ürünlerin bilgilerini, güç (kW/HP) veya fiyat güncellemelerini buradan yapabilirsiniz.")
    
    # Seçim alanı
    secilen_urun = st.selectbox("Düzenlenecek Ürünü Seçin", ["Kopeland KR17 - 15 kW", "Arces PUR Panel 80mm", "Bitzer Motor 20 HP"])
    
    st.subheader(f"✏️ Düzenlenen Ürün: {secilen_urun}")
    
    col_u1, col_u2 = st.columns(2)
    with col_u1:
        yeni_isim = st.text_input("Ürün Modeli / Adı", value="Kopeland KR17")
        yeni_guc_kw = st.number_input("Güç (kW)", value=15.0)
        yeni_guc_hp = st.number_input("Beygir Gücü (HP / BG)", value=20.0)
    with col_u2:
        yeni_fiyat = st.number_input("Birim Fiyat", value=1200.0)
        yeni_para_birimi = st.selectbox("Para Birimi", ["EUR", "TL"])
        
    col_b1, col_b2 = st.columns(2)
    with col_b1:
        if st.button("💾 Ürünü Güncelle", type="primary", use_container_width=True):
            st.success("Ürün bilgileri veritabanında başarıyla güncellendi!")
    with col_b2:
        if st.button("🗑️ Ürünü Sil", use_container_width=True):
            st.warning("Ürün katalogdan kalıcı olarak silindi.")

# ==========================================
# SEKME 3: BAYİ VE CRM PANELİ
# ==========================================
with tab3:
    st.header("Üye Profilleri ve Teklif Arşivi")
    
    st.subheader("👥 Kayıtlı Bayiler / Üyeler")
    bayiler_verisi = {
        "Şirket Ünvanı": ["Marmara Soğutma", "Ege İklimlendirme"],
        "Yetkili": ["Ahmet Yılmaz", "Mehmet Kaya"],
        "Bölge/İl": ["İstanbul", "İzmir"],
        "Durum": ["Aktif", "Onay Bekliyor"]
    }
    st.dataframe(pd.DataFrame(bayiler_verisi), use_container_width=True)
    
    st.markdown("---")
    
    st.subheader("🗂️ Geçmiş Teklifler (CRM Arşivi)")
    teklifler_verisi = {
        "Proje / Bayi": ["Marmara Depo Projesi", "Ege Lojistik Soğuk Oda"],
        "Tarih": ["20.07.2026", "25.07.2026"],
        "Kullanılan Kur (TL)": ["38.45", "38.50"],
        "Toplam Tutar (EUR)": ["15,400.00 EUR", "22,150.00 EUR"]
    }
    st.dataframe(pd.DataFrame(teklifler_verisi), use_container_width=True)
