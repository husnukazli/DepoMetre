import streamlit as st
import pandas as pd
import math
import uuid
import os
import time
from fpdf import FPDF
from supabase import create_client, Client

# ==========================================
# 1. AYARLAR VE ARAYÜZ YAPILANDIRMASI
# ==========================================
st.set_page_config(page_title="Arces Mühendislik - İleri Düzey Konfigüratör", page_icon="❄️", layout="wide")

st.markdown("""
    <style>
    #MainMenu {visibility: hidden;}
    header {visibility: hidden!important;}
    footer {visibility: hidden!important;}
  .block-container {padding-top: 2rem!important;}
    h1, h2, h3 {color: #0284c7; font-weight: 600;}
  .info-kutu {border: 1px solid #ddd; padding: 20px; border-radius: 10px; background-color: #f8fafc; margin-bottom: 20px;}
    </style>
""", unsafe_allow_html=True)

# Oturum (Session) Değişkenleri
if 'sepet' not in st.session_state:
    st.session_state['sepet'] =
if 'kullanici_rol' not in st.session_state:
    st.session_state['kullanici_rol'] = 'bayi' # Demo için varsayılan yetkili yapıldı

# ==========================================
# 2. VERİTABANI (YEREL VE SUPABASE ENTEGRASYONU)
# ==========================================
# Gelişmiş hesaplamalar için 2026 fiyatlı donanım veritabanı (Mock DB)
yerel_veritabani = {
    "kompresorler":,
    "evaporatorler":,
    "paneller": [
        {"kalinlik_mm": 80, "u_degeri": 0.275, "fiyat_eur_m2": 22},
        {"kalinlik_mm": 100, "u_degeri": 0.220, "fiyat_eur_m2": 24},
        {"kalinlik_mm": 120, "u_degeri": 0.183, "fiyat_eur_m2": 28},
        {"kalinlik_mm": 150, "u_degeri": 0.146, "fiyat_eur_m2": 30}
    ],
    "urun_verileri": {
        "Sebze/Meyve (Elma vb.)": {"cp": 3.65, "solunum_kj_kg": 1.9},
        "Et/Tavuk": {"cp": 2.70, "solunum_kj_kg": 0.0},
        "Süt Ürünleri": {"cp": 3.10, "solunum_kj_kg": 0.0},
        "Genel Endüstriyel": {"cp": 2.00, "solunum_kj_kg": 0.0}
    }
}

GUNCEL_KUR_EUR = 38.50 # 2026 Projeksiyonlu Kur

# ==========================================
# 3. TERMODİNAMİK HESAPLAMA MOTORU (ENGINE)
# ==========================================
def hesapla_sogutma_yuku(en, boy, yukseklik, t_dis, t_ic, panel_kalinlik, urun_tipi, urun_miktar_kg, kapi_acilis):
    # 1. Transmisyon (İletim) Yükü Hesaplaması (Q = U * A * ΔT * 24 / 1000)
    panel = next(p for p in yerel_veritabani["paneller"] if p["kalinlik_mm"] == panel_kalinlik)
    u_degeri = panel["u_degeri"]
    
    zemin_alani = en * boy
    duvar_tavan_alani = (2 * en * yukseklik) + (2 * boy * yukseklik) + (en * boy) # Zemin hariç
    
    q_duvar_tavan = u_degeri * duvar_tavan_alani * (t_dis - t_ic) * 24 / 1000
    q_zemin = u_degeri * zemin_alani * (15 - t_ic) * 24 / 1000 # Zemin sıcaklığı ortalama 15°C alınır
    q_iletim = q_duvar_tavan + q_zemin
    
    # 2. Ürün Yükü Hesaplaması (Q = m * Cp * ΔT / 3600)
    urun = yerel_veritabani["urun_verileri"][urun_tipi]
    q_urun_duyulur = urun_miktar_kg * urun["cp"] * (t_dis - t_ic) / 3600
    q_urun_solunum = (urun_miktar_kg * urun["solunum_kj_kg"]) / 3600
    q_urun_toplam = q_urun_duyulur + q_urun_solunum
    
    # 3. İç Yükler (İnsan ve Aydınlatma)
    # Varsayım: 2 kişi günde 4 saat çalışır, lamba adedi alan büyüklüğüne göre belirlenir
    kisi_sayisi = 1 if zemin_alani < 20 else 2
    q_personel = (kisi_sayisi * 4 * 270) / 1000 # Çalışan başına 270W
    lamba_sayisi = math.ceil(zemin_alani / 10)
    q_aydinlatma = (lamba_sayisi * 4 * 100) / 1000 # Lamba başına 100W, 4 saat
    q_ic = q_personel + q_aydinlatma
    
    # 4. İnfiltrasyon (Hava Sızıntısı) Yükü
    hacim = en * boy * yukseklik
    degisim_katsayisi = {"Düşük": 3, "Orta": 5, "Yüksek": 8}[kapi_acilis]
    # Havanın özgül hacim enerjisi yaklaşık 2 kJ/m³°C
    q_infiltrasyon = degisim_katsayisi * hacim * 2 * (t_dis - t_ic) / 3600
    
    # 5. Ekipman Yükleri (Fan ve Defrost - Tahmini ön hesap)
    q_fan_defrost = (q_iletim + q_urun_toplam) * 0.15 # Toplam yükün yaklaşık %15'i parazitiktir
    
    # 6. TOPLAM YÜK VE KAPASİTE TAYİNİ
    toplam_gunluk_kwh = q_iletim + q_urun_toplam + q_ic + q_infiltrasyon + q_fan_defrost
    emniyetli_yuk_kwh = toplam_gunluk_kwh * 1.20 # %20 Güvenlik Faktörü (Emniyet Payı)
    
    # Kompresör günde 16 saat çalışacak şekilde boyutlandırılır
    gerekli_komp_kw = emniyetli_yuk_kwh / 16.0 
    
    return {
        "q_iletim": q_iletim, "q_urun": q_urun_toplam, "q_infiltrasyon": q_infiltrasyon,
        "toplam_kwh": toplam_gunluk_kwh, "gerekli_kw": gerekli_komp_kw,
        "zemin_alani": zemin_alani, "toplam_panel_m2": zemin_alani * 2 + duvar_tavan_alani
    }

