import streamlit as st
import pandas as pd
import os
from create_sim_template import create_sim_template
from create_sim_sample import create_sim_samples

st.set_page_config(
    page_title="Simülasyon Analizi",
    page_icon="📊",
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

SIM_TEMPLATE_PATH = "sample_data/simulasyon_sablon.xlsx"
SIM_ONCE_PATH = "sample_data/simulasyon_once.xlsx"
SIM_SONRA_PATH = "sample_data/simulasyon_sonra.xlsx"
MIME_XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
SHEETS_REQUIRED = ["Atama", "Sicil_Hiz_Gun", "Portfoy_Is_Yuku_Gun"]
SHEETS_OPTIONAL = ["Havuzda_Bekleme"]

@st.cache_resource
def _init_sim_files():
    os.makedirs("sample_data", exist_ok=True)
    create_sim_samples("sample_data")

_init_sim_files()
create_sim_template(SIM_TEMPLATE_PATH)  # her zaman güncel şablon

st.title("Simülasyon Analizi")
st.caption("Optimizasyon öncesi ve sonrası gerçek performansı karşılaştır")

with st.expander("Nasıl kullanılır?", expanded=False):
    st.markdown("""
**Akış:**
1. Optimizasyon uygulanmadan önceki gün verisini **Önce** dosyasına doldur
2. Optimizasyon uygulandıktan sonraki gün verisini **Sonra** dosyasına doldur
3. Her iki dosyayı yükle → KPI karşılaştırması otomatik çıkar

**Her dosyada doldurulacak sheetler:**
- `Atama` — o günkü aktif atamalar (sisteminizden çekin)
- `Sicil_Hiz_Gun` — o gün sicil başına portföy bazında gerçek çalışma süresi ve ref adedi
- `Portfoy_Is_Yuku_Gun` — o gün portföy bazında toplam gelen ref
- `Havuzda_Bekleme` — saatlik bekleme verisi (opsiyonel, ilk temas süresi için)
    """)

btn1, btn2, btn3 = st.columns(3)
try:
    with open(SIM_TEMPLATE_PATH, "rb") as f:
        btn1.download_button(
            "Boş Şablonu İndir",
            data=f.read(),
            file_name="simulasyon_sablon.xlsx",
            mime=MIME_XLSX,
            help="Önce ve Sonra dosyaları için aynı şablonu kullanın",
        )
except FileNotFoundError:
    pass

try:
    with open(SIM_ONCE_PATH, "rb") as f:
        btn2.download_button(
            "Örnek: Önce Verisi",
            data=f.read(),
            file_name="simulasyon_once.xlsx",
            mime=MIME_XLSX,
            help="Optimizasyon öncesi gün — dağınık atamalar, düşük karşılama",
        )
except FileNotFoundError:
    pass

try:
    with open(SIM_SONRA_PATH, "rb") as f:
        btn3.download_button(
            "Örnek: Sonra Verisi",
            data=f.read(),
            file_name="simulasyon_sonra.xlsx",
            mime=MIME_XLSX,
            help="Optimizasyon sonrası gün — daha iyi atamalar, bazı siciller ek yetki eklemiş",
        )
except FileNotFoundError:
    pass

st.divider()


def _parse(xl, name):
    df = xl.parse(name, header=0)
    cols = [str(c) for c in df.columns]
    first = cols[0] if cols else ""
    if len(first) > 40:
        df = xl.parse(name, header=1)
    return df


def _load_sim_file(uploaded, etiket: str):
    if uploaded is None:
        return None
    try:
        xl = pd.ExcelFile(uploaded)
        missing = [s for s in SHEETS_REQUIRED if s not in xl.sheet_names]
        if missing:
            st.error(f"{etiket}: Eksik sekme(ler): {', '.join(missing)}")
            return None
        sheets = {s: _parse(xl, s) for s in SHEETS_REQUIRED}
        for s in SHEETS_OPTIONAL:
            if s in xl.sheet_names:
                sheets[s] = _parse(xl, s)
        st.success(f"{etiket} yüklendi.")
        return sheets
    except Exception as e:
        st.error(f"{etiket} okuma hatası: {e}")
        return None


col_once, col_sonra = st.columns(2)
with col_once:
    st.subheader("Önce (Mevcut Atama)")
    f_once = st.file_uploader("Optimizasyon öncesi gün verisi", type=["xlsx"], key="once")
    once = _load_sim_file(f_once, "Önce")

with col_sonra:
    st.subheader("Sonra (Optimizasyon Uygulandı)")
    f_sonra = st.file_uploader("Optimizasyon sonrası gün verisi", type=["xlsx"], key="sonra")
    sonra = _load_sim_file(f_sonra, "Sonra")

if once is None or sonra is None:
    st.stop()


# ── ANALİZ FONKSİYONLARI ─────────────────────────────────────────────────────

def _cs(s):
    return str(s).strip() if pd.notna(s) else ""


def _hesapla_kpi(sheets: dict) -> dict:
    atama = sheets["Atama"].copy()
    atama.columns = [str(c).strip() for c in atama.columns]
    atama["Sicil"] = atama["Sicil"].apply(_cs)
    atama["Portfoy"] = atama["Portfoy"].apply(_cs)
    atama["Portfoy Seviyesi"] = atama["Portfoy Seviyesi"].apply(_cs)
    atama = atama[atama["Sicil"] != ""]

    hiz = sheets["Sicil_Hiz_Gun"].copy()
    hiz.columns = [str(c).strip() for c in hiz.columns]
    hiz["Portfoy"] = hiz["Portfoy"].apply(_cs)
    hiz["Sicil"] = hiz["Sicil"].apply(_cs)
    hiz["Calisma_Suresi_Sn"] = pd.to_numeric(hiz["Calisma_Suresi_Sn"], errors="coerce").fillna(0)
    hiz["Referans_Adedi"] = pd.to_numeric(hiz["Referans_Adedi"], errors="coerce").fillna(0)

    piy = sheets["Portfoy_Is_Yuku_Gun"].copy()
    piy.columns = [str(c).strip() for c in piy.columns]
    piy["Portfoy"] = piy["Portfoy"].apply(_cs)
    piy["Gelen_Ref"] = pd.to_numeric(piy["Gelen_Ref"], errors="coerce").fillna(0)
    gelen_ref = dict(zip(piy["Portfoy"], piy["Gelen_Ref"]))

    # Portföy başına atanan siciller (ANA + DESTEK)
    ic_atamalik = atama[atama["Portfoy Seviyesi"].isin(["ANA", "DESTEK"])]
    pf_siciller: dict[str, list] = {}
    for _, row in ic_atamalik.iterrows():
        pf_siciller.setdefault(row["Portfoy"], []).append(row["Sicil"])

    # Sicil bazında toplam çalışma süresi (tüm portföylerin toplamı)
    sicil_toplam = hiz.groupby("Sicil")["Calisma_Suresi_Sn"].sum().to_dict()

    # Portföy başına gerçek kapasite: o portföyde çalışan sicillerin toplam süresi
    pf_kapasite: dict[str, float] = {}
    for pf, siciller in pf_siciller.items():
        pf_hiz = hiz[(hiz["Portfoy"] == pf) & (hiz["Sicil"].isin(siciller))]
        pf_kapasite[pf] = float(pf_hiz["Calisma_Suresi_Sn"].sum())

    # Portföy başına talep: gelen_ref × o portföydeki ort. ref süresi
    pf_ref_sure: dict[str, float] = {}
    for pf in pf_siciller:
        pf_hiz = hiz[hiz["Portfoy"] == pf]
        toplam_cal = pf_hiz["Calisma_Suresi_Sn"].sum()
        toplam_ref = pf_hiz["Referans_Adedi"].sum()
        pf_ref_sure[pf] = toplam_cal / toplam_ref if toplam_ref > 0 else 0.0

    global_ref_sure = (
        hiz["Calisma_Suresi_Sn"].sum() / hiz["Referans_Adedi"].sum()
        if hiz["Referans_Adedi"].sum() > 0 else 0.0
    )

    pf_talep: dict[str, float] = {}
    for pf in pf_siciller:
        ref = gelen_ref.get(pf, 0.0)
        sure = pf_ref_sure.get(pf) or global_ref_sure
        pf_talep[pf] = ref * sure

    # Karşılama oranı
    pf_karsilama: dict[str, float] = {}
    for pf in pf_siciller:
        talep = pf_talep.get(pf, 0.0)
        kap = pf_kapasite.get(pf, 0.0)
        pf_karsilama[pf] = kap / talep if talep > 0 else 0.0

    # Sicil yük dağılımı (std sapma — düşük = dengeli)
    sicil_sure_list = list(sicil_toplam.values())
    yuk_std = pd.Series(sicil_sure_list).std() if len(sicil_sure_list) > 1 else 0.0

    # Havuzda_Bekleme — ilk temas ve bekleyen oran
    pf_ilk_temas: dict[str, float] = {}
    pf_bekleme_oran: dict[str, float] = {}
    if "Havuzda_Bekleme" in sheets:
        hb = sheets["Havuzda_Bekleme"].copy()
        hb.columns = [str(c).strip() for c in hb.columns]
        if "Portfoy" in hb.columns and "Gelen_Ref" in hb.columns:
            hb["Portfoy"] = hb["Portfoy"].apply(_cs)
            hb["Gelen_Ref"] = pd.to_numeric(hb["Gelen_Ref"], errors="coerce").fillna(0)
            if "Ort_Ilk_Temas_Sn" in hb.columns:
                hb["Ort_Ilk_Temas_Sn"] = pd.to_numeric(hb["Ort_Ilk_Temas_Sn"], errors="coerce").fillna(0)
                grp = hb[hb["Gelen_Ref"] > 0].groupby("Portfoy")
                for pf, g in grp:
                    toplam = g["Gelen_Ref"].sum()
                    ag_ort = (g["Ort_Ilk_Temas_Sn"] * g["Gelen_Ref"]).sum() / toplam if toplam > 0 else 0
                    pf_ilk_temas[pf] = ag_ort
            if "Ayni_Saatte_Baslanan" in hb.columns:
                hb["Ayni_Saatte_Baslanan"] = pd.to_numeric(hb["Ayni_Saatte_Baslanan"], errors="coerce").fillna(0)
                grp2 = hb[hb["Gelen_Ref"] > 0].groupby("Portfoy").agg(
                    toplam_gelen=("Gelen_Ref", "sum"),
                    toplam_baslanan=("Ayni_Saatte_Baslanan", "sum"),
                ).reset_index()
                for _, row in grp2.iterrows():
                    pf = row["Portfoy"]
                    oran = (row["toplam_gelen"] - row["toplam_baslanan"]) / row["toplam_gelen"]
                    pf_bekleme_oran[pf] = max(0.0, oran)

    # Sicil bazında portföy kırılımı (hangi portföyde ne kadar çalışmış)
    sicil_pf_sure: dict[str, dict[str, float]] = {}
    for _, row in hiz.iterrows():
        s, pf2 = row["Sicil"], row["Portfoy"]
        if s and pf2:
            sicil_pf_sure.setdefault(s, {})[pf2] = float(row["Calisma_Suresi_Sn"])

    # Planlı siciller (Atama'da ANA/DESTEK olanlar)
    planli_siciller = set(
        atama.loc[atama["Portfoy Seviyesi"].isin(["ANA", "DESTEK"]), "Sicil"]
    )
    # Atama'da olmayan ama Sicil_Hiz_Gun'da görünen siciller = plansız katkı
    gercek_siciller = set(hiz["Sicil"].unique())
    plansiz_siciller = gercek_siciller - planli_siciller

    return {
        "pf_siciller": pf_siciller,
        "pf_kapasite": pf_kapasite,
        "pf_talep": pf_talep,
        "pf_karsilama": pf_karsilama,
        "gelen_ref": gelen_ref,
        "sicil_toplam": sicil_toplam,
        "sicil_pf_sure": sicil_pf_sure,
        "planli_siciller": planli_siciller,
        "plansiz_siciller": plansiz_siciller,
        "yuk_std": yuk_std,
        "pf_ilk_temas": pf_ilk_temas,
        "pf_bekleme_oran": pf_bekleme_oran,
    }


once_kpi = _hesapla_kpi(once)
sonra_kpi = _hesapla_kpi(sonra)

tum_pf = sorted(set(once_kpi["pf_siciller"]) | set(sonra_kpi["pf_siciller"]))

# ── OKUMA KILAVUZU ────────────────────────────────────────────────────────────
with st.expander("Metrikler nasıl okunur?", expanded=False):
    st.markdown("""
**pp (yüzde puanı):** İki yüzde değerinin farkı. Örneğin karşılama %49 → %70 ise fark **+21pp**'dir.
Yüzde değil, yüzde puan — %49'un %21 artışı değil, 21 puan artışıdır.

---

| Metrik | Ne anlama gelir | İyi yön |
|--------|----------------|---------|
| **Ort. Karşılama Oranı** | Portföylerin günlük talebinin kaçta kaçı karşılandı. %100 = talep tam karşılandı, >%100 = fazla kapasite var, <%100 = açık var. | ↑ Yüksek |
| **Yük Dengesi (Std Sapma)** | Siciller arasındaki çalışma süresi farkı. Düşük = herkes benzer süre çalışmış, yük dengeli dağılmış. | ↓ Düşük |
| **Ort. İlk Temas (sn)** | Bir referansın havuza düştükten sonra ilk işleme alınma süresi. | ↓ Düşük |
| **Ort. Bekleyen Ref Oranı** | Gelen referansların aynı saatte işleme alınamayan kısmı. %0 = hepsi anında işleme alındı. | ↓ Düşük |

---

**Değerlendirme kutucukları:**
- 🟢 **İyileşen:** Önce → Sonra karşılama oranı **+5pp'den fazla** arttı
- 🔴 **Kötüleşen:** Karşılama oranı **-5pp'den fazla** düştü — o portföyde sonra günü daha az sicil kalmış olabilir
- ⬜ **Değişmeyen:** ±5pp içinde kaldı, anlamlı bir fark yok

**Karşılama oranı >%100 çıkıyorsa:** Siciller o portföyün talebinden fazla çalışmış demek — talep tahmini düşük kalmış ya da siciller ek işler de yapmış olabilir.
    """)

# ── ÖZET METRİKLER ────────────────────────────────────────────────────────────
st.header("Özet")

def _ort_karsilama(kpi):
    vals = [v for v in kpi["pf_karsilama"].values() if v > 0]
    return sum(vals) / len(vals) * 100 if vals else 0.0

def _ort_ilk_temas(kpi):
    vals = list(kpi["pf_ilk_temas"].values())
    return sum(vals) / len(vals) if vals else None

def _ort_bekleme(kpi):
    vals = list(kpi["pf_bekleme_oran"].values())
    return sum(vals) / len(vals) * 100 if vals else None

m1, m2, m3, m4 = st.columns(4)

once_ort = _ort_karsilama(once_kpi)
sonra_ort = _ort_karsilama(sonra_kpi)
m1.metric("Ort. Karşılama Oranı", f"%{sonra_ort:.1f}", f"{sonra_ort - once_ort:+.1f}pp",
          help="Önce → Sonra. Pozitif = iyileşme")

once_std = once_kpi["yuk_std"]
sonra_std = sonra_kpi["yuk_std"]
m2.metric("Yük Dengesi (Std Sapma)", f"{sonra_std/60:.0f} dk", f"{(sonra_std - once_std)/60:+.0f} dk",
          delta_color="inverse",
          help="Siciller arası çalışma süresi std sapması. Düşük = daha dengeli dağılım")

once_temas = _ort_ilk_temas(once_kpi)
sonra_temas = _ort_ilk_temas(sonra_kpi)
if once_temas is not None and sonra_temas is not None:
    m3.metric("Ort. İlk Temas (sn)", f"{sonra_temas:.0f}",
              f"{sonra_temas - once_temas:+.0f} sn", delta_color="inverse",
              help="Havuzda_Bekleme'den. Düşük = daha hızlı ilk temas")
else:
    m3.metric("Ort. İlk Temas (sn)", "—", help="Havuzda_Bekleme sheetiyle hesaplanır")

once_bk = _ort_bekleme(once_kpi)
sonra_bk = _ort_bekleme(sonra_kpi)
if once_bk is not None and sonra_bk is not None:
    m4.metric("Ort. Bekleyen Ref Oranı", f"%{sonra_bk:.1f}",
              f"{sonra_bk - once_bk:+.1f}pp", delta_color="inverse",
              help="(Gelen - Aynı Saatte Başlanan) / Gelen. Düşük = daha az bekleme")
else:
    m4.metric("Ort. Bekleyen Ref Oranı", "—", help="Havuzda_Bekleme sheetiyle hesaplanır")

# ── YORUM ─────────────────────────────────────────────────────────────────────
st.divider()
st.header("Değerlendirme")

ESIK_PP = 5.0  # karşılama oranında anlamlı fark eşiği

iyilesen = []
kotuleen = []
degismeyen = []

for pf in tum_pf:
    o = once_kpi["pf_karsilama"].get(pf, 0.0) * 100
    s = sonra_kpi["pf_karsilama"].get(pf, 0.0) * 100
    delta = s - o
    if delta > ESIK_PP:
        iyilesen.append((pf, o, s, delta))
    elif delta < -ESIK_PP:
        kotuleen.append((pf, o, s, delta))
    else:
        degismeyen.append((pf, o, s, delta))

iyilesen.sort(key=lambda x: -x[3])
kotuleen.sort(key=lambda x: x[3])

col_iyi, col_kotu, col_ayni = st.columns(3)

with col_iyi:
    st.success(f"**İyileşen — {len(iyilesen)} portföy**")
    if iyilesen:
        for pf, o, s, d in iyilesen:
            st.markdown(f"- **{pf}**: %{o:.0f} → %{s:.0f} *(+{d:.0f}pp)*")
    else:
        st.markdown("—")

with col_kotu:
    st.error(f"**Kötüleşen — {len(kotuleen)} portföy**")
    if kotuleen:
        for pf, o, s, d in kotuleen:
            st.markdown(f"- **{pf}**: %{o:.0f} → %{s:.0f} *({d:.0f}pp)*")
    else:
        st.markdown("—")

with col_ayni:
    st.info(f"**Değişmeyen (±{ESIK_PP:.0f}pp) — {len(degismeyen)} portföy**")
    if degismeyen:
        for pf, o, s, d in degismeyen:
            isaret = f"+{d:.0f}" if d >= 0 else f"{d:.0f}"
            st.markdown(f"- **{pf}**: %{o:.0f} → %{s:.0f} *({isaret}pp)*")
    else:
        st.markdown("—")

# Havuzda_Bekleme yorumu
if once_temas is not None and sonra_temas is not None:
    st.divider()
    temas_delta = sonra_temas - once_temas
    bekleme_satirlari = []
    for pf in tum_pf:
        ot = once_kpi["pf_ilk_temas"].get(pf)
        st2 = sonra_kpi["pf_ilk_temas"].get(pf)
        if ot and st2:
            d = st2 - ot
            if d < -30:
                bekleme_satirlari.append(f"- **{pf}**: {ot:.0f}sn → {st2:.0f}sn *(−{abs(d):.0f}sn, hızlandı)*")
            elif d > 30:
                bekleme_satirlari.append(f"- **{pf}**: {ot:.0f}sn → {st2:.0f}sn *(+{d:.0f}sn, yavaşladı)*")
    if bekleme_satirlari:
        if temas_delta < 0:
            st.success(f"**İlk temas süresi ortalama {abs(temas_delta):.0f}sn kısaldı.** Belirgin değişen portföyler:")
        else:
            st.warning(f"**İlk temas süresi ortalama {temas_delta:.0f}sn uzadı.** Belirgin değişen portföyler:")
        for s in bekleme_satirlari:
            st.markdown(s)

# ── PORTFÖY DETAY TABLOSU ─────────────────────────────────────────────────────
st.divider()
st.header("Portföy Bazlı Karşılaştırma")

rows = []
for pf in tum_pf:
    o_kar = once_kpi["pf_karsilama"].get(pf, 0.0) * 100
    s_kar = sonra_kpi["pf_karsilama"].get(pf, 0.0) * 100
    o_sic = len(once_kpi["pf_siciller"].get(pf, []))
    s_sic = len(sonra_kpi["pf_siciller"].get(pf, []))
    o_ref = once_kpi["gelen_ref"].get(pf, 0)
    s_ref = sonra_kpi["gelen_ref"].get(pf, 0)
    o_temas = once_kpi["pf_ilk_temas"].get(pf)
    s_temas = sonra_kpi["pf_ilk_temas"].get(pf)
    o_bk = once_kpi["pf_bekleme_oran"].get(pf)
    s_bk = sonra_kpi["pf_bekleme_oran"].get(pf)

    row = {
        "Portföy": pf,
        "Önce Sicil": o_sic,
        "Sonra Sicil": s_sic,
        "Δ Sicil": s_sic - o_sic,
        "Önce Gelen Ref": int(o_ref),
        "Sonra Gelen Ref": int(s_ref),
        "Önce Karşılama %": round(o_kar, 1),
        "Sonra Karşılama %": round(s_kar, 1),
        "Δ Karşılama pp": round(s_kar - o_kar, 1),
    }
    if o_temas is not None or s_temas is not None:
        row["Önce İlk Temas sn"] = round(o_temas) if o_temas else "—"
        row["Sonra İlk Temas sn"] = round(s_temas) if s_temas else "—"
    if o_bk is not None or s_bk is not None:
        row["Önce Bekleme %"] = round(o_bk * 100, 1) if o_bk is not None else "—"
        row["Sonra Bekleme %"] = round(s_bk * 100, 1) if s_bk is not None else "—"
    rows.append(row)

df = pd.DataFrame(rows)

def _renk(row):
    renkler = [""] * len(row)
    idx = list(row.index)
    delta = row.get("Δ Karşılama pp", 0)
    if isinstance(delta, (int, float)):
        c = idx.index("Δ Karşılama pp")
        if delta > 5:
            renkler[c] = "background-color: #C6EFCE"
        elif delta < -5:
            renkler[c] = "background-color: #FFC7CE"
        else:
            renkler[c] = "background-color: #FFEB9C"
    for col in ["Önce Karşılama %", "Sonra Karşılama %"]:
        if col in idx:
            val = row.get(col, 0)
            if isinstance(val, (int, float)):
                c = idx.index(col)
                if val < 50:
                    renkler[c] = "background-color: #FFC7CE"
                elif val < 80:
                    renkler[c] = "background-color: #FFEB9C"
    return renkler

st.dataframe(
    df.style.apply(_renk, axis=1),
    use_container_width=True,
    hide_index=True,
)
st.caption("Δ Karşılama: 🟢 >+5pp iyileşme | 🟡 ±5pp | 🔴 >-5pp kötüleşme")

# ── KARŞILAMA ORANI GRAFİĞİ ───────────────────────────────────────────────────
st.divider()
st.subheader("Karşılama Oranı — Önce vs Sonra")
st.caption("Her portföy için önce (açık mavi) ve sonra (koyu mavi) değerleri yan yana gösterilir. %100 çizgisi = talep tam karşılandı.")

import altair as alt

karsilama_rows = []
for pf in tum_pf:
    karsilama_rows.append({"Portföy": pf, "Dönem": "Önce", "Karşılama (%)": round(once_kpi["pf_karsilama"].get(pf, 0) * 100, 1)})
    karsilama_rows.append({"Portföy": pf, "Dönem": "Sonra", "Karşılama (%)": round(sonra_kpi["pf_karsilama"].get(pf, 0) * 100, 1)})

karsilama_df = pd.DataFrame(karsilama_rows)

bars = alt.Chart(karsilama_df).mark_bar().encode(
    x=alt.X("Dönem:N", title=None, axis=alt.Axis(labelAngle=0)),
    y=alt.Y("Karşılama (%):Q", title="Karşılama Oranı (%)"),
    color=alt.Color("Dönem:N", scale=alt.Scale(domain=["Önce", "Sonra"], range=["#AED6F1", "#1A5276"])),
    column=alt.Column("Portföy:N", title=None, spacing=8),
    tooltip=["Portföy", "Dönem", "Karşılama (%)"],
).properties(width=55, height=300)

rule = alt.Chart(pd.DataFrame({"y": [100]})).mark_rule(color="red", strokeDash=[4, 4]).encode(y="y:Q")

st.altair_chart(bars + rule, use_container_width=False)

# ── SİCİL YÜK DAĞILIMI ────────────────────────────────────────────────────────
st.divider()
st.subheader("Sicil Bazlı Yük Dağılımı")
col_o, col_s = st.columns(2)

with col_o:
    st.markdown("**Önce**")
    sicil_df_once = pd.DataFrame([
        {"Sicil": s, "Toplam Çalışma (dk)": round(v / 60)}
        for s, v in sorted(once_kpi["sicil_toplam"].items())
    ])
    st.bar_chart(sicil_df_once.set_index("Sicil"), use_container_width=True)

with col_s:
    st.markdown("**Sonra**")
    sicil_df_sonra = pd.DataFrame([
        {"Sicil": s, "Toplam Çalışma (dk)": round(v / 60)}
        for s, v in sorted(sonra_kpi["sicil_toplam"].items())
    ])
    st.bar_chart(sicil_df_sonra.set_index("Sicil"), use_container_width=True)

# ── DÜŞÜK PERFORMANSLI SİCİL TESPİTİ ────────────────────────────────────────
st.divider()
st.header("Sicil Performans Analizi (Sonra Günü)")

sonra_sure = sonra_kpi["sicil_toplam"]
once_sure = once_kpi["sicil_toplam"]

if sonra_sure:
    medyan_sure = pd.Series(list(sonra_sure.values())).median()
    DUSUK_ESIK = 0.60   # medyanın %60'ından az = düşük performans
    DUSUS_ESIK = 0.30   # önceki güne göre %30'dan fazla düşüş = belirgin azalma

    sicil_rows = []
    for s in sorted(set(sonra_sure) | set(once_sure)):
        s_sure = sonra_sure.get(s, 0.0)
        o_sure = once_sure.get(s, 0.0)
        dusus = (s_sure - o_sure) / o_sure if o_sure > 0 else None
        planli = s in sonra_kpi["planli_siciller"]
        dusuk = s_sure < medyan_sure * DUSUK_ESIK
        belirgin_dusus = dusus is not None and dusus < -DUSUS_ESIK

        uyari = []
        if dusuk:
            uyari.append(f"medyan altı (%{s_sure/medyan_sure*100:.0f})")
        if belirgin_dusus:
            uyari.append(f"önceki güne göre %{abs(dusus)*100:.0f} düşüş")

        sicil_rows.append({
            "Sicil": s,
            "Planlı mı?": "Evet" if planli else "Hayır (İstisna/Plansız)",
            "Önce Çalışma (dk)": round(o_sure / 60) if o_sure else "—",
            "Sonra Çalışma (dk)": round(s_sure / 60),
            "Değişim": f"%{dusus*100:+.0f}" if dusus is not None else "—",
            "Uyarı": " | ".join(uyari) if uyari else "",
        })

    df_sicil = pd.DataFrame(sicil_rows)

    def _renk_sicil(row):
        renkler = [""] * len(row)
        idx = list(row.index)
        if row["Uyarı"]:
            renkler[idx.index("Sonra Çalışma (dk)")] = "background-color: #FFC7CE"
            renkler[idx.index("Uyarı")] = "background-color: #FFC7CE"
        if row["Planlı mı?"] != "Evet":
            renkler[idx.index("Planlı mı?")] = "background-color: #EDEDED; color: #888"
        return renkler

    st.dataframe(
        df_sicil.style.apply(_renk_sicil, axis=1),
        use_container_width=True,
        hide_index=True,
    )

    dusuk_sayisi = sum(1 for r in sicil_rows if r["Uyarı"])
    plansiz_sayisi = sum(1 for r in sicil_rows if r["Planlı mı?"] != "Evet")
    st.caption(
        f"Medyan çalışma süresi (sonra günü): **{medyan_sure/60:.0f} dk** | "
        f"Düşük performans uyarısı: **{dusuk_sayisi} sicil** | "
        f"Plansız katkı (istisna/atama dışı): **{plansiz_sayisi} sicil**"
    )

# ── OPTİMİZASYON DIŞI ÇALIŞMA ANALİZİ ───────────────────────────────────────
st.divider()
st.header("Optimizer Dışı Çalışma — Kendi Eklenen Yetkiler")
st.caption(
    "Optimizer'ın atamadığı portföylerde gerçekte çalışılmış olması, "
    "sicillerin ek yetki ekleyip o portföylere girdiğinin göstergesidir. "
    "Bu portföyler optimizer'ın yetersiz kapattığı alanlara işaret eder."
)

# Sonra günü: her sicil için atanan vs gerçekte çalışılan portföyler
sonra_atama = sonra["Atama"].copy()
sonra_atama.columns = [str(c).strip() for c in sonra_atama.columns]
sonra_atama["Sicil"] = sonra_atama["Sicil"].apply(_cs)
sonra_atama["Portfoy"] = sonra_atama["Portfoy"].apply(_cs)
sonra_atama["Portfoy Seviyesi"] = sonra_atama["Portfoy Seviyesi"].apply(_cs)

# Sicil → atanan portföyler seti
sicil_atanan: dict[str, set] = {}
for _, row in sonra_atama.iterrows():
    if row["Sicil"] and row["Portfoy Seviyesi"] in ("ANA", "DESTEK"):
        sicil_atanan.setdefault(row["Sicil"], set()).add(row["Portfoy"])

# Sicil → gerçekte çalışılan portföyler (Sicil_Hiz_Gun)
sicil_gercek = sonra_kpi["sicil_pf_sure"]  # {sicil: {portfoy: sure_sn}}

# Kendi eklenen: gerçekte çalışılmış ama atanmamış portföyler
disi_rows = []
pf_disi_katki: dict[str, float] = {}  # portföy bazında optimizer dışı toplam katki

for sicil, pf_sureler in sicil_gercek.items():
    atanan = sicil_atanan.get(sicil, set())
    for pf, sure in pf_sureler.items():
        if pf not in atanan and sure > 0:
            disi_rows.append({
                "Sicil": sicil,
                "Portföy": pf,
                "Atamada Var mı?": "Hayır",
                "Çalışma (dk)": round(sure / 60),
                "Not": "Ek yetki ile girilmiş olabilir",
            })
            pf_disi_katki[pf] = pf_disi_katki.get(pf, 0.0) + sure

if disi_rows:
    tab_sicil, tab_portfoy = st.tabs(["Sicil Bazlı", "Portföy Bazlı"])

    with tab_sicil:
        st.markdown("**Hangi sicil, optimizer'ın atamadığı portföylerde çalıştı?**")
        df_disi = pd.DataFrame(disi_rows).sort_values(["Sicil", "Çalışma (dk)"], ascending=[True, False])
        st.dataframe(df_disi, use_container_width=True, hide_index=True)
        st.caption(f"Toplam {len(set(r['Sicil'] for r in disi_rows))} sicil, "
                   f"{len(set(r['Portföy'] for r in disi_rows))} farklı portföyde optimizer dışı çalışmış.")

    with tab_portfoy:
        st.markdown("**Hangi portföyler en çok optimizer dışı katkı aldı? → Optimizer'ın yetersiz kapattığı alanlar**")
        pf_disi_rows = sorted(pf_disi_katki.items(), key=lambda x: -x[1])
        df_pf_disi = pd.DataFrame([
            {
                "Portföy": pf,
                "Optimizer Dışı Katkı (dk)": round(sure / 60),
                "Optimizer Dışı Katkı Yapan Sicil Sayısı": sum(
                    1 for r in disi_rows if r["Portföy"] == pf
                ),
                "Yorum": "Optimizer bu portföyü yeterince kapatamamış olabilir",
            }
            for pf, sure in pf_disi_rows
        ])

        def _renk_pf_disi(row):
            renkler = [""] * len(row)
            idx = list(row.index)
            katki = row["Optimizer Dışı Katkı (dk)"]
            if katki > 60:
                renkler[idx.index("Optimizer Dışı Katkı (dk)")] = "background-color: #FFC7CE"
                renkler[idx.index("Yorum")] = "background-color: #FFC7CE"
            elif katki > 20:
                renkler[idx.index("Optimizer Dışı Katkı (dk)")] = "background-color: #FFEB9C"
            return renkler

        st.dataframe(
            df_pf_disi.style.apply(_renk_pf_disi, axis=1),
            use_container_width=True,
            hide_index=True,
        )
        st.caption("🔴 >60dk optimizer dışı katkı — ciddi açık | 🟡 20-60dk — orta | ⬜ <20dk — düşük")
else:
    st.success("Tüm siciller yalnızca atandıkları portföylerde çalışmış — optimizer dışı yetki eklenmemiş.")
