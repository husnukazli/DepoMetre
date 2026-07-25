import streamlit as st
import pandas as pd
import math
import os
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

# Oturum Değişkenleri
if 'sepet' not in st.session_state:
    st.session_state['sepet'] = []
if 'kullanici_rol' not in st.session_state:
    st.session_state['kullanici_rol'] = 'bayi'

# ==========================================
# 2. SUPABASE BAĞLANTISI VE ÖNBELLEKLİ VERİ ÇEKME
# ==========================================
# Not: Streamlit secrets (st.secrets) veya çevre değişkenleri kullanılmalıdır.
@st.cache_resource
def init_supabase():
    url = os.environ.get("SUPABASE_URL") or st.secrets.get("SUPABASE_URL", "")
    key = os.environ.get("SUPABASE_KEY") or st.secrets.get("SUPABASE_KEY", "")
    return create_client(url, key)

supabase = init_supabase()

# Verilerin her seferinde sorgulanıp yavaşlamaması için @st.cache_data kullanıyoruz
@st.cache_data(ttl=600)
def veritabani_verilerini_cek():
    paneller = supabase.table("paneller").select("*").execute().data
    urun_verileri_raw = supabase.table("urun_verileri").select("*").execute().data
    parcalar = supabase.table("parcalar").select("*").execute().data
    
    # Ürün verilerini Streamlit'in kolay okuyabileceği sözlük formatına çevirelim
    urun_sozlugu = {item["urun_tipi"]: {"cp": item["cp"], "solunum_kj_kg": item["solunum_kj_kg"]} for item in urun_verileri_raw}
    
    return {
        "paneller": paneller,
        "urun_verileri": urun_sozlugu,
        "kompresorler": [p for p in parcalar if p.get("tip") == "kompresor"],
        "evaporatorler": [p for p in parcalar if p.get("tip") == "evaporator"]
    }

db = veritabani_verilerini_cek()
GUNCEL_KUR_EUR = 38.50 # 2026 Projeksiyonlu Kur

# ==========================================
# 3. TERMODİNAMİK HESAPLAMA MOTORU
# ==========================================
def hesapla_sogutma_yuku(en, boy, yukseklik, t_dis, t_ic, panel_kalinlik, urun_tipi, urun_miktar_kg, kapi_acilis):
    panel = next(p for p in db["paneller"] if p["kalinlik_mm"] == panel_kalinlik)
    u_degeri = float(panel["u_degeri"])
    
    zemin_alani = en * boy
    duvar_tavan_alani = (2 * en * yukseklik) + (2 * boy * yukseklik) + (en * boy)
    
    q_duvar_tavan = u_degeri * duvar_tavan_alani * (t_dis - t_ic) * 24 / 1000
    q_zemin = u_degeri * zemin_alani * (15 - t_ic) * 24 / 1000
    q_iletim = q_duvar_tavan + q_zemin
    
    urun = db["urun_verileri"][urun_tipi]
    q_urun_duyulur = urun_miktar_kg * float(urun["cp"]) * (t_dis - t_ic) / 3600
    q_urun_solunum = (urun_miktar_kg * float(urun["solunum_kj_kg"])) / 3600
    q_urun_toplam = q_urun_duyulur + q_urun_solunum
    
    kisi_sayisi = 1 if zemin_alani < 20 else 2
    q_personel = (kisi_sayisi * 4 * 270) / 1000
    lamba_sayisi = math.ceil(zemin_alani / 10)
    q_aydinlatma = (lamba_sayisi * 4 * 100) / 1000
    q_ic = q_personel + q_aydinlatma
    
    hacim = en * boy * yukseklik
    degisim_katsayisi = {"Düşük": 3, "Orta": 5, "Yüksek": 8}[kapi_acilis]
    q_infiltrasyon = degisim_katsayisi * hacim * 2 * (t_dis - t_ic) / 3600
    
    q_fan_defrost = (q_iletim + q_urun_toplam) * 0.15
    
    toplam_gunluk_kwh = q_iletim + q_urun_toplam + q_ic + q_infiltrasyon + q_fan_defrost
    emniyetli_yuk_kwh = toplam_gunluk_kwh * 1.20
    gerekli_komp_kw = emniyetli_yuk_kwh / 16.0
    
    return {
        "q_iletim": q_iletim, "q_urun": q_urun_toplam, "q_infiltrasyon": q_infiltrasyon,
        "toplam_kwh": toplam_gunluk_kwh, "gerekli_kw": gerekli_komp_kw,
        "zemin_alani": zemin_alani, "toplam_panel_m2": zemin_alani * 2 + duvar_tavan_alani
    }

