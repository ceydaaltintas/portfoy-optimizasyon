import streamlit as st
import pandas as pd
import os
from datetime import date

import data_loader
import optimizer
import excel_export
from create_sample import create_sample
from create_template import create_template

SAMPLE_PATH = "sample_data/ornek_veri.xlsx"
TEMPLATE_PATH = "sample_data/sablon.xlsx"
if not os.path.exists(SAMPLE_PATH):
    os.makedirs("sample_data", exist_ok=True)
    create_sample(SAMPLE_PATH)
if not os.path.exists(TEMPLATE_PATH):
    os.makedirs("sample_data", exist_ok=True)
    create_template(TEMPLATE_PATH)

st.set_page_config(
    page_title="Portföy Destek Optimizasyonu",
    page_icon="🏦",
    layout="wide",
    menu_items={"Get Help": None, "Report a bug": None, "About": None},
)

st.markdown("""
<style>
    #MainMenu {visibility: hidden;}
    header [data-testid="stToolbar"] {visibility: hidden;}
    footer {visibility: hidden;}
</style>
""", unsafe_allow_html=True)

st.title("Portföy Destek Dağıtım Optimizasyonu")
st.caption("Talimat yönetim sistemi — portföy destek ataması optimizasyon aracı")

# ── 1. VERİ YÜKLEME ───────────────────────────────────────────────────────────
st.header("1. Veri Yükleme")

SHEET_NAMES_REQUIRED = ["Mevcut_Atama", "Portfoy_Is_Yuku", "Sicil_Hiz", "Portfoy_Aktif_Sicil", "Istisna"]
SHEET_NAMES_OPTIONAL = ["Havuzda_Bekleme"]
SHEET_NAMES = SHEET_NAMES_REQUIRED  # geriye dönük uyumluluk için
MIME_XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

mod = st.radio(
    "Yükleme modu",
    ["Tek Excel dosyası (.xlsx)", "Ayrı CSV dosyaları"],
    horizontal=True,
)

raw_sheets = None

if mod == "Tek Excel dosyası (.xlsx)":
    uploaded = st.file_uploader(
        "Excel dosyasını yükleyin",
        type=["xlsx"],
        help="Zorunlu sekmeler: Mevcut_Atama, Portfoy_Is_Yuku, Sicil_Hiz, Portfoy_Aktif_Sicil, Istisna | Opsiyonel: Havuzda_Bekleme",
    )
    if uploaded:
        try:
            xl = pd.ExcelFile(uploaded)
            missing = [s for s in SHEET_NAMES_REQUIRED if s not in xl.sheet_names]
            if missing:
                st.error(f"Eksik sekme(ler): {', '.join(missing)}")
            else:
                def _parse_sheet(xl, name):
                    df = xl.parse(name, header=0)
                    cols = [str(c) for c in df.columns]
                    first = cols[0] if cols else ""
                    if len(first) > 50 or not any(k in cols for k in ["Sicil", "Portfoy", "Gunluk"]):
                        df = xl.parse(name, header=1)
                    return df
                raw_sheets = {s: _parse_sheet(xl, s) for s in SHEET_NAMES_REQUIRED}
                for s in SHEET_NAMES_OPTIONAL:
                    if s in xl.sheet_names:
                        raw_sheets[s] = _parse_sheet(xl, s)
                opsiyonel_yuklendi = [s for s in SHEET_NAMES_OPTIONAL if s in raw_sheets]
                msg = "Dosya başarıyla yüklendi."
                if opsiyonel_yuklendi:
                    msg += f" Opsiyonel sekme(ler) de okundu: {', '.join(opsiyonel_yuklendi)}."
                st.success(msg)
        except Exception as e:
            st.error(f"Dosya okuma hatası: {e}")
else:
    st.info(f"Her tablo için ayrı bir CSV yükleyin. Zorunlu dosyalar: {', '.join(SHEET_NAMES_REQUIRED)} | Opsiyonel: {', '.join(SHEET_NAMES_OPTIONAL)}")
    csv_files = {}
    st.markdown("**Zorunlu tablolar**")
    cols = st.columns(3)
    for i, sn in enumerate(SHEET_NAMES_REQUIRED):
        with cols[i % 3]:
            f = st.file_uploader(f"{sn}.csv", type=["csv"], key=f"csv_{sn}")
            if f:
                csv_files[sn] = pd.read_csv(f)
    st.markdown("**Opsiyonel tablolar**")
    for sn in SHEET_NAMES_OPTIONAL:
        f = st.file_uploader(f"{sn}.csv (opsiyonel)", type=["csv"], key=f"csv_{sn}")
        if f:
            csv_files[sn] = pd.read_csv(f)
    if all(s in csv_files for s in SHEET_NAMES_REQUIRED):
        raw_sheets = csv_files
        st.success("Zorunlu CSV dosyaları başarıyla yüklendi.")
    elif csv_files:
        eksik = [s for s in SHEET_NAMES_REQUIRED if s not in csv_files]
        if eksik:
            st.warning(f"Eksik dosyalar: {', '.join(eksik)}")

