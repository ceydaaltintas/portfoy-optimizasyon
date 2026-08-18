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

    def _cs(series):
        """fillna → str → strip: boş hücreler '' olur, asla 'nan' olmaz."""
        return series.fillna("").astype(str).str.strip()

    ma["Sicil"] = _cs(ma["Sicil"])
    ma["Portfoy"] = _cs(ma["Portfoy"])
    ma["Portfoy Seviyesi"] = (
        _cs(ma["Portfoy Seviyesi"])
        .replace({"1": "ANA", "5": "DESTEK", "2": "GECİCİ"})
        .str.upper()
    )
    for c in ["Baslangic Zamani", "Bitis Zamani"]:
        if c not in ma.columns:
            ma[c] = ""

    ma = ma[ma["Sicil"] != ""]
    ma = ma[ma["Portfoy"] != ""]

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

    # GEÇİCİ bloklar → saat bloğundan fallback süre
    gecici_blok_saat: dict[str, int] = {}
    gecici_pf_per_sicil: dict[str, list] = {}   # hangi sicil hangi GEÇİCİ portföylere gidiyor
    for _, row in gecici_df.iterrows():
        s, pf = row["Sicil"], row["Portfoy"]
        blok = _parse_hhmm(row["Bitis Zamani"]) - _parse_hhmm(row["Baslangic Zamani"])
        gecici_blok_saat[s] = gecici_blok_saat.get(s, 0) + max(0, blok)
        gecici_pf_per_sicil.setdefault(s, []).append(pf)

    GUN_SN = gun_kapasite_sn(saatlik_mola_dk, ogle_arasi_dk)
    # capacity Sicil_Hiz işlendikten sonra güncellenecek; şimdilik saat bloğuyla başlat
    capacity: dict[str, float] = {s: float(GUN_SN - gecici_blok_saat.get(s, 0)) for s in tum_siciller}

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
        ist["Sicil"] = _cs(ist["Sicil"])
        ist = ist[ist["Sicil"] != ""]
        if "Portfoy" in ist.columns:
            ist["Portfoy"] = _cs(ist["Portfoy"])
            for _, row in ist.iterrows():
                pf, s = row["Portfoy"], row["Sicil"]
                if not pf:
                    istisna_sicil.add(s)
                else:
                    istisna_set.add((s, pf))
                    if pf not in tum_portfoyler:
                        uyarilar.append(f"İstisna: Portföy '{pf}' Mevcut_Atama'da yok.")
        else:
            for s in ist["Sicil"].unique():
                istisna_sicil.add(s)

    if istisna_sicil:
        uyarilar.append(f"Optimizasyondan dışlanan siciller: {', '.join(sorted(istisna_sicil))}")
        tum_siciller = [s for s in tum_siciller if s not in istisna_sicil]

    # ── Portfoy_Is_Yuku ───────────────────────────────────────────────────────
    piy = sheets["Portfoy_Is_Yuku"].copy()
    piy["Portfoy"] = _cs(piy["Portfoy"])
    piy = piy[piy["Portfoy"] != ""]

    # Portfoy_Is_Yuku'daki yeni portföyleri ic_pf'e ekle (Mevcut_Atama'da olmasa bile)
    piy_portfoyler = [p for p in piy["Portfoy"].unique() if p]
    for pf in piy_portfoyler:
        if pf not in tum_portfoyler:
            tum_portfoyler.append(pf)
            uyarilar.append(f"Portföy '{pf}': Mevcut_Atama'da yok, yeni portföy olarak eklendi.")
    tum_portfoyler = sorted(tum_portfoyler)
    ic_pf = [p for p in tum_portfoyler if p not in gecici_pf]

    if med:
        om_ref_col = _col(piy, "Gunluk Medyan OM`ye Yonlendirilen Referans Adedi")
        om_disi_col = _col(piy, "Gunluk Medyan OM`ye Yonlendirilmeyen Islem Adedi")
        piy_ref_col = _col(piy, "Gunluk Medyan Referans Adedi")
    else:
        om_ref_col = _col(piy, "Gunluk Ortalama OM`ye Yonlendirilen Referans Adedi")
        om_disi_col = _col(piy, "Gunluk Ortalama OM`ye Yonlendirilmeyen Islem Adedi")
        piy_ref_col = _col(piy, "Günlük Ortalama Referans Adedi", "Gunluk Ortalama Referans Adedi")

    om_ref_adedi: dict[str, float] = {}
    om_disi_islem_adedi: dict[str, float] = {}
    portfoy_daily_refs: dict[str, float] = {}
    for _, row in piy.iterrows():
        pf = row["Portfoy"]
        om_ref_adedi[pf] = float(row[om_ref_col]) if om_ref_col and not pd.isna(row.get(om_ref_col, None)) else 0.0
        om_disi_islem_adedi[pf] = float(row[om_disi_col]) if om_disi_col and not pd.isna(row.get(om_disi_col, None)) else 0.0
        portfoy_daily_refs[pf] = float(row[piy_ref_col]) if piy_ref_col and not pd.isna(row.get(piy_ref_col, None)) else 0.0

    # ── Portfoy_Aktif_Sicil ───────────────────────────────────────────────────
    pas = sheets["Portfoy_Aktif_Sicil"].copy()
    pas["Portfoy"] = _cs(pas["Portfoy"])
    pas = pas[pas["Portfoy"] != ""]

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

    # ── Sicil_Hiz ─────────────────────────────────────────────────────────────
    sh = sheets["Sicil_Hiz"].copy()
    sh["Sicil"] = _cs(sh["Sicil"])
    sh["Portfoy"] = _cs(sh["Portfoy"])
    sh = sh[(sh["Sicil"] != "") & (sh["Portfoy"] != "")]

    hiz_col = _col(sh, "Gunluk Medyan Calisma Suresi", "Gunluk Ortalama Calisma Suresi")
    sh_ref_col = _col(sh, "Gunluk Medyan Referans Adedi", "Gunluk Ortalama Referans Adedi")
    if not hiz_col:
        uyarilar.append("Sicil_Hiz: hız kolonu bulunamadı.")

    # Aykırı değer filtresi: yalnızca fiziksel sınırlar.
    # Üst sınır: GUN_SN — bir kişi net iş günü kapasitesini aşamaz (sistem hatası).
    # Alt sınır: 0 — negatif veya sıfır değerler geçersiz.
    if hiz_col and not sh.empty:
        sure_vals = pd.to_numeric(sh[hiz_col], errors="coerce")
        mask = (sure_vals > 0) & (sure_vals <= GUN_SN) & sure_vals.notna()
        onceki = len(sh)
        sh = sh[mask]
        cikarilan = onceki - len(sh)
        if cikarilan > 0:
            uyarilar.append(
                f"Sicil_Hiz: {cikarilan} aykırı çalışma süresi satırı dışlandı "
                f"(kabul aralığı: >0–{GUN_SN} sn)."
            )

    # (sicil, portfoy) → gerçek günlük çalışma süresi
    sicil_portfoy_sure: dict[tuple, float] = {}
    if hiz_col:
        for _, row in sh.iterrows():
            s, pf = row["Sicil"], row["Portfoy"]
            try:
                sicil_portfoy_sure[(s, pf)] = float(row[hiz_col])
            except Exception:
                pass

    # portföy bazında ortalama referans başına süre → talep hesabı için
    pf_ref_sure: dict[str, list] = {pf: [] for pf in ic_pf}
    if hiz_col and sh_ref_col:
        for _, row in sh.iterrows():
            s, pf = row["Sicil"], row["Portfoy"]
            if pf not in pf_ref_sure:
                continue
            sure = sicil_portfoy_sure.get((s, pf), 0.0)
            try:
                refs = float(row[sh_ref_col])
            except Exception:
                refs = 0.0
            if refs > 0 and sure > 0:
                pf_ref_sure[pf].append(sure / refs)
    portfoy_time_per_ref: dict[str, float] = {
        pf: sum(v) / len(v) if v else 0.0
        for pf, v in pf_ref_sure.items()
    }
    global_time_per_ref = (
        sum(portfoy_time_per_ref.values()) / len([v for v in portfoy_time_per_ref.values() if v > 0])
        if any(v > 0 for v in portfoy_time_per_ref.values()) else 0.0
    )

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

    # ── GEÇİCİ kapasite: Sicil_Hiz gerçek verisiyle güncelle ────────────────
    # Sicil_Hiz'de (sicil, gecici_pf) çifti varsa → gerçek ortalama süreyi kullan.
    # Yoksa → Mevcut_Atama'daki saat bloğu (bas-bit) fallback olarak kalır.
    for s, pf_listesi in gecici_pf_per_sicil.items():
        gercek_toplam = 0.0
        saat_toplam = gecici_blok_saat.get(s, 0)
        herhangi_gercek = False
        for pf in pf_listesi:
            gercek = sicil_portfoy_sure.get((s, pf))
            if gercek is not None:
                gercek_toplam += gercek
                herhangi_gercek = True
            else:
                # Bu portföy için Sicil_Hiz'de veri yok; saat bloğundaki payını ekle
                pf_saat = _parse_hhmm(
                    gecici_df.loc[
                        (gecici_df["Sicil"] == s) & (gecici_df["Portfoy"] == pf), "Bitis Zamani"
                    ].values[0]
                ) - _parse_hhmm(
                    gecici_df.loc[
                        (gecici_df["Sicil"] == s) & (gecici_df["Portfoy"] == pf), "Baslangic Zamani"
                    ].values[0]
                )
                gercek_toplam += max(0, pf_saat)
        if herhangi_gercek:
            capacity[s] = float(GUN_SN - gercek_toplam)

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

    # ── Havuzda_Bekleme (opsiyonel) ───────────────────────────────────────────
    # Sheet yoksa veya boşsa hiçbir şey değişmez.
    # Varsa: portföy bazında bekleyen oran hesaplanır, yüksek bekleyen portföylerin
    # talebi şişirilerek optimizer daha fazla kapasite yönlendirmeye zorlanır.
    bekleme_katsayisi: dict[str, float] = {}
    if "Havuzda_Bekleme" in sheets:
        hb = sheets["Havuzda_Bekleme"].copy()
        hb.columns = [str(c).strip() for c in hb.columns]
        if "Portfoy" in hb.columns and "Tarih" in hb.columns and "Gelen_Ref" in hb.columns and "Ayni_Saatte_Baslanan" in hb.columns:
            hb["Portfoy"] = _cs(hb["Portfoy"])
            hb = hb[hb["Portfoy"] != ""]
            hb["Gelen_Ref"] = pd.to_numeric(hb["Gelen_Ref"], errors="coerce").fillna(0)
            hb["Ayni_Saatte_Baslanan"] = pd.to_numeric(hb["Ayni_Saatte_Baslanan"], errors="coerce").fillna(0)
            hb["Tarih"] = pd.to_datetime(hb["Tarih"], dayfirst=True, errors="coerce")
            hb = hb[hb["Tarih"].notna()]
            if not hb.empty:
                # Her (Portfoy, Tarih) için günlük toplam → günlük bekleyen oran
                gun_grp = hb.groupby(["Portfoy", "Tarih"]).agg(
                    gun_gelen=("Gelen_Ref", "sum"),
                    gun_baslanan=("Ayni_Saatte_Baslanan", "sum"),
                ).reset_index()
                gun_grp = gun_grp[gun_grp["gun_gelen"] > 0]
                gun_grp["bekleyen_oran"] = (
                    (gun_grp["gun_gelen"] - gun_grp["gun_baslanan"]) / gun_grp["gun_gelen"]
                ).clip(lower=0)
                # Portföy bazında günlük oranların medyanı
                grp = gun_grp.groupby("Portfoy")["bekleyen_oran"].median().reset_index()
                medyan_oran = grp["bekleyen_oran"].median()
                if medyan_oran > 0:
                    for _, row in grp.iterrows():
                        pf = row["Portfoy"]
                        kat = row["bekleyen_oran"] / medyan_oran
                        bekleme_katsayisi[pf] = max(1.0, kat)
                if bekleme_katsayisi:
                    uyarilar.append(
                        f"Havuzda_Bekleme verisi kullanıldı: "
                        f"{len(bekleme_katsayisi)} portföy için talep ağırlığı ayarlandı."
                    )

    # ── Talep: günlük referans adedi × referans başına süre ──────────────────
    demand: dict[str, float] = {}
    for pf in tum_portfoyler:
        daily_refs = portfoy_daily_refs.get(pf, 0.0)
        tpr = portfoy_time_per_ref.get(pf, 0.0) or global_time_per_ref
        if daily_refs > 0 and tpr > 0:
            demand[pf] = daily_refs * tpr
        else:
            # fallback: aktif sicil × sicil başı süre
            aktif = max(portfoy_aktif.get(pf, 1.0), 1.0)
            demand[pf] = aktif * portfoy_sicil_sure.get(pf, 0.0)

    # Havuzda_Bekleme katsayısı uygula (varsa)
    if bekleme_katsayisi:
        for pf in tum_portfoyler:
            if pf in bekleme_katsayisi and bekleme_katsayisi[pf] > 1.0:
                demand[pf] = demand[pf] * bekleme_katsayisi[pf]

    # Verisi olmayan iç portföyler için ortalama ile doldur
    ic_demand_vals = [demand[pf] for pf in ic_pf if demand.get(pf, 0.0) > 0]
    ort_demand = sum(ic_demand_vals) / len(ic_demand_vals) if ic_demand_vals else 0.0
    for pf in ic_pf:
        if demand.get(pf, 0.0) == 0.0:
            demand[pf] = ort_demand
            uyarilar.append(f"Portföy '{pf}': talep verisi bulunamadı, ortalama kullanıldı.")

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