# ==========================================
# 4. KULLANICI ARAYÜZÜ
# ==========================================
st.markdown("<div class='info-kutu'><h1 style='text-align: center;'>ARCES Soğutma Sistemleri Konfigüratörü</h1></div>", unsafe_allow_html=True)

col1, col2 = st.columns(2)

with col1:
    st.header("1. Mimari ve Fiziksel Veriler")
    en = st.number_input("En (Metre)", min_value=1.0, value=4.0, step=0.5)
    boy = st.number_input("Boy (Metre)", min_value=1.0, value=5.0, step=0.5)
    yukseklik = st.number_input("Yükseklik (Metre)", min_value=2.0, value=2.5, step=0.1)
    
    st.header("2. Termodinamik Parametreler")
    t_dis = st.number_input("Dış Ortam Sıcaklığı (°C)", value=35.0)
    t_ic = st.selectbox("Hedef Depo Sıcaklığı (°C)", [4.0, -18.0])
    
    urun_tipi = st.selectbox("Depolanacak Ürün Cinsi", list(db["urun_verileri"].keys()))
    urun_miktar_kg = st.number_input("Günlük Ürün Girişi (Kg/Gün)", min_value=0, value=2000, step=500)
    kapi_acilis = st.selectbox("Kapı Açılma Frekansı", ["Düşük", "Orta", "Yüksek"], index=1)