# İndirme butonları — her zaman görünür
btn_col1, btn_col2 = st.columns(2)
try:
    with open(TEMPLATE_PATH, "rb") as f:
        btn_col1.download_button(
            "Boş Şablonu İndir",
            data=f.read(),
            file_name="portfoy_optimizasyon_sablon.xlsx",
            mime=MIME_XLSX,
            use_container_width=True,
            help="5 sekme, başlıklar ve kılavuz notlar dolu — kendi verinizle doldurun",
        )
except FileNotFoundError:
    pass

try:
    with open(SAMPLE_PATH, "rb") as f:
        btn_col2.download_button(
            "Doldurulmuş Örnek Veriyi İndir",
            data=f.read(),
            file_name="ornek_portfoy_verisi.xlsx",
            mime=MIME_XLSX,
            use_container_width=True,
            help="20 sicil, 15 iç + 2 dış portföy ile dolu örnek — uygulamayı test etmek için",
        )
except FileNotFoundError:
    pass

if raw_sheets is None:
    st.stop()

# ── VERİ KONTROL RAPORU ───────────────────────────────────────────────────────
try:
    data_check, uyari_check, hata_check = data_loader.load(raw_sheets, sure_tipi="Medyan", tolerans_pct=0,
                                                            saatlik_mola_dk=5, ogle_arasi_dk=45)
except Exception as e:
    st.error(f"Veri doğrulama hatası: {e}")
    st.stop()

st.subheader("Veri Kontrol Raporu")

if hata_check:
    st.error("**Kritik Hatalar — Optimizasyon çalıştırılamaz:**")
    for h in hata_check:
        st.error(f"• {h}")
    st.stop()

c1, c2, c3, c4 = st.columns(4)
c1.metric("Toplam Sicil", len(data_check["tum_siciller"]))
c2.metric("İç Portföy", len(data_check["ic_portfoyler"]))
c3.metric("GECİCİ Portföy", len(data_check["gecici_portfoyler"]))
c4.metric("İstisna Çifti", len(data_check["istisna_set"]))

if uyari_check:
    with st.expander(f"⚠️ {len(uyari_check)} uyarı var — detaylar için tıklayın"):
        for u in uyari_check:
            st.warning(f"• {u}")
else:
    st.success("Veri doğrulaması tamamlandı, hata bulunamadı.")

# ── 2. OPTİMİZASYON PARAMETRELERİ ────────────────────────────────────────────
st.header("2. Optimizasyon Parametreleri")

with st.expander("Optimizasyon nasıl çalışır? Parametreler ne anlama gelir?", expanded=False):
    st.markdown("""
### Genel Mantık

Model iki aşamalı çalışır:

**1. ANA Katmanı** — ANA atamaları sabit tutuluyorsa Mevcut_Atama tablosundaki ANA atamaları doğrudan alınır.
Serbest bırakılırsa MILP ile her sicile tam 1 ANA portföy atanır; portföy kapsama oranı maksimize edilir.

**2. DESTEK Katmanı** — Her portföy için hangi ek sicillerin DESTEK vereceği optimize edilir.
Hedef: portföy taleplerini karşılama oranını maksimize ederken hızlı/yavaş sicilleri portföylere dengeli dağıtmak.

---

### Parametreler

| Parametre | Ne yapar |
|---|---|
| **Süre Tipi** | Talep hesabında ortalama mı medyan mı kullanılsın. Medyan aykırı değerleri eler. |
| **ANA sabit tut** | Açıksa mevcut ANA atamaları değişmez; kapalıysa ANA da yeniden optimize edilir. |
| **Hız dengeleme ağırlığı** | 0 = yalnızca kapasite karşılama, 1 = yalnızca hız dengesi. |
| **Min. DESTEK sicil** | Her portföye en az kaç DESTEK sicil atansın. |
| **Maks. DESTEK sicil** | Her portföye en fazla kaç DESTEK sicil atansın. |
| **Maks. DESTEK portföy** | Bir sicil en fazla kaç portföye DESTEK verebilir. |
    """)

