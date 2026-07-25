import streamlit as st
from supabase import create_client, Client
import pandas as pd
import os
import uuid
import time
import math
from fpdf import FPDF

# ==========================================
# 1. SUPABASE BAĞLANTISI VE AYARLAR
# ==========================================
st.set_page_config(page_title="Arces Mühendislik - Konfigüratör", page_icon="❄️", layout="wide")

st.markdown("""
    <style>
    /* BEYAZ ÜST BARI VE STREAMLIT İZLERİNİ KÖKTEN GİZLEME */
    #MainMenu {visibility: hidden;}
    header {visibility: hidden !important;}
    footer {visibility: hidden !important;}
    .stApp > header {display: none !important;}
    [data-testid="stHeader"] {display: none !important;}
    .block-container {padding-top: 2rem !important; margin-top: 0 !important;}
    
    .stDataFrame {font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;}
    h1, h2, h3 {color: #0284c7; font-weight: 600;}
    .fiyat-gizli {color: #eab308; font-weight: bold;}
    .auth-kutu {border: 1px solid #ddd; padding: 20px; border-radius: 10px; background-color: #f8fafc; margin-bottom: 20px;}
    .info-kutu {border: 1px solid #ddd; padding: 20px; border-radius: 10px; background-color: #f0f9ff; margin-bottom: 20px;}
    </style>
""", unsafe_allow_html=True)

@st.cache_resource
def init_supabase():
    url = os.environ.get("SUPABASE_URL") or st.secrets.get("SUPABASE_URL", "")
    key = os.environ.get("SUPABASE_KEY") or st.secrets.get("SUPABASE_KEY", "")
    return create_client(url, key)

supabase = init_supabase()
GUNCEL_KUR_EUR = 38.50 

# Session State (Hafıza) Başlatma
if 'sepet' not in st.session_state:
    st.session_state['sepet'] = []
if 'kullanici_rol' not in st.session_state:
    st.session_state['kullanici_rol'] = 'ziyaretci' 
if 'kullanici_email' not in st.session_state:
    st.session_state['kullanici_email'] = ''

is_logged_in = st.session_state['kullanici_rol'] in ['bayi', 'admin']
is_admin = st.session_state['kullanici_rol'] == 'admin'

# ==========================================
# 2. PDF OLUŞTURMA VE SEPET FONKSİYONLARI
# ==========================================
def create_pdf(sepet_verisi, toplam):
    pdf = FPDF()
    pdf.add_page()
    
    has_font = os.path.exists("arial.ttf")
    if has_font:
        pdf.add_font("ArialTR", "", "arial.ttf", uni=True)
        pdf.add_font("ArialTR_B", "B", "arial.ttf", uni=True)
    
    try:
        if os.path.exists("logo.png"):
            pdf.image("logo.png", x=10, y=8, w=40)
    except:
        pass 
        
    pdf.set_font("ArialTR_B" if has_font else "Arial", "B", 20)
    pdf.cell(0, 10, txt="ARCES MUHENDISLIK", ln=True, align='C')
    pdf.set_font("ArialTR" if has_font else "Arial", "", 12)
    pdf.cell(0, 6, txt="Soguk Hava Deposu Konfigurasyon Teklifi", ln=True, align='C')
    pdf.cell(0, 6, txt="Web: www.arcesmuhendislik.com", ln=True, align='C')
    pdf.ln(15)
        
    pdf.set_font("ArialTR_B" if has_font else "Arial", "B", 12)
    pdf.cell(40, 10, txt="Kategori", border=1)
    pdf.cell(110, 10, txt="Marka / Model", border=1)
    pdf.cell(40, 10, txt="Fiyat (TL)", border=1, ln=True)
    
    pdf.set_font("ArialTR" if has_font else "Arial", "", 12)
    for index, row in sepet_verisi.iterrows():
        pdf.cell(40, 10, txt=str(row['Kategori'])[:15], border=1)
        pdf.cell(110, 10, txt=str(row['Marka/Model'])[:45], border=1)
        pdf.cell(40, 10, txt=f"{row['Fiyat']:,.2f}", border=1, ln=True)
        
    pdf.ln(10)
    pdf.set_font("ArialTR_B" if has_font else "Arial", "B", 14)
    pdf.cell(0, 10, txt=f"Genel Toplam: {toplam:,.2f} TL + KDV", ln=True, align='R')
    return bytes(pdf.output())