# ==========================================
# 4. KULLANICI ARAYÜZÜ VE YAPILANDIRMA
# ==========================================
st.markdown("<div class='info-kutu'><h1 style='text-align: center;'>ARCES Soğutma Sistemleri Konfigüratörü</h1></div>", unsafe_allow_html=True)

col1, col2 = st.columns()

with col1:
    st.header("1. Mimari ve Fiziksel Veriler")
    en = st.number_input("En (Metre)", min_value=1.0, value=4.0, step=0.5)
    boy = st.number_input("Boy (Metre)", min_value=1.0, value=5.0, step=0.5)
    yukseklik = st.number_input("Yükseklik (Metre)", min_value=2.0, value=2.5, step=0.1)
    
    st.header("2. Termodinamik Parametreler")
    t_dis = st.number_input("Dış Ortam Sıcaklığı (°C)", value=35.0)
    t_ic = st.selectbox("Hedef Depo Sıcaklığı (°C)", [4.0, -18.0])
    
    urun_tipi = st.selectbox("Depolanacak Ürün Cinsi", list(yerel_veritabani["urun_verileri"].keys()))
    urun_miktar_kg = st.number_input("Günlük Ürün Girişi (Kg/Gün)", min_value=0, value=2000, step=500)
    kapi_acilis = st.selectbox("Kapı Açılma Frekansı",, index=1)