col_srt, col_tol, col_mola, col_ogle = st.columns(4)
sure_tipi = col_srt.selectbox(
    "Süre Tipi",
    ["Medyan", "Ortalama"],
    help="Talep ve hız hesabında kullanılacak istatistik. Medyan aykırı değerlere karşı daha sağlamdır.",
)
tolerans_pct = col_tol.number_input(
    "Talep Toleransı (%)",
    min_value=0, max_value=50, value=10, step=5,
    help="Hesaplanan talep bu oran kadar yukarı yuvarlanır. Referans sayısı veya aktif sicil sayısındaki dalgalanmalara karşı tampon sağlar.",
)
saatlik_mola_dk = col_mola.number_input(
    "Saatlik Mola (dk)",
    min_value=0, max_value=15, value=5, step=1,
    help="Saat başına düşen ortalama mola süresi. 9 saatlik çalışmada toplam mola = 9 × bu değer.",
)
ogle_arasi_dk = col_ogle.number_input(
    "Öğle Arası (dk)",
    min_value=0, max_value=90, value=45, step=5,
    help="Günlük öğle molası süresi. Kapasiteden sabit olarak düşülür.",
)

with st.expander("Gelişmiş Ayarlar (opsiyonel)", expanded=False):
    ana_sabit = st.checkbox(
        "ANA atamaları sabit tut",
        value=True,
        help="Kapalıysa ANA atamaları da yeniden optimize edilir.",
    )
    ana_tercih_agirligi = st.slider(
        "Mevcut ANA tercih ağırlığı",
        0.0, 1.0, 0.7, 0.05,
        disabled=ana_sabit,
        help="Yalnızca 'ANA atamaları sabit tut' kapalıyken aktif olur. "
             "0 = tamamen serbest dağıtım, 1 = mevcut atamaları mümkün olduğunca koru.",
    )
    hiz_agirlik = st.slider(
        "Hız dengeleme ağırlığı",
        0.0, 1.0, 0.5, 0.05,
        help="0 = yalnızca kapasite karşılama, 1 = yalnızca hız dengesi",
    )
    col_b, col_c = st.columns(2)
    max_destek = col_b.number_input("Portföy başına maks. DESTEK sicil", 1, 50, 10)
    max_portfoy = col_c.number_input("Sicil başına maks. DESTEK portföy", 1, 20, 5)
    min_destek = 0

st.caption("Gelişmiş ayarlar varsayılan değerleriyle kullanılacaktır. Değiştirmek isterseniz genişletin.")
submitted = st.button("Optimize Et", type="primary", use_container_width=True)

# ── 3. OPTİMİZASYON & SONUÇLAR ───────────────────────────────────────────────
if submitted:
    with st.spinner("Veri hazırlanıyor..."):
        try:
            data, uyarilar, hatalar = data_loader.load(raw_sheets, sure_tipi=sure_tipi, tolerans_pct=tolerans_pct,
                                                        saatlik_mola_dk=saatlik_mola_dk, ogle_arasi_dk=ogle_arasi_dk)
        except Exception as e:
            st.error(f"Veri yükleme hatası: {e}")
            st.stop()

    if hatalar:
        for h in hatalar:
            st.error(h)
        st.stop()

    with st.spinner("Optimizasyon çalışıyor, lütfen bekleyin..."):
        try:
            sonuc = optimizer.optimize(
                data,
                ana_sabit=ana_sabit,
                ana_tercih_agirligi=ana_tercih_agirligi,
                hiz_agirlik=hiz_agirlik,
                min_destek_sicil=min_destek,
                max_destek_sicil=max_destek,
                max_destek_portfoy=max_portfoy,
            )
        except Exception as e:
            st.error(f"Optimizasyon hatası: {e}")
            st.stop()

    st.session_state["sonuc"] = sonuc
    st.session_state["data"] = data
    st.session_state["uyarilar_veri"] = uyarilar

if "sonuc" not in st.session_state:
    st.stop()

sonuc = st.session_state["sonuc"]
data = st.session_state["data"]
uyarilar_veri = st.session_state.get("uyarilar_veri", [])

st.success(
    f"Optimizasyon tamamlandı! "
    f"ANA atama: {len(sonuc['ana_atama'])} çift, "
    f"DESTEK atama: {len(sonuc['destek_atama'])} çift."
)

d_ana = sonuc["durum_ana"]
d_destek = sonuc["durum_destek"]
if "Optimal" not in d_destek and "kullanıldı" not in d_destek:
    st.warning(f"DESTEK katmanı: {d_destek} — parametreleri kontrol edin.")