with col2:
    st.header("3. Sistem Analizi ve Bileşen Seçimi")
    
    tavsiye_panel = 80 if t_ic > 0 else 120
    panel_secenekleri = [p["kalinlik_mm"] for p in db["paneller"]]
    secilen_panel_kalinlik = st.selectbox("İzolasyon Paneli Kalınlığı (mm)", panel_secenekleri, index=panel_secenekleri.index(tavsiye_panel) if tavsiye_panel in panel_secenekleri else 0)

    if st.button("Termodinamik Yükleri Hesapla ve Sistem Öner", type="primary"):
        sonuclar = hesapla_sogutma_yuku(en, boy, yukseklik, t_dis, t_ic, secilen_panel_kalinlik, urun_tipi, urun_miktar_kg, kapi_acilis)
        
        st.success(f"### ⚙️ Gereksinim Duyulan Soğutma Kapasitesi: {sonuclar['gerekli_kw']:.2f} kW")
        st.caption(f"Öngörülen Günlük Enerji (Isı) Yükü: {sonuclar['toplam_kwh']:.2f} kWh/Gün. Hesaplamalarda %20 emniyet faktörü baz alınmıştır.")
        
        st.write("#### Isı Kazancı Dağılımı (kWh/Gün)")
        c1, c2, c3 = st.columns(3)
        c1.metric("İletim (Transmisyon)", f"{sonuclar['q_iletim']:.1f}")
        c2.metric("Ürün ve Solunum", f"{sonuclar['q_urun']:.1f}")
        c3.metric("İnfiltrasyon", f"{sonuclar['q_infiltrasyon']:.1f}")
        
        st.divider()
        st.write("#### 🛠️ Önerilen Sistem Bileşenleri")
        
        # Kompresör Seçimi
        uygun_komp = [k for k in db["kompresorler"] if float(k.get("kapasite_kw", 0)) >= sonuclar['gerekli_kw']]
        if uygun_komp:
            komp = min(uygun_komp, key=lambda x: float(x["kapasite_kw"]))
            st.info(f"**Kompresör:** {komp.get('marka', '')} {komp.get('model', '')} ({komp.get('tip', 'Standart')}) - {komp.get('hp', 0)} HP | Kapasite: {komp['kapasite_kw']} kW")
            fiyat_komp = float(komp.get("fiyat_eur", 0)) * GUNCEL_KUR_EUR
        else:
            st.warning("Bu kapasite için tek bir kompresör yetersiz. Paralel (Rack) Sistem önerilir.")
            komp = db["kompresorler"][-1] if db["kompresorler"] else {"hp": 5, "fiyat_eur": 1500}
            fiyat_komp = float(komp.get("fiyat_eur", 1500)) * GUNCEL_KUR_EUR * 2
            
        # Evaporatör Seçimi (Önceki hatayı düzelterek liste kontrolü eklendi)
        uygun_evap = [e for e in db["evaporatorler"] if float(e.get("min_kw", 0)) <= sonuclar['gerekli_kw'] <= float(e.get("max_kw", 999))]
        if uygun_evap:
            evap = uygun_evap[0] # Liste hatası (TypeError) önlendi
            st.info(f"**Evaporatör:** {evap.get('marka', '')} {evap.get('model', '')} - (Kapasite Uyumlu)")
            fiyat_evap = float(evap.get("fiyat_eur", 0)) * GUNCEL_KUR_EUR
        else:
            st.warning("Bu kapasite aralığına uygun standart evaporatör bulunamadı, özel üretim gerekir.")
            fiyat_evap = 1200 * GUNCEL_KUR_EUR
        
        # İzolasyon Paneli Maliyeti
        panel_veri = next(p for p in db["paneller"] if p["kalinlik_mm"] == secilen_panel_kalinlik)
        panel_m2_fiyat = float(panel_veri["fiyat_eur_m2"])
        brut_panel_m2 = sonuclar['toplam_panel_m2'] * 1.08
        fiyat_panel = brut_panel_m2 * panel_m2_fiyat * GUNCEL_KUR_EUR
        st.info(f"**İzolasyon Paneli:** {secilen_panel_kalinlik} mm PUR/PIR Sandviç Panel. Yaklaşık {brut_panel_m2:.1f} m² (Fire Dahil)")
        
        # Kapı Seçimi
        kapi_tipi = "Sürgülü Kapı (120x200)" if sonuclar['zemin_alani'] > 20 else "Menteşeli Çarpma Kapı (90x190)"
        fiyat_kapi = 450 * GUNCEL_KUR_EUR if "Sürgülü" in kapi_tipi else 325 * GUNCEL_KUR_EUR
        if t_ic < 0: fiyat_kapi += 50 * GUNCEL_KUR_EUR
        st.info(f"**Kapı:** {kapi_tipi} (Termal Geçiş Optimizasyonu)")
        
        # Finansal Özet
        toplam_malzeme = fiyat_komp + fiyat_evap + fiyat_panel + fiyat_kapi
        muhendislik_kari = toplam_malzeme * 0.20
        toplam_satis = toplam_malzeme + muhendislik_kari
        
        st.success(f"### 💰 Anahtar Teslim Proje Tahmini Bedeli: {toplam_satis:,.2f} ₺ + KDV")
        hp_degeri = float(komp.get("hp", 3))
        tahmini_aylik_kwh = (hp_degeri * 0.75 * 16 * 30) + (1.2 * 1.5 * 30)
        st.caption(f"💡 **OPEX Bilgisi:** Seçilen {hp_degeri} HP sistemin aylık ortalama elektrik tüketimi {tahmini_aylik_kwh:.0f} kWh seviyesinde öngörülmektedir.")