def sepetten_cikar(uid):
    st.session_state['sepet'] = [item for item in st.session_state['sepet'] if item.get('sepet_id') != uid]

# ==========================================
# 3. TERMODİNAMİK HESAPLAMA MOTORU 
# ==========================================
def hesapla_sogutma_yuku(en, boy, yukseklik, t_dis, t_ic, panel_kalinlik, urun_tipi, urun_miktar_kg, kapi_acilis, db):
    panel = next((p for p in db["paneller"] if str(p["kalinlik_mm"]) == str(panel_kalinlik)), None)
    if panel is None: return None
        
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
# 4. EN ÜST ALAN: MARKA VE KULLANICI GİRİŞİ
# ==========================================
st.markdown("<div class='auth-kutu'>", unsafe_allow_html=True)
col_logo, col_auth = st.columns([1, 2])

with col_logo:
    if os.path.exists("logo.png"):
        st.image("logo.png", width=250)
    else:
        st.markdown("## ARCES MÜHENDİSLİK")

with col_auth:
    if not is_logged_in:
        auth_sekmeler = st.tabs(["Giriş Yap", "Kayıt Ol", "Şifremi Unuttum"])
        
        with auth_sekmeler[0]:
            col_g1, col_g2, col_g3 = st.columns([2, 2, 1])
            g_email = col_g1.text_input("E-Posta", key="g_email", label_visibility="collapsed", placeholder="E-Posta Adresiniz")
            g_sifre = col_g2.text_input("Şifre", type="password", key="g_sifre", label_visibility="collapsed", placeholder="Şifreniz")
            if col_g3.button("Giriş Yap", use_container_width=True):
                temiz_email = g_email.strip().lower()
                temiz_sifre = g_sifre.strip()
                try:
                    user_req = supabase.table("kullanicilar").select("*").eq("email", temiz_email).eq("sifre", temiz_sifre).execute()
                    if user_req.data:
                        user_data = user_req.data[0]
                        if user_data.get('onayli_mi', False):
                            st.session_state['kullanici_rol'] = user_data.get('rol', 'bayi')
                            st.session_state['kullanici_email'] = user_data['email']
                            st.rerun()
                        else:
                            st.warning("Hesabınız onay bekliyor.")
                    else:
                        st.error("Hatalı e-posta veya şifre.")
                except Exception as e:
                    st.error(f"Bağlantı hatası: {e}")
                    
        with auth_sekmeler[1]:
            col_k1, col_k2, col_k3 = st.columns([2, 2, 1])
            k_email = col_k1.text_input("E-Posta", key="k_email", label_visibility="collapsed", placeholder="E-Posta Adresiniz")
            k_sifre = col_k2.text_input("Şifre", type="password", key="k_sifre", label_visibility="collapsed", placeholder="Şifre Belirleyin")
            if col_k3.button("Kayıt Ol", use_container_width=True):
                try:
                    supabase.table("kullanicilar").insert({"email": k_email.strip().lower(), "sifre": k_sifre.strip()}).execute()
                    st.success("Kayıt başarılı! Yönetici onayından sonra girebilirsiniz.")
                except:
                    st.error("Bu e-posta sistemde zaten var.")
                    
        with auth_sekmeler[2]:
            col_u1, col_u2 = st.columns([3, 1])
            u_email = col_u1.text_input("E-Posta", key="u_email", label_visibility="collapsed", placeholder="Kayıtlı E-Posta Adresiniz")
            if col_u2.button("Talep Gönder", use_container_width=True):
                check = supabase.table("kullanicilar").select("id").eq("email", u_email.strip().lower()).execute()
                if check.data:
                    supabase.table("kullanicilar").update({"sifre_sifirlama_istendi": True}).eq("email", u_email.strip().lower()).execute()
                    st.success("Talebiniz iletildi.")
                else:
                    st.error("E-posta bulunamadı.")
    else:
        st.success(f"Hoş geldiniz, {st.session_state['kullanici_email']} ({st.session_state['kullanici_rol'].upper()})")
        col_btn1, col_btn2 = st.columns([1, 1])
        with st.expander("🔑 Şifremi Değiştir"):
            yeni_sifre = st.text_input("Yeni Şifreniz", type="password")
            if st.button("Şifreyi Güncelle"):
                supabase.table("kullanicilar").update({"sifre": yeni_sifre.strip()}).eq("email", st.session_state['kullanici_email']).execute()
                st.success("Şifreniz değiştirildi!")
        if st.button("🚪 Çıkış Yap", type="secondary"):
            for key in ['kullanici_rol', 'kullanici_email']: st.session_state[key] = 'ziyaretci' if key == 'kullanici_rol' else ''
            st.session_state['sepet'] = []
            st.rerun()