tum_uyarilar = uyarilar_veri + sonuc.get("uyarilar", [])
if tum_uyarilar:
    with st.expander(f"⚠️ {len(tum_uyarilar)} uyarı", expanded=False):
        for u in tum_uyarilar:
            st.warning(f"• {u}")

# ── SONUÇ SEKMELERİ ───────────────────────────────────────────────────────────
tab1, tab2, tab3, tab4, tab5 = st.tabs(["Portföy Özet", "Sicil Özet", "Atama Matrisi", "Karşılaştırma", "Veri Uyarıları"])

ana_atama = sonuc["ana_atama"]
destek_atama = sonuc["destek_atama"]
demand = sonuc["demand"]
ana_kapasite = sonuc["ana_kapasite"]
destek_kapasite = sonuc["destek_kapasite"]
coverage = sonuc["coverage"]
ic_pf = data["ic_portfoyler"]
gecici_pf = data["gecici_portfoyler"]
tum_pf = ic_pf + gecici_pf
tum_siciller = data["tum_siciller"]
speed_raw = data["speed_raw"]

pf_ana = {pf: [] for pf in ic_pf}
for s, pf in ana_atama.items():
    if pf in pf_ana:
        pf_ana[pf].append(s)
pf_destek = {pf: [] for pf in ic_pf}
for s, pf in destek_atama:
    pf_destek[pf].append(s)

with tab1:
    st.subheader("Portföy Bazlı Özet")
    rows = []
    for pf in ic_pf:
        all_s = pf_ana.get(pf, []) + pf_destek.get(pf, [])
        ort_hiz = sum(speed_raw.get(s, 0) for s in all_s) / len(all_s) if all_s else 0
        cov = coverage.get(pf, 0.0)
        rows.append({
            "Portföy": pf,
            "Günlük Talep (sn)": round(demand.get(pf, 0)),
            "ANA Sicil": len(pf_ana.get(pf, [])),
            "DESTEK Sicil": len(pf_destek.get(pf, [])),
            "Toplam Kapasite (sn)": round(ana_kapasite.get(pf, 0) + destek_kapasite.get(pf, 0)),
            "Karşılama Oranı (%)": round(cov * 100, 1),
            "Ort. Hız Skoru (sn)": round(ort_hiz),
        })
    df1 = pd.DataFrame(rows)

    def _renk_satir(row):
        oran = row["Karşılama Oranı (%)"]
        if oran < 50:
            return ["background-color: #FFC7CE"] * len(row)
        elif oran < 80:
            return ["background-color: #FFEB9C"] * len(row)
        return [""] * len(row)

    st.dataframe(
        df1.style.apply(_renk_satir, axis=1),
        use_container_width=True,
        hide_index=True,
    )
    st.caption("🔴 < %50 | 🟡 %50–80 | ⬜ > %80 karşılama oranı")
    st.bar_chart(df1.set_index("Portföy")["Karşılama Oranı (%)"], use_container_width=True)

with tab2:
    st.subheader("Sicil Bazlı Özet")
    gecici_per_sicil = {}
    for g in data["gecici_mevcut"]:
        pf = g["portfoy"]
        lst = gecici_per_sicil.setdefault(g["sicil"], [])
        if pf not in lst:
            lst.append(pf)

    rows2 = []
    for s in tum_siciller:
        dest_list = sorted([pf for (ss, pf) in destek_atama if ss == s])
        gecici_list = gecici_per_sicil.get(s, [])
        rows2.append({
            "Sicil": s,
            "ANA Portföy": ana_atama.get(s, "—"),
            "DESTEK Portföyler": ", ".join(dest_list) if dest_list else "—",
            "DESTEK Sayısı": len(dest_list),
            "GECİCİ": ", ".join(gecici_list) if gecici_list else "—",
            "Kapasite (sn)": round(data["capacity"].get(s, 0)),
            "Hız Skoru (sn)": round(speed_raw.get(s, 0)),
        })
    st.dataframe(pd.DataFrame(rows2), use_container_width=True, hide_index=True)

