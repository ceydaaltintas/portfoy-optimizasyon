from __future__ import annotations
import re
import pandas as pd

GUN_SAAT = 9          # 09:00–18:00
DESTEK_CONTRIB = 0.30


def gun_kapasite_sn(saatlik_mola_dk: int = 5, ogle_arasi_dk: int = 45) -> int:
    """Net günlük kapasite (saniye): molalar ve öğle arası düşülmüş."""
    brut_dk = GUN_SAAT * 60
    mola_dk = GUN_SAAT * saatlik_mola_dk
    return max(0, (brut_dk - mola_dk - ogle_arasi_dk) * 60)


def _parse_hhmm(val) -> int:
    if pd.isna(val) or str(val).strip() == "":
        return 0
    m = re.match(r"(\d+):(\d+)", str(val).strip())
    return int(m.group(1)) * 3600 + int(m.group(2)) * 60 if m else 0


def _col(df: pd.DataFrame, *candidates) -> str | None:
    for c in candidates:
        if c in df.columns:
            return c
    return None


def load(sheets: dict[str, pd.DataFrame], sure_tipi: str = "Medyan", tolerans_pct: float = 0.0,
         saatlik_mola_dk: int = 5, ogle_arasi_dk: int = 45) -> tuple[dict, list[str], list[str]]:
    uyarilar: list[str] = []
    hatalar: list[str] = []
    med = (sure_tipi == "Medyan")

    # ── Mevcut_Atama ─────────────────────────────────────────────────────────
    ma = sheets["Mevcut_Atama"].copy()
    ma.columns = [str(c).strip() for c in ma.columns]
    for req in ["Sicil", "Portfoy", "Portfoy Seviyesi"]:
        if req not in ma.columns:
            hatalar.append(f"Mevcut_Atama: '{req}' kolonu eksik.")
    if hatalar:
        return {}, uyarilar, hatalar

    ma["Sicil"] = ma["Sicil"].astype(str).str.strip()
    ma["Portfoy"] = ma["Portfoy"].astype(str).str.strip()
    ma["Portfoy Seviyesi"] = (
        ma["Portfoy Seviyesi"].astype(str).str.strip()
        .replace({"1": "ANA", "5": "DESTEK", "2": "GECİCİ"})
        .str.upper()
    )
    for c in ["Baslangic Zamani", "Bitis Zamani"]:
        if c not in ma.columns:
            ma[c] = ""

    tum_siciller = sorted(ma["Sicil"].unique().tolist())
    tum_portfoyler = sorted(ma["Portfoy"].unique().tolist())

    ana_df = ma[ma["Portfoy Seviyesi"] == "ANA"]
    gecici_df = ma[ma["Portfoy Seviyesi"] == "GECİCİ"]
    gecici_pf = sorted(gecici_df["Portfoy"].unique().tolist())
    ic_pf = [p for p in tum_portfoyler if p not in gecici_pf]

    ana_per_sicil = ana_df.groupby("Sicil")["Portfoy"].count()
    for s, cnt in ana_per_sicil.items():
        if cnt > 1:
            uyarilar.append(f"Sicil {s}: {cnt} ANA portföyü var (beklenen: 1).")
    for s in tum_siciller:
        if s not in ana_per_sicil.index:
            hatalar.append(f"Sicil {s}: ANA portföyü tanımlanmamış.")

    destek_df = ma[ma["Portfoy Seviyesi"] == "DESTEK"]
    ana_set_all = set(zip(ana_df["Sicil"], ana_df["Portfoy"]))
    for _, row in destek_df.iterrows():
        if (row["Sicil"], row["Portfoy"]) in ana_set_all:
            hatalar.append(f"Sicil {row['Sicil']}: ANA portföyü ({row['Portfoy']}) aynı zamanda DESTEK.")

    if hatalar:
        return {}, uyarilar, hatalar

    # GEÇİCİ bloklar → kapasite
    gecici_blok: dict[str, int] = {}
    for _, row in gecici_df.iterrows():
        s = row["Sicil"]
        blok = _parse_hhmm(row["Bitis Zamani"]) - _parse_hhmm(row["Baslangic Zamani"])
        gecici_blok[s] = gecici_blok.get(s, 0) + max(0, blok)

    GUN_SN = gun_kapasite_sn(saatlik_mola_dk, ogle_arasi_dk)
    capacity: dict[str, float] = {s: float(GUN_SN - gecici_blok.get(s, 0)) for s in tum_siciller}

    ana_atama_mevcut: dict[str, str] = {}
    for _, row in ana_df.iterrows():
        ana_atama_mevcut[row["Sicil"]] = row["Portfoy"]

    # Eski DESTEK listesi (karşılaştırma sayfası için)
    mevcut_atama_raw: dict[str, list] = {s: [] for s in tum_siciller}
    for _, row in ma.iterrows():
        s, pf, rol = row["Sicil"], row["Portfoy"], row["Portfoy Seviyesi"]
        mevcut_atama_raw[s].append((rol, pf))

    gecici_mevcut = [
        {"sicil": r["Sicil"], "portfoy": r["Portfoy"],
         "bas": r.get("Baslangic Zamani", ""), "bit": r.get("Bitis Zamani", "")}
        for _, r in gecici_df.iterrows()
    ]

    # ── İstisna ───────────────────────────────────────────────────────────────
    ist = sheets["Istisna"].copy()
    istisna_set: set[tuple] = set()
    istisna_sicil: set[str] = set()
    if not ist.empty and "Sicil" in ist.columns:
        ist["Sicil"] = ist["Sicil"].astype(str).str.strip()
        if "Portfoy" in ist.columns:
            ist["Portfoy"] = ist["Portfoy"].astype(str).str.strip()
            for _, row in ist.iterrows():
                pf = row["Portfoy"]
                s = row["Sicil"]
                if pf in ("", "nan", "None"):
                    # Portföy boşsa sicili tamamen dışla
                    istisna_sicil.add(s)
                else:
                    istisna_set.add((s, pf))
                    if pf not in tum_portfoyler:
                        uyarilar.append(f"İstisna: Portföy '{pf}' Mevcut_Atama'da yok.")
        else:
            # Sadece Sicil kolonu varsa tüm satırlar sicil istisnası
            for s in ist["Sicil"].unique():
                istisna_sicil.add(s)

    if istisna_sicil:
        uyarilar.append(f"Optimizasyondan dışlanan siciller: {', '.join(sorted(istisna_sicil))}")
        tum_siciller = [s for s in tum_siciller if s not in istisna_sicil]

    # ── Portfoy_Is_Yuku ───────────────────────────────────────────────────────
    piy = sheets["Portfoy_Is_Yuku"].copy()
    piy["Portfoy"] = piy["Portfoy"].astype(str).str.strip()

    if med:
        om_ref_col = _col(piy, "Gunluk Medyan OM`ye Yonlendirilen Referans Adedi")
        om_disi_col = _col(piy, "Gunluk Medyan OM`ye Yonlendirilmeyen Islem Adedi")
    else:
        om_ref_col = _col(piy, "Gunluk Ortalama OM`ye Yonlendirilen Referans Adedi")
        om_disi_col = _col(piy, "Gunluk Ortalama OM`ye Yonlendirilmeyen Islem Adedi")

    om_ref_adedi: dict[str, float] = {}
    om_disi_islem_adedi: dict[str, float] = {}
    for _, row in piy.iterrows():
        pf = row["Portfoy"]
        om_ref_adedi[pf] = float(row[om_ref_col]) if om_ref_col and not pd.isna(row.get(om_ref_col, None)) else 0.0
        om_disi_islem_adedi[pf] = float(row[om_disi_col]) if om_disi_col and not pd.isna(row.get(om_disi_col, None)) else 0.0

    # ── Portfoy_Aktif_Sicil ───────────────────────────────────────────────────
    pas = sheets["Portfoy_Aktif_Sicil"].copy()
    pas["Portfoy"] = pas["Portfoy"].astype(str).str.strip()

    if med:
        aktif_col = _col(pas, "Gunluk Medyan Aktif Sicil")
        sicil_sure_col = _col(pas, "Sicil bazlı günlük medyan çalışma süresi")
        om_sure_col = _col(pas, "Sicil bazlı günlük medyan OM`ye yonlendırılen referanslarda çalışma süresi")
        om_disi_sure_col = _col(pas, "Sicil bazlı günlük medyan OM`ye yonlendırılmeyen referanslarda çalışma süresi")
    else:
        aktif_col = _col(pas, "Gunluk Ortalama Aktif Sicil")
        sicil_sure_col = _col(pas, "Sicil bazlı günlük ortalama çalışma süresi")
        om_sure_col = _col(pas, "Sicil bazlı günlük ortalama OM`ye yonlendırılen referanslarda çalışma süresi")
        om_disi_sure_col = _col(pas, "Sicil bazlı günlük ortalama OM`ye yonlendırılmeyen referanslarda çalışma süresi")

    portfoy_aktif: dict[str, float] = {}
    portfoy_sicil_sure: dict[str, float] = {}
    portfoy_om_sure: dict[str, float] = {}
    portfoy_om_disi_sure: dict[str, float] = {}

    for _, row in pas.iterrows():
        pf = row["Portfoy"]
        portfoy_aktif[pf] = float(row[aktif_col]) if aktif_col and not pd.isna(row.get(aktif_col)) else 1.0
        portfoy_sicil_sure[pf] = float(row[sicil_sure_col]) if sicil_sure_col and not pd.isna(row.get(sicil_sure_col)) else 0.0
        portfoy_om_sure[pf] = float(row[om_sure_col]) if om_sure_col and not pd.isna(row.get(om_sure_col)) else 0.0
        portfoy_om_disi_sure[pf] = float(row[om_disi_sure_col]) if om_disi_sure_col and not pd.isna(row.get(om_disi_sure_col)) else 0.0

    # Talep hesabı: iki bileşenli
    demand: dict[str, float] = {}
    for pf in tum_portfoyler:
        aktif = portfoy_aktif.get(pf, 1.0)
        if aktif <= 0:
            aktif = 1.0

        # OM bileşeni: birim sure = portfoy_om_sure / (om_ref_adedi / aktif)
        om_r = om_ref_adedi.get(pf, 0.0)
        om_s = portfoy_om_sure.get(pf, 0.0)
        if om_r > 0:
            om_birim = om_s / (om_r / aktif)
            om_demand = om_r * om_birim
        else:
            om_demand = 0.0

        # OM dışı bileşeni: birim sure = portfoy_om_disi_sure / (om_disi_islem_adedi / aktif)
        disi_r = om_disi_islem_adedi.get(pf, 0.0)
        disi_s = portfoy_om_disi_sure.get(pf, 0.0)
        if disi_r > 0:
            disi_birim = disi_s / (disi_r / aktif)
            disi_demand = disi_r * disi_birim
        else:
            disi_demand = 0.0

        if om_demand == 0.0 and disi_demand == 0.0:
            demand[pf] = aktif * portfoy_sicil_sure.get(pf, 0.0)
        else:
            demand[pf] = om_demand + disi_demand

    # Verisi olmayan iç portföyler için ortalama ile doldur
    ic_demand_vals = [demand[pf] for pf in ic_pf if demand.get(pf, 0.0) > 0]
    ic_aktif_vals = [portfoy_aktif[pf] for pf in ic_pf if portfoy_aktif.get(pf, 0.0) > 0]
    ic_sicil_sure_vals = [portfoy_sicil_sure[pf] for pf in ic_pf if portfoy_sicil_sure.get(pf, 0.0) > 0]
    ic_om_sure_vals = [portfoy_om_sure[pf] for pf in ic_pf if portfoy_om_sure.get(pf, 0.0) > 0]
    ic_disi_sure_vals = [portfoy_om_disi_sure[pf] for pf in ic_pf if portfoy_om_disi_sure.get(pf, 0.0) > 0]

    ort_demand = sum(ic_demand_vals) / len(ic_demand_vals) if ic_demand_vals else 0.0
    ort_aktif = sum(ic_aktif_vals) / len(ic_aktif_vals) if ic_aktif_vals else 1.0
    ort_sicil_sure = sum(ic_sicil_sure_vals) / len(ic_sicil_sure_vals) if ic_sicil_sure_vals else 0.0
    ort_om_sure = sum(ic_om_sure_vals) / len(ic_om_sure_vals) if ic_om_sure_vals else 0.0
    ort_disi_sure = sum(ic_disi_sure_vals) / len(ic_disi_sure_vals) if ic_disi_sure_vals else 0.0

    for pf in ic_pf:
        if demand.get(pf, 0.0) == 0.0:
            demand[pf] = ort_demand
            portfoy_aktif.setdefault(pf, ort_aktif)
            portfoy_sicil_sure.setdefault(pf, ort_sicil_sure)
            portfoy_om_sure.setdefault(pf, ort_om_sure)
            portfoy_om_disi_sure.setdefault(pf, ort_disi_sure)
            uyarilar.append(f"Portföy '{pf}': veri bulunamadı, diğer portföylerin ortalaması kullanıldı.")

    # ── Sicil_Hiz ─────────────────────────────────────────────────────────────
    sh = sheets["Sicil_Hiz"].copy()
    sh["Sicil"] = sh["Sicil"].astype(str).str.strip()
    sh["Portfoy"] = sh["Portfoy"].astype(str).str.strip()

    hiz_col = _col(sh, "Gunluk Medyan Calisma Suresi", "Gunluk Ortalama Calisma Suresi")
    if not hiz_col:
        uyarilar.append("Sicil_Hiz: hız kolonu bulunamadı.")

    # (sicil, portfoy) → gerçek günlük çalışma süresi
    sicil_portfoy_sure: dict[tuple, float] = {}
    if hiz_col:
        for _, row in sh.iterrows():
            s, pf = row["Sicil"], row["Portfoy"]
            try:
                sicil_portfoy_sure[(s, pf)] = float(row[hiz_col])
            except Exception:
                pass

    speed_raw: dict[str, float] = {}
    if hiz_col:
        for s in tum_siciller:
            vals = sh[sh["Sicil"] == s][hiz_col].dropna().tolist()
            if vals:
                speed_raw[s] = sum(float(v) for v in vals) / len(vals)

    no_speed = [s for s in tum_siciller if s not in speed_raw]
    if no_speed:
        uyarilar.append(f"Hız verisi olmayan siciller (ortalama kullanıldı): {', '.join(no_speed)}")
    global_avg = sum(speed_raw.values()) / len(speed_raw) if speed_raw else GUN_SN / 2.0
    for s in no_speed:
        speed_raw[s] = global_avg

    max_speed = max(speed_raw.values()) if speed_raw else 1.0
    speed_norm: dict[str, float] = {s: speed_raw[s] / max_speed for s in tum_siciller}

    # ── Sicil toplam günlük çalışma süresi ───────────────────────────────────
    sicil_toplam_sure: dict[str, float] = {}
    for u in tum_siciller:
        sicil_toplam_sure[u] = sum(
            v for (s, pf), v in sicil_portfoy_sure.items() if s == u
        )
        if sicil_toplam_sure[u] == 0 and u in speed_raw:
            sicil_toplam_sure[u] = speed_raw[u]

    # ── Portföy bazında ortalama DESTEK katkısı (yeni çiftler için fallback) ─
    destek_df_rows = ma[ma["Portfoy Seviyesi"] == "DESTEK"]
    destek_sure_vals: dict[str, list] = {pf: [] for pf in ic_pf}
    for _, row in destek_df_rows.iterrows():
        pf = row["Portfoy"]
        s = row["Sicil"]
        if pf in destek_sure_vals and (s, pf) in sicil_portfoy_sure:
            destek_sure_vals[pf].append(sicil_portfoy_sure[(s, pf)])
    portfoy_destek_avg: dict[str, float] = {}
    global_destek_avg = 0.0
    all_destek_vals = [v for vals in destek_sure_vals.values() for v in vals]
    if all_destek_vals:
        global_destek_avg = sum(all_destek_vals) / len(all_destek_vals)
    for pf in ic_pf:
        if destek_sure_vals[pf]:
            portfoy_destek_avg[pf] = sum(destek_sure_vals[pf]) / len(destek_sure_vals[pf])
        else:
            portfoy_destek_avg[pf] = global_destek_avg

    # ── Eligible set: tüm (sicil × iç portföy), yalnızca istisna çıkar ──────
    eligible: set[tuple] = set()
    for u in tum_siciller:
        for pf in ic_pf:
            if (u, pf) not in istisna_set:
                eligible.add((u, pf))

    # Talep toleransı
    if tolerans_pct > 0:
        carpan = 1 + tolerans_pct / 100.0
        demand = {pf: v * carpan for pf, v in demand.items()}

    return {
        "tum_siciller": tum_siciller,
        "tum_portfoyler": tum_portfoyler,
        "ic_portfoyler": ic_pf,
        "gecici_portfoyler": gecici_pf,
        "capacity": capacity,
        "demand": demand,
        "speed_raw": speed_raw,
        "speed_norm": speed_norm,
        "eligible": eligible,
        "ana_atama_mevcut": ana_atama_mevcut,
        "istisna_set": istisna_set,
        "gecici_mevcut": gecici_mevcut,
        "portfoy_aktif": portfoy_aktif,
        "portfoy_sicil_sure": portfoy_sicil_sure,
        "sicil_portfoy_sure": sicil_portfoy_sure,
        "sicil_toplam_sure": sicil_toplam_sure,
        "portfoy_destek_avg": portfoy_destek_avg,
        "mevcut_atama_raw": mevcut_atama_raw,
    }, uyarilar, hatalar