st.markdown("</div>", unsafe_allow_html=True)

# ==========================================
# 5. VERİTABANI ÖN YÜKLEME (ÖNBELLEKLİ)
# ==========================================
@st.cache_data(ttl=600)
def veritabani_cek():
    try:
        pnl = supabase.table("paneller").select("*").execute().data
        urn = supabase.table("urun_verileri").select("*").execute().data
        prc = supabase.table("parcalar").select("*").execute().data 
        
        urun_dict = {item["urun_tipi"]: {"cp": item["cp"], "solunum_kj_kg": item["solunum_kj_kg"]} for item in urn}
        return {
            "paneller": pnl, 
            "urun_verileri": urun_dict, 
            "parcalar_db": prc,
            "kompresorler": [p for p in prc if str(p.get("tip")).lower() == "kompresor"],
            "evaporatorler": [p for p in prc if str(p.get("tip")).lower() == "evaporator"]
        }
    except Exception as e:
        st.error(f"Veri çekme hatası: {e}")
        return None

db = veritabani_cek()

# ==========================================
# 6. ANA EKRAN YÖNETİMİ (SEKMELER)
# ==========================================
if db:
    ana_sekmeler = ["İleri Düzey Konfigüratör"]
    if is_admin: ana_sekmeler.append("⚙️ Admin Paneli")
    secilen_ana_sekme = st.tabs(ana_sekmeler)

    # ----------------- KONFİGÜRATÖR SEKMESİ -----------------
    with secilen_ana_sekme[0]:
        if not is_logged_in:
            st.warning("⚠️ Ziyaretçi Modu: Sistemi test edebilirsiniz ancak fiyatları görmek ve teklif (PDF) almak için üye girişi yapmalısınız.")
            
        st.markdown("<div class='info-kutu'><h3 style='text-align: center;'>1. Adım: Termodinamik Analiz ve Otomatik Öneri</h3></div>", unsafe_allow_html=True)
        
        c_sol, c_sag = st.columns(2)
        with c_sol:
            en = st.number_input("En (Metre)", min_value=1.0, value=4.0, step=0.5)
            boy = st.number_input("Boy (Metre)", min_value=1.0, value=5.0, step=0.5)
            yukseklik = st.number_input("Yükseklik (Metre)", min_value=2.0, value=2.5, step=0.1)
            t_dis = st.number_input("Dış Ortam Sıcaklığı (°C)", value=35.0)
            
        with c_sag:
            t_ic = st.selectbox("Hedef Depo Sıcaklığı (°C)", [4.0, -18.0])
            urun_tipi = st.selectbox("Depolanacak Ürün Cinsi", list(db["urun_verileri"].keys()))
            urun_miktar_kg = st.number_input("Günlük Ürün Girişi (Kg/Gün)", min_value=0, value=2000, step=500)
            kapi_acilis = st.selectbox("Kapı Açılma Frekansı", ["Düşük", "Orta", "Yüksek"], index=1)
            
            tavsiye_panel = 80 if t_ic > 0 else 120
            panel_secenekleri = [p["kalinlik_mm"] for p in db["paneller"]]
            secilen_panel_kalinlik = st.selectbox("İzolasyon Paneli Kalınlığı (mm)", panel_secenekleri, index=panel_secenekleri.index(tavsiye_panel) if tavsiye_panel in panel_secenekleri else 0)

        # HATA ÇÖZÜMÜ: Buton tıklamasını hafızaya alma
        if st.button("Termodinamik Yükleri Hesapla ve Sistem Öner", type="primary"):
            st.session_state['hesaplama_yapildi'] = True
            
        # Hafızadaki bilgi True olduğu sürece bu blok açık kalır ve içindeki "Sepete Ekle" butonu çalışır
        if st.session_state.get('hesaplama_yapildi', False):
            sonuclar = hesapla_sogutma_yuku(en, boy, yukseklik, t_dis, t_ic, secilen_panel_kalinlik, urun_tipi, urun_miktar_kg, kapi_acilis, db)
            
            if sonuclar:
                st.success(f"### ⚙️ Gereksinim Duyulan Soğutma Kapasitesi: {sonuclar['gerekli_kw']:.2f} kW")
                
                uygun_komp = [k for k in db["kompresorler"] if float(k.get("kapasite_kw", 0)) >= sonuclar['gerekli_kw']]
                komp = min(uygun_komp, key=lambda x: float(x["kapasite_kw"])) if uygun_komp else None
                
                uygun_evap = [e for e in db["evaporatorler"] if float(e.get("min_kw", 0)) <= sonuclar['gerekli_kw'] <= float(e.get("max_kw", 999))]
                evap = uygun_evap[0] if uygun_evap else None
                
                panel_veri = next((p for p in db["paneller"] if str(p["kalinlik_mm"]) == str(secilen_panel_kalinlik)), None)
                brut_panel_m2 = sonuclar['toplam_panel_m2'] * 1.08
                
                kapi_tipi = "Sürgülü Kapı (120x200)" if sonuclar['zemin_alani'] > 20 else "Menteşeli Çarpma Kapı (90x190)"
                kapi_fiyat_tl = (450 if "Sürgülü" in kapi_tipi else 325) * GUNCEL_KUR_EUR
                if t_ic < 0: kapi_fiyat_tl += 50 * GUNCEL_KUR_EUR

                st.write("#### 🛠️ Motorun Sizin İçin Önerdiği Bileşenler")
                
                onerilen_sepet_listesi = []
                
                if komp:
                    fiyat_tl = float(komp.get("fiyat", komp.get("fiyat_eur", 0) * GUNCEL_KUR_EUR))
                    st.info(f"**Kompresör:** {komp.get('marka','')} {komp.get('model_adi','')} | Kapasite: {komp.get('kapasite_kw','')} kW")
                    onerilen_sepet_listesi.append({"Kategori": "Kompresör", "Marka/Model": f"{komp.get('marka','')} - {komp.get('model_adi','')}", "Fiyat": fiyat_tl})
                
                if evap:
                    fiyat_tl = float(evap.get("fiyat", evap.get("fiyat_eur", 0) * GUNCEL_KUR_EUR))
                    st.info(f"**Evaporatör:** {evap.get('marka','')} {evap.get('model_adi','')}")
                    onerilen_sepet_listesi.append({"Kategori": "Evaporatör", "Marka/Model": f"{evap.get('marka','')} - {evap.get('model_adi','')}", "Fiyat": fiyat_tl})
                    
                if panel_veri:
                    panel_fiyat_tl = float(panel_veri["fiyat_eur_m2"]) * brut_panel_m2 * GUNCEL_KUR_EUR
                    st.info(f"**Panel:** {secilen_panel_kalinlik} mm PUR/PIR. Miktar: {brut_panel_m2:.1f} m² (Fire Dahil)")
                    onerilen_sepet_listesi.append({"Kategori": "İzolasyon Paneli", "Marka/Model": f"{secilen_panel_kalinlik} mm PUR/PIR Panel ({brut_panel_m2:.1f} m²)", "Fiyat": panel_fiyat_tl})
                
                st.info(f"**Kapı:** {kapi_tipi}")
                onerilen_sepet_listesi.append({"Kategori": "Kapı", "Marka/Model": kapi_tipi, "Fiyat": kapi_fiyat_tl})
                
                if st.button("🛒 BU ÖNERİLEN SİSTEMİ SEPETE EKLE", type="primary"):
                    for urun in onerilen_sepet_listesi:
                        urun["sepet_id"] = str(uuid.uuid4())
                        st.session_state['sepet'].append(urun)
                    st.success("Tüm önerilen parçalar sepete eklendi! Sayfanın en altından inceleyebilirsiniz.")
                    # İsteğe bağlı: Eklendikten sonra hesaplama ekranı kapansın derseniz alttaki satırı aktif edebilirsiniz.
                    # st.session_state['hesaplama_yapildi'] = False

        st.divider()
        
        # --- MANUEL PARÇA SEÇİMİ (ESKİ KATALOG YAPISI) ---
        st.markdown("<div class='info-kutu'><h3 style='text-align: center;'>2. Adım: Manuel Katalog (İstediğiniz Parçayı Kendiniz Seçin)</h3></div>", unsafe_allow_html=True)
        
        # Kategorileri (Tipleri) bul
        kategori_isimleri = list(set([str(p.get("tip", "Diger")).capitalize() for p in db["parcalar_db"] if p.get("tip")]))
        if kategori_isimleri:
            sekmeler_kat = st.tabs(kategori_isimleri)
            
            for index, sekme in enumerate(sekmeler_kat):
                with sekme:
                    aktif_tip = kategori_isimleri[index].lower()
                    uygun_parcalar = [p for p in db["parcalar_db"] if str(p.get("tip", "")).lower() == aktif_tip]
                    
                    if uygun_parcalar:
                        for parca in uygun_parcalar:
                            marka_adi = parca.get("marka", "Markasız")
                            model_adi = parca.get("model_adi", parca.get("model", "İsimsiz"))
                            # Eğer fiyat TL değil EUR girilmişse çevir, TL ise doğrudan al
                            raw_fiyat = parca.get("fiyat")
                            if raw_fiyat is None or float(raw_fiyat) == 0:
                                gosterilecek_fiyat = float(parca.get("fiyat_eur", 0)) * GUNCEL_KUR_EUR
                            else:
                                gosterilecek_fiyat = float(raw_fiyat)

                            p_col1, p_col2, p_col3, p_col4 = st.columns([4, 2, 2, 2])
                            p_col1.write(f"**{marka_adi} - {model_adi}**")
                            p_col2.write(f"Kapasite: {parca.get('kapasite_kw', 0)} kW" if parca.get("kapasite_kw") else "")
                            
                            if is_logged_in:
                                p_col3.write(f"Fiyat: {gosterilecek_fiyat:,.2f} TL")
                            else:
                                p_col3.markdown("<span class='fiyat-gizli'>🔒 Giriş Gerekli</span>", unsafe_allow_html=True)
                            
                            if p_col4.button("Sepete Ekle", key=f"ekle_mnl_{parca['id']}"):
                                st.session_state['sepet'].append({
                                    "sepet_id": str(uuid.uuid4()),
                                    "Kategori": aktif_tip.capitalize(),
                                    "Marka/Model": f"{marka_adi} - {model_adi}",
                                    "Fiyat": gosterilecek_fiyat
                                })
                                st.rerun()
                    else:
                        st.caption("Bu kategoride ürün bulunamadı.")
        else:
            st.info("Katalogda manuel seçilecek parça bulunamadı.")

        st.divider()

        # --- SEPET ÖZETİ VE PDF ÇIKTISI ---
        st.header("🛒 3. Adım: Konfigürasyon Sepeti ve Teklif Çıktısı")
        if st.session_state['sepet']:
            for item in st.session_state['sepet']:
                if 'sepet_id' not in item: item['sepet_id'] = str(uuid.uuid4())
                s_col1, s_col2, s_col3, s_col4 = st.columns([2, 5, 3, 2])
                s_col1.write(item['Kategori'])
                s_col2.write(item['Marka/Model'])
                
                if is_logged_in: s_col3.write(f"{item['Fiyat']:,.2f} TL")
                else: s_col3.markdown("<span class='fiyat-gizli'>🔒 Gizli</span>", unsafe_allow_html=True)
                    
                s_col4.button("❌ Çıkar", key=f"sil_{item['sepet_id']}", on_click=sepetten_cikar, args=(item['sepet_id'],))
                
            st.write("---")
            df_sepet = pd.DataFrame(st.session_state['sepet'])
            toplam_tutar = df_sepet["Fiyat"].sum()
            
            if is_logged_in:
                st.success(f"### 💰 Toplam Sistem Maliyeti: {toplam_tutar:,.2f} TL")
                col_pdf, col_temizle = st.columns([1, 1])
                with col_pdf:
                    try:
                        pdf_bytes = create_pdf(df_sepet, toplam_tutar)
                        st.download_button(label="📄 PDF Olarak İndir (Arces Teklifi)", data=pdf_bytes, file_name="Arces_Teklif.pdf", mime="application/pdf", type="primary", use_container_width=True)
                    except Exception as e:
                        st.error(f"PDF hatası: {e}")
                with col_temizle:
                    if st.button("Tüm Sepeti Temizle", type="secondary", use_container_width=True):
                        st.session_state['sepet'] = []
                        st.rerun()
            else:
                st.error("🔒 Sistemin toplam maliyetini görmek ve PDF Teklif alabilmek için giriş yapınız.")
                if st.button("Sepeti Temizle", type="secondary"):
                    st.session_state['sepet'] = []
                    st.rerun()
        else:
            st.info("Sepetinizde henüz parça yok. Yukarıdan önerilenleri veya manuel katalogdan seçtiklerinizi ekleyebilirsiniz.")

    # ----------------- ADMİN PANELİ SEKMESİ -----------------
    if is_admin:
        with secilen_ana_sekme[1]:
            st.header("⚙️ Yönetici (Admin) Paneli")
            admin_tab1, admin_tab3, admin_tab4 = st.tabs(["Kullanıcı Onayları", "➕ Yeni Ürün Ekle", "Şifre Sıfırlama Talepleri"])
            
            with admin_tab1:
                bekleyenler = supabase.table("kullanicilar").select("*").eq("onayli_mi", False).execute().data
                if bekleyenler:
                    for usr in bekleyenler:
                        u_col1, u_col2 = st.columns([3,1])
                        u_col1.write(f"📧 **{usr['email']}**")
                        if u_col2.button("✅ Onayla", key=f"onay_{usr['id']}"):
                            supabase.table("kullanicilar").update({"onayli_mi": True}).eq("id", usr['id']).execute()
                            st.rerun()
                else:
                    st.info("Onay bekleyen yeni kayıt yok.")
                    
            with admin_tab3:
                st.subheader("Kataloğa Yeni Cihaz Ekle")
                with st.form("yeni_urun_formu"):
                    y_tip = st.selectbox("Parça Tipi (Kategori)", ["kompresor", "evaporator", "panel", "kapi", "diger"])
                    y_marka = st.text_input("Marka", placeholder="Örn: Bitzer")
                    y_model = st.text_input("Model Adı", placeholder="Örn: Yeni Seri 10HP")
                    y_kw = st.number_input("Kapasite (kW)", min_value=0.0, step=1.0)
                    y_fiyat_tl = st.number_input("Birim Fiyatı (TL)", min_value=0.0, step=100.0)
                    
                    if st.form_submit_button("Ürünü Kaydet"):
                        if not y_marka or not y_model:
                            st.error("Marka ve Model adı zorunludur.")
                        else:
                            supabase.table("parcalar").insert({
                                "tip": y_tip,
                                "marka": y_marka,
                                "model_adi": y_model,
                                "kapasite_kw": y_kw,
                                "fiyat": y_fiyat_tl
                            }).execute()
                            st.success("✅ Yeni ürün eklendi! Önbelleği temizlediğinizde katalogda görünecektir.")

            with admin_tab4:
                sifre_isteyenler = supabase.table("kullanicilar").select("*").eq("sifre_sifirlama_istendi", True).execute().data
                if sifre_isteyenler:
                    for usr in sifre_isteyenler:
                        s_col1, s_col2 = st.columns([3, 1])
                        s_col1.write(f"📧 **{usr['email']}** şifre sıfırlama bekliyor.")
                        if s_col2.button("Geçici Şifre Ata", key=f"sifirla_{usr['id']}"):
                            supabase.table("kullanicilar").update({"sifre": "arces1234", "sifre_sifirlama_istendi": False}).eq("id", usr['id']).execute()
                            st.rerun()
                else:
                    st.info("Şifre sıfırlama talebi bulunmuyor.")