with col2:
    st.header("3. Sistem Analizi ve Bileşen Seçimi")
    
    # Hedef sıcaklığa göre otomatik panel kalınlığı önerme
    tavsiye_panel = 80 if t_ic > 0 else 120
    panel_secenekleri = 
    secilen_panel_kalinlik = st.selectbox("İzolasyon Paneli Kalınlığı (mm)", panel_secenekleri, index=panel_secenekleri.index(tavsiye_panel))

    if st.button("Termodinamik Yükleri Hesapla ve Sistem Öner", type="primary"):
        sonuclar = hesapla_sogutma_yuku(en, boy, yukseklik, t_dis, t_ic, secilen_panel_kalinlik, urun_tipi, urun_miktar_kg, kapi_acilis)
        
        st.success(f"### ⚙️ Gereksinim Duyulan Soğutma Kapasitesi: {sonuclar['gerekli_kw']:.2f} kW")
        st.caption(f"Öngörülen Günlük Enerji (Isı) Yükü: {sonuclar['toplam_kwh']:.2f} kWh/Gün. Hesaplamalarda %20 emniyet faktörü ve kompresörün günde 16 saat aktif çalışacağı (run-time) baz alınmıştır.")
        
        # Grafiksel Dağılım
        st.write("#### Isı Kazancı Dağılımı (kWh/Gün)")
        c1, c2, c3 = st.columns(3)
        c1.metric("İletim (Transmisyon)", f"{sonuclar['q_iletim']:.1f}")
        c2.metric("Ürün ve Solunum", f"{sonuclar['q_urun']:.1f}")
        c3.metric("İnfiltrasyon", f"{sonuclar['q_infiltrasyon']:.1f}")
        
        st.divider()
        st.write("#### 🛠️ Önerilen Sistem Bileşenleri")
        
        # 1. Kompresör Seçimi Algoritması (Kapasiteyi karşılayan en uygun makine)
        uygun_komp = [k for k in yerel_veritabani["kompresorler"] if k["kapasite_kw"] >= sonuclar['gerekli_kw']]
        if uygun_komp:
            komp = min(uygun_komp, key=lambda x: x["kapasite_kw"]) # İhtiyacı karşılayan en küçük (en optimize) cihaz
            st.info(f"**Kompresör:** {komp['marka']} {komp['model']} ({komp['tip']}) - {komp['hp']} HP | Kapasite: {komp['kapasite_kw']} kW")
            fiyat_komp = komp["fiyat_eur"] * GUNCEL_KUR_EUR
        else:
            st.warning("Bu kapasite için tek bir kompresör yetersiz. Paralel (Rack) Sistem önerilir.")
            komp = yerel_veritabani["kompresorler"][-1]
            fiyat_komp = komp["fiyat_eur"] * GUNCEL_KUR_EUR * 2 # Çift cihaz
            
        # 2. Evaporatör Seçimi
        uygun_evap = [e for e in yerel_veritabani["evaporatorler"] if e["min_kw"] <= sonuclar['gerekli_kw'] <= e["max_kw"]]
        if uygun_evap:
            evap = uygun_evap
            st.info(f"**Evaporatör:** {evap['marka']} {evap['model']} - (Kapasite Uyumlu)")
            fiyat_evap = evap["fiyat_eur"] * GUNCEL_KUR_EUR
        else:
            st.warning("Bu kapasite aralığına uygun standart evaporatör bulunamadı, özel üretim gerekir.")
            fiyat_evap = 1200 * GUNCEL_KUR_EUR
        
        # 3. İzolasyon Paneli Maliyeti (Fire payı eklenerek)
        panel_veri = next(p for p in yerel_veritabani["paneller"] if p["kalinlik_mm"] == secilen_panel_kalinlik)
        panel_m2_fiyat = panel_veri["fiyat_eur_m2"]
        brut_panel_m2 = sonuclar['toplam_panel_m2'] * 1.08 # %8 Montaj ve Kesim Firesi
        fiyat_panel = brut_panel_m2 * panel_m2_fiyat * GUNCEL_KUR_EUR
        st.info(f"**İzolasyon Paneli:** {secilen_panel_kalinlik} mm PUR/PIR Sandviç Panel. Yaklaşık {brut_panel_m2:.1f} m² (Fire Dahil)")
        
        # 4. Kapı Seçimi Algoritması
        kapi_tipi = "Sürgülü Kapı (120x200)" if sonuclar['zemin_alani'] > 20 else "Menteşeli Çarpma Kapı (90x190)"
        fiyat_kapi = 450 * GUNCEL_KUR_EUR if "Sürgülü" in kapi_tipi else 325 * GUNCEL_KUR_EUR
        if t_ic < 0: fiyat_kapi += 50 * GUNCEL_KUR_EUR # Donuk oda rezistans farkı
        st.info(f"**Kapı:** {kapi_tipi} (Termal Geçiş Optimizasyonu)")
        
        # Finansal Özet
        toplam_malzeme = fiyat_komp + fiyat_evap + fiyat_panel + fiyat_kapi
        muhendislik_kari = toplam_malzeme * 0.20 # %20 Marj
        toplam_satis = toplam_malzeme + muhendislik_kari
        
        st.success(f"### 💰 Anahtar Teslim Proje Tahmini Bedeli: {toplam_satis:,.2f} ₺ + KDV")
        
        # OPEX (İşletme Maliyeti) Tahmini
        tahmini_aylik_kwh = (komp["hp"] * 0.75 * 16 * 30) + (1.2 * 1.5 * 30) # Komp + Defrost tahmini
        st.caption(f"💡 **OPEX Bilgisi:** Seçilen {komp['hp']} HP sistemin aylık ortalama elektrik tüketimi {tahmini_aylik_kwh:.0f} kWh seviyesinde öngörülmektedir.")