with tab3:
    st.subheader("Atama Matrisi (Sicil × Portföy)")
    gecici_set_map = {(g["sicil"], g["portfoy"]) for g in data["gecici_mevcut"]}
    istisna_set = data["istisna_set"]

    matrix = {}
    for s in tum_siciller:
        row = {}
        for pf in tum_pf:
            if ana_atama.get(s) == pf:
                row[pf] = "ANA"
            elif (s, pf) in destek_atama:
                row[pf] = "DESTEK"
            elif (s, pf) in gecici_set_map:
                row[pf] = "GECİCİ"
            elif (s, pf) in istisna_set:
                row[pf] = "İSTİSNA"
            else:
                row[pf] = "—"
        matrix[s] = row

    df3 = pd.DataFrame(matrix).T
    df3.index.name = "Sicil"

    def _matris_renk(val):
        if val == "ANA":
            return "background-color: #C6EFCE; font-weight: bold"
        elif val == "DESTEK":
            return "background-color: #FFEB9C"
        elif val == "GECİCİ":
            return "background-color: #FCE4D6"
        elif val == "İSTİSNA":
            return "background-color: #EDEDED; color: #999999"
        return "color: #CCCCCC"

    st.dataframe(
        df3.style.map(_matris_renk, subset=tum_pf),
        use_container_width=True,
    )

with tab4:
    st.subheader("Eski / Yeni Yetki Karşılaştırması")
    mevcut_ana = data.get("ana_atama_mevcut", {})
    ma_raw = data.get("mevcut_atama_raw", {})

    eski_destek_per_sicil = {s: set() for s in tum_siciller}
    for s in tum_siciller:
        for rol, pf in ma_raw.get(s, []):
            if rol == "DESTEK" and pf in ic_pf:
                eski_destek_per_sicil[s].add(pf)

    yeni_destek_per_sicil = {s: set() for s in tum_siciller}
    for s, pf in destek_atama:
        yeni_destek_per_sicil[s].add(pf)

    karsi_rows = []
    for s in tum_siciller:
        eski_ana = mevcut_ana.get(s, "—")
        yeni_ana = ana_atama.get(s, "—")
        eski_d = eski_destek_per_sicil[s]
        yeni_d = yeni_destek_per_sicil[s]
        eklenen = yeni_d - eski_d
        cikarilan = eski_d - yeni_d
        karsi_rows.append({
            "Sicil": s,
            "Eski ANA": eski_ana,
            "Yeni ANA": yeni_ana,
            "ANA Değişti?": "✓ EVET" if eski_ana != yeni_ana else "hayır",
            "Eski DESTEK": ", ".join(sorted(eski_d)) if eski_d else "—",
            "Yeni DESTEK": ", ".join(sorted(yeni_d)) if yeni_d else "—",
            "Eklenen DESTEK": ", ".join(sorted(eklenen)) if eklenen else "—",
            "Çıkarılan DESTEK": ", ".join(sorted(cikarilan)) if cikarilan else "—",
        })

    df_karsi = pd.DataFrame(karsi_rows)

    def _renk_karsi(row):
        renkler = [""] * len(row.index)
        idx = list(row.index)
        if row["ANA Değişti?"].startswith("✓"):
            for col in ["Eski ANA", "Yeni ANA", "ANA Değişti?"]:
                renkler[idx.index(col)] = "background-color: #FFE699"
        if row["Eklenen DESTEK"] != "—":
            renkler[idx.index("Eklenen DESTEK")] = "background-color: #C6EFCE"
        if row["Çıkarılan DESTEK"] != "—":
            renkler[idx.index("Çıkarılan DESTEK")] = "background-color: #FFC7CE"
        return renkler

    st.dataframe(
        df_karsi.style.apply(_renk_karsi, axis=1),
        use_container_width=True,
        hide_index=True,
    )
    degisen_ana = sum(1 for r in karsi_rows if r["ANA Değişti?"].startswith("✓"))
    eklenen_destek = sum(1 for r in karsi_rows if r["Eklenen DESTEK"] != "—")
    cikarilan_destek = sum(1 for r in karsi_rows if r["Çıkarılan DESTEK"] != "—")
    st.caption(
        f"ANA değişen: **{degisen_ana}** sicil  |  "
        f"DESTEK eklenen: **{eklenen_destek}** sicil  |  "
        f"DESTEK çıkarılan: **{cikarilan_destek}** sicil"
    )

with tab5:
    st.subheader("Veri Uyarıları")
    if tum_uyarilar:
        for i, u in enumerate(tum_uyarilar, 1):
            st.warning(f"{i}. {u}")
    else:
        st.success("Herhangi bir uyarı bulunmuyor.")

# ── EXCEL İNDİR ───────────────────────────────────────────────────────────────
st.divider()
try:
    excel_bytes = excel_export.export(sonuc, data)
    dosya_adi = f"Portfoy_Destek_Atama_{date.today().strftime('%Y%m%d')}.xlsx"
    st.download_button(
        label="Excel İndir",
        data=excel_bytes,
        file_name=dosya_adi,
        mime=MIME_XLSX,
        type="primary",
        use_container_width=True,
    )
except Exception as e:
    st.error(f"Excel oluşturma hatası: {e}")
